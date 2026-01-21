"""EasyOCR engine implementation."""
import logging
from typing import List, Optional

from .base import OCREngine

logger = logging.getLogger(__name__)


class EasyOCREngine(OCREngine):
    """EasyOCR implementation - works well on ARM64 and general CPU."""

    def __init__(self):
        """Initialize EasyOCR engine."""
        self._engine = None

    @property
    def name(self) -> str:
        """Return engine name for logging."""
        return "EasyOCR"

    def initialize(self, languages: List[str], use_gpu: bool) -> None:
        """
        Initialize EasyOCR engine.

        Args:
            languages: List of language codes to support
            use_gpu: Whether to use GPU acceleration if available
        """
        import easyocr

        # Auto-detect GPU availability if use_gpu is True
        actual_use_gpu = use_gpu
        if use_gpu:
            try:
                import torch
                if not torch.cuda.is_available():
                    logger.warning("GPU requested but CUDA not available, falling back to CPU")
                    actual_use_gpu = False
                else:
                    logger.info(f"GPU detected: {torch.cuda.get_device_name(0)}")
            except ImportError:
                logger.warning("PyTorch not available for GPU detection, falling back to CPU")
                actual_use_gpu = False

        # EasyOCR supports multiple languages
        lang_list = list(languages)

        self._engine = easyocr.Reader(
            lang_list=lang_list,
            gpu=actual_use_gpu
        )
        logger.info(f"EasyOCR engine initialized with languages: {lang_list}, GPU: {actual_use_gpu}")

    def extract_text(self, image_path: str) -> Optional[str]:
        """
        Extract text from image using EasyOCR.

        Args:
            image_path: Path to the image file

        Returns:
            Extracted text or None if extraction failed
        """
        if self._engine is None:
            logger.error("EasyOCR engine not initialized")
            return None

        try:
            # EasyOCR returns: [([bbox], text, confidence), ...]
            result = self._engine.readtext(image_path)

            if not result:
                logger.warning(f"EasyOCR returned no text detections for: {image_path}")
                return ""

            # Extract text from OCR results
            text_lines = []
            for detection in result:
                if len(detection) >= 3:
                    bbox, text, confidence = detection
                    if confidence > 0.5:  # Only include confident results
                        text_lines.append(text)

            extracted_text = "\n".join(text_lines)
            logger.info(f"EasyOCR extracted {len(text_lines)} text lines, {len(extracted_text)} total characters")

            return extracted_text

        except Exception as e:
            logger.error(f"Failed to extract text from image {image_path}: {type(e).__name__}: {str(e)}", exc_info=True)
            return None
