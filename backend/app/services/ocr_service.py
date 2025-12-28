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
        self.use_gpu = settings.OCR_USE_GPU
        self._ocr_engine = None

    def _initialize_engine(self):
        """Lazy initialize OCR engine."""
        if not self.enabled:
            return

        if self._ocr_engine is None:
            try:
                import easyocr

                # Auto-detect GPU availability if use_gpu is True
                use_gpu = self.use_gpu
                if use_gpu:
                    try:
                        import torch
                        if not torch.cuda.is_available():
                            logger.warning("GPU requested but CUDA not available, falling back to CPU")
                            use_gpu = False
                        else:
                            logger.info(f"GPU detected: {torch.cuda.get_device_name(0)}")
                    except ImportError:
                        logger.warning("PyTorch not available for GPU detection, falling back to CPU")
                        use_gpu = False

                # EasyOCR supports multiple languages and works well on ARM64
                # Map our language codes to EasyOCR format
                lang_list = [lang if lang != "en" else "en" for lang in self.languages]

                self._ocr_engine = easyocr.Reader(
                    lang_list=lang_list,
                    gpu=use_gpu
                )
                logger.info(f"EasyOCR engine initialized successfully with languages: {lang_list}, GPU: {use_gpu}")
            except ImportError:
                logger.warning(
                    "EasyOCR not installed. OCR features will be disabled. "
                    "Install with: pip install easyocr"
                )
                self.enabled = False
            except Exception as e:
                logger.error(f"Failed to initialize EasyOCR: {e}")
                self.enabled = False

    def extract_text(self, file_path: str) -> Optional[str]:
        """
        Extract text from an image or PDF file.

        Args:
            file_path: Path to the file to process

        Returns:
            Extracted text or None if extraction failed
        """
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                logger.error(f"File not found: {file_path}")
                return None

            # Handle PDF files - always try to extract embedded text first
            if file_path_obj.suffix.lower() == ".pdf":
                return self._extract_text_from_pdf(file_path)

            # For images, we need OCR
            if not self.enabled:
                logger.info("OCR is disabled, cannot extract text from images")
                return None

            self._initialize_engine()
            if self._ocr_engine is None:
                return None

            return self._extract_text_from_image(file_path)

        except Exception as e:
            logger.error(f"Text extraction failed for {file_path}: {e}")
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
            # EasyOCR returns: [([bbox], text, confidence), ...]
            result = self._ocr_engine.readtext(image_path)

            if not result:
                return ""

            # Extract text from OCR results
            text_lines = []
            for detection in result:
                if len(detection) >= 3:
                    bbox, text, confidence = detection
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

                # If no embedded text or very little, use OCR (if available)
                if (not text or len(text.strip()) < 50) and self.enabled:
                    self._initialize_engine()
                    if self._ocr_engine:
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
