"""Tests for the capabilities endpoint and the shared disabled-capability refusal."""
from typing import Iterator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import capabilities
from app.core.capabilities import TURN_ON_ASSISTANT_MODEL, capability_disabled_error
from app.dependencies import get_current_user
from app.main import app
from tests.fakes import FakeEmbedder, ScriptedChatModel


@pytest.fixture
def client() -> Iterator[TestClient]:
    """The app with authentication satisfied, so the flags are what is under test.

    Not entered as a context manager: the lifespan starts the background workers,
    which these tests do not need and cannot run twice in one process.
    """
    app.dependency_overrides[get_current_user] = lambda: MagicMock()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _models(
    monkeypatch: pytest.MonkeyPatch,
    *,
    vision: object = None,
    embedder: object = None,
    assistant: object = None,
) -> None:
    """Point the endpoint's factory calls at the given models; None means off."""
    monkeypatch.setattr(capabilities, "get_vision_model", lambda: vision)
    monkeypatch.setattr(capabilities, "get_embedder", lambda: embedder)
    monkeypatch.setattr(capabilities, "get_assistant_model", lambda: assistant)


class TestGetCapabilities:
    def test_reports_everything_off_when_no_models_are_built(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A capability is off exactly when its factory returns None (ADR 0001)."""
        _models(monkeypatch)

        response = client.get("/api/v1/capabilities")

        assert response.status_code == 200
        assert response.json() == {
            "ocr": False,
            "embeddings": False,
            "chat": False,
            "metadata": False,
        }

    def test_reports_everything_on_when_every_model_is_built(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _models(
            monkeypatch,
            vision=ScriptedChatModel(),
            embedder=FakeEmbedder(),
            assistant=ScriptedChatModel(),
        )

        assert client.get("/api/v1/capabilities").json() == {
            "ocr": True,
            "embeddings": True,
            "chat": True,
            "metadata": True,
        }

    def test_assistant_model_drives_both_chat_and_metadata(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Both share LLM_ENABLED, so a client need not know they are one flag."""
        _models(monkeypatch, embedder=FakeEmbedder(), assistant=ScriptedChatModel())

        body = client.get("/api/v1/capabilities").json()

        assert body["chat"] is True
        assert body["metadata"] is True
        assert body["ocr"] is False

    def test_each_capability_is_independent(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _models(monkeypatch, vision=ScriptedChatModel())

        assert client.get("/api/v1/capabilities").json() == {
            "ocr": True,
            "embeddings": False,
            "chat": False,
            "metadata": False,
        }

    def test_a_misconfigured_provider_is_reported_off_not_raised(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A builder that cannot read its settings must not take the whole answer down."""
        def unknown_provider() -> object:
            raise ValueError("Unknown LLM_PROVIDER 'wat': expected ollama, openai or gemini")

        _models(monkeypatch, vision=ScriptedChatModel())
        monkeypatch.setattr(capabilities, "get_assistant_model", unknown_provider)

        response = client.get("/api/v1/capabilities")

        assert response.status_code == 200
        assert response.json()["chat"] is False
        assert response.json()["ocr"] is True

    def test_requires_authentication(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Which capabilities a deployment runs is configuration, not public."""
        _models(monkeypatch)

        response = TestClient(app).get("/api/v1/capabilities")

        assert response.status_code in (401, 403)


class TestCapabilityDisabledError:
    def test_answers_503(self) -> None:
        """One status code for every disabled capability (ADR 0003)."""
        error = capability_disabled_error(
            "Chat needs an assistant model, and none is configured.",
            TURN_ON_ASSISTANT_MODEL,
        )

        assert error.status_code == 503
        assert error.detail.startswith("Chat needs an assistant model, and none is configured.")

    def test_detail_tells_an_operator_what_to_change(self) -> None:
        """Nothing the caller sends can fix this, so the message is for the operator."""
        error = capability_disabled_error("Chat needs one.", TURN_ON_ASSISTANT_MODEL)

        assert "LLM_ENABLED=true" in error.detail
        assert "restart the backend" in error.detail
