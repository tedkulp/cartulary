# An IMAP message is finished only when every attachment on it is

The IMAP watcher imported each attachment in a `try`, logged whatever went wrong and carried
on, then marked the message read — or moved it to the processed folder — because the message
itself had been handled. A message is where an attachment that was never stored lives. Marking
it read discards the only record that the archive still owes that attachment, and neither the
log line nor the import source's `last_error`, which the next successful run clears, brings it
back.

**The message is the unit of completion.** A message is marked read or moved only once every
attachment on it has settled:

- **imported** — a Document now holds the bytes;
- **duplicate** — the archive already holds them, which ADR 0009 makes the database's answer;
- **rejected** — the bytes can never become a Document, and a row in `import_failures` says
  so.

Anything else — storage away, the database away, the broker away — is **deferred**: the
message is not flagged, not copied, not expunged, and the next pass over the mailbox finds it
`UNSEEN` and offers it again.

**Retrying the whole message is safe because intake deduplicates.** The attachments that
landed on the failed pass come back as `DuplicateError` against the per-Owner checksum index,
which settles them without a second Document, a second file in storage or a second trip
through OCR. That is the reason this design needs no per-attachment progress record: ADR 0009
already made "these bytes are in this archive" a question the database answers. Two
attachments carrying identical bytes on one message resolve the same way — the first is
imported, the second is the duplicate it is.

**A refusal is terminal, and terminal means written down.** `InvalidDocumentError` says the
bytes will never be accepted, so deferring the message would repeat the refusal every minute
forever. `import_failures` holds one row per (import source, message, attachment checksum)
with the filename and the error, and only once that row exists does the attachment count as
settled — a record that could not be written leaves the message open, because an unwritten
failure is the silent discard this ADR exists to prevent. The next pass reads the recorded
checksums for the message first and skips what is already there, so a message carrying one
refused attachment beside good ones completes without attempting the refusal again.

**Reading a message must not finish it.** A `FETCH (RFC822)` sets `\Seen` as a side effect,
so the watcher's own read completed every message it looked at and the next `UID SEARCH
UNSEEN` would never offer a deferred one again — the deferral would have been the silent
discard wearing a different hat. The fetch is `BODY.PEEK[]`, and `complete_email()` is the
only thing that flags a message. The fake mailbox the tests run against flags `\Seen` on a
non-PEEK fetch for that reason, so the mistake cannot come back unnoticed. A fetch response
may also carry more than the body — an untagged `FLAGS` update beside it, in any order — so
the literal is found by looking for the first `(descriptor, payload)` pair rather than taking
the first element.

**The message's identity is its `Message-Id`.** It survives a reconnect, a move to another
folder, and a mailbox rebuilt under a new `UIDVALIDITY`, which is what a durable record needs.
A message without one falls back to `uid:<UIDVALIDITY>:<UID>`. The watcher now issues `UID
SEARCH`, `UID FETCH`, `UID STORE` and `UID COPY` rather than sequence numbers, which an
expunge renumbers underneath a session.

**Completing a message can itself fail, and that is deferral too.** A copy to the processed
folder that is refused does not flag the original `\Deleted`, and the message is not marked
read either; `EXPUNGE` runs only when a move actually happened. A copy that succeeded whose
`\Deleted` flag was refused is a failed move as well: reporting it as done would expunge
nothing and copy the same message into the processed folder again on every pass that follows.
The message stays where it is and is retried, where before a failed move was logged and the
message left in a state nothing would revisit.

**Deferral is unbounded, and says so.** A failure that is neither a refusal nor transient —
storage misconfigured, a bug in a code path intake reaches — leaves its message retried every
poll for as long as the deployment runs, re-fetching it and re-running each attachment that
already landed through a duplicate lookup. That is the cost of refusing to guess which
failures are permanent, and it is cheap; what it must not be is invisible, so a pass that
leaves any message behind writes that on the import source's `last_error` instead of clearing
it. The source stays `ACTIVE` — a message waiting is not a source that is broken — and an
operator reading the import sources sees how many are owed. A retry schedule per message
would be a second processing machine beside the one in `app/processing/`, keeping its own
state in a mailbox that is not ours to write to.

The alternative was per-attachment progress: persist every attachment of every message with
its own state and retry only the failed ones. It stores more, needs its own retry schedule and
its own notion of when a message is done, and buys nothing the checksum index does not already
give — the only thing whole-message retry repeats is a lookup per attachment that already
landed.

The rows are backend-only for now: nothing in the API or the web app reads `import_failures`
yet, so a refused attachment is visible to an operator in the database and the log rather than
in the UI. Surfacing them on the import source is follow-up work, not part of the rule.

Closes #33.
