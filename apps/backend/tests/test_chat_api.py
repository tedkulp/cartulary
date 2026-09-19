"""Tests for the chat API's service dependency."""
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1 import chat
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
        """With no assistant model there is nothing to answer with."""
        monkeypatch.setattr(chat, "get_assistant_model", lambda: None)

        with pytest.raises(HTTPException) as raised:
            chat.get_chat_service(db=MagicMock())

        assert raised.value.status_code == 400
