"""Processing: the stages a Document goes through, and what runs them.

`stages` is the machine itself — the statuses, the transition table and the stage
functions — and is pure; `chunking` is the pure splitter the embedding stage feeds. `runner` is the plumbing around one stage: the session, the
models, the transaction, the status event and what to enqueue next. Neither imports
Celery; a Celery task is an adapter over `run_stage`. `queue` is the one entry point,
and the one module here that knows a task by name.

Only `stages` is re-exported here, and `stages` itself imports nothing heavier than
the model ports: the Document model names `ProcessingStatus`, so anything this package
pulls in at import time is pulled in by importing the ORM. `runner` imports the ORM
models, which would close that circle, and `queue` reaches the tasks. Reach for them
as `from app.processing.runner import run_stage` and
`from app.processing.queue import enqueue_stage`.
"""
from app.processing.stages import (
    EmbeddedChunk,
    EmbeddingWrite,
    ProcessingStatus,
    Stage,
    StageResult,
    enrich_text,
    next_stage,
    run_embedding,
    run_metadata,
    run_ocr,
    should_reembed,
)

__all__ = [
    "EmbeddedChunk",
    "EmbeddingWrite",
    "ProcessingStatus",
    "Stage",
    "StageResult",
    "enrich_text",
    "next_stage",
    "run_embedding",
    "run_metadata",
    "run_ocr",
    "should_reembed",
]
