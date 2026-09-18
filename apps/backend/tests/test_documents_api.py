"""Tests for document API endpoints."""
import uuid
from types import SimpleNamespace
from typing import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1 import documents
from app.schemas.document import DocumentUpdate


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
