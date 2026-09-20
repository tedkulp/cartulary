"""Behavior tests for the single Document intake seam."""

import uuid
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PIL import Image

from app.core.exceptions import DuplicateError, InvalidDocumentError
from app.models.user import User
from app.services.document_intake import DocumentIntakeService
from app.services.notification_service import NotificationService
from app.services.storage_service import StorageService, StoredFile


def _session(existing=None) -> MagicMock:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = existing
    return db


def test_intake_stores_commits_queues_and_announces_document() -> None:
    owner_id = uuid.uuid4()
    uploader_id = uuid.uuid4()
    storage = MagicMock()
    storage.save_bytes.return_value = StoredFile(
        relative_path="ab/document/invoice.pdf",
        filename="invoice.pdf",
        mime_type="application/pdf",
        size=12,
    )
    enqueue = MagicMock()
    notify = MagicMock()
    db = _session()

    document = DocumentIntakeService(db, storage, enqueue, notify).intake(
        content=b"invoice pdf",
        filename="invoice.pdf",
        owner_id=owner_id,
        uploader_id=uploader_id,
        title="  September invoice  ",
    )

    assert document.title == "September invoice"
    assert document.original_filename == "invoice.pdf"
    assert document.file_path == "ab/document/invoice.pdf"
    assert document.file_size == 12
    assert document.mime_type == "application/pdf"
    assert document.owner_id == owner_id
    assert document.uploaded_by == uploader_id
    db.add.assert_called_once_with(document)
    db.commit.assert_called_once()
    enqueue.assert_called_once_with(str(document.id))
    notify.assert_called_once_with(document.id, owner_id, uploader_id)


def test_duplicate_reports_existing_document_without_side_effects() -> None:
    existing_id = uuid.uuid4()
    storage = MagicMock()
    enqueue = MagicMock()
    notify = MagicMock()
    service = DocumentIntakeService(
        _session(SimpleNamespace(id=existing_id)), storage, enqueue, notify
    )

    with pytest.raises(DuplicateError) as raised:
        service.intake(
            content=b"same bytes",
            filename="copy.pdf",
            owner_id=uuid.uuid4(),
        )

    assert raised.value.detail == {"document_id": str(existing_id)}
    storage.save_bytes.assert_not_called()
    enqueue.assert_not_called()
    notify.assert_not_called()


def test_same_bytes_are_allowed_for_different_owners(db_session, tmp_path) -> None:
    first_owner = User(email=f"{uuid.uuid4()}@example.com")
    second_owner = User(email=f"{uuid.uuid4()}@example.com")
    db_session.add_all([first_owner, second_owner])
    db_session.commit()
    service = DocumentIntakeService(
        db_session, StorageService(str(tmp_path)), MagicMock(), MagicMock()
    )

    first = service.intake(
        content=b"same report", filename="report.pdf", owner_id=first_owner.id
    )
    second = service.intake(
        content=b"same report", filename="report.pdf", owner_id=second_owner.id
    )

    assert first.id != second.id


@pytest.mark.parametrize(
    ("content", "filename"),
    [
        (b"", "empty.pdf"),
        (b"content", "notes.txt"),
        (b"content", "../"),
        (b"content", "..\\"),
    ],
)
def test_invalid_source_is_rejected_before_deduplication(
    content: bytes, filename: str
) -> None:
    db = _session()
    storage = MagicMock()
    service = DocumentIntakeService(db, storage, MagicMock(), MagicMock())

    with pytest.raises(InvalidDocumentError):
        service.intake(content=content, filename=filename, owner_id=uuid.uuid4())

    db.query.assert_not_called()
    storage.save_bytes.assert_not_called()


def test_database_failure_rolls_back_and_removes_stored_file() -> None:
    storage = MagicMock()
    storage.save_bytes.return_value = StoredFile(
        relative_path="ab/document/report.pdf",
        filename="report.pdf",
        mime_type="application/pdf",
        size=6,
    )
    db = _session()
    db.commit.side_effect = RuntimeError("database unavailable")
    service = DocumentIntakeService(db, storage, MagicMock(), MagicMock())

    with pytest.raises(RuntimeError, match="database unavailable"):
        service.intake(
            content=b"report",
            filename="report.pdf",
            owner_id=uuid.uuid4(),
        )

    db.rollback.assert_called_once()
    storage.delete_file.assert_called_once_with("ab/document/report.pdf")


def test_queue_failure_returns_created_document_marked_failed() -> None:
    storage = MagicMock()
    storage.save_bytes.return_value = StoredFile(
        relative_path="ab/document/report.pdf",
        filename="report.pdf",
        mime_type="application/pdf",
        size=6,
    )
    enqueue = MagicMock(side_effect=RuntimeError("broker unavailable"))
    notify = MagicMock()
    db = _session()
    service = DocumentIntakeService(db, storage, enqueue, notify)
    owner_id = uuid.uuid4()

    document = service.intake(
        content=b"report", filename="report.pdf", owner_id=owner_id
    )

    assert document.processing_status == "failed"
    assert document.processing_error == "Processing could not be queued: broker unavailable"
    assert db.commit.call_count == 2
    notify.assert_called_once_with(document.id, owner_id, None)


def test_failed_status_commit_does_not_turn_created_document_into_failed_intake() -> None:
    storage = MagicMock()
    storage.save_bytes.return_value = StoredFile(
        relative_path="ab/document/report.pdf",
        filename="report.pdf",
        mime_type="application/pdf",
        size=6,
    )
    db = _session()
    db.commit.side_effect = [None, RuntimeError("database unavailable")]
    notify = MagicMock()

    document = DocumentIntakeService(
        db,
        storage,
        MagicMock(side_effect=RuntimeError("broker unavailable")),
        notify,
    ).intake(
        content=b"report",
        filename="report.pdf",
        owner_id=uuid.uuid4(),
    )

    assert document.processing_status == "failed"
    db.rollback.assert_called_once()
    notify.assert_called_once()


def test_title_longer_than_database_column_is_rejected() -> None:
    service = DocumentIntakeService(_session(), MagicMock(), MagicMock(), MagicMock())

    with pytest.raises(InvalidDocumentError, match="500 characters"):
        service.intake(
            content=b"report",
            filename="report.pdf",
            owner_id=uuid.uuid4(),
            title="x" * 501,
        )


def test_malformed_image_is_rejected_without_leaving_a_file(tmp_path) -> None:
    service = DocumentIntakeService(
        _session(), StorageService(str(tmp_path)), MagicMock(), MagicMock()
    )

    with pytest.raises(InvalidDocumentError, match="Image content is invalid"):
        service.intake(
            content=b"not a png",
            filename="scan.png",
            owner_id=uuid.uuid4(),
        )

    assert list(tmp_path.rglob("*")) == []


def test_mislabeled_image_is_rejected_without_leaving_a_file(tmp_path) -> None:
    content = BytesIO()
    Image.new("RGB", (1, 1), "white").save(content, "JPEG")
    service = DocumentIntakeService(
        _session(), StorageService(str(tmp_path)), MagicMock(), MagicMock()
    )

    with pytest.raises(InvalidDocumentError, match="does not match"):
        service.intake(
            content=content.getvalue(),
            filename="scan.png",
            owner_id=uuid.uuid4(),
        )

    assert list(tmp_path.rglob("*")) == []


def test_storage_failure_removes_partial_document_directory(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_write_bytes = Path.write_bytes

    def fail_after_partial_write(path: Path, content: bytes) -> int:
        original_write_bytes(path, content[:1])
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_bytes", fail_after_partial_write)
    db = _session()
    service = DocumentIntakeService(
        db, StorageService(str(tmp_path)), MagicMock(), MagicMock()
    )

    with pytest.raises(OSError, match="disk full"):
        service.intake(
            content=b"report",
            filename="report.pdf",
            owner_id=uuid.uuid4(),
        )

    assert list(tmp_path.rglob("*")) == []
    db.rollback.assert_called_once()


def test_valid_image_is_retained_when_pdf_conversion_fails(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    content = BytesIO()
    Image.new("RGB", (1, 1), "white").save(content, "PNG")
    monkeypatch.setattr(
        "img2pdf.convert", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError())
    )
    service = DocumentIntakeService(
        _session(), StorageService(str(tmp_path)), MagicMock(), MagicMock()
    )

    document = service.intake(
        content=content.getvalue(),
        filename="scan.png",
        owner_id=uuid.uuid4(),
    )

    assert document.file_path.endswith("/scan.png")
    assert document.mime_type == "image/png"
    assert (tmp_path / document.file_path).is_file()


def test_valid_image_is_normally_stored_as_pdf(tmp_path) -> None:
    content = BytesIO()
    Image.new("RGB", (100, 100), "white").save(content, "PNG")
    service = DocumentIntakeService(
        _session(), StorageService(str(tmp_path)), MagicMock(), MagicMock()
    )

    document = service.intake(
        content=content.getvalue(),
        filename="scan.png",
        owner_id=uuid.uuid4(),
    )

    assert document.file_path.endswith("/scan.pdf")
    assert document.mime_type == "application/pdf"
    assert (tmp_path / document.file_path).is_file()


def test_notification_failure_does_not_fail_intake() -> None:
    storage = MagicMock()
    storage.save_bytes.return_value = StoredFile(
        relative_path="ab/document/report.pdf",
        filename="report.pdf",
        mime_type="application/pdf",
        size=6,
    )
    notify = MagicMock(side_effect=RuntimeError("redis unavailable"))

    document = DocumentIntakeService(
        _session(), storage, MagicMock(), notify
    ).intake(
        content=b"report",
        filename="report.pdf",
        owner_id=uuid.uuid4(),
    )

    assert document.processing_status == "pending"


def test_creation_event_distinguishes_owner_from_uploader() -> None:
    owner_id = uuid.uuid4()
    uploader_id = uuid.uuid4()
    notifications = NotificationService()
    notifications.publish_event_sync = MagicMock()

    notifications.notify_document_created_sync(
        uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"), owner_id, uploader_id
    )

    notifications.publish_event_sync.assert_called_once_with(
        "document.created",
        {
            "document_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "owner_id": str(owner_id),
            "user_id": str(uploader_id),
        },
    )
