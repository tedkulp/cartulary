"""OCR engine factory and exports."""
import logging
import platform
from typing import Optional

from app.config import settings
from .base import OCREngine

logger = logging.getLogger(__name__)


def create_ocr_engine() -> Optional[OCREngine]:
    """
    Factory to create the configured OCR engine.

    Defaults to PaddleOCR for better accuracy, but falls back to EasyOCR
    when PaddleOCR is not available or when running on ARM processors.

    Returns:
        OCREngine instance or None if creation fails
    """
    provider = settings.OCR_PROVIDER.lower()

    # Detect ARM architecture
    machine = platform.machine().lower()
    is_arm = any(arch in machine for arch in ["arm", "aarch"])

    logger.info(f"OCR Provider Configuration: OCR_PROVIDER={settings.OCR_PROVIDER}, Architecture={machine}")

    if is_arm:
        logger.info(f"ARM architecture detected ({machine}), EasyOCR is recommended for compatibility")

    # Auto mode: try PaddleOCR first (better accuracy), fall back to EasyOCR (better compatibility)
    if provider == "auto":
        if is_arm:
            logger.info("ARM detected, defaulting to EasyOCR for better compatibility")
            provider = "easyocr"
        else:
            logger.info("x86/AMD64 detected, defaulting to PaddleOCR for better accuracy")
            provider = "paddleocr"

    # Try to create the requested provider
    if provider == "paddleocr":
        try:
            from .paddleocr_engine import PaddleOCREngine
            logger.info("🔍 Using PaddleOCR (better accuracy for complex documents)")
            return PaddleOCREngine()
        except ImportError as e:
            logger.warning(
                f"PaddleOCR not installed: {e}. "
                "Install with: pip install paddlepaddle paddleocr"
            )
            # Fall back to EasyOCR if PaddleOCR is not available
            if settings.OCR_PROVIDER.lower() == "auto":
                logger.info("Falling back to EasyOCR")
                provider = "easyocr"
            else:
                return None

    if provider == "easyocr":
        try:
            from .easyocr_engine import EasyOCREngine
            logger.info("🔍 Using EasyOCR (better compatibility for ARM/Apple Silicon)")
            return EasyOCREngine()
        except ImportError as e:
            logger.warning(
                f"EasyOCR not installed: {e}. "
                "Install with: pip install easyocr"
            )
            # If we were in auto mode and EasyOCR also failed, try PaddleOCR as last resort
            if settings.OCR_PROVIDER.lower() == "auto" and not is_arm:
                logger.info("EasyOCR failed, trying PaddleOCR as fallback")
                try:
                    from .paddleocr_engine import PaddleOCREngine
                    logger.info("🔍 Using PaddleOCR (fallback from EasyOCR)")
                    return PaddleOCREngine()
                except ImportError:
                    logger.error("Neither EasyOCR nor PaddleOCR could be loaded")
                    return None
            return None

    logger.error(f"Unknown OCR provider: {provider}. Use 'auto', 'paddleocr', or 'easyocr'")
    return None


__all__ = ["OCREngine", "create_ocr_engine"]
