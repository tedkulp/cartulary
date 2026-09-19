"""Tests for the model factory's OCR, assistant and embedder roles."""
import pytest

from app.config import settings
from app.providers import factory
from app.providers.gemini import GeminiChatModel
from app.providers.local import LocalEmbedder
from app.providers.ollama import OllamaChatModel, OllamaEmbedder
from app.providers.openai import OpenAIChatModel, OpenAIEmbedder


@pytest.fixture(autouse=True)
def fresh_factory(monkeypatch):
    """Configure OCR and the model host explicitly and clear the per-process cache around each test."""
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


class TestAssistantRole:
    @pytest.fixture(autouse=True)
    def assistant_settings(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_ENABLED", True)
        monkeypatch.setattr(settings, "LLM_MODEL", "assistant-model")
        monkeypatch.setattr(settings, "OPENAI_API_KEY", "openai-key")
        monkeypatch.setattr(settings, "GEMINI_API_KEY", "gemini-key")
        factory.get_assistant_model.cache_clear()
        yield
        factory.get_assistant_model.cache_clear()

    def test_builds_ollama_model_from_settings(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_PROVIDER", "ollama")

        model = factory.get_assistant_model()

        assert isinstance(model, OllamaChatModel)
        assert model.model == "assistant-model"
        assert model.host == "http://ollama.test:11434"
        assert model.timeout == 42.0

    def test_ollama_model_defaults_to_local_ollama_without_base_url(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_PROVIDER", "ollama")
        monkeypatch.setattr(settings, "LLM_BASE_URL", None)

        assert factory.get_assistant_model().host == "http://localhost:11434"

    def test_builds_openai_model_with_openai_key(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")

        model = factory.get_assistant_model()

        assert isinstance(model, OpenAIChatModel)
        assert model.model == "assistant-model"
        assert model.api_key == "openai-key"
        assert model.timeout == 42.0

    def test_builds_gemini_model_with_gemini_key(self, monkeypatch):
        """Regression test for #13: chat on Gemini was built without the Gemini key."""
        monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")

        model = factory.get_assistant_model()

        assert isinstance(model, GeminiChatModel)
        assert model.model == "assistant-model"
        assert model.api_key == "gemini-key"
        assert model.timeout == 42.0

    def test_rejects_unknown_provider(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_PROVIDER", "local")

        with pytest.raises(ValueError, match="LLM_PROVIDER"):
            factory.get_assistant_model()

    def test_is_cached_per_process(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")

        assert factory.get_assistant_model() is factory.get_assistant_model()

    def test_returns_no_model_when_llm_disabled(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
        monkeypatch.setattr(settings, "LLM_ENABLED", False)

        assert factory.get_assistant_model() is None


class TestEmbedderRole:
    @pytest.fixture(autouse=True)
    def embedding_settings(self, monkeypatch):
        monkeypatch.setattr(settings, "EMBEDDING_ENABLED", True)
        monkeypatch.setattr(settings, "EMBEDDING_MODEL", "embedding-model")
        monkeypatch.setattr(settings, "EMBEDDING_DIMENSION", 768)
        monkeypatch.setattr(settings, "OPENAI_API_KEY", "openai-key")
        factory.get_embedder.cache_clear()
        yield
        factory.get_embedder.cache_clear()

    def test_builds_ollama_embedder_from_settings(self, monkeypatch):
        monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "ollama")

        embedder = factory.get_embedder()

        assert isinstance(embedder, OllamaEmbedder)
        assert embedder.model_name == "embedding-model"
        assert embedder.dimension == 768
        assert embedder.host == "http://ollama.test:11434"
        assert embedder.timeout == 42.0

    def test_ollama_embedder_defaults_to_local_ollama_without_base_url(self, monkeypatch):
        monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "ollama")
        monkeypatch.setattr(settings, "LLM_BASE_URL", None)

        assert factory.get_embedder().host == "http://localhost:11434"

    def test_builds_openai_embedder_with_openai_key(self, monkeypatch):
        monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "openai")

        embedder = factory.get_embedder()

        assert isinstance(embedder, OpenAIEmbedder)
        assert embedder.model_name == "embedding-model"
        assert embedder.dimension == 768
        assert embedder.api_key == "openai-key"
        assert embedder.timeout == 42.0

    def test_builds_local_embedder(self, monkeypatch):
        monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "local")

        embedder = factory.get_embedder()

        assert isinstance(embedder, LocalEmbedder)
        assert embedder.model_name == "embedding-model"
        assert embedder.dimension == 768

    def test_rejects_unknown_provider(self, monkeypatch):
        monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "gemini")

        with pytest.raises(ValueError, match="EMBEDDING_PROVIDER"):
            factory.get_embedder()

    def test_is_cached_per_process(self, monkeypatch):
        monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "ollama")

        assert factory.get_embedder() is factory.get_embedder()

    def test_returns_no_embedder_when_embeddings_disabled(self, monkeypatch):
        monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "ollama")
        monkeypatch.setattr(settings, "EMBEDDING_ENABLED", False)

        assert factory.get_embedder() is None
