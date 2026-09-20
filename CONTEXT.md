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
