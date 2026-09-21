"""The durable record of an attachment an import source will never take in.

Against the real PostgreSQL, because the unique index is what makes recording
the same failure twice harmless, and a mocked Session cannot say whether the
second row landed. See ADR 0005 and ADR 0011.
"""

import uuid

from app.models.import_failure import ImportFailure
from app.models.import_source import ImportSource, ImportSourceStatus, ImportSourceType
from app.models.user import User
from app.services.import_failure_service import ImportFailureService

MESSAGE_KEY = "<scan-2026-09-21@example.test>"
CHECKSUM = "c" * 64


def make_source(db_session) -> ImportSource:
    owner = User(email=f"{uuid.uuid4()}@example.com")
    db_session.add(owner)
    db_session.commit()
    source = ImportSource(
        name="Scanner mailbox",
        source_type=ImportSourceType.IMAP,
        status=ImportSourceStatus.ACTIVE,
        owner_id=owner.id,
    )
    db_session.add(source)
    db_session.commit()
    return source


def test_a_terminal_failure_is_written_down(db_session) -> None:
    source = make_source(db_session)
    service = ImportFailureService(db_session)

    recorded = service.record(
        import_source_id=source.id,
        message_key=MESSAGE_KEY,
        filename="broken.pdf",
        checksum=CHECKSUM,
        error="File type not supported",
    )

    assert recorded is not None
    stored = db_session.query(ImportFailure).filter(
        ImportFailure.import_source_id == source.id
    ).one()
    assert stored.filename == "broken.pdf"
    assert stored.error == "File type not supported"


def test_recording_the_same_failure_twice_leaves_one_record(db_session) -> None:
    source = make_source(db_session)
    service = ImportFailureService(db_session)
    arguments = dict(
        import_source_id=source.id,
        message_key=MESSAGE_KEY,
        filename="broken.pdf",
        checksum=CHECKSUM,
        error="File type not supported",
    )

    first = service.record(**arguments)
    second = service.record(**arguments)

    assert first is not None and second is not None
    assert first.id == second.id
    assert db_session.query(ImportFailure).filter(
        ImportFailure.import_source_id == source.id
    ).count() == 1


def test_a_recorded_failure_is_recalled_by_message(db_session) -> None:
    source = make_source(db_session)
    service = ImportFailureService(db_session)
    service.record(
        import_source_id=source.id,
        message_key=MESSAGE_KEY,
        filename="broken.pdf",
        checksum=CHECKSUM,
        error="File type not supported",
    )

    assert service.recorded_checksums(
        import_source_id=source.id, message_key=MESSAGE_KEY
    ) == {CHECKSUM}
    assert service.recorded_checksums(
        import_source_id=source.id, message_key="<another@example.test>"
    ) == set()


def test_the_same_attachment_on_another_message_is_its_own_record(db_session) -> None:
    source = make_source(db_session)
    service = ImportFailureService(db_session)
    for key in (MESSAGE_KEY, "<resent@example.test>"):
        service.record(
            import_source_id=source.id,
            message_key=key,
            filename="broken.pdf",
            checksum=CHECKSUM,
            error="File type not supported",
        )

    assert db_session.query(ImportFailure).filter(
        ImportFailure.import_source_id == source.id
    ).count() == 2


def test_an_over_long_message_key_is_truncated_consistently(db_session) -> None:
    source = make_source(db_session)
    service = ImportFailureService(db_session)
    key = "<" + "x" * 900 + "@example.test>"

    service.record(
        import_source_id=source.id,
        message_key=key,
        filename="broken.pdf",
        checksum=CHECKSUM,
        error="File type not supported",
    )

    assert service.recorded_checksums(
        import_source_id=source.id, message_key=key
    ) == {CHECKSUM}
