"""Tests for OCRService."""
import pytest

from app.services.ocr_service import OCRService


@pytest.fixture
def ocr_service() -> OCRService:
    """OCR service instance (no Ollama client is created until OCR runs)."""
    return OCRService()


class TestDetectLanguage:
    """Tests for OCRService.detect_language()."""

    def test_detects_english(self, ocr_service):
        """English prose is detected as English."""
        text = (
            "This invoice covers the services rendered during the month of "
            "March, and payment is due within thirty days of receipt."
        )
        assert ocr_service.detect_language(text) == "en"

    def test_detects_german(self, ocr_service):
        """Non-English text is not silently reported as English."""
        text = (
            "Diese Rechnung umfasst die im Monat Marz erbrachten Leistungen, "
            "und die Zahlung ist innerhalb von dreissig Tagen zu leisten."
        )
        assert ocr_service.detect_language(text) == "de"

    @pytest.mark.parametrize("text", ["", "   ", "\n\n", "123 456", "..."])
    def test_returns_default_for_textless_input(self, ocr_service, text):
        """Empty or unusable text falls back to 'en' instead of raising."""
        assert ocr_service.detect_language(text) == "en"

    def test_is_deterministic(self, ocr_service):
        """Repeated detection of the same short text gives the same result.

        langdetect is randomized unless its factory is seeded, so this guards
        the seeding in ocr_service against being dropped.
        """
        text = "Total 42.00 Date 2026-01-26 Invoice"
        results = {ocr_service.detect_language(text) for _ in range(20)}
        assert len(results) == 1
