"""Abstract base class for OCR engines."""
from abc import ABC, abstractmethod
from typing import List, Optional


class OCREngine(ABC):
    """Abstract base class for OCR engines."""

    @abstractmethod
    def initialize(self, languages: List[str], use_gpu: bool) -> None:
        """
        Initialize the OCR engine.

        Args:
            languages: List of language codes to support
            use_gpu: Whether to use GPU acceleration if available
        """
        pass

    @abstractmethod
    def extract_text(self, image_path: str) -> Optional[str]:
        """
        Extract text from an image file.

        Args:
            image_path: Path to the image file

        Returns:
            Extracted text or None if extraction failed
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return engine name for logging."""
        pass
