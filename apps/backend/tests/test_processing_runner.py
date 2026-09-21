"""The runner: what actually lands in the row, and what clients and the queue are told.

Against the real PostgreSQL from the `db_session` fixture, because the runner's whole
job is to write a status and then describe the write — a mocked Session would only let
these tests assert the mock's behaviour. See ADR 0005 and ADR 0006.

The models are the fakes from `tests/fakes.py` and the queue is a list, so nothing here
needs Redis, a Celery worker or a model server.
"""
import uuid
from pathlib import Path
from typing import Iterator, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest

from app.config import settings
from app.models.document import Document, DocumentEmbedding
from app.models.tag import Tag
from app.models.user import User
from app.processing import ProcessingStatus, Stage
from app.processing.retry import RETRY_DELAYS
from app.processing.runner import Models, run_stage
from app.providers import ModelError
from tests.fakes import FailingEmbedder, FakeEmbedder, ScriptedChatModel

DIMENSION = settings.EMBEDDING_DIMENSION
METADATA_REPLY = (
    '{"title": "Slate invoice", "correspondent": "Borrowdale Quarry",'
    ' "document_date": "1897-04-02", "document_type": "Invoice",'
    ' "summary": "An invoice for two tons of slate.",'
    ' "suggested_tags": ["invoice", "quarry"]}'
)
RECONCILE_REPLY = '["invoice", "quarry"]'


@pytest.fixture
def owner(db_session) -> User:
    user = User(
        id=uuid.uuid4(), email=f"{uuid.uuid4().hex}@example.com", hashed_password="x",
        is_active=True, is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    return user


def make_document(
    db_session,
    owner: User,
    *,
    status: ProcessingStatus = ProcessingStatus.PENDING,
    ocr_text: Optional[str] = None,
) -> Document:
    doc = Document(
        id=uuid.uuid4(),
        title="scan-0042.pdf",
        original_filename="scan-0042.pdf",
        file_path="scan-0042.pdf",
        file_size=1,
        mime_type="application/pdf",
        checksum=uuid.uuid4().hex,
        ocr_text=ocr_text,
        owner_id=owner.id,
        processing_status=status.value,
    )
    db_session.add(doc)
    db_session.commit()
    return doc


@pytest.fixture
def events(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """The notification service, stubbed. Every status event lands in its calls."""
    from app.processing import runner

    stub = MagicMock()
    monkeypatch.setattr(runner, "notification_service", stub)
    return stub


def transitions(events: MagicMock) -> List[Tuple[str, str]]:
    """Every (from, to) a status event reported, in order."""
    calls = events.notify_status_changed_sync.call_args_list
    return [(call.args[1], call.args[2]) for call in calls]


@pytest.fixture
def queue() -> List[Tuple[str, Stage]]:
    """What the runner asked to be enqueued next."""
    return []


@pytest.fixture
def enqueue(queue: List[Tuple[str, Stage]]):
    return lambda document_id, stage: queue.append((document_id, stage))


@pytest.fixture
def read_file(monkeypatch: pytest.MonkeyPatch):
    """Point OCR at a canned read, so no file, page cache or model server is needed."""
    from app.processing import runner

    monkeypatch.setattr(runner, "settings", settings)

    def _read(text: Optional[str]):
        return patch.multiple(
            "app.services.ocr_service.OCRService",
            extract_text=MagicMock(return_value=text),
            detect_language=MagicMock(return_value="en"),
        )

    return _read


class FakeStorage:
    """Where a document's file would be, without a storage root to create."""

    def get_file_path(self, relative_path: str) -> Path:
        return Path("/tmp") / relative_path


@pytest.fixture(autouse=True)
def no_infrastructure(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep the runner off Redis and off the configured storage root."""
    monkeypatch.setattr("app.services.page_cache.get_page_cache", lambda: None)
    monkeypatch.setattr("app.services.storage_service.StorageService", FakeStorage)
    yield


@pytest.fixture
def session_factory(db_session):
    """A session of the runner's own, on the fixture's connection.

    The runner opens and closes a session per stage, as it does under Celery, so it
    must not be handed the test's — closing that would detach every object the test
    still wants to read. Sharing the connection keeps both inside the rolled-back
    transaction and lets the test see what the runner committed.
    """
    from sqlalchemy.orm import Session

    connection = db_session.connection()
    return lambda: Session(bind=connection, join_transaction_mode="create_savepoint")


def run(document: Document, stage: Stage, session_factory, enqueue, models: Models, **options):
    return run_stage(
        str(document.id),
        stage,
        enqueue=enqueue,
        session_factory=session_factory,
        models=models,
        **options,
    )


def BOTH_ON() -> Models:
    """Every capability on. The assistant is scripted for extraction and, because the
    archive may already hold tags, for the reconciliation pass that follows it."""
    return Models(
        embedder=FakeEmbedder(dimension=DIMENSION),
        assistant=ScriptedChatModel(METADATA_REPLY, RECONCILE_REPLY),
    )


class TestOcrStage:
    """Reading a document: the write, the two transitions it reports, and what follows."""

    def test_writes_the_text_and_the_status_it_reached(
        self, db_session, session_factory, owner, events, enqueue, read_file
    ) -> None:
        doc = make_document(db_session, owner)

        with read_file("Two tons of Borrowdale slate."):
            result = run(doc, Stage.OCR, session_factory, enqueue, BOTH_ON())

        db_session.refresh(doc)
        assert doc.processing_status == ProcessingStatus.OCR_COMPLETE
        assert doc.ocr_text == "Two tons of Borrowdale slate."
        assert doc.ocr_language == "en"
        assert result["status"] == "success"

    def test_reports_the_state_it_read_from_the_row_not_a_literal(
        self, db_session, session_factory, owner, events, enqueue, read_file
    ) -> None:
        """A document retried from `failed` came from `failed`, whatever `pending` used
        to be hard-coded at the call site."""
        doc = make_document(db_session, owner, status=ProcessingStatus.FAILED)

        with read_file("Some text"):
            run(doc, Stage.OCR, session_factory, enqueue, BOTH_ON())

        assert transitions(events) == [
            ("failed", "processing"),
            ("processing", "ocr_complete"),
        ]

    def test_a_document_nothing_could_be_read_from_stops_at_ocr_failed(
        self, db_session, session_factory, owner, events, enqueue, read_file, queue
    ) -> None:
        doc = make_document(db_session, owner)

        with read_file(""):
            run(doc, Stage.OCR, session_factory, enqueue, BOTH_ON())

        db_session.refresh(doc)
        assert doc.processing_status == ProcessingStatus.OCR_FAILED
        assert doc.processing_error == "No text could be extracted from document"
        assert transitions(events)[-1] == ("processing", "ocr_failed")
        assert queue == []

    def test_reports_the_documents_page_count_not_just_what_this_read_counted(
        self, db_session, session_factory, owner, events, enqueue, read_file
    ) -> None:
        """Re-reading something that is not a PDF leaves the stored count standing."""
        doc = make_document(db_session, owner)
        doc.page_count = 7
        db_session.commit()

        with read_file("Some text"):
            result = run(doc, Stage.OCR, session_factory, enqueue, BOTH_ON())

        assert result["page_count"] == 7

    def test_chains_onto_embeddings_when_there_is_an_embedder(
        self, db_session, session_factory, owner, events, enqueue, read_file, queue
    ) -> None:
        doc = make_document(db_session, owner)

        with read_file("Some text"):
            run(doc, Stage.OCR, session_factory, enqueue, BOTH_ON())

        assert queue == [(str(doc.id), Stage.EMBEDDING)]

    def test_chains_straight_to_metadata_when_there_is_no_embedder(
        self, db_session, session_factory, owner, events, enqueue, read_file, queue
    ) -> None:
        """And the event says the document came from `ocr_complete`, which is where it is."""
        doc = make_document(db_session, owner)
        models = Models(assistant=ScriptedChatModel(METADATA_REPLY))

        with read_file("Some text"):
            run(doc, Stage.OCR, session_factory, enqueue, models)

        assert queue == [(str(doc.id), Stage.METADATA)]
        assert transitions(events)[-1] == ("processing", "ocr_complete")

    def test_stops_when_neither_capability_is_on(
        self, db_session, session_factory, owner, events, enqueue, read_file, queue
    ) -> None:
        doc = make_document(db_session, owner)

        with read_file("Some text"):
            run(doc, Stage.OCR, session_factory, enqueue, Models())

        assert queue == []

    def test_a_stage_that_raises_leaves_the_document_failed_and_says_so(
        self, db_session, session_factory, owner, events, enqueue, queue
    ) -> None:
        doc = make_document(db_session, owner)

        with patch(
            "app.services.ocr_service.OCRService.extract_text",
            side_effect=RuntimeError("the page renderer fell over"),
        ):
            result = run(doc, Stage.OCR, session_factory, enqueue, BOTH_ON())

        db_session.refresh(doc)
        assert doc.processing_status == ProcessingStatus.FAILED
        assert doc.processing_error == "the page renderer fell over"
        assert transitions(events)[-1] == ("processing", "failed")
        assert result["status"] == "error"
        assert queue == []


class TestEmbeddingStage:
    """Making a document searchable: the chunks written and the next stage."""

    def test_replaces_the_documents_chunks_and_moves_to_embedding_complete(
        self, db_session, session_factory, owner, events, enqueue, queue
    ) -> None:
        doc = make_document(
            db_session, owner, status=ProcessingStatus.OCR_COMPLETE, ocr_text="x" * 120
        )
        db_session.add(
            DocumentEmbedding(
                document_id=doc.id, chunk_index=0, chunk_text="stale",
                embedding=[0.5] * DIMENSION, embedding_model="old",
            )
        )
        db_session.commit()

        result = run(doc, Stage.EMBEDDING, session_factory, enqueue, BOTH_ON())

        db_session.refresh(doc)
        chunks = (
            db_session.query(DocumentEmbedding)
            .filter(DocumentEmbedding.document_id == doc.id)
            .order_by(DocumentEmbedding.chunk_index)
            .all()
        )
        assert doc.processing_status == ProcessingStatus.EMBEDDING_COMPLETE
        assert [chunk.embedding_model for chunk in chunks] == ["fake-embedder"] * len(chunks)
        assert "stale" not in [chunk.chunk_text for chunk in chunks]
        assert result["embedding_count"] == len(chunks)
        assert transitions(events) == [("ocr_complete", "embedding_complete")]
        assert queue == [(str(doc.id), Stage.METADATA)]

    def test_stops_after_embedding_when_there_is_no_assistant(
        self, db_session, session_factory, owner, events, enqueue, queue
    ) -> None:
        doc = make_document(
            db_session, owner, status=ProcessingStatus.OCR_COMPLETE, ocr_text="Some text"
        )

        models = Models(embedder=FakeEmbedder(DIMENSION))
        run(doc, Stage.EMBEDDING, session_factory, enqueue, models)

        assert queue == []

    def test_a_document_with_no_text_changes_nothing_and_says_nothing(
        self, db_session, session_factory, owner, events, enqueue, queue
    ) -> None:
        """No status change means no status event, and nothing to hand on."""
        doc = make_document(db_session, owner, status=ProcessingStatus.OCR_COMPLETE)

        result = run(doc, Stage.EMBEDDING, session_factory, enqueue, BOTH_ON())

        db_session.refresh(doc)
        assert doc.processing_status == ProcessingStatus.OCR_COMPLETE
        assert result["status"] == "skipped"
        assert transitions(events) == []
        assert queue == []

    def test_an_embedder_that_fails_leaves_the_document_failed(
        self, db_session, session_factory, owner, events, enqueue
    ) -> None:
        doc = make_document(
            db_session, owner, status=ProcessingStatus.OCR_COMPLETE, ocr_text="Some text"
        )

        error = RuntimeError("embedder unreachable")
        models = Models(embedder=FailingEmbedder(error, DIMENSION))
        run(doc, Stage.EMBEDDING, session_factory, enqueue, models)

        db_session.refresh(doc)
        assert doc.processing_status == ProcessingStatus.FAILED
        assert doc.processing_error == "Embedding generation failed: embedder unreachable"
        assert transitions(events) == [("ocr_complete", "failed")]

    def test_with_no_embedder_configured_the_stage_is_skipped_untouched(
        self, db_session, session_factory, owner, events, enqueue
    ) -> None:
        doc = make_document(
            db_session, owner, status=ProcessingStatus.OCR_COMPLETE, ocr_text="Some text"
        )

        result = run(doc, Stage.EMBEDDING, session_factory, enqueue, Models())

        db_session.refresh(doc)
        assert result == {
            "status": "skipped",
            "document_id": str(doc.id),
            "message": "Embeddings disabled",
        }
        assert doc.processing_status == ProcessingStatus.OCR_COMPLETE


class TestMetadataStage:
    """Describing a document: the fields, the tags, and the failure that used to lie."""

    def test_writes_the_extracted_fields_and_lands_at_llm_complete(
        self, db_session, session_factory, owner, events, enqueue, queue
    ) -> None:
        doc = make_document(
            db_session, owner, status=ProcessingStatus.EMBEDDING_COMPLETE, ocr_text="Some text"
        )

        result = run(doc, Stage.METADATA, session_factory, enqueue, BOTH_ON())

        db_session.refresh(doc)
        assert doc.processing_status == ProcessingStatus.LLM_COMPLETE
        assert doc.extracted_title == "Slate invoice"
        assert doc.extracted_correspondent == "Borrowdale Quarry"
        assert doc.extracted_date.isoformat() == "1897-04-02"
        assert doc.title == "Slate invoice"  # The title was still the filename
        assert result["tags_added"] == 2
        assert transitions(events) == [("embedding_complete", "llm_complete")]
        assert queue == []

    def test_replaces_the_documents_tags_with_the_ones_suggested(
        self, db_session, session_factory, owner, events, enqueue
    ) -> None:
        doc = make_document(
            db_session, owner, status=ProcessingStatus.EMBEDDING_COMPLETE, ocr_text="Some text"
        )
        stale = Tag(id=uuid.uuid4(), name="stale", created_by=owner.id)
        db_session.add(stale)
        doc.tags = [stale]
        db_session.commit()

        run(doc, Stage.METADATA, session_factory, enqueue, BOTH_ON())

        db_session.refresh(doc)
        assert sorted(tag.name for tag in doc.tags) == ["invoice", "quarry"]

    def test_reuses_a_tag_the_archive_already_has(
        self, db_session, session_factory, owner, events, enqueue
    ) -> None:
        """Tags are global and named uniquely: describing a document coins no duplicate."""
        doc = make_document(
            db_session, owner, status=ProcessingStatus.EMBEDDING_COMPLETE, ocr_text="Some text"
        )
        existing = Tag(id=uuid.uuid4(), name="invoice", color="#abcdef", created_by=owner.id)
        db_session.add(existing)
        db_session.commit()

        run(doc, Stage.METADATA, session_factory, enqueue, BOTH_ON())

        assert db_session.query(Tag).filter(Tag.name == "invoice").count() == 1
        db_session.refresh(existing)
        assert existing.color == "#abcdef"

    def test_suggesting_no_tags_leaves_the_ones_the_document_has(
        self, db_session, session_factory, owner, events, enqueue
    ) -> None:
        doc = make_document(
            db_session, owner, status=ProcessingStatus.EMBEDDING_COMPLETE, ocr_text="Some text"
        )
        kept = Tag(id=uuid.uuid4(), name="kept", created_by=owner.id)
        db_session.add(kept)
        doc.tags = [kept]
        db_session.commit()
        models = Models(assistant=ScriptedChatModel('{"title": "Invoice", "suggested_tags": []}'))

        result = run(doc, Stage.METADATA, session_factory, enqueue, models)

        db_session.refresh(doc)
        assert [tag.name for tag in doc.tags] == ["kept"]
        assert result["tags_added"] == 0

    def test_counts_the_tags_that_landed_not_the_ones_suggested(
        self, db_session, session_factory, owner, events, enqueue
    ) -> None:
        """A suggestion that cleans away to nothing, or repeats one already taken, was
        never a tag, so it is neither written nor counted."""
        doc = make_document(
            db_session, owner, status=ProcessingStatus.EMBEDDING_COMPLETE, ocr_text="Some text"
        )
        reply = '{"title": "Invoice", "suggested_tags": ["invoice", "   ", "INVOICE"]}'
        models = Models(assistant=ScriptedChatModel(reply, RECONCILE_REPLY))

        result = run(doc, Stage.METADATA, session_factory, enqueue, models)

        db_session.refresh(doc)
        assert [tag.name for tag in doc.tags] == ["invoice"]
        assert result["tags_added"] == 1

    def test_a_failure_leaves_the_document_failed_with_the_error_recorded(
        self, db_session, session_factory, owner, events, enqueue
    ) -> None:
        """It used to record the error and leave the status reading `embedding_complete`."""
        doc = make_document(
            db_session, owner, status=ProcessingStatus.EMBEDDING_COMPLETE, ocr_text="Some text"
        )

        with patch(
            "app.services.assistant_service.AssistantService.extract_metadata",
            side_effect=RuntimeError("the assistant fell over"),
        ):
            result = run(doc, Stage.METADATA, session_factory, enqueue, BOTH_ON())

        db_session.refresh(doc)
        assert doc.processing_status == ProcessingStatus.FAILED
        assert doc.processing_error == "Metadata extraction failed: the assistant fell over"
        assert transitions(events) == [("embedding_complete", "failed")]
        assert result["status"] == "error"

    def test_tells_clients_the_document_changed(
        self, db_session, session_factory, owner, events, enqueue
    ) -> None:
        doc = make_document(
            db_session, owner, status=ProcessingStatus.EMBEDDING_COMPLETE, ocr_text="Some text"
        )

        run(doc, Stage.METADATA, session_factory, enqueue, BOTH_ON())

        events.notify_document_updated_sync.assert_called_once_with(doc.id, owner.id)


class TestHandingOn:
    """What follows a stage is off to a broker; it cannot unwrite what the stage did."""

    def test_a_queue_that_will_not_take_the_next_stage_leaves_the_status_it_reached(
        self, db_session, session_factory, owner, events, read_file
    ) -> None:
        """The document really is `ocr_complete`; saying `failed` would be a lie, and
        the event would report a transition no stage made."""
        doc = make_document(db_session, owner)

        def refuse(document_id: str, stage: Stage) -> None:
            raise RuntimeError("broker unreachable")

        with read_file("Some text"):
            result = run(doc, Stage.OCR, session_factory, refuse, BOTH_ON())

        db_session.refresh(doc)
        assert doc.processing_status == ProcessingStatus.OCR_COMPLETE
        assert result["status"] == "success"
        assert transitions(events) == [("pending", "processing"), ("processing", "ocr_complete")]


class TestUnknownDocument:
    def test_a_document_that_is_not_there_is_an_error_not_a_crash(
        self, db_session, session_factory, events, enqueue
    ) -> None:
        result = run_stage(
            str(uuid.uuid4()),
            Stage.EMBEDDING,
            enqueue=enqueue,
            session_factory=session_factory,
            models=BOTH_ON(),
        )

        assert result["status"] == "error"
        assert result["message"] == "Document not found"

    def test_something_that_is_not_an_id_is_an_error_not_a_crash(
        self, db_session, session_factory, events, enqueue
    ) -> None:
        result = run_stage(
            "not-a-uuid",
            Stage.OCR,
            enqueue=enqueue,
            session_factory=session_factory,
            models=BOTH_ON(),
        )

        assert result["status"] == "error"


class Retried(Exception):
    """What a retrying caller raises: Celery's `self.retry` in every way that matters here."""

    def __init__(self, error: BaseException, countdown: int) -> None:
        super().__init__(f"retrying in {countdown}s after {error}")
        self.error = error
        self.countdown = countdown


@pytest.fixture
def retry():
    """A caller that retries, as the Celery adapter does: it raises rather than returning."""

    def _retry(error: BaseException, countdown: int):
        raise Retried(error, countdown)

    return _retry


class TestRetryingAModelFailure:
    """A stage that failed on a model comes round again; anything else is terminal.

    What the Document reads between attempts is the point of most of these: nothing is
    written, so it keeps the status it already had. See ADR 0007.
    """

    def test_a_model_failure_is_handed_back_to_the_caller_to_retry(
        self, db_session, session_factory, owner, events, enqueue, queue, retry
    ) -> None:
        doc = make_document(
            db_session, owner, status=ProcessingStatus.OCR_COMPLETE, ocr_text="Some text"
        )
        models = Models(embedder=FailingEmbedder(ModelError("connection refused"), DIMENSION))

        with pytest.raises(Retried) as raised:
            run(doc, Stage.EMBEDDING, session_factory, enqueue, models, retry=retry)

        assert raised.value.countdown == 10
        assert isinstance(raised.value.error, ModelError)

    def test_a_document_waiting_on_a_retry_keeps_the_status_it_had(
        self, db_session, session_factory, owner, events, enqueue, queue, retry
    ) -> None:
        doc = make_document(
            db_session, owner, status=ProcessingStatus.OCR_COMPLETE, ocr_text="Some text"
        )
        models = Models(embedder=FailingEmbedder(ModelError("connection refused"), DIMENSION))

        with pytest.raises(Retried):
            run(doc, Stage.EMBEDDING, session_factory, enqueue, models, retry=retry)

        db_session.refresh(doc)
        assert doc.processing_status == ProcessingStatus.OCR_COMPLETE
        assert doc.processing_error is None
        assert transitions(events) == []
        assert queue == []

    def test_a_document_read_by_a_model_that_went_away_waits_at_processing(
        self, db_session, session_factory, owner, events, enqueue, queue, retry, read_file
    ) -> None:
        doc = make_document(db_session, owner)

        with patch.multiple(
            "app.services.ocr_service.OCRService",
            extract_text=MagicMock(side_effect=ModelError("no page could be read")),
        ):
            with pytest.raises(Retried):
                run(doc, Stage.OCR, session_factory, enqueue, BOTH_ON(), retry=retry)

        db_session.refresh(doc)
        assert doc.processing_status == ProcessingStatus.PROCESSING
        assert transitions(events) == [("pending", "processing")]

    def test_each_attempt_waits_longer_than_the_one_before(
        self, db_session, session_factory, owner, events, enqueue, retry
    ) -> None:
        doc = make_document(
            db_session, owner, status=ProcessingStatus.OCR_COMPLETE, ocr_text="Some text"
        )
        embedder = FailingEmbedder(ModelError("connection refused"), DIMENSION)
        models = Models(embedder=embedder)

        waits = []
        for attempt in range(len(RETRY_DELAYS)):
            with pytest.raises(Retried) as raised:
                run(
                    doc, Stage.EMBEDDING, session_factory, enqueue, models,
                    retry=retry, attempt=attempt,
                )
            waits.append(raised.value.countdown)

        assert waits == list(RETRY_DELAYS)
        # Every attempt really ran the stage, rather than the schedule being walked
        # by a runner that had already given up on reaching the model.
        assert embedder.calls == len(RETRY_DELAYS)

    def test_a_schedule_that_is_spent_leaves_the_document_failed(
        self, db_session, session_factory, owner, events, enqueue, retry
    ) -> None:
        doc = make_document(
            db_session, owner, status=ProcessingStatus.OCR_COMPLETE, ocr_text="Some text"
        )
        models = Models(embedder=FailingEmbedder(ModelError("connection refused"), DIMENSION))

        result = run(
            doc, Stage.EMBEDDING, session_factory, enqueue, models,
            retry=retry, attempt=len(RETRY_DELAYS),
        )

        db_session.refresh(doc)
        assert result["status"] == "error"
        assert doc.processing_status == ProcessingStatus.FAILED
        assert doc.processing_error == "Embedding generation failed: connection refused"
        assert transitions(events) == [("ocr_complete", "failed")]

    def test_a_failure_that_is_not_a_model_failure_is_terminal_on_the_first_try(
        self, db_session, session_factory, owner, events, enqueue, retry
    ) -> None:
        doc = make_document(
            db_session, owner, status=ProcessingStatus.OCR_COMPLETE, ocr_text="Some text"
        )
        models = Models(embedder=FailingEmbedder(RuntimeError("a bad row"), DIMENSION))

        result = run(doc, Stage.EMBEDDING, session_factory, enqueue, models, retry=retry)

        db_session.refresh(doc)
        assert result["status"] == "error"
        assert doc.processing_status == ProcessingStatus.FAILED
        assert transitions(events) == [("ocr_complete", "failed")]

    def test_describing_a_document_retries_on_a_model_too(
        self, db_session, session_factory, owner, events, enqueue, retry
    ) -> None:
        doc = make_document(
            db_session,
            owner,
            status=ProcessingStatus.EMBEDDING_COMPLETE,
            ocr_text="Some text",
        )
        models = Models(assistant=ScriptedChatModel(ModelError("rate limited")))

        with pytest.raises(Retried) as raised:
            run(doc, Stage.METADATA, session_factory, enqueue, models, retry=retry)

        db_session.refresh(doc)
        assert raised.value.countdown == RETRY_DELAYS[0]
        assert doc.processing_status == ProcessingStatus.EMBEDDING_COMPLETE

    def test_a_caller_that_cannot_retry_leaves_every_failure_terminal(
        self, db_session, session_factory, owner, events, enqueue
    ) -> None:
        """The runner never retries on its own: running it again is the caller's to do."""
        doc = make_document(
            db_session, owner, status=ProcessingStatus.OCR_COMPLETE, ocr_text="Some text"
        )
        models = Models(embedder=FailingEmbedder(ModelError("connection refused"), DIMENSION))

        result = run(doc, Stage.EMBEDDING, session_factory, enqueue, models)

        db_session.refresh(doc)
        assert result["status"] == "error"
        assert doc.processing_status == ProcessingStatus.FAILED
