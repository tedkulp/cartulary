"""OCR service for extracting text from documents using a vision model."""
import hashlib
import logging
import re
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF
from langdetect import DetectorFactory, detect
from langdetect.lang_detect_exception import LangDetectException

from app.providers import ChatModel, Message, ModelError
from app.services.page_cache import PageCache

logger = logging.getLogger(__name__)

# langdetect is non-deterministic by default: the same text can yield different
# results across calls. Seeding makes detection reproducible.
DetectorFactory.seed = 0


@dataclass(frozen=True)
class PageRead:
    """What reading one page came to: the text to keep, and the model failure if any.

    The two are not exclusive. A page whose models failed still keeps its embedded
    text, because one unreadable page should not lose the others; the error rides
    along so the caller can tell a document that was read badly from one the models
    never answered for at all. See ADR 0007.
    """

    text: Optional[str]
    model_error: Optional[ModelError] = None


# A page with less embedded text than this is sent to the vision model.
MIN_EMBEDDED_TEXT_CHARS = 50
# Vision output shorter than this skips the formatter model.
MIN_VISION_TEXT_CHARS = 10

VISION_PROMPT = """TASK:
Extract all visible text from the image.

RULES:
- Output plain text only
- Preserve wording and order
- No formatting
- No explanations"""

FORMATTER_SYSTEM_PROMPT = "You are a text formatter. You do not explain."

FORMATTER_PROMPT = """OUTPUT RULES:
- Output Markdown only
- Convert html output to markdown if possible
- Do not created nested markdown code blocks. It should be a single markdown document comprised of all pages.
- Strip out any think tags
- Do not add, remove, or reorder content
- Do not add headers unless present
- Do not add lists unless present
- Do not add code blocks
- Do not explain or comment
- Do not return any text if the page is empty or has no meaningful content -- do not explain why you didn't return any text

TASK:
Convert the following text into Markdown while preserving structure exactly.

TEXT:
{raw_text}"""


# Reasoning a thinking model wraps in <think> tags
THINK_BLOCK = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
# Reasoning whose opening tag the chat template put in the prompt: all text up to a bare </think>
LEADING_UNOPENED_THINK = re.compile(r"^.*?</think>", re.IGNORECASE | re.DOTALL)
# Reasoning cut off before its closing tag: everything from the <think> on
UNCLOSED_THINK = re.compile(r"<think>.*$", re.IGNORECASE | re.DOTALL)
# A whole reply wrapped in one code fence, optionally tagged as markdown
OUTER_FENCE = re.compile(
    r"```[ \t]*(?:markdown|md)?[ \t]*\n(?P<body>.*)\n```", re.IGNORECASE | re.DOTALL
)
FENCE_LINE = re.compile(r"^[ \t]*```", re.MULTILINE)
# A first line introducing the reply ("Sure! Here is the formatted text:"). It must name what
# it introduces and end in a colon, so most documents that open with "Here is..." are left alone.
PREAMBLE = re.compile(
    r"^(?:(?:sure|certainly|okay|ok|of course)[!,.]?[ \t]*)?"
    r"(?:here is|here's|below is)\b[^\n]*"
    r"\b(?:markdown|formatted|converted|text|output|result)\b[^\n]*:[ \t]*(?:\n|$)",
    re.IGNORECASE,
)


# Prefix on every page cache key, so OCR's entries are recognisable in a shared Redis
CACHE_KEY_PREFIX = "cartulary:ocr:page:"
# Bumped when a change to the OCR *rules* — cleanup, thresholds, what a pass returns —
# makes older entries wrong. Changes to the models or prompts invalidate on their own,
# because the key already covers both.
CACHE_SCHEMA_VERSION = "1"


def _model_identity(model: Optional[ChatModel]) -> str:
    """How a model is named in a cache key: its adapter and its model name.

    The adapter is part of it because the same model name at two providers is two
    different models, and they need not agree on what a page says.
    """
    if model is None:
        return "none"
    return f"{type(model).__name__}:{model.model_name}"


def _cache_key(
    image: bytes, vision_model: ChatModel, formatter_model: Optional[ChatModel]
) -> str:
    """The page cache key for one page image read by these two models.

    Everything that decides the text hashes into the key: the page image, both models,
    the prompts sent to them, and the rules version. Change any of them and the entry is
    a different one, so nothing stale is ever served.
    """
    digest = hashlib.sha256()
    for part in (
        CACHE_SCHEMA_VERSION,
        _model_identity(vision_model),
        _model_identity(formatter_model),
        VISION_PROMPT,
        FORMATTER_SYSTEM_PROMPT,
        FORMATTER_PROMPT,
    ):
        digest.update(part.encode())
        digest.update(b"\0")
    digest.update(image)
    return CACHE_KEY_PREFIX + digest.hexdigest()


def _clean_formatter_output(text: str, raw_text: str) -> str:
    """Remove artifacts a reasoning or chatty formatter model leaves around its markdown.

    Anything that also appears in the vision model's raw text came off the page, so it is
    document content and kept.
    """
    if "think>" not in raw_text.lower():
        text = THINK_BLOCK.sub("", text)
        text = LEADING_UNOPENED_THINK.sub("", text)
        text = UNCLOSED_THINK.sub("", text)
    text = text.strip()

    preamble = PREAMBLE.match(text)
    if preamble and preamble.group().strip() not in raw_text:
        text = text[preamble.end() :].strip()

    fenced = OUTER_FENCE.fullmatch(text)
    # A fence inside the body means the reply's first and last fences belong to different blocks
    if fenced and not FENCE_LINE.search(fenced.group("body")):
        text = fenced.group("body")

    return text.strip()


class OCRService:
    """Two-pass text extraction: a vision model reads pages, a formatter model makes markdown.

    Either model may be None. With no vision model, PDFs yield only their embedded text
    and images yield nothing. With no formatter model, the vision model's raw text is used.

    `page_concurrency` is the most PDF pages that may be in the models at once. Both passes
    for one page run on the same thread, so it is also a ceiling on the model requests OCR
    has outstanding. Rendering stays on the calling thread, because PyMuPDF is not
    thread-safe; pages are joined in document order however they finish.

    With a `page_cache`, a page image these models have already read is served from the
    cache instead of going to them again. Callers that want fresh output ask for it per
    call with `refresh_cache`.
    """

    def __init__(
        self,
        vision_model: Optional[ChatModel] = None,
        formatter_model: Optional[ChatModel] = None,
        page_concurrency: int = 1,
        page_cache: Optional[PageCache] = None,
    ) -> None:
        """Initialize OCR service with the models for each pass."""
        if page_concurrency < 1:
            raise ValueError(f"page_concurrency must be at least 1, got {page_concurrency}")
        self.vision_model = vision_model
        self.formatter_model = formatter_model
        self.page_concurrency = page_concurrency
        self.page_cache = page_cache

    def extract_text(
        self, file_path: str, force_ocr: bool = False, refresh_cache: bool = False
    ) -> Optional[str]:
        """
        Extract text from an image or PDF file.

        Args:
            file_path: Path to the file to process
            force_ocr: If True, force OCR even if embedded text exists (for reprocessing)
            refresh_cache: If True, read every page with the models again and replace
                whatever the page cache holds for it

        Returns:
            Extracted text or None if extraction failed

        Raises:
            ModelError: If no page that needed the models could be read by them. The
                whole read is worth running again in that case, so it is raised for
                the stage to be retried rather than reported as a document with no
                text in it (ADR 0007).
        """
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            logger.error(f"File not found: {file_path}")
            return None

        file_size = file_path_obj.stat().st_size
        logger.info(f"File size: {file_size} bytes")
        if file_size == 0:
            logger.error(f"File is empty: {file_path}")
            return None

        # Handle PDF files - try to extract embedded text first unless forced
        if file_path_obj.suffix.lower() == ".pdf":
            return self._extract_text_from_pdf(
                file_path, force_ocr=force_ocr, refresh_cache=refresh_cache
            )

        # For images, use vision OCR
        if self.vision_model is None:
            logger.info("Vision OCR is disabled, cannot extract text from images")
            return None

        try:
            image = file_path_obj.read_bytes()
        except OSError as e:
            logger.error(f"Failed to read image {file_path}: {e}")
            return None

        # An image is one page, and it always needs the models: there is no embedded
        # text to fall back on, so a provider failure is the whole read failing.
        return self._read_image(self.vision_model, image, refresh_cache=refresh_cache)

    def _read_image(
        self, vision_model: ChatModel, image: bytes, refresh_cache: bool = False
    ) -> str:
        """
        Read text from one image, from the page cache or with two-pass processing.

        Pass 1: Vision model extracts raw text from image
        Pass 2: Formatter model formats raw text into proper markdown

        A hit in the page cache replaces both passes. Text is only remembered when there
        is some, and when both passes ran as intended: an empty read says nothing worth
        keeping about the page, and text that missed its formatting pass would be served
        again under a key naming the formatter that never saw it.

        Raises:
            ModelError: If the vision model fails
        """
        cache = self.page_cache
        if cache is None:
            text, _ = self._read_image_with_models(vision_model, image)
            return text

        key = _cache_key(image, vision_model, self.formatter_model)
        if refresh_cache:
            logger.info("Page cache bypassed, re-reading the page")
        else:
            cached = cache.get(key)
            if cached is not None:
                logger.info(f"Page cache hit: {len(cached)} chars, skipping both passes")
                return cached

        text, formatted = self._read_image_with_models(vision_model, image)

        if text and formatted:
            cache.set(key, text)

        return text

    def _read_image_with_models(
        self, vision_model: ChatModel, image: bytes
    ) -> Tuple[str, bool]:
        """Both OCR passes over one image, with no page cache in the way.

        Returns:
            The page's text, and whether it came out of the passes the caller asked
            for. A page whose formatter failed is still read, but is not text worth
            remembering.

        Raises:
            ModelError: If the vision model fails. Pass 1 is the read; without it
                there is no page. A pass 2 that fails is worked around (ADR 0007).
        """
        # PASS 1: Extract raw text with vision model
        logger.info(f"Pass 1: Calling vision model {vision_model!r} for raw text extraction")
        raw_text = vision_model.chat(
            [Message(role="user", content=VISION_PROMPT, images=[image])]
        )

        logger.info(f"Pass 1 complete: Extracted {len(raw_text)} chars")
        logger.info("--- BEGIN RAW EXTRACTION ---")
        logger.info(raw_text)
        logger.info("--- END RAW EXTRACTION ---")

        if len(raw_text.strip()) < MIN_VISION_TEXT_CHARS:
            logger.warning("Pass 1 returned insufficient text, skipping Pass 2")
            return raw_text.strip(), True

        if self.formatter_model is None:
            logger.info("No formatter model, skipping Pass 2")
            return raw_text.strip(), True

        # PASS 2: Format raw text into proper markdown
        logger.info(
            f"Pass 2: Calling formatter model {self.formatter_model!r} for markdown formatting"
        )
        try:
            formatted_text = self.formatter_model.chat(
                [
                    Message(role="system", content=FORMATTER_SYSTEM_PROMPT),
                    Message(role="user", content=FORMATTER_PROMPT.format(raw_text=raw_text)),
                ]
            )
        except ModelError as e:
            # Pass 1 read the page; only its formatting is missing. That is a failure
            # this page can work around, so the raw text stands rather than losing a
            # read the vision model already paid for (ADR 0007). It is not cached: the
            # next attempt should format it, not be served this.
            logger.error(f"Pass 2 failed, keeping the raw text pass 1 read: {e}")
            return raw_text.strip(), False

        logger.info(f"Pass 2 complete: Formatted to {len(formatted_text)} chars")
        logger.info("--- BEGIN FORMATTED TEXT ---")
        logger.info(formatted_text)
        logger.info("--- END FORMATTED TEXT ---")

        final_text = _clean_formatter_output(formatted_text, raw_text)
        logger.info(f"Cleaned formatter output to {len(final_text)} chars")
        logger.info("--- BEGIN FINAL OUTPUT ---")
        logger.info(final_text)
        logger.info("--- END FINAL OUTPUT ---")

        return final_text, True

    def _extract_text_from_pdf(
        self, pdf_path: str, force_ocr: bool = False, refresh_cache: bool = False
    ) -> Optional[str]:
        """
        Extract text from a PDF, page by page.

        Args:
            pdf_path: Path to PDF file
            force_ocr: If True, skip embedded text and force vision OCR
            refresh_cache: If True, re-read every page with the models, replacing its
                page cache entry

        Returns:
            Extracted text from all pages

        Raises:
            ModelError: If every page that needed the models failed on them
        """
        logger.info(f"Starting PDF text extraction for: {pdf_path}")

        try:
            doc = fitz.open(pdf_path)
        except (fitz.FileDataError, RuntimeError) as e:
            logger.error(f"Failed to open PDF {pdf_path}: {type(e).__name__}: {e}")
            return None

        page_count = len(doc)
        logger.info(f"PDF has {page_count} pages, {self.page_concurrency} OCR'd at a time")

        # One slot per page, filled in whatever order the pages finish, joined in page order.
        # Indexed by page index, which is one less than the page number the logs use.
        page_text: List[Optional[str]] = [None] * page_count
        # Pages submitted for OCR but not yet collected, by the page index each fills. Never
        # larger than page_concurrency, so no more rendered images than that are held at once.
        in_flight: Dict[Future[PageRead], int] = {}
        # How many pages went to the models, how many of those the models read, and the
        # failures they gave. Counting the reads rather than comparing the failures with
        # what was sent keeps a page dropped for some other reason from standing in for
        # one the models answered.
        sent_to_models = 0
        read_by_models = 0
        model_errors: List[ModelError] = []

        def collect_finished() -> None:
            """Store every page that has finished, waiting for at least one to.

            Collecting all of them rather than the oldest keeps the pool fed: one slow page
            no longer holds back the slots of pages that finished behind it.
            """
            done, _ = wait(in_flight, return_when=FIRST_COMPLETED)
            for future in done:
                index = in_flight.pop(future)
                try:
                    read = future.result()
                except RuntimeError as e:
                    # Whatever went wrong on the worker, one page shouldn't lose the others
                    logger.error(
                        f"Failed to OCR page {index + 1} of {pdf_path}: {type(e).__name__}: {e}",
                        exc_info=True,
                    )
                    continue
                page_text[index] = read.text
                if read.model_error is not None:
                    model_errors.append(read.model_error)
                else:
                    nonlocal read_by_models
                    read_by_models += 1

        vision_model = self.vision_model

        with doc, ThreadPoolExecutor(
            max_workers=self.page_concurrency, thread_name_prefix="ocr-page"
        ) as pool:
            for index in range(page_count):
                page_number = index + 1
                try:
                    embedded_text, is_enough = self._read_embedded_text(
                        doc[index], page_number, force_ocr
                    )
                    if is_enough or vision_model is None:
                        page_text[index] = embedded_text
                        continue
                    # Wait for a slot before rendering, so the image goes straight to a worker
                    while len(in_flight) >= self.page_concurrency:
                        collect_finished()
                    image = self._render_page(doc[index], page_number)
                except RuntimeError as e:
                    # PyMuPDF errors: one unreadable page shouldn't lose the others
                    logger.error(
                        f"Failed to process page {page_number} of {pdf_path}: "
                        f"{type(e).__name__}: {e}",
                        exc_info=True,
                    )
                    continue
                sent_to_models += 1
                in_flight[
                    pool.submit(
                        self._ocr_page,
                        vision_model,
                        image,
                        page_number,
                        embedded_text,
                        refresh_cache,
                    )
                ] = index

            while in_flight:
                collect_finished()

        all_text = []
        processed_pages = []
        missing_pages = []
        for index, text in enumerate(page_text):
            if text:
                all_text.append(text)
                processed_pages.append(index + 1)
            else:
                missing_pages.append(index + 1)
                logger.warning(f"Page {index + 1}: No text extracted (text is None or empty)")

        total_text = "\n\n".join(all_text)
        logger.info(
            f"PDF extraction complete: {len(all_text)}/{page_count} pages processed successfully"
        )
        logger.info(f"Successfully processed pages: {processed_pages}")
        logger.info(f"Total extracted text: {len(total_text)} characters")

        if missing_pages:
            logger.warning(f"Missing {len(missing_pages)} pages: {missing_pages}")

        if sent_to_models and read_by_models == 0 and model_errors:
            # Not one page the models were asked about came back, and the models are
            # what failed. That is them being unreachable far more often than it is a
            # document of blank pages, so it is raised for the stage to try again
            # rather than written down as a document nothing could be read from
            # (ADR 0007). What embedded text there was is dropped with it: a later
            # attempt reads the file from the start, and the page cache makes the
            # pages that did work cheap.
            raise ModelError(
                f"No page of {pdf_path} could be read by the models "
                f"({sent_to_models} attempted): {model_errors[-1]}"
            )

        return total_text

    def _read_embedded_text(
        self, page: fitz.Page, page_number: int, force_ocr: bool
    ) -> Tuple[Optional[str], bool]:
        """One page's embedded text, and whether it is enough to use without vision OCR.

        Text is enough when there is at least MIN_EMBEDDED_TEXT_CHARS of it and OCR is not
        forced. Whether anything can be done about text that isn't enough is the caller's
        question: with no vision model, too little text is still all the page has.
        """
        if force_ocr:
            logger.info(f"Page {page_number}: Forcing vision OCR (ignoring embedded text)")
            return None, False

        text = page.get_text()
        if text and len(text.strip()) >= MIN_EMBEDDED_TEXT_CHARS:
            logger.info(
                f"Page {page_number}: Extracted {len(text.strip())} chars of embedded text"
            )
            return text, True

        logger.info(
            f"Page {page_number}: Embedded text too short "
            f"({len(text.strip()) if text else 0} chars)"
        )
        return text, False

    def _render_page(self, page: fitz.Page, page_number: int) -> bytes:
        """Render a page to PNG bytes at 2x scale (~144 DPI) for better quality.

        PyMuPDF is not thread-safe, so rendering stays on the calling thread and only the
        model calls that follow it fan out across workers.
        """
        image = page.get_pixmap(matrix=fitz.Matrix(2, 2)).tobytes("png")
        logger.info(f"Page {page_number}: Rendered page image, calling vision model...")
        return image

    def _ocr_page(
        self,
        vision_model: ChatModel,
        image: bytes,
        page_number: int,
        embedded_text: Optional[str],
        refresh_cache: bool = False,
    ) -> PageRead:
        """Read one rendered page, falling back to its embedded text if the models fail.

        Runs on a worker thread, one page per worker, so it touches nothing but its
        arguments, the models and the page cache, which several workers may share.
        The failure is reported alongside the fallback rather than swallowed: it is
        still this page's own business, but the caller counts them.
        """
        try:
            vision_text = self._read_image(vision_model, image, refresh_cache=refresh_cache)
        except ModelError as e:
            logger.error(f"Page {page_number}: Vision OCR failed: {e}")
            return PageRead(embedded_text, model_error=e)

        if vision_text:
            logger.info(f"Page {page_number}: Vision OCR extracted {len(vision_text)} characters")
            return PageRead(vision_text)

        logger.warning(f"Page {page_number}: Vision OCR returned None or empty text")
        return PageRead(embedded_text)

    def detect_language(self, text: str) -> str:
        """
        Detect language of extracted text.

        Args:
            text: Text to analyze

        Returns:
            Language code (e.g., 'en', 'de', 'fr')
        """
        try:
            return detect(text)
        except LangDetectException:
            return "en"
