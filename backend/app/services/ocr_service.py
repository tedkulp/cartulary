"""OCR service for extracting text from documents."""
import logging
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class OCRService:
    """Service for OCR text extraction."""

    def __init__(self):
        """Initialize OCR service."""
        self.enabled = settings.OCR_ENABLED
        self.languages = settings.OCR_LANGUAGES
        self.use_gpu = settings.PADDLEOCR_USE_GPU
        self._ocr_engine = None

    def _initialize_engine(self):
        """Lazy initialize OCR engine."""
        if not self.enabled:
            return

        if self._ocr_engine is None:
            try:
                from paddleocr import PaddleOCR

                self._ocr_engine = PaddleOCR(
                    use_angle_cls=True,
                    lang="en",  # TODO: Support multiple languages
                    use_gpu=self.use_gpu,
                    show_log=False,
                )
                logger.info("PaddleOCR engine initialized successfully")
            except ImportError:
                logger.warning(
                    "PaddleOCR not installed. OCR features will be disabled. "
                    "Install with: pip install paddleocr paddlepaddle"
                )
                self.enabled = False
            except Exception as e:
                logger.error(f"Failed to initialize PaddleOCR: {e}")
                self.enabled = False

    def extract_text(self, file_path: str) -> Optional[str]:
        """
        Extract text from an image or PDF file.

        Args:
            file_path: Path to the file to process

        Returns:
            Extracted text or None if OCR is disabled/failed
        """
        if not self.enabled:
            logger.info("OCR is disabled, skipping text extraction")
            return None

        self._initialize_engine()

        if self._ocr_engine is None:
            return None

        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                logger.error(f"File not found: {file_path}")
                return None

            # Handle PDF files by converting to images first
            if file_path_obj.suffix.lower() == ".pdf":
                return self._extract_text_from_pdf(file_path)
            else:
                return self._extract_text_from_image(file_path)

        except Exception as e:
            logger.error(f"OCR extraction failed for {file_path}: {e}")
            return None

    def _extract_text_from_image(self, image_path: str) -> Optional[str]:
        """
        Extract text from a single image.

        Args:
            image_path: Path to image file

        Returns:
            Extracted text
        """
        try:
            result = self._ocr_engine.ocr(image_path, cls=True)

            if not result or not result[0]:
                return ""

            # Extract text from OCR results
            # PaddleOCR returns: [[[bbox], (text, confidence)], ...]
            text_lines = []
            for line in result[0]:
                if line and len(line) >= 2:
                    text, confidence = line[1]
                    if confidence > 0.5:  # Only include confident results
                        text_lines.append(text)

            return "\n".join(text_lines)

        except Exception as e:
            logger.error(f"Failed to extract text from image {image_path}: {e}")
            return None

    def _extract_text_from_pdf(self, pdf_path: str) -> Optional[str]:
        """
        Extract text from PDF file.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Extracted text from all pages
        """
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(pdf_path)
            all_text = []

            for page_num in range(len(doc)):
                page = doc[page_num]

                # First try to extract embedded text
                text = page.get_text()

                # If no embedded text or very little, use OCR
                if not text or len(text.strip()) < 50:
                    # Convert page to image
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x scale for better OCR
                    img_path = f"/tmp/page_{page_num}.png"
                    pix.save(img_path)

                    # Run OCR on the image
                    ocr_text = self._extract_text_from_image(img_path)
                    if ocr_text:
                        text = ocr_text

                    # Clean up temp file
                    Path(img_path).unlink(missing_ok=True)

                if text:
                    all_text.append(text)

            doc.close()
            return "\n\n".join(all_text)

        except ImportError:
            logger.error(
                "PyMuPDF not installed. Install with: pip install pymupdf"
            )
            return None
        except Exception as e:
            logger.error(f"Failed to extract text from PDF {pdf_path}: {e}")
            return None

    def detect_language(self, text: str) -> str:
        """
        Detect language of extracted text.

        Args:
            text: Text to analyze

        Returns:
            Language code (e.g., 'en', 'de', 'fr')
        """
        # TODO: Implement language detection using langdetect or similar
        # For now, just return the first configured language
        return self.languages[0] if self.languages else "en"
