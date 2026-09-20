"""Tests for how document tasks chain onto the capabilities that are on."""
from typing import Iterator, Optional
from unittest.mock import MagicMock, patch

import pytest

from app.tasks import document_tasks
from tests.fakes import FakeEmbedder, ScriptedChatModel


@pytest.fixture
def enqueue() -> Iterator[tuple[MagicMock, MagicMock]]:
    """The two tasks OCR can chain onto, stubbed; yields (embeddings, metadata)."""
    with patch.object(
        document_tasks.generate_embeddings, "delay"
    ) as embeddings, patch.object(
        document_tasks.extract_metadata, "delay"
    ) as metadata:
        yield embeddings, metadata


def _capabilities(
    monkeypatch: pytest.MonkeyPatch,
    *,
    embedder: Optional[object] = None,
    assistant: Optional[object] = None,
) -> None:
    """Point the task's factory calls at the given models; None means off."""
    monkeypatch.setattr(document_tasks, "get_embedder", lambda: embedder)
    monkeypatch.setattr(document_tasks, "get_assistant_model", lambda: assistant)


class TestEnqueueNextAfterOcr:
    """A capability is off when its model is None, never by reading a setting (ADR 0001)."""

    def test_prefers_embeddings_when_both_are_on(
        self, enqueue: tuple[MagicMock, MagicMock], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Embeddings chain onto metadata themselves, so only the first is enqueued."""
        embeddings, metadata = enqueue
        _capabilities(monkeypatch, embedder=FakeEmbedder(), assistant=ScriptedChatModel())

        document_tasks._enqueue_next_after_ocr("doc-1", "ocr_complete", "Some text")

        embeddings.assert_called_once_with("doc-1")
        metadata.assert_not_called()

    def test_goes_straight_to_metadata_when_there_is_no_embedder(
        self, enqueue: tuple[MagicMock, MagicMock], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        embeddings, metadata = enqueue
        _capabilities(monkeypatch, assistant=ScriptedChatModel())

        document_tasks._enqueue_next_after_ocr("doc-1", "ocr_complete", "Some text")

        embeddings.assert_not_called()
        metadata.assert_called_once_with("doc-1")

    def test_stops_when_neither_capability_is_on(
        self, enqueue: tuple[MagicMock, MagicMock], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        embeddings, metadata = enqueue
        _capabilities(monkeypatch)

        document_tasks._enqueue_next_after_ocr("doc-1", "ocr_complete", "Some text")

        embeddings.assert_not_called()
        metadata.assert_not_called()

    @pytest.mark.parametrize(
        "processing_status,ocr_text",
        [("failed", "Some text"), ("ocr_complete", ""), ("ocr_complete", None)],
    )
    def test_chains_nothing_without_text_to_work_from(
        self,
        processing_status: str,
        ocr_text: Optional[str],
        enqueue: tuple[MagicMock, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Every capability on is still nothing to do when OCR produced nothing."""
        embeddings, metadata = enqueue
        _capabilities(monkeypatch, embedder=FakeEmbedder(), assistant=ScriptedChatModel())

        document_tasks._enqueue_next_after_ocr("doc-1", processing_status, ocr_text)

        embeddings.assert_not_called()
        metadata.assert_not_called()
