"""Tests for document API endpoints."""
import uuid
from io import BytesIO
from types import SimpleNamespace
from typing import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi import UploadFile

from app.api.v1 import documents
from app.core.exceptions import DuplicateError
from app.schemas.document import DocumentUpdate
from tests.fakes import FakeEmbedder, ScriptedChatModel


def _document(processing_status: str) -> SimpleNamespace:
    """A stand-in for a Document row with the fields update_document touches."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        title="Old title",
        description=None,
        is_public=False,
        processing_status=processing_status,
    )


@pytest.fixture
def enqueue_embeddings() -> Iterator[MagicMock]:
    """Stub out notifications and yield the mocked generate_embeddings.delay."""
    with patch.object(
        documents.notification_service, "notify_document_updated", new=AsyncMock()
    ), patch("app.tasks.document_tasks.generate_embeddings.delay") as delay:
        yield delay


class TestUpdateDocument:
    """Tests for the update_document endpoint handler."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", ["embedding_complete", "llm_complete"])
    async def test_title_change_on_processed_document_enqueues_reembedding(
        self, status: str, enqueue_embeddings: MagicMock
    ) -> None:
        """Editing the title of an embedded document saves it and re-embeds (issue #12)."""
        document = _document(status)
        db = MagicMock()

        result = await documents.update_document(
            document_id=document.id,
            document_update=DocumentUpdate(title="New title"),
            document=document,
            db=db,
        )

        assert result.title == "New title"
        db.commit.assert_called_once()
        enqueue_embeddings.assert_called_once_with(str(document.id))

    @pytest.mark.asyncio
    async def test_is_public_change_does_not_reembed(
        self, enqueue_embeddings: MagicMock
    ) -> None:
        """Changing only visibility saves it but leaves the embedding text alone."""
        document = _document("llm_complete")
        db = MagicMock()

        await documents.update_document(
            document_id=document.id,
            document_update=DocumentUpdate(is_public=True),
            document=document,
            db=db,
        )

        assert document.is_public is True
        db.commit.assert_called_once()
        enqueue_embeddings.assert_not_called()


class TestUploadDocument:
    """Tests for the multipart adapter around Document intake."""

    def test_duplicate_response_has_standard_fastapi_detail_shape(self) -> None:
        existing_id = uuid.uuid4()
        intake = MagicMock()
        intake.intake.side_effect = DuplicateError(
            "Document already exists", detail={"document_id": str(existing_id)}
        )
        user = SimpleNamespace(id=uuid.uuid4())
        upload = UploadFile(file=BytesIO(b"same bytes"), filename="copy.pdf")

        with pytest.raises(HTTPException) as raised:
            documents.upload_document(
                file=upload,
                title=None,
                current_user=user,
                intake_service=intake,
            )

        assert raised.value.status_code == 409
        assert raised.value.detail == {
            "error": "duplicate",
            "message": "Document already exists",
            "document_id": str(existing_id),
        }
        intake.intake.assert_called_once_with(
            content=b"same bytes",
            filename="copy.pdf",
            owner_id=user.id,
            uploader_id=user.id,
            title=None,
        )

    def test_unexpected_failure_does_not_disclose_internal_error(self) -> None:
        intake = MagicMock()
        intake.intake.side_effect = RuntimeError("postgres password was secret")
        upload = UploadFile(file=BytesIO(b"report"), filename="report.pdf")

        with pytest.raises(HTTPException) as raised:
            documents.upload_document(
                file=upload,
                title=None,
                current_user=SimpleNamespace(id=uuid.uuid4()),
                intake_service=intake,
            )

        assert raised.value.status_code == 500
        assert raised.value.detail == "Failed to upload document"


class TestRegenerateEmbeddings:
    """Tests for the regenerate_embeddings endpoint handler."""

    def test_refuses_when_embeddings_disabled(
        self, enqueue_embeddings: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With no embedder, the task would skip, so the endpoint must not claim it started.

        503, not 400: the request is fine, the capability is off (ADR 0003), and
        the detail names the setting that turns it back on.
        """
        monkeypatch.setattr(documents, "get_embedder", lambda: None)
        document = SimpleNamespace(id=uuid.uuid4(), ocr_text="Some text")

        with pytest.raises(HTTPException) as raised:
            documents.regenerate_embeddings(document_id=document.id, document=document)

        assert raised.value.status_code == 503
        assert "EMBEDDING_ENABLED=true" in raised.value.detail
        enqueue_embeddings.assert_not_called()

    def test_enqueues_when_embeddings_enabled(
        self, enqueue_embeddings: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(documents, "get_embedder", lambda: FakeEmbedder())
        document = SimpleNamespace(id=uuid.uuid4(), ocr_text="Some text")

        documents.regenerate_embeddings(document_id=document.id, document=document)

        enqueue_embeddings.assert_called_once_with(str(document.id))

    def test_refuses_a_document_with_no_text(
        self, enqueue_embeddings: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nothing to embed is the caller's problem, so it stays a 400."""
        monkeypatch.setattr(documents, "get_embedder", lambda: FakeEmbedder())
        document = SimpleNamespace(id=uuid.uuid4(), ocr_text="")

        with pytest.raises(HTTPException) as raised:
            documents.regenerate_embeddings(document_id=document.id, document=document)

        assert raised.value.status_code == 400
        enqueue_embeddings.assert_not_called()


class TestRegenerateMetadata:
    """Tests for the regenerate_metadata endpoint handler."""

    @pytest.fixture
    def enqueue_metadata(self) -> Iterator[MagicMock]:
        with patch("app.tasks.document_tasks.extract_metadata.delay") as delay:
            yield delay

    def test_refuses_when_no_assistant_model(
        self, enqueue_metadata: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Same answer as chat, which shares LLM_ENABLED with this (issue #28)."""
        monkeypatch.setattr(documents, "get_assistant_model", lambda: None)
        document = SimpleNamespace(id=uuid.uuid4(), ocr_text="Some text")

        with pytest.raises(HTTPException) as raised:
            documents.regenerate_metadata(document_id=document.id, document=document)

        assert raised.value.status_code == 503
        assert "LLM_ENABLED=true" in raised.value.detail
        enqueue_metadata.assert_not_called()

    def test_enqueues_when_an_assistant_model_exists(
        self, enqueue_metadata: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(documents, "get_assistant_model", lambda: ScriptedChatModel())
        document = SimpleNamespace(id=uuid.uuid4(), ocr_text="Some text")

        documents.regenerate_metadata(document_id=document.id, document=document)

        enqueue_metadata.assert_called_once_with(str(document.id))

    def test_refuses_a_document_with_no_text(
        self, enqueue_metadata: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nothing to read metadata off is the caller's problem, so it stays a 400."""
        monkeypatch.setattr(documents, "get_assistant_model", lambda: ScriptedChatModel())
        document = SimpleNamespace(id=uuid.uuid4(), ocr_text=None)

        with pytest.raises(HTTPException) as raised:
            documents.regenerate_metadata(document_id=document.id, document=document)

        assert raised.value.status_code == 400
        enqueue_metadata.assert_not_called()
