"""When an IMAP message may be marked read, and what happens when it may not.

The rule under test is ADR 0011: a message is completed only once every
attachment on it has settled — imported, already held by the archive, or
written down as a terminal failure. Anything else leaves the message where it
is, because the mailbox is the only record that the attachment is still owed.
"""

import hashlib
import uuid
from email.message import EmailMessage
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import DuplicateError, InvalidDocumentError
from app.workers.imap_watcher import (
    AttachmentOutcome,
    IMAPMailboxHandler,
    message_is_complete,
)

MESSAGE_ID = "<invoice-2026-09@example.test>"
UID = b"17"


def make_email(
    attachments: list[tuple[str, bytes]], message_id: str | None = MESSAGE_ID
) -> bytes:
    msg = EmailMessage()
    msg["Subject"] = "Scans"
    msg["From"] = "scanner@example.test"
    if message_id:
        msg["Message-Id"] = message_id
    msg.set_content("Attached.")
    for filename, content in attachments:
        msg.add_attachment(
            content, maintype="application", subtype="pdf", filename=filename
        )
    return msg.as_bytes()


class FakeMailbox:
    """The few IMAP commands the watcher issues, and what it did with them."""

    def __init__(
        self,
        messages: dict[bytes, bytes],
        copy_succeeds: bool = True,
        store_succeeds: bool = True,
        chatty_fetch: bool = False,
    ):
        self.messages = messages
        self.flags: dict[bytes, list[str]] = {}
        self.copied: list[tuple[bytes, str]] = []
        self.copy_succeeds = copy_succeeds
        self.store_succeeds = store_succeeds
        self.chatty_fetch = chatty_fetch
        self.expunged = False
        self.fetch_items: list[str] = []

    def select(self, mailbox):
        return "OK", [b"1"]

    def response(self, name):
        return name, [b"4242"]

    def expunge(self):
        self.expunged = True
        return "OK", [b""]

    def uid(self, command, *args):
        command = command.upper()
        if command == "SEARCH":
            unseen = [
                uid for uid in self.messages if "\\Seen" not in self.flags.get(uid, [])
            ]
            return "OK", [b" ".join(unseen)]
        if command == "FETCH":
            uid, item = args
            self.fetch_items.append(item)
            # A real server flags a message read when the body is fetched
            # without PEEK, which is how a deferred message would be lost.
            if "PEEK" not in item.upper():
                self.flags.setdefault(uid, []).append("\\Seen")
            literal = (b"1 (BODY[] {0})", self.messages[uid])
            # Servers may answer with an untagged FLAGS update beside the
            # literal, and need not put it last.
            if self.chatty_fetch:
                return "OK", [b"1 (FLAGS (\\Seen))", literal, b")"]
            return "OK", [literal]
        if command == "STORE":
            uid, _, flag = args
            if not self.store_succeeds:
                return "NO", [b"mailbox is read-only"]
            self.flags.setdefault(uid, []).append(flag)
            return "OK", [b""]
        if command == "COPY":
            uid, folder = args
            if not self.copy_succeeds:
                return "NO", [b"[TRYCREATE] no such folder"]
            self.copied.append((uid, folder))
            return "OK", [b""]
        raise AssertionError(f"unexpected UID command: {command}")

    def is_seen(self, uid: bytes = UID) -> bool:
        return "\\Seen" in self.flags.get(uid, [])

    def is_deleted(self, uid: bytes = UID) -> bool:
        return "\\Deleted" in self.flags.get(uid, [])


class FakeFailures:
    """The durable record of terminal failures, in memory."""

    def __init__(self, recorded: dict[str, set[str]] | None = None):
        self.recorded = {key: set(value) for key, value in (recorded or {}).items()}
        self.records: list[dict] = []
        self.record_succeeds = True

    def recorded_checksums(self, *, import_source_id, message_key):
        return set(self.recorded.get(message_key, set()))

    def record(self, *, import_source_id, message_key, filename, checksum, error):
        self.records.append(
            {
                "import_source_id": import_source_id,
                "message_key": message_key,
                "filename": filename,
                "checksum": checksum,
                "error": error,
            }
        )
        if not self.record_succeeds:
            return None
        self.recorded.setdefault(message_key, set()).add(checksum)
        return SimpleNamespace(id=uuid.uuid4())


def make_source(processed_folder: str | None = None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        name="Scanner mailbox",
        owner_id=uuid.uuid4(),
        imap_mailbox="INBOX",
        imap_processed_folder=processed_folder,
        last_run=None,
        last_error=None,
        status="active",
    )


def make_handler(
    attachments: list[tuple[str, bytes]],
    intake_results: list,
    processed_folder: str | None = None,
    copy_succeeds: bool = True,
    store_succeeds: bool = True,
    chatty_fetch: bool = False,
    failures: FakeFailures | None = None,
    message_id: str | None = MESSAGE_ID,
):
    intake = MagicMock()
    intake.intake.side_effect = intake_results
    source = make_source(processed_folder)
    handler = IMAPMailboxHandler(
        source, MagicMock(), intake, failures or FakeFailures()
    )
    handler.mail = FakeMailbox(
        {UID: make_email(attachments, message_id)},
        copy_succeeds=copy_succeeds,
        store_succeeds=store_succeeds,
        chatty_fetch=chatty_fetch,
    )
    return handler


def imported():
    return SimpleNamespace(id=uuid.uuid4())


def duplicate():
    return DuplicateError(detail={"document_id": str(uuid.uuid4())})


# --- the rule itself -------------------------------------------------------


@pytest.mark.parametrize(
    "outcomes,complete",
    [
        ([], True),
        ([AttachmentOutcome.IMPORTED], True),
        ([AttachmentOutcome.DUPLICATE], True),
        ([AttachmentOutcome.REJECTED], True),
        ([AttachmentOutcome.DEFERRED], False),
        ([AttachmentOutcome.IMPORTED, AttachmentOutcome.DEFERRED], False),
        ([AttachmentOutcome.REJECTED, AttachmentOutcome.DUPLICATE], True),
    ],
)
def test_only_a_deferred_attachment_holds_a_message_open(outcomes, complete) -> None:
    assert message_is_complete(outcomes) is complete


# --- partial success -------------------------------------------------------


def test_a_failed_attachment_leaves_the_whole_message_unread() -> None:
    handler = make_handler(
        [("first.pdf", b"first"), ("second.pdf", b"second")],
        [imported(), OSError("storage is away")],
    )

    handler.check_mailbox()

    assert handler.mail.is_seen() is False
    assert handler.mail.copied == []


def test_a_failed_attachment_leaves_the_message_in_the_inbox() -> None:
    handler = make_handler(
        [("first.pdf", b"first"), ("second.pdf", b"second")],
        [imported(), OSError("storage is away")],
        processed_folder="Processed",
    )

    handler.check_mailbox()

    assert handler.mail.copied == []
    assert handler.mail.is_deleted() is False
    assert handler.mail.expunged is False


def test_the_attachments_that_landed_are_still_imported() -> None:
    handler = make_handler(
        [("first.pdf", b"first"), ("second.pdf", b"second")],
        [imported(), OSError("storage is away")],
    )

    handler.check_mailbox()

    assert handler.intake_service.intake.call_count == 2


# --- the retry -------------------------------------------------------------


def test_the_retry_completes_the_message_once_the_rest_lands() -> None:
    handler = make_handler(
        [("first.pdf", b"first"), ("second.pdf", b"second")],
        [duplicate(), imported()],
    )

    handler.check_mailbox()

    assert handler.mail.is_seen() is True


def test_the_retry_does_not_duplicate_what_already_landed() -> None:
    """The archive refuses the bytes it already holds, which settles them."""
    handler = make_handler(
        [("first.pdf", b"first"), ("second.pdf", b"second")],
        [duplicate(), imported()],
    )

    handler.check_mailbox()

    filenames = [
        call.kwargs["filename"]
        for call in handler.intake_service.intake.call_args_list
    ]
    assert filenames == ["first.pdf", "second.pdf"]


def test_the_retry_moves_the_message_once_every_attachment_settles() -> None:
    handler = make_handler(
        [("only.pdf", b"only")], [imported()], processed_folder="Processed"
    )

    handler.check_mailbox()

    assert handler.mail.copied == [(UID, "Processed")]
    assert handler.mail.is_deleted() is True
    assert handler.mail.expunged is True


# --- terminal failures -----------------------------------------------------


def test_an_attachment_the_archive_refuses_is_recorded() -> None:
    failures = FakeFailures()
    handler = make_handler(
        [("broken.pdf", b"broken")],
        [InvalidDocumentError("File type not supported")],
        failures=failures,
    )

    handler.check_mailbox()

    assert len(failures.records) == 1
    record = failures.records[0]
    assert record["filename"] == "broken.pdf"
    assert record["checksum"] == hashlib.sha256(b"broken").hexdigest()
    assert record["message_key"] == MESSAGE_ID
    assert "not supported" in record["error"]


def test_a_recorded_refusal_lets_the_message_complete() -> None:
    handler = make_handler(
        [("broken.pdf", b"broken")], [InvalidDocumentError("File type not supported")]
    )

    handler.check_mailbox()

    assert handler.mail.is_seen() is True


def test_a_refusal_that_could_not_be_recorded_holds_the_message_open() -> None:
    failures = FakeFailures()
    failures.record_succeeds = False
    handler = make_handler(
        [("broken.pdf", b"broken")],
        [InvalidDocumentError("File type not supported")],
        failures=failures,
    )

    handler.check_mailbox()

    assert handler.mail.is_seen() is False


def test_a_recorded_refusal_is_not_attempted_again() -> None:
    failures = FakeFailures(
        {MESSAGE_ID: {hashlib.sha256(b"broken").hexdigest()}}
    )
    handler = make_handler(
        [("broken.pdf", b"broken"), ("good.pdf", b"good")],
        [imported()],
        failures=failures,
    )

    handler.check_mailbox()

    filenames = [
        call.kwargs["filename"]
        for call in handler.intake_service.intake.call_args_list
    ]
    assert filenames == ["good.pdf"]
    assert handler.mail.is_seen() is True


# --- completing the message can itself fail --------------------------------


def test_a_move_that_fails_leaves_the_message_where_it_is() -> None:
    handler = make_handler(
        [("only.pdf", b"only")],
        [imported()],
        processed_folder="Processed",
        copy_succeeds=False,
    )

    handler.check_mailbox()

    assert handler.mail.copied == []
    assert handler.mail.is_deleted() is False
    assert handler.mail.is_seen() is False
    assert handler.mail.expunged is False


# --- message identity ------------------------------------------------------


def test_a_message_is_identified_by_its_message_id() -> None:
    handler = make_handler([("only.pdf", b"only")], [imported()])
    handler.check_mailbox()

    assert handler.failure_service.recorded_checksums(
        import_source_id=handler.import_source.id, message_key=MESSAGE_ID
    ) == set()


def test_a_message_without_a_message_id_falls_back_to_its_uid() -> None:
    failures = FakeFailures()
    handler = make_handler(
        [("broken.pdf", b"broken")],
        [InvalidDocumentError("File type not supported")],
        failures=failures,
        message_id=None,
    )

    handler.check_mailbox()

    assert failures.records[0]["message_key"] == "uid:4242:17"


# --- nothing to import -----------------------------------------------------


def test_a_message_with_no_attachments_is_completed() -> None:
    handler = make_handler([], [])

    handler.check_mailbox()

    assert handler.mail.is_seen() is True
    handler.intake_service.intake.assert_not_called()


def test_a_message_that_cannot_be_fetched_is_left_alone() -> None:
    handler = make_handler([("only.pdf", b"only")], [imported()])
    handler.mail.uid = lambda command, *args: (
        ("OK", [b"17"]) if command.upper() == "SEARCH" else ("NO", [None])
    )

    handler.check_mailbox()

    handler.intake_service.intake.assert_not_called()


# --- reading a message must not complete it --------------------------------


def test_reading_a_message_does_not_mark_it_read() -> None:
    """A plain RFC822 fetch flags \\Seen, which would lose every deferral."""
    handler = make_handler(
        [("only.pdf", b"only")], [OSError("storage is away")]
    )

    handler.check_mailbox()

    assert handler.mail.fetch_items == ["(BODY.PEEK[])"]
    assert handler.mail.is_seen() is False


def test_a_deferred_message_is_still_unseen_on_the_next_pass() -> None:
    handler = make_handler(
        [("only.pdf", b"only")], [OSError("storage is away"), imported()]
    )

    handler.check_mailbox()
    handler.check_mailbox()

    assert handler.intake_service.intake.call_count == 2
    assert handler.mail.is_seen() is True


def test_extra_fetch_responses_do_not_hide_the_message() -> None:
    handler = make_handler(
        [("only.pdf", b"only")], [imported()], chatty_fetch=True
    )

    handler.check_mailbox()

    assert handler.intake_service.intake.call_count == 1
    assert handler.mail.is_seen() is True


def test_a_copy_whose_flag_is_refused_is_not_expunged() -> None:
    handler = make_handler(
        [("only.pdf", b"only")],
        [imported()],
        processed_folder="Processed",
        store_succeeds=False,
    )

    handler.check_mailbox()

    assert handler.mail.copied == [(UID, "Processed")]
    assert handler.mail.is_deleted() is False
    assert handler.mail.expunged is False


def test_a_message_left_behind_is_reported_on_the_source() -> None:
    handler = make_handler([("only.pdf", b"only")], [OSError("storage is away")])

    handler.check_mailbox()

    assert "1 message(s) left unprocessed" in handler.import_source.last_error


def test_a_pass_that_finishes_everything_clears_the_error() -> None:
    handler = make_handler([("only.pdf", b"only")], [imported()])
    handler.import_source.last_error = "1 message(s) left unprocessed; see the log"

    handler.check_mailbox()

    assert handler.import_source.last_error is None
