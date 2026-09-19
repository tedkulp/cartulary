"""OCR service for extracting text from documents using a vision model."""
import logging
import re
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF
from langdetect import DetectorFactory, detect
from langdetect.lang_detect_exception import LangDetectException

from app.providers import ChatModel, Message, ModelError

logger = logging.getLogger(__name__)

# langdetect is non-deterministic by default: the same text can yield different
# results across calls. Seeding makes detection reproducible.
DetectorFactory.seed = 0

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
    """

    def __init__(
        self,
        vision_model: Optional[ChatModel] = None,
        formatter_model: Optional[ChatModel] = None,
        page_concurrency: int = 1,
    ) -> None:
        """Initialize OCR service with the models for each pass."""
        if page_concurrency < 1:
            raise ValueError(f"page_concurrency must be at least 1, got {page_concurrency}")
        self.vision_model = vision_model
        self.formatter_model = formatter_model
        self.page_concurrency = page_concurrency

    def extract_text(self, file_path: str, force_ocr: bool = False) -> Optional[str]:
        """
        Extract text from an image or PDF file.

        Args:
            file_path: Path to the file to process
            force_ocr: If True, force OCR even if embedded text exists (for reprocessing)

        Returns:
            Extracted text or None if extraction failed
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
            return self._extract_text_from_pdf(file_path, force_ocr=force_ocr)

        # For images, use vision OCR
        if self.vision_model is None:
            logger.info("Vision OCR is disabled, cannot extract text from images")
            return None

        try:
            image = file_path_obj.read_bytes()
        except OSError as e:
            logger.error(f"Failed to read image {file_path}: {e}")
            return None

        try:
            return self._read_image(self.vision_model, image)
        except ModelError as e:
            logger.error(f"Vision OCR failed for {file_path}: {e}")
            return None

    def _read_image(self, vision_model: ChatModel, image: bytes) -> str:
        """
        Read text from one image using two-pass processing.

        Pass 1: Vision model extracts raw text from image
        Pass 2: Formatter model formats raw text into proper markdown

        Raises:
            ModelError: If either model fails
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
            return raw_text.strip()

        if self.formatter_model is None:
            logger.info("No formatter model, skipping Pass 2")
            return raw_text.strip()

        # PASS 2: Format raw text into proper markdown
        logger.info(
            f"Pass 2: Calling formatter model {self.formatter_model!r} for markdown formatting"
        )
        formatted_text = self.formatter_model.chat(
            [
                Message(role="system", content=FORMATTER_SYSTEM_PROMPT),
                Message(role="user", content=FORMATTER_PROMPT.format(raw_text=raw_text)),
            ]
        )

        logger.info(f"Pass 2 complete: Formatted to {len(formatted_text)} chars")
        logger.info("--- BEGIN FORMATTED TEXT ---")
        logger.info(formatted_text)
        logger.info("--- END FORMATTED TEXT ---")

        final_text = _clean_formatter_output(formatted_text, raw_text)
        logger.info(f"Cleaned formatter output to {len(final_text)} chars")
        logger.info("--- BEGIN FINAL OUTPUT ---")
        logger.info(final_text)
        logger.info("--- END FINAL OUTPUT ---")

        return final_text

    def _extract_text_from_pdf(self, pdf_path: str, force_ocr: bool = False) -> Optional[str]:
        """
        Extract text from a PDF, page by page.

        Args:
            pdf_path: Path to PDF file
            force_ocr: If True, skip embedded text and force vision OCR

        Returns:
            Extracted text from all pages
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
        in_flight: Dict[Future[Optional[str]], int] = {}

        def collect_finished() -> None:
            """Store every page that has finished, waiting for at least one to.

            Collecting all of them rather than the oldest keeps the pool fed: one slow page
            no longer holds back the slots of pages that finished behind it.
            """
            done, _ = wait(in_flight, return_when=FIRST_COMPLETED)
            for future in done:
                index = in_flight.pop(future)
                try:
                    page_text[index] = future.result()
                except RuntimeError as e:
                    # Whatever went wrong on the worker, one page shouldn't lose the others
                    logger.error(
                        f"Failed to OCR page {index + 1} of {pdf_path}: {type(e).__name__}: {e}",
                        exc_info=True,
                    )

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
                in_flight[
                    pool.submit(self._ocr_page, vision_model, image, page_number, embedded_text)
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
    ) -> Optional[str]:
        """Read one rendered page, falling back to its embedded text if the models fail.

        Runs on a worker thread, one page per worker, so it touches nothing but its
        arguments and the models.
        """
        try:
            vision_text = self._read_image(vision_model, image)
        except ModelError as e:
            logger.error(f"Page {page_number}: Vision OCR failed: {e}")
            return embedded_text

        if vision_text:
            logger.info(f"Page {page_number}: Vision OCR extracted {len(vision_text)} characters")
            return vision_text

        logger.warning(f"Page {page_number}: Vision OCR returned None or empty text")
        return embedded_text

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
