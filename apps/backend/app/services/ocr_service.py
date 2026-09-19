"""OCR service for extracting text from documents using a vision model."""
import logging
from pathlib import Path
from typing import Optional

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


class OCRService:
    """Two-pass text extraction: a vision model reads pages, a formatter model makes markdown.

    Either model may be None. With no vision model, PDFs yield only their embedded text
    and images yield nothing. With no formatter model, the vision model's raw text is used.
    """

    def __init__(
        self,
        vision_model: Optional[ChatModel] = None,
        formatter_model: Optional[ChatModel] = None,
    ) -> None:
        """Initialize OCR service with the models for each pass."""
        self.vision_model = vision_model
        self.formatter_model = formatter_model

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

        return formatted_text.strip()

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
        logger.info(f"PDF has {page_count} pages")

        all_text = []
        processed_pages = []

        with doc:
            for page_num in range(page_count):
                try:
                    text = self._extract_text_from_page(doc[page_num], page_num + 1, force_ocr)
                except RuntimeError as e:
                    # PyMuPDF errors: one unreadable page shouldn't lose the others
                    logger.error(
                        f"Failed to process page {page_num + 1} of {pdf_path}: "
                        f"{type(e).__name__}: {e}",
                        exc_info=True,
                    )
                    text = None
                if text:
                    all_text.append(text)
                    processed_pages.append(page_num + 1)
                else:
                    logger.warning(
                        f"Page {page_num + 1}: No text extracted (text is None or empty)"
                    )

        total_text = "\n\n".join(all_text)
        logger.info(
            f"PDF extraction complete: {len(all_text)}/{page_count} pages processed successfully"
        )
        logger.info(f"Successfully processed pages: {processed_pages}")
        logger.info(f"Total extracted text: {len(total_text)} characters")

        if len(all_text) < page_count:
            missing_pages = [p for p in range(1, page_count + 1) if p not in processed_pages]
            logger.warning(f"Missing {page_count - len(all_text)} pages: {missing_pages}")

        return total_text

    def _extract_text_from_page(
        self, page: fitz.Page, page_number: int, force_ocr: bool
    ) -> Optional[str]:
        """Return one page's text: embedded text, or vision OCR when it is too short or forced."""
        text = None

        # If force_ocr is True, skip embedded text extraction entirely
        if force_ocr:
            logger.info(f"Page {page_number}: Forcing vision OCR (ignoring embedded text)")
        else:
            text = page.get_text()

        # Use vision OCR if: forced, no embedded text, or embedded text too short
        should_use_vision_ocr = (
            force_ocr or not text or len(text.strip()) < MIN_EMBEDDED_TEXT_CHARS
        )

        if not should_use_vision_ocr or self.vision_model is None:
            if text:
                logger.info(
                    f"Page {page_number}: Extracted {len(text.strip())} chars of embedded text"
                )
            return text

        if not force_ocr:
            logger.info(
                f"Page {page_number}: Embedded text too short "
                f"({len(text.strip()) if text else 0} chars), attempting vision OCR"
            )

        # Render at 2x scale (~144 DPI) for better quality
        image = page.get_pixmap(matrix=fitz.Matrix(2, 2)).tobytes("png")
        logger.info(f"Page {page_number}: Rendered page image, calling vision model...")

        try:
            vision_text = self._read_image(self.vision_model, image)
        except ModelError as e:
            logger.error(f"Page {page_number}: Vision OCR failed: {e}")
            vision_text = None

        if vision_text:
            logger.info(f"Page {page_number}: Vision OCR extracted {len(vision_text)} characters")
            return vision_text

        logger.warning(f"Page {page_number}: Vision OCR returned None or empty text")
        return text

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
