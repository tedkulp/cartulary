"""Runs one stage over one Document: the plumbing the stage functions do not do.

The runner loads the Document, asks the factory for the models, calls the stage,
applies its result in one transaction, emits the transition with the state it read
from the row, and enqueues whatever the machine says comes next. A stage that raises
leaves the Document at `failed` with the error recorded, and that transition is
emitted too.

It imports no Celery and no tasks: enqueueing is a callable the caller passes in, so
the runner can be driven from a test with no broker.
"""
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.document import Document, DocumentEmbedding
from app.models.tag import Tag
from app.processing.stages import (
    ProcessingStatus,
    Stage,
    StageResult,
    next_stage,
    run_embedding,
    run_metadata,
    run_ocr,
    skipped,
)
from app.providers.factory import (
    get_assistant_model,
    get_embedder,
    get_formatter_model,
    get_vision_model,
)
from app.processing.tags import replace_tags
from app.providers.ports import ChatModel, Embedder
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)

Enqueue = Callable[[str, Stage], None]
SessionFactory = Callable[[], Session]


@dataclass(frozen=True)
class Models:
    """Every model role the runner hands to a stage. None means the capability is off."""

    vision: Optional[ChatModel] = None
    formatter: Optional[ChatModel] = None
    assistant: Optional[ChatModel] = None
    embedder: Optional[Embedder] = None

    @classmethod
    def from_factory(cls) -> "Models":
        """Ask the factory once. A builder returning None is how a capability is off."""
        return cls(
            vision=get_vision_model(),
            formatter=get_formatter_model(),
            assistant=get_assistant_model(),
            embedder=get_embedder(),
        )


def run_stage(
    document_id: str,
    stage: Stage,
    *,
    enqueue: Enqueue,
    session_factory: Optional[SessionFactory] = None,
    models: Optional[Models] = None,
    **options: Any,
) -> dict:
    """Run one stage over one Document and return the task's result dict.

    `enqueue` is called with the next stage, if the machine names one. Passing
    `session_factory` or `models` is for tests; left out, the runner opens its own
    session on a freshly disposed engine and asks the factory.
    """
    try:
        document_uuid = UUID(document_id)
    except (ValueError, AttributeError, TypeError):
        logger.error(f"Not a document id: {document_id!r}")
        return {"status": "error", "document_id": document_id, "message": "Invalid document id"}

    if session_factory is None:
        # Celery forks, and a connection inherited across the fork is not ours to use.
        from app.database import engine

        engine.dispose()
        session_factory = SessionLocal

    if models is None:
        models = Models.from_factory()

    spec = _STAGES[stage]
    unavailable = _capability_missing(spec, models)
    if unavailable is not None:
        logger.info(f"{stage} is off, skipping document {document_id}")
        return _result_dict(document_id, unavailable)

    db = session_factory()
    try:
        try:
            doc = db.query(Document).filter(Document.id == document_uuid).first()
            if doc is None:
                logger.error(f"Document not found: {document_id}")
                return {
                    "status": "error",
                    "document_id": document_id,
                    "message": "Document not found",
                }

            logger.info(f"Running {stage} for document {document_id}: {doc.original_filename}")

            if spec.running_status is not None:
                _commit_and_announce(db, doc, spec.running_status)

            result = spec.invoke(db, doc, models, options)
            tags_added = _apply(db, doc, result)

        except Exception as e:
            logger.error(f"Error running {stage} for document {document_id}: {e}", exc_info=True)
            _record_failure(db, document_uuid, f"{spec.error_prefix}{e}")
            return {"status": "error", "document_id": document_id, "message": str(e)}

        # The stage has landed. A broker or socket that fails from here on has not
        # unwritten it, so the status stays what the stage reached: marking the
        # Document failed now would report a transition no stage ever made.
        _hand_on(document_id, doc, result, models, enqueue)

        extra: Dict[str, Any] = {}
        if tags_added is not None:
            extra["tags_added"] = tags_added
        if "page_count" in result.info:
            # The Document's count, not just what this read of the file could see:
            # re-reading something that is not a PDF leaves the stored one standing.
            extra["page_count"] = doc.page_count
        return _result_dict(document_id, result, extra)

    finally:
        db.close()


def _hand_on(
    document_id: str,
    doc: Document,
    result: StageResult,
    models: Models,
    enqueue: Enqueue,
) -> None:
    """Tell clients the Document changed, and enqueue whatever the machine says is next.

    Everything here is off to somewhere else — a websocket, a broker — and none of it
    can fail the stage that has already been written, so a failure is logged and the
    Document is left reading what it truly reached.
    """
    try:
        if result.notify_updated and doc.owner_id is not None:
            notification_service.notify_document_updated_sync(doc.id, doc.owner_id)

        # A stage that moved nothing has nothing to hand on: asking the machine from a
        # status the stage just declined to leave would enqueue this same stage again.
        following = (
            next_stage(
                result.status,
                has_embedder=models.embedder is not None,
                has_assistant=models.assistant is not None,
            )
            if result.status is not None
            else None
        )
        if following is None:
            logger.info(f"Nothing follows {doc.processing_status} for document {document_id}")
            return

        logger.info(f"Enqueuing {following} for document {document_id}")
        enqueue(document_id, following)
    except Exception as e:
        logger.error(
            f"Document {document_id} reached {doc.processing_status}, but handing it on "
            f"failed: {e}",
            exc_info=True,
        )


def _capability_missing(spec: "_StageSpec", models: Models) -> Optional[StageResult]:
    """The skip a stage answers with when the model it needs is not configured."""
    if spec.requires is None or getattr(models, spec.requires) is not None:
        return None
    assert spec.off is not None  # a stage that requires a model says how it declines
    return spec.off()


def _result_dict(
    document_id: str, result: StageResult, extra: Optional[Dict[str, Any]] = None
) -> dict:
    """The task's return value: what the stage reported, plus what only the runner knows."""
    return {
        "status": result.outcome,
        "document_id": document_id,
        **result.info,
        **(extra or {}),
    }


# ─── The stages, as the runner sees them ──────────────────────────────────────


def _invoke_ocr(
    db: Session, doc: Document, models: Models, options: Dict[str, Any]
) -> StageResult:
    from app.services.page_cache import get_page_cache
    from app.services.storage_service import StorageService

    absolute_path = str(StorageService().get_file_path(doc.file_path))
    logger.info(f"Absolute file path: {absolute_path}")

    return run_ocr(
        file_path=absolute_path,
        vision_model=models.vision,
        formatter_model=models.formatter,
        force_ocr=bool(options.get("force_ocr")),
        refresh_cache=bool(options.get("refresh_cache")),
        page_concurrency=settings.OCR_PAGE_CONCURRENCY,
        page_cache=get_page_cache(),
    )


def _invoke_embedding(
    db: Session, doc: Document, models: Models, options: Dict[str, Any]
) -> StageResult:
    assert models.embedder is not None  # _capability_missing ran first
    return run_embedding(
        ocr_text=doc.ocr_text,
        embedder=models.embedder,
        title=doc.title,
        description=doc.description,
        tags=sorted(tag.name for tag in doc.tags),
        chunk_size=settings.EMBEDDING_CHUNK_SIZE,
        chunk_overlap=settings.EMBEDDING_CHUNK_OVERLAP,
    )


def _invoke_metadata(
    db: Session, doc: Document, models: Models, options: Dict[str, Any]
) -> StageResult:
    assert models.assistant is not None  # _capability_missing ran first
    existing_tags = [name for (name,) in db.query(Tag.name).order_by(Tag.name).all()]
    return run_metadata(
        ocr_text=doc.ocr_text,
        original_filename=doc.original_filename,
        assistant_model=models.assistant,
        current_title=doc.title,
        current_description=doc.description,
        existing_tags=existing_tags,
    )


@dataclass(frozen=True)
class _StageSpec:
    """Everything the runner needs to know about one stage, in one row.

    `requires` names the attribute of `Models` that must not be None for the stage to
    run at all; without it the stage is skipped with `off`, untouched. `running_status`
    is what the Document reads while the stage is in flight — only OCR announces
    itself, the other two being short enough not to.
    """

    invoke: Callable[[Session, Document, Models, Dict[str, Any]], StageResult]
    error_prefix: str = ""
    running_status: Optional[ProcessingStatus] = None
    requires: Optional[str] = None
    off: Optional[Callable[[], StageResult]] = None


_STAGES: Dict[Stage, _StageSpec] = {
    Stage.OCR: _StageSpec(
        invoke=_invoke_ocr,
        running_status=ProcessingStatus.PROCESSING,
    ),
    Stage.EMBEDDING: _StageSpec(
        invoke=_invoke_embedding,
        error_prefix="Embedding generation failed: ",
        requires="embedder",
        off=lambda: skipped("Embeddings disabled"),
    ),
    Stage.METADATA: _StageSpec(
        invoke=_invoke_metadata,
        error_prefix="Metadata extraction failed: ",
        requires="assistant",
        off=lambda: skipped("LLM disabled", key="reason"),
    ),
}


# ─── Writing, and describing the write ────────────────────────────────────────


def _apply(db: Session, doc: Document, result: StageResult) -> Optional[int]:
    """Write everything a stage asked for, in one transaction, then emit the transition.

    The "from" state is the one in the row at the moment of the write, so no caller
    ever passes a literal and no client is told a transition that did not happen.
    """
    for name, value in result.fields.items():
        setattr(doc, name, value)

    if result.embeddings is not None:
        db.query(DocumentEmbedding).filter(
            DocumentEmbedding.document_id == doc.id
        ).delete(synchronize_session=False)
        for index, chunk in enumerate(result.embeddings.chunks):
            db.add(
                DocumentEmbedding(
                    document_id=doc.id,
                    chunk_index=index,
                    chunk_text=chunk.text,
                    embedding=chunk.vector,
                    embedding_model=result.embeddings.model_name,
                )
            )

    tags_added = replace_tags(db, doc, result.tags) if result.tags is not None else None

    _commit_and_announce(db, doc, result.status)
    return tags_added


def _commit_and_announce(db: Session, doc: Document, status: Optional[ProcessingStatus]) -> None:
    """Commit the pending changes, moving to `status`, and tell clients if it moved."""
    was = doc.processing_status
    if status is not None:
        doc.processing_status = status.value
    now = doc.processing_status

    db.commit()

    if was != now:
        notification_service.notify_status_changed_sync(doc.id, was, now)
        logger.info(f"Document {doc.id} moved {was} -> {now}")


def _record_failure(db: Session, document_uuid: UUID, message: str) -> None:
    """Leave a Document that raised at `failed`, with the error, and say so."""
    try:
        db.rollback()
        doc = db.query(Document).filter(Document.id == document_uuid).first()
        if doc is None:
            return
        doc.processing_error = message
        _commit_and_announce(db, doc, ProcessingStatus.FAILED)
    except Exception as db_error:
        logger.error(f"Failed to update error status: {db_error}")
