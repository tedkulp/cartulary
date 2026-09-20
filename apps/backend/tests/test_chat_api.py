"""Tests for the chat API's service dependency."""
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.v1 import chat
from app.api.v1.auth import get_current_user
from app.database import get_db
from app.main import app
from tests.fakes import FakeEmbedder, ScriptedChatModel


@pytest.fixture(autouse=True)
def fake_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat, "get_embedder", lambda: FakeEmbedder())


class TestGetChatService:
    def test_uses_assistant_model_from_factory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        model = ScriptedChatModel()
        monkeypatch.setattr(chat, "get_assistant_model", lambda: model)

        service = chat.get_chat_service(db=MagicMock())

        assert service.assistant_service.model is model

    def test_refuses_when_llm_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With no assistant model there is nothing to answer with, and the
        operator is told which setting turns chat back on (issue #26)."""
        monkeypatch.setattr(chat, "get_assistant_model", lambda: None)

        with pytest.raises(HTTPException) as raised:
            chat.get_chat_service(db=MagicMock())

        assert raised.value.status_code == 503
        assert "LLM_ENABLED=true" in raised.value.detail


class TestChatRoute:
    """The refusal over the real request path, not just the dependency."""

    def test_disabled_chat_answers_503(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The handler wraps its body in `except Exception`; a dependency's refusal
        must not be rewritten into a generic 500 on the way out."""
        monkeypatch.setattr(chat, "get_assistant_model", lambda: None)
        app.dependency_overrides[get_current_user] = lambda: MagicMock()
        app.dependency_overrides[get_db] = lambda: MagicMock()
        try:
            with TestClient(app) as client:
                response = client.post("/api/v1/chat/", json={"question": "why?"})
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 503
        assert "LLM_ENABLED=true" in response.json()["detail"]
