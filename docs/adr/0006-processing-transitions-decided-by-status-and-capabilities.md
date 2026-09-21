# Processing transitions are decided by status and capabilities

What a Document does next is `next_stage(status, has_embedder, has_assistant)` in
`app/processing/stages.py`: a pure function of the processing status stored on the row and
the two capabilities that can be off. It reads no Document content, opens no session and
imports no Celery, so the whole machine is one readable table and a test can exercise every
row of it with no fixtures.

Before this, the machine did not exist as anything. It was thirteen `.delay()` calls — five
of them inside API routes — and seven bare status strings, described only by a comment on the
model that left out `ocr_failed`. Adding a stage meant finding every call site; the status
events clients received carried a hard-coded "from" state that was wrong whenever embeddings
were off; and a metadata failure recorded its error while leaving the status reading
`embedding_complete`.

The alternative worth weighing was deciding the next stage from what the Document holds:
has it text, has it chunks, has it an extracted title. It is tempting because it would
resume a half-processed Document after a crash without anyone recording where it got to.
It was rejected. Content answers a different question from the one being asked — a Document
can hold text and still have failed, and an empty read is not the same as an unread page —
so the two answers drift and the status becomes decoration. A status that is the single
answer can also be read by a person, indexed, and shown to a client. Resuming from content
would also mean every transition loads the row's text, which is the largest column in the
table.

Capabilities enter as booleans rather than settings because a capability is on exactly when
its builder in the factory returned a model (ADR 0003). The machine never learns which
provider that was, or whether `EMBEDDING_ENABLED` is what turned it off.

The statuses became a `StrEnum` whose members are the exact strings already stored, so the
column stays `String(50)` and no migration runs. A native Postgres enum or a `CHECK`
constraint would catch a bad write at the database, at the cost of a migration for every new
stage; the enum in Python is where every write already goes.

## Consequences

- The runner reads the "from" state off the row inside the same transaction as the write, so
  no call site passes a literal and no client is told a transition that did not happen.
- Any stage that raises leaves the Document at `failed` with `processing_error` set, and that
  transition is emitted. A metadata failure now reads `failed` rather than
  `embedding_complete`, and clients update instead of going quiet.
- A stage that changes no status — nothing to embed, nothing to describe — emits no event and
  enqueues nothing. Asking the machine from a status a stage has just declined to leave would
  enqueue that same stage for ever.
- A Document interrupted mid-stage stays at the status it was last written with, and needs
  reprocessing rather than resuming itself. That is the cost of the rejected alternative, and
  reprocessing was already how it was handled.
- Handing a Document on — the update event, the next stage on the queue — happens outside
  what the failure path covers. A broker that will not take the next stage has not unwritten
  the stage that landed, so the Document keeps the status it truly reached and the failure is
  logged. The alternative marks it `failed` and emits a transition no stage ever made.
- A date the assistant model gives that will not parse is logged and dropped, rather than
  written. It used to reach the database as a string and fail the whole document, which is
  not a rule worth keeping: a hallucinated date should cost the date, not the document.
- `autoretry_for` was removed from the three tasks rather than repaired. It had never fired:
  each task catches every exception and returns a dict, so Celery never saw a failure.
  Retrying only what is worth retrying — `ModelError` — is its own decision and its own issue.
