"""Tests for the model factory's OCR roles."""
import pytest

from app.config import settings
from app.providers import factory
from app.providers.ollama import OllamaChatModel


@pytest.fixture(autouse=True)
def fresh_factory(monkeypatch):
    """Configure OCR explicitly and clear the per-process cache around each test."""
    monkeypatch.setattr(settings, "OCR_ENABLED", True)
    monkeypatch.setattr(settings, "VISION_OCR_MODEL", "vision-model")
    monkeypatch.setattr(settings, "OCR_FORMATTER_MODEL", "formatter-model")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "http://ollama.test:11434")
    monkeypatch.setattr(settings, "MODEL_TIMEOUT_SECONDS", 42.0)
    factory.get_vision_model.cache_clear()
    factory.get_formatter_model.cache_clear()
    yield
    factory.get_vision_model.cache_clear()
    factory.get_formatter_model.cache_clear()


@pytest.mark.parametrize(
    ("build", "model_name"),
    [(factory.get_vision_model, "vision-model"), (factory.get_formatter_model, "formatter-model")],
)
class TestOcrRoles:
    def test_builds_ollama_model_from_settings(self, build, model_name):
        model = build()

        assert isinstance(model, OllamaChatModel)
        assert model.model == model_name
        assert model.host == "http://ollama.test:11434"
        assert model.timeout == 42.0

    def test_defaults_to_local_ollama_without_base_url(self, build, model_name, monkeypatch):
        monkeypatch.setattr(settings, "LLM_BASE_URL", None)

        assert build().host == "http://localhost:11434"

    def test_is_cached_per_process(self, build, model_name):
        assert build() is build()

    def test_returns_no_model_when_ocr_disabled(self, build, model_name, monkeypatch):
        monkeypatch.setattr(settings, "OCR_ENABLED", False)

        assert build() is None
