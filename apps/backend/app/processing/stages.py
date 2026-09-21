"""The processing stage machine: the statuses, the transition table, the stage functions.

A Document goes through stages — it is read (OCR), made searchable (embedding), then
described (metadata extraction). This module is the whole description of that, and it
is pure: nothing here opens a database session, enqueues work or reads settings. The
runner owns all of that.

Stage functions take the inputs they need plus the models they need and return a
`StageResult`: the fields to write, the status to move to, and whether clients should
hear the Document changed.
"""
import logging
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Protocol, Sequence

from app.processing import chunking
from app.providers.ports import ChatModel, Embedder

if TYPE_CHECKING:  # Importing the model names this enum; keep Redis out of that path.
    from app.services.page_cache import PageCache

logger = logging.getLogger(__name__)

NO_TEXT_EXTRACTED = "No text could be extracted from document"
UNKNOWN = "Unknown"


class ProcessingStatus(StrEnum):
    """Where a Document is in processing. The values are the strings stored in the row.

    The column is `String(50)` and these are exactly what is already in it, so the enum
    arrived without a migration and a status read back as a bare string still compares
    equal.
    """

    PENDING = "pending"
    PROCESSING = "processing"
    OCR_COMPLETE = "ocr_complete"
    OCR_FAILED = "ocr_failed"
    EMBEDDING_COMPLETE = "embedding_complete"
    LLM_COMPLETE = "llm_complete"
    FAILED = "failed"


class Stage(StrEnum):
    """One step of processing: reading, making searchable, describing."""

    OCR = "ocr"
    EMBEDDING = "embedding"
    METADATA = "metadata"


def next_stage(
    status: ProcessingStatus, has_embedder: bool, has_assistant: bool
) -> Optional[Stage]:
    """The stage to run next from this status, or None when there is nothing to do.

    The whole machine, in one table. It reads no Document content: a status already
    says whether OCR found text, because OCR that found none writes `ocr_failed`.
    The two booleans are capabilities — a builder in the factory returned a model
    rather than None — never a `*_ENABLED` setting (ADR 0003, ADR 0006).
    """
    if status is ProcessingStatus.PENDING:
        return Stage.OCR
    if status is ProcessingStatus.OCR_COMPLETE:
        # Embeddings go first; that stage leads on to metadata itself.
        if has_embedder:
            return Stage.EMBEDDING
        return Stage.METADATA if has_assistant else None
    if status is ProcessingStatus.EMBEDDING_COMPLETE:
        return Stage.METADATA if has_assistant else None
    # processing is in flight; ocr_failed, llm_complete and failed are the ends.
    return None


#: The statuses at which a Document has embeddings that an edit can make stale.
#: Anything earlier is on its way to being embedded and will pick the edit up; the ends
#: that never got there have nothing to refresh.
EMBEDDED: tuple[ProcessingStatus, ...] = (
    ProcessingStatus.EMBEDDING_COMPLETE,
    ProcessingStatus.LLM_COMPLETE,
)


class HasProcessingStatus(Protocol):
    """A Document, as this predicate needs to see one."""

    processing_status: str


def should_reembed(document: HasProcessingStatus) -> bool:
    """Whether editing this Document's metadata is worth re-embedding it over.

    Written once, for the three routes — a title or description edit, a tag added, a
    tag removed — that used to carry a copy of the status list. A row loads its status
    as a plain string, so the comparison is by value and not by enum identity.
    """
    return document.processing_status in EMBEDDED


@dataclass(frozen=True)
class EmbeddedChunk:
    """One chunk of a Document's text and the vector standing for it."""

    text: str
    vector: List[float]


@dataclass(frozen=True)
class EmbeddingWrite:
    """Every chunk a Document should have, replacing whatever it has now."""

    model_name: str
    chunks: List[EmbeddedChunk]


@dataclass(frozen=True)
class StageResult:
    """What a finished stage asks the runner to do. No stage writes anything itself.

    `status` of None leaves the Document where it is, and emits no status event.
    `tags` of None leaves the Document's tags alone; a list replaces them entirely.
    `outcome` and `info` become the task's return value.
    """

    status: Optional[ProcessingStatus] = None
    fields: Dict[str, Any] = field(default_factory=dict)
    embeddings: Optional[EmbeddingWrite] = None
    tags: Optional[List[str]] = None
    notify_updated: bool = False
    outcome: str = "success"
    info: Dict[str, Any] = field(default_factory=dict)


def skipped(message: str, key: str = "message") -> StageResult:
    """A stage with nothing to do: no writes, no status change, no event."""
    return StageResult(outcome="skipped", info={key: message})


def run_ocr(
    *,
    file_path: str,
    vision_model: Optional[ChatModel],
    formatter_model: Optional[ChatModel],
    force_ocr: bool = False,
    refresh_cache: bool = False,
    page_concurrency: int = 1,
    page_cache: Optional["PageCache"] = None,
) -> StageResult:
    """Read a Document's file, and say what it now holds.

    Text found means `ocr_complete`; nothing found means `ocr_failed` with the reason
    recorded, so the status alone tells the machine whether to go on.
    """
    from app.services.ocr_service import OCRService

    ocr_service = OCRService(
        vision_model=vision_model,
        formatter_model=formatter_model,
        page_concurrency=page_concurrency,
        page_cache=page_cache,
    )

    extracted_text = ocr_service.extract_text(
        file_path, force_ocr=force_ocr, refresh_cache=refresh_cache
    )

    fields: Dict[str, Any] = {}
    if extracted_text and extracted_text.strip():
        fields["ocr_text"] = extracted_text
        fields["ocr_language"] = ocr_service.detect_language(extracted_text)
        status = ProcessingStatus.OCR_COMPLETE
        logger.info(f"Extracted {len(extracted_text)} characters from {file_path}")
    else:
        logger.warning(f"No text extracted from {file_path}")
        fields["ocr_text"] = ""
        fields["processing_error"] = NO_TEXT_EXTRACTED
        status = ProcessingStatus.OCR_FAILED

    page_count = _count_pdf_pages(file_path)
    if page_count is not None:
        fields["page_count"] = page_count

    return StageResult(
        status=status,
        fields=fields,
        info={
            "text_length": len(extracted_text) if extracted_text else 0,
            "page_count": page_count,
        },
    )


def _count_pdf_pages(file_path: str) -> Optional[int]:
    """The page count of a PDF, or None for anything else or an unreadable file."""
    if not file_path.endswith(".pdf"):
        return None
    try:
        import fitz

        pdf_doc = fitz.open(file_path)
        try:
            return len(pdf_doc)
        finally:
            pdf_doc.close()
    except Exception as e:
        logger.error(f"Failed to count PDF pages: {e}")
        return None


def run_embedding(
    *,
    ocr_text: Optional[str],
    embedder: Embedder,
    title: Optional[str] = None,
    description: Optional[str] = None,
    tags: Sequence[str] = (),
    chunk_size: int,
    chunk_overlap: int,
) -> StageResult:
    """Turn a Document's text into the chunks and vectors that make it searchable.

    What gets embedded is the text with its metadata in front of it, so a search for
    a title or a tag can match the chunk as well as the words on the page.
    """
    if not ocr_text:
        return skipped("No text to embed")

    enriched_text = enrich_text(ocr_text, title=title, description=description, tags=tags)
    logger.info(
        f"Embedding {len(enriched_text)} characters of enriched text "
        f"(OCR: {len(ocr_text)}) with {embedder!r}"
    )

    chunks = chunking.chunk(enriched_text, chunk_size, chunk_overlap)
    if not chunks:
        return skipped("No chunks to embed")

    vectors = embedder.embed(chunks)
    logger.info(f"Generated {len(vectors)} embeddings from {len(chunks)} chunks")

    return StageResult(
        status=ProcessingStatus.EMBEDDING_COMPLETE,
        embeddings=EmbeddingWrite(
            model_name=embedder.model_name,
            chunks=[
                EmbeddedChunk(text=chunk, vector=vector)
                for chunk, vector in zip(chunks, vectors)
            ],
        ),
        info={"embedding_count": len(vectors), "chunk_count": len(chunks)},
    )


def enrich_text(
    ocr_text: str,
    *,
    title: Optional[str] = None,
    description: Optional[str] = None,
    tags: Sequence[str] = (),
) -> str:
    """The text to embed: the Document's metadata, then its content."""
    prefix: List[str] = []
    if title:
        prefix.append(f"Title: {title}")
    if tags:
        prefix.append(f"Tags: {', '.join(tags)}")
    if description:
        prefix.append(f"Description: {description}")
    if not prefix:
        return ocr_text
    return "\n".join(prefix) + "\n\nContent:\n" + ocr_text


def run_metadata(
    *,
    ocr_text: Optional[str],
    original_filename: str,
    assistant_model: ChatModel,
    current_title: Optional[str] = None,
    current_description: Optional[str] = None,
    existing_tags: Sequence[str] = (),
) -> StageResult:
    """Ask the assistant model what this Document is, and say what to record.

    The model sees the tags the archive already has so it prefers them over coining a
    synonym. An empty suggestion list means "nothing to add", never "clear what is
    there", so `tags` stays None and the Document keeps the tags it has.
    """
    from app.services.assistant_service import AssistantService

    if not ocr_text:
        return skipped("No text content", key="reason")

    logger.info(
        f"Calling assistant model for metadata extraction ({len(existing_tags)} known tags)"
    )
    metadata = AssistantService(assistant_model).extract_metadata(
        ocr_text, original_filename, list(existing_tags)
    )
    logger.info(f"Extracted metadata: {metadata}")

    fields: Dict[str, Any] = {}

    extracted_title = _meaningful(metadata.get("title"))
    if extracted_title:
        fields["extracted_title"] = extracted_title
        # A title still reading as the filename was never chosen by anyone.
        if current_title == original_filename:
            fields["title"] = extracted_title

    correspondent = _meaningful(metadata.get("correspondent"))
    if correspondent:
        fields["extracted_correspondent"] = correspondent

    document_date = _as_date(metadata.get("document_date"))
    if document_date:
        fields["extracted_date"] = document_date

    document_type = _meaningful(metadata.get("document_type"))
    if document_type:
        fields["extracted_document_type"] = document_type

    summary = metadata.get("summary")
    if summary:
        fields["extracted_summary"] = summary
        if not (current_description or "").strip():
            fields["description"] = summary

    suggested_tags = metadata.get("suggested_tags") or []

    return StageResult(
        status=ProcessingStatus.LLM_COMPLETE,
        fields=fields,
        tags=list(suggested_tags) or None,
        notify_updated=True,
        # The runner writes the tags, so it overwrites the count once they have landed.
        info={"metadata": metadata, "tags_added": 0},
    )


def _meaningful(value: Optional[str]) -> Optional[str]:
    """A model answer worth recording: present, and not its stand-in for "I don't know"."""
    return value if value and value != UNKNOWN else None


def _as_date(value: Any) -> Optional[date]:
    """A model's date as a `date`, or None when it gave none or gave nonsense."""
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        logger.warning(f"Ignoring unparseable document_date from the model: {value!r}")
        return None
