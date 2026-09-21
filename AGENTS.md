# Cartulary — agent guide

A digital archive: documents come in, are read (OCR), described (metadata), and made
searchable and askable. See `CONTEXT.md` for the domain vocabulary and `docs/adr/` for the
decisions behind the sections below.

**Status**: Phase 7 complete (mobile app, Ollama vision OCR). Phase 8 is testing and
production.

## Layout

- `apps/backend` — FastAPI, Python 3.11+, SQLAlchemy 2.0, Alembic, Celery/Redis,
  PostgreSQL 16 with pgvector.
- `apps/web` — React 18 + TypeScript, Vite, Zustand, Tailwind, Radix/shadcn.
- `apps/mobile` — Expo SDK 54 + React Native, React Native Paper, React Navigation.
- `packages/shared` — `@cartulary/shared`: API services, types, hooks and stores used by
  both web and mobile. Rebuild it (`just build-shared`) after changing it.
- pnpm workspaces + Turborepo; Docker Compose for the stack.

## Running things

Every task runs through the `justfile` at the repo root. `just --list` shows all of them,
grouped (setup, dev, mobile, build, test, db, docker, clean). Use the recipe rather than the
underlying command, so there is one definition to keep correct.

**The user runs Docker.** Leave `just up`, `just down`, the other `docker` group recipes and
`docker compose` itself to them.

Backend recipes use `apps/backend/.venv` and fail with an explicit message if it is missing
(`just install-py` creates it). Host-side backend recipes reach the Postgres and Redis that
compose publishes on localhost, so the stack must be up for `just test-backend` and the `db`
recipes.

Settings live in `.env`, documented by `.env.example`. Read that file rather than guessing a
variable's name or its accepted values.

## Vision OCR (two-pass)

OCR runs in two passes in `apps/backend/app/services/ocr_service.py`:

1. **Pass 1 (vision model)** — extracts raw text from the page image. The prompt asks for
   plain text only.
2. **Pass 2 (formatter model)** — a text-only instruct model turns that raw text into
   markdown.

**Why two passes**: vision models read text well but follow formatting instructions poorly.
Separating extraction from formatting gives better output from each, and either model can be
swapped independently.

**Models are passed in**: `OCRService(vision_model=..., formatter_model=...)` takes two
**chat models** (the port in `app/providers/ports.py`) and never reads settings or builds
clients. The factory in `app/providers/factory.py` builds both from settings (Ollama at
`LLM_BASE_URL` for now), caches them per process, and returns `None` when `OCR_ENABLED` is
false. With no vision model, PDFs use embedded text only and images yield nothing; with no
formatter model, pass 2 is skipped. A model request that gets no response for
`MODEL_TIMEOUT_SECONDS` (default 300) fails; the Ollama adapter streams, so this bounds each
silence rather than the whole reply. Any provider failure, including a timeout, surfaces as
`ModelError`, or `ModelConfigurationError` when the fault is this deployment's — no key, no
SDK — which is a `ModelError` that is never retried. OCR catches one per page (the page keeps
its embedded text, if any) and one from pass 2 alone (the page keeps the raw text pass 1 read,
and is not cached), but a read the models read **no** page of raises instead — that is the
models being away, not a document of blank pages, and the stage retries on it (ADR 0007). An
image is always that case: one page, no embedded text to fall back on. See ADR 0001.

**Page cache**: with `OCR_PAGE_CACHE_ENABLED` (default true), each page's finished OCR text
is remembered in Redis under a key covering the page image, both models and both prompts, so
an identical page — a document reprocessed, a letterhead shared across documents — costs a
lookup instead of both passes. Entries expire after `OCR_PAGE_CACHE_TTL_SECONDS` (default 30
days) and a model or prompt change invalidates them by changing the key. Redis being down
only costs the speed-up: every failure is logged and read as a miss. `get_page_cache()` in
`app/services/page_cache.py` builds it from settings and returns `None` when caching is off.
Reprocessing reuses the cache; `POST /documents/{id}/reprocess?refresh_cache=true` (and the
`/reprocess/force` variant) re-reads every page with the models and replaces what is cached.
See ADR 0002.

In tests, `tests/fakes.py` provides `ScriptedChatModel`, `FakeEmbedder` and `FakePageCache`,
so OCR rules run with no model server. Live contract tests for adapters are marked `live` and
run only with `pytest --live` (`just test-live`).

### Behaviour notes

- Pages with embedded text are used as-is; vision OCR runs only when a page yields under 50
  characters, or when `force_ocr` is set.
- A page whose OCR text is already cached skips both passes. Text is only cached when there
  is some: an empty read is never remembered.
- Pages render at `fitz.Matrix(2, 2)` (~144 DPI). Raise it for higher fidelity at the cost of
  speed.
- Pass 2 is skipped when pass 1 returns under 10 characters.
- `OCR_PAGE_CONCURRENCY` (default 1) sets how many pages are OCR'd at once. Pages are
  rendered on the calling thread, since PyMuPDF is not thread-safe, and only the model calls
  fan out to a thread pool; the combined text always follows page order. Both passes for a
  page run together, so the setting is also a ceiling on the model requests outstanding at a
  time. Each page's raw and formatted output is logged.
- Pass-2 output is cleaned before use: `<think>` blocks (including one missing its opening or
  closing tag), a single fence wrapping the whole reply, and a leading "Here is the formatted
  text:"-style preamble are removed. Tags or an opening line that also appear in the pass-1
  raw text are kept as document content. Each page's cleaned text is logged between
  `--- BEGIN FINAL OUTPUT ---` markers.
- `detect_language()` uses `langdetect` with a fixed seed for reproducibility, and falls back
  to `"en"` on unusable text.
- Expect roughly 5–15s per page for pass 1 and 3–8s for pass 2. Raising
  `OCR_PAGE_CONCURRENCY` overlaps those per-page costs.
- Ollama needs the models pulled (`ollama pull minicpm-v`). `.env.example` lists the
  recommended model for each pass and the alternatives.

## Processing

A Document goes through **stages**: it is read (OCR), made searchable (embedding), then
described (metadata extraction). That machine is `app/processing/`: every transition, and
every stage's own rules, are decided there and nowhere else. Starting one is
`enqueue_stage`, and nothing else reaches the broker.

- `stages.py` is the machine and is **pure**: `ProcessingStatus` (a `StrEnum` whose seven
  members are the exact strings stored in `documents.processing_status`, which is why the
  column stays a `String` and no migration runs), the transition table
  `next_stage(status, has_embedder, has_assistant) -> Stage | None`, and one function per
  stage. It opens no session, enqueues nothing and reads no settings. The two booleans are
  capabilities — a builder in the factory returned a model — never a `*_ENABLED` setting.
- A stage function takes the inputs it needs plus the models it needs and returns a
  **stage result**: the fields to write, the status to move to, the chunks or tags to
  replace, and whether clients should hear the Document changed. It never writes anything.
- `runner.py` is the plumbing: `engine.dispose()`, a fresh session, loading the Document,
  asking the factory for the vision, formatter, assistant and embedder roles, calling the
  stage, applying the result in one transaction, emitting the transition, enqueuing what
  the machine says is next, and the error write. It imports no Celery and no tasks —
  enqueueing is a callable passed in — so a test drives it with no broker.
- Each Celery task in `app/tasks/document_tasks.py` is a two-line adapter naming its stage
  and handing over `_plumbing(self)`: the queue, this attempt's number and `self.retry`.
  Task names are unchanged, so queued work survives a deploy. There is no `autoretry_for`:
  what is worth retrying is decided per caught exception, not by a decorator.
- `retry.py` is the retry policy and is **pure**: `worth_retrying(error)` — true for
  `ModelError`, but not for its `ModelConfigurationError` subclass, and nothing else — and
  `retry_delay(attempt)`, which walks `RETRY_DELAYS` (10s, 60s, 300s) and returns None once
  it is spent. The runner asks both, then calls the `retry` callable the task handed it,
  which raises; **the runner never imports Celery**. With no `retry` callable every failure
  is terminal, which is how tests drive the path with no broker.
- Because a pending retry is written nowhere, the queued message is the only record of it,
  so `task_acks_late` and `task_reject_on_worker_lost` are on in `celery_app.py`. Don't turn
  them off: a worker restarted mid-countdown would otherwise strand the Document at
  `processing`. A stage may therefore be redelivered and run twice, which is safe — each
  writes once, at the end, in one transaction.
- **A Document waiting on a retry is not `failed`.** Nothing is written: it keeps the status
  it had, emits no event, and the transaction is rolled back. Only an exhausted schedule
  writes `failed` with `processing_error`. Do not add a `retrying` status; see ADR 0007.
- A `ModelError` a stage can work around is absorbed — a page that failed beside pages that
  read, tags that could not be reconciled against the ones the archive has. One that leaves
  the stage with nothing to show is raised, so it can be retried. That is why
  `AssistantService.extract_metadata` no longer turns a provider failure into empty
  metadata: a Document no model ever saw must not read `llm_complete`.
- `queue.py` is the one entry point: `enqueue_stage(document_id, stage, **options)` names
  the task a stage is queued as, returns the Celery result (the reprocess and regenerate
  routes answer with its `task_id`), and refuses an option the stage does not take —
  `force_ocr` and `refresh_cache` belong to OCR alone. It is the only module in the
  package that imports `app.tasks`; **no route, service or watcher calls `.delay()`**, and
  `tests/test_processing_queue.py` fails if one starts to. Reprocessing is `Stage.OCR`
  with `force_ocr`, not a task of its own.
- `should_reembed(document)` in `stages.py` is the one answer to "is this Document
  embedded enough that editing its metadata should re-embed it" — true at
  `embedding_complete` and `llm_complete`. The title/description edit and both tag routes
  ask it rather than carrying a copy of the status list.

- `chunking.py` splits the text the embedding stage embeds, and is pure: `chunk(text,
  size, overlap)`, with `EMBEDDING_CHUNK_SIZE` and `EMBEDDING_CHUNK_OVERLAP` passed in by
  the runner. A chunk ends at the last sentence boundary before the size cap, or at the cap
  when none falls there, and no chunk is empty. **The start position strictly advances**,
  enforced in the loop: a boundary landing inside the overlap is ignored in favour of the
  cap, and the next start is floored at `previous + 1`. That is the invariant the chunker
  this replaced lacked — `"A. " + "x" * 600` at 500/50 used to hang.

Rules the runner keeps, which nothing else may take over:

- **The "from" state is read from the row**, in the same transaction as the write. No call
  site passes a literal. A result that changes no status emits no status event and enqueues
  nothing.
- **Any stage that raises leaves the Document at `failed`** with `processing_error` set, and
  emits that transition — unless the failure is a `ModelError` with an attempt left, in
  which case nothing is written at all and the stage is run again.

See ADR 0006 and ADR 0007. Tests: `test_processing_machine.py` covers the table exhaustively
with no fixtures, `test_processing_retry.py` does the same for the retry policy,
`test_processing_stages.py` runs the stage functions on the fakes in `tests/fakes.py`,
`test_chunking.py` covers the chunking rules and the input that used to hang,
`test_document_tasks.py` pins what a task hands the runner, and `test_processing_runner.py`
runs the runner — including every retry path — against the real PostgreSQL from the
`db_session` fixture, because a mocked Session cannot say what landed in the row (ADR 0005).

## Capabilities

OCR, embeddings, chat and metadata extraction are **capabilities**: each is on exactly when
its builder in `app/providers/factory.py` returns a model rather than `None`.

- An endpoint that needs a capability that is off raises `capability_disabled_error()` from
  `app/core/capabilities.py` and answers **503**. Don't write the status code at the call
  site; don't read the `*_ENABLED` setting in a handler — ask the factory. Pass what is
  missing plus the matching `TURN_ON_*` constant, so the instruction to the operator is
  written once, since nothing the caller sends can fix it.
- A caller's own mistake still answers 4xx: regenerating embeddings for a document with no
  text stays 400.
- Processing asks the factory too: the runner passes what the builders returned into
  `next_stage()`, which chains a finished OCR onto embeddings, or straight to metadata when
  there is no embedder.
- `GET /api/v1/capabilities` (authenticated) reports all four capabilities from the same
  builders. Web fetches it once after login into `useCapabilityStore` (`packages/shared`) and
  hides what is off: the Chat nav entry, and the regenerate-embeddings/metadata actions on
  the document detail page and the bulk bar. A failed fetch leaves every capability true, so
  an older backend without the route keeps working.

`LLM_ENABLED` covers both metadata extraction and chat: both go through `AssistantService`
(`app/services/assistant_service.py`) on the chat model from `get_assistant_model()`, which
picks the adapter from `LLM_PROVIDER` and the key that matches it (`OPENAI_API_KEY` or
`GEMINI_API_KEY`).

`EMBEDDING_DIMENSION` must match the embedding model (768 for nomic-embed-text, 384 for
local, 1536 for OpenAI); nothing guesses it from the model name. Changing it needs
`just embedding-dimension <n>`, which drops every stored embedding.

See ADR 0003.

## Document access

"Which Documents can this user see" is answered once, by `accessible_documents(user, level)`
in `app/core/permissions.py`. It is a boolean SQLAlchemy expression, so every read path —
the document list, full-text search and its count, semantic search, hybrid search, RAG
chat — passes it to `.filter()`. A Document is accessible when the user owns it, when it is
public (read only), or when a **live share** (one that has not expired, measured against the
database clock) grants the level asked for. Superusers reach everything.

**Never filter on `Document.owner_id` in a new read path, and never compare
`DocumentShare.expires_at` yourself** — expiry is `share_is_live()`, which
`accessible_documents` and `GET /shared-with-me` both call.
`tests/test_access_filter_is_the_only_rule.py` fails if you do either. A line that is not an
access check — per-owner deduplication on upload and import — opts out with a trailing
`# not an access check: <why>` comment.

Because the expression needs `is_superuser`, services take a `User`, not a `user_id`.
Single-document checks go through `require_document_access(level)`, which asks
`can_access_document`, which asks the same expression — so a list and a document detail can
never disagree. Semantic search is ORM, not raw SQL, for this reason; see ADR 0004.

## Backend conventions

- Line length 100. Type hints on every signature. Async/await for I/O, consistently.
- Business logic lives in `services/`, not in API routes. Services are
  dependency-injectable and own their transactions.
- Routes are versioned under `/api/v1/`, return Pydantic schemas rather than ORM models, and
  carry their OpenAPI summary and status code.
- Pydantic validates every input; settings are read through `app/core/config.py` (and, for
  models, only by the factory).
- Models use `Mapped[...]` / `mapped_column`, and relationships use `lazy="selectin"` for
  async compatibility. Use `selectinload()` on queries that would otherwise N+1.
- Multiple providers behind one thing means an abstract port with adapters — storage
  (local/S3), the two model ports, the page cache. See ADR 0001.
- Uploads are deduplicated by SHA-256 checksum per owner; a duplicate answers 409.
- Search is hybrid: PostgreSQL full-text and pgvector semantic results combined with RRF.
- Errors: a user-friendly message out, the detail in the log.

## Frontend conventions

- TypeScript strict, functional components, hooks.
- Shared code goes in `packages/shared` — API services, types, stores — and is imported from
  `@cartulary/shared` by both apps. Web-only or mobile-only code stays in its app.
- A Document's processing status is the `ProcessingStatus` union from `@cartulary/shared`,
  the same seven values as the backend enum. Switch on it; never on a bare string.
- API calls live in `services/`, never in components; state in Zustand stores.
- Files: `PascalCase.tsx` for components, `useThing.ts` for hooks,
  `thing.service.ts` for services, `camelCase.ts` for stores and types.
- Web styles with Tailwind and shadcn/ui; mobile with React Native Paper and `StyleSheet`.

## Testing

- `just test` is what CI gates on: backend pytest plus the web type-check.
  `just test-backend -k ocr` passes arguments through. Keep coverage above 80%.
- Most backend tests mock the `Session`. Access-rule tests do not: `test_document_access.py`
  and `test_access_filter_is_the_only_rule.py` run against the real PostgreSQL from the
  `db_session` fixture, because a mocked Session cannot say which rows a query returns. See
  ADR 0005.
- Model-backed code is tested through the fakes in `tests/fakes.py`, never a live server,
  except the adapter contract tests marked `live`.
- Web tests are Vitest + Testing Library; `just e2e` runs Playwright.

## Migrations

`just migration "Description"` autogenerates a revision; `just migrate` applies it. Always
read the generated file before applying it — autogenerate misses index and type changes and
happily drops columns. Write `downgrade()` as well as `upgrade()`, and add indexes on large
tables as their own operation.

## Commits

Conventional commits: `<type>(<scope>): <subject>`, with a body listing what changed and a
`Closes #N` footer where one applies. Types: `feat`, `fix`, `docs`, `style`, `refactor`,
`perf`, `test`, `chore`, `build`.

**Commit at the end of a section of work, not after every change.** A complete feature
(backend + frontend + tests), a finished phase, or a finished refactor earns a commit.
Individual bug fixes, small corrections and lint fixes made along the way do not — they
belong in the commit for the work they were part of.

## Gotchas

- **pgvector missing**: `CREATE EXTENSION IF NOT EXISTS vector;` in the database.
- **Embedding OOM**: prefer Ollama embeddings; for local embeddings lower
  `ENCODE_BATCH_SIZE` in `app/providers/local.py` or use a smaller model (and match
  `EMBEDDING_DIMENSION`).
- **Stale workspace builds**: `just build-shared` after touching `packages/shared`;
  `just reinstall` when node_modules go wrong; `just mobile-clean` for Expo's cache.

## Agent skills

### Issue tracker

Issues live in GitHub Issues on `tedkulp/cartulary`, managed via the `gh` CLI. See
`docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, each label string equal to its name. See
`docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
