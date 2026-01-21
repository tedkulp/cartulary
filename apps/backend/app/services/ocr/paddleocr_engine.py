"""PaddleOCR engine implementation."""
import logging
from typing import List, Optional

from .base import OCREngine

logger = logging.getLogger(__name__)


class PaddleOCREngine(OCREngine):
    """PaddleOCR implementation - better accuracy, works well on AMD processors."""

    def __init__(self):
        """Initialize PaddleOCR engine."""
        self._engine = None

    @property
    def name(self) -> str:
        """Return engine name for logging."""
        return "PaddleOCR"

    def initialize(self, languages: List[str], use_gpu: bool) -> None:
        """
        Initialize PaddleOCR engine.

        Args:
            languages: List of language codes to support
            use_gpu: Whether to use GPU acceleration if available
        """
        from paddleocr import PaddleOCR

        # PaddleOCR uses single language string, not list
        # Map common language codes
        lang_map = {
            "en": "en",
            "ch": "ch",
            "chinese": "ch",
            "de": "german",
            "german": "german",
            "fr": "french",
            "french": "french",
            "ja": "japan",
            "japanese": "japan",
            "ko": "korean",
            "korean": "korean",
            "es": "spanish",
            "spanish": "spanish",
            "pt": "portuguese",
            "portuguese": "portuguese",
            "ru": "russian",
            "russian": "russian",
            "ar": "arabic",
            "arabic": "arabic",
        }

        lang = languages[0] if languages else "en"
        paddle_lang = lang_map.get(lang.lower(), lang)

        # PaddleOCR 2.x API
        self._engine = PaddleOCR(
            use_angle_cls=True,
            lang=paddle_lang,
            use_gpu=use_gpu,
            enable_mkldnn=False  # Disable OneDNN/MKL-DNN to avoid runtime errors
        )
        logger.info(f"PaddleOCR engine initialized with language: {paddle_lang}, GPU: {use_gpu}")

    def extract_text(self, image_path: str) -> Optional[str]:
        """
        Extract text from image using PaddleOCR.

        Args:
            image_path: Path to the image file

        Returns:
            Extracted text or None if extraction failed
        """
        if self._engine is None:
            logger.error("PaddleOCR engine not initialized")
            return None

        try:
            # PaddleOCR returns nested structure: [[[box, (text, conf)], ...]]
            result = self._engine.ocr(image_path, cls=True)

            if not result:
                logger.warning(f"PaddleOCR returned no text detections for: {image_path}")
                return ""

            text_lines = []
            for page in result:
                if page:
                    for line in page:
                        if len(line) >= 2:
                            text, confidence = line[1]
                            if confidence > 0.5:  # Only include confident results
                                text_lines.append(text)

            extracted_text = "\n".join(text_lines)
            logger.info(f"PaddleOCR extracted {len(text_lines)} text lines, {len(extracted_text)} total characters")

            return extracted_text

        except Exception as e:
            logger.error(f"Failed to extract text from image {image_path}: {type(e).__name__}: {str(e)}", exc_info=True)
            return None
