# Cartulary

A personal and team document archive: documents come in, are read (OCR), described (metadata), and made searchable and askable.

## Language

### Models

**Provider**:
A service Cartulary sends model work to: Ollama, OpenAI, Gemini, or local sentence-transformers.
_Avoid_: backend, vendor, client

**Chat model**:
A specific model at a specific provider that turns messages, optionally carrying images, into text.
_Avoid_: LLM, vision-chat, client

**Assistant model**:
The chat model that extracts document metadata and answers questions about documents.
_Avoid_: LLM

**Embedder**:
A specific model at a specific provider that turns text into vectors of one fixed dimension.
_Avoid_: embedding service, embedding client

### OCR

**Vision model**:
The chat model that reads raw text off a page image in the first OCR pass.

**Formatter model**:
The chat model that turns the vision model's raw text into markdown in the second OCR pass.

**Page concurrency**:
The most of a PDF's pages that are in the models at once. Both passes for one page run
together, so it is also a ceiling on the model requests OCR has outstanding.
_Avoid_: batch size, OCR parallelism

**Page cache**:
Where a page image's finished OCR text is remembered, so an identical page is never read
twice by the same models. A speed-up, never a source of truth.
_Avoid_: OCR cache, result store

### Documents

**Owner**:
The User whose archive contains a Document. Ownership identifies where the Document belongs,
not necessarily who initiated its intake.
_Avoid_: uploader, creator

**Uploader**:
The User who directly initiated a Document's intake. Automated directory and email imports
have no Uploader, even though every imported Document has an Owner.
_Avoid_: owner, creator

**Document intake**:
The act of adding a source file to an Owner's archive. Intake ends before the Document is
read, described, made searchable, or made askable.
_Avoid_: upload, import

**Duplicate document**:
A source file whose original bytes match a Document already in the same Owner's archive.
The same bytes in another Owner's archive are not a duplicate.
_Avoid_: copy, matching filename

**Accessible document**:
A Document a User may act on at a given permission level — because they own it, because
it is public (read only), or because a live share grants it. Superusers reach everything.
One expression decides this for every read of the documents table. See ADR 0004.
_Avoid_: visible document, my documents, owned documents

**Share**:
A grant of one permission level on one Document to one other User, optionally until a
date. Read, write and admin rank in that order: a share grants every level below its own.
_Avoid_: permission, ACL

**Live share**:
A Share that has not expired, measured against the database clock. An expired Share
grants nothing — it does not degrade to read. Whether a Share is live is decided in one
place, so the documents listed as shared with you are exactly the ones you can reach.
_Avoid_: active share, valid share

**Public document**:
A Document any User may read, whoever owns it. Public confers read and nothing more:
editing one still needs ownership or a write share.
_Avoid_: shared with everyone, open document

### Capabilities

**Capability**:
Optional work a deployment either can or cannot do: OCR, embeddings, chat, metadata
extraction. A capability is on exactly when its builder in the factory returns a model
rather than `None`. An endpoint needing one that is off answers 503; `GET /capabilities`
reports all four so a client can hide the feature instead of offering it. See ADR 0003.
_Avoid_: feature flag, toggle

### Processing

**Stage**:
One step of processing a Document: reading it (OCR), making it searchable (embedding),
describing it (metadata extraction). A stage is a pure function from its inputs and its
models to a stage result; running one is the runner's job.
_Avoid_: step, phase, job, task

**Processing status**:
Where a Document is in processing, stored on the row and the only record of it. One of
seven: pending, processing, ocr_complete, ocr_failed, embedding_complete, llm_complete,
failed. Nothing infers it from what the Document holds. See ADR 0006.
_Avoid_: state, processing state

**Processing status group**:
What a processing status means to someone reading it: queued, in flight, stage complete,
complete, failed. Defined once in `@cartulary/shared` beside the status itself, so web and
mobile share the reading and differ only in how they paint it. `stage_complete` and
`complete` stay apart because a Document that has only been read is not one that has been
described, and a surface saying "ready" may only say it of `complete`.
_Avoid_: status category, status kind

**Stage result**:
What a finished stage asks for: the fields to write, the status to move to, the chunks or
tags to replace, and whether clients should hear the Document changed. A stage returns one;
it never writes.
_Avoid_: outcome, response

**Chunk**:
A piece of a Document's text small enough to embed, and the unit search and chat retrieve.
A chunk ends at the last sentence boundary before the configured size, or at the size when
no boundary falls there, and overlaps the chunk before it so a passage spanning a boundary
is still findable. No chunk is empty. Chunking is pure: text in, chunks out.
_Avoid_: segment, passage, fragment, page

**Runner**:
What runs one stage over one Document: the session, the models, the transaction, the status
event with the state read from the row, and what to enqueue next. The only part of
processing that touches the database, and it reaches the queue only through the entry point.
_Avoid_: orchestrator, pipeline, worker

**Entry point**:
`enqueue_stage(document_id, stage, **options)`: the one way a stage becomes queued work.
Everything that starts processing — a route, the intake service, the runner handing a
Document on — names a stage and calls it, and nothing else knows a Celery task by name.
_Avoid_: trigger, dispatch, kick off
