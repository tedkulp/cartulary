"""Tests for how document tasks chain onto the capabilities that are on."""
from typing import Any, Dict, Iterator, List, Optional, Tuple
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


DOC_ID = "11111111-1111-1111-1111-111111111111"
OWNER_ID = "22222222-2222-2222-2222-222222222222"


class _Result:
    """The slice of a SQLAlchemy Result the metadata task actually uses."""

    def __init__(self, rows: List[Tuple[Any, ...]]) -> None:
        self._rows = rows

    def fetchone(self) -> Optional[Tuple[Any, ...]]:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> List[Tuple[Any, ...]]:
        return self._rows


class FakeSession:
    """A DB session that answers the metadata task's reads and records its writes.

    Statements are matched on a distinctive fragment rather than in call order, so
    a change to the order of unrelated queries doesn't break the test.
    """

    def __init__(self, *, ocr_text: str = "Some text") -> None:
        self.statements: List[str] = []
        self._ocr_text = ocr_text
        self.closed = False

    def execute(self, statement: Any, params: Optional[Dict[str, Any]] = None) -> _Result:
        sql = " ".join(str(statement).split())
        self.statements.append(sql)

        if "SELECT ocr_text" in sql:
            return _Result([(self._ocr_text, "invoice.pdf", "invoice.pdf")])
        if "SELECT name FROM tags" in sql:
            return _Result([("existing-tag",)])
        if "SELECT description" in sql:
            return _Result([("",)])
        if "SELECT owner_id" in sql:
            return _Result([(OWNER_ID,)])
        if "SELECT id FROM tags" in sql:
            return _Result([])
        return _Result([])

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True

    def deletes_document_tags(self) -> bool:
        return any("DELETE FROM document_tags" in sql for sql in self.statements)


@pytest.fixture
def metadata_task(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeSession]:
    """Runs extract_metadata against a fake session and a scripted assistant.

    Yields the session so a test can set up the reply first and then assert on
    what the task wrote.
    """
    session = FakeSession()
    monkeypatch.setattr(document_tasks, "SessionLocal", lambda: session)
    monkeypatch.setattr(document_tasks, "get_assistant_model", lambda: ScriptedChatModel())
    monkeypatch.setattr("app.database.engine", MagicMock())
    monkeypatch.setattr(document_tasks, "notification_service", MagicMock())
    yield session


class TestExtractMetadataTags:
    """The LLM replacing a document's tags must not mean it can empty them."""

    def _run(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        with patch(
            "app.services.assistant_service.AssistantService.extract_metadata",
            return_value=metadata,
        ):
            return document_tasks.extract_metadata.run(DOC_ID)

    def test_keeps_existing_tags_when_the_llm_suggests_none(
        self, metadata_task: FakeSession
    ) -> None:
        """An empty suggestion list means 'nothing to add', never 'clear what is there'."""
        self._run({"title": "Invoice", "suggested_tags": []})

        assert not metadata_task.deletes_document_tags()

    def test_keeps_existing_tags_when_the_reply_has_no_tag_field(
        self, metadata_task: FakeSession
    ) -> None:
        """A reply the model left the tags out of is the same as suggesting none."""
        self._run({"title": "Invoice"})

        assert not metadata_task.deletes_document_tags()

    def test_replaces_existing_tags_when_the_llm_suggests_some(
        self, metadata_task: FakeSession
    ) -> None:
        """With tags to write, the old associations still go first."""
        self._run({"title": "Invoice", "suggested_tags": ["receipt"]})

        assert metadata_task.deletes_document_tags()
        assert any("INSERT INTO document_tags" in sql for sql in metadata_task.statements)

    def test_counts_the_tags_that_landed_not_the_ones_suggested(
        self, metadata_task: FakeSession
    ) -> None:
        """A suggestion that cleans away to nothing was never added."""
        result = self._run({"title": "Invoice", "suggested_tags": ["receipt", "   "]})

        assert result["tags_added"] == 1

    def test_counts_no_tags_when_the_llm_suggests_none(
        self, metadata_task: FakeSession
    ) -> None:
        result = self._run({"title": "Invoice", "suggested_tags": []})

        assert result["tags_added"] == 0
