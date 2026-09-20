"""Thin tests for source adapters around the Document intake seam."""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.core.exceptions import DuplicateError
from app.workers.directory_watcher import _process_file
from app.workers.imap_watcher import IMAPMailboxHandler


def _source(**overrides):
    values = {
        "owner_id": uuid.uuid4(),
        "move_after_import": False,
        "move_to_path": None,
        "delete_after_import": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_directory_adapter_hands_bytes_to_intake_then_disposes_source(tmp_path) -> None:
    path = tmp_path / "report.pdf"
    path.write_bytes(b"report")
    source = _source(delete_after_import=True)
    intake = MagicMock()
    intake.intake.return_value = SimpleNamespace(id=uuid.uuid4())

    handled = _process_file(path, source, MagicMock(), intake)

    assert handled is True
    intake.intake.assert_called_once_with(
        content=b"report", filename="report.pdf", owner_id=source.owner_id
    )
    assert not path.exists()


def test_directory_adapter_disposes_duplicate_source(tmp_path) -> None:
    path = tmp_path / "report.pdf"
    path.write_bytes(b"report")
    source = _source(delete_after_import=True)
    intake = MagicMock()
    intake.intake.side_effect = DuplicateError(
        detail={"document_id": str(uuid.uuid4())}
    )

    assert _process_file(path, source, MagicMock(), intake) is True
    assert not path.exists()


def test_imap_adapter_hands_attachment_to_intake() -> None:
    source = _source()
    intake = MagicMock()
    intake.intake.return_value = SimpleNamespace(id=uuid.uuid4())
    handler = IMAPMailboxHandler(source, MagicMock(), intake)

    handler.import_attachment("report.pdf", b"report")

    intake.intake.assert_called_once_with(
        content=b"report", filename="report.pdf", owner_id=source.owner_id
    )


def test_imap_adapter_treats_duplicate_as_handled() -> None:
    intake = MagicMock()
    intake.intake.side_effect = DuplicateError(
        detail={"document_id": str(uuid.uuid4())}
    )
    handler = IMAPMailboxHandler(_source(), MagicMock(), intake)

    handler.import_attachment("report.pdf", b"report")
