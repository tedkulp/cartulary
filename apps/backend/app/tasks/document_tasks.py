"""Celery tasks for document processing.

Each task is an adapter: it names a stage and hands it to the runner, which owns the
session, the models, the transaction, the status event and what comes next. The whole
machine lives in `app/processing/`; nothing about processing is decided here.

Task names are unchanged, so work already queued survives a deploy. There is no
`autoretry_for`: a stage that fails is terminal today, and the retry configuration
that used to sit here never fired, because the runner returns a dict rather than
raising. Making `ModelError` retryable is its own issue.
"""
from app.processing import Stage
from app.processing.queue import enqueue_stage
from app.processing.runner import run_stage
from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, name="app.tasks.process_document")
def process_document(
    self, document_id: str, force_ocr: bool = False, refresh_cache: bool = False
) -> dict:
    """Read a document: OCR its file and record what it says."""
    return run_stage(
        document_id,
        Stage.OCR,
        enqueue=enqueue_stage,
        force_ocr=force_ocr,
        refresh_cache=refresh_cache,
    )


@celery_app.task(bind=True, name="app.tasks.generate_embeddings")
def generate_embeddings(self, document_id: str) -> dict:
    """Make a document searchable: chunk its text and embed the chunks."""
    return run_stage(document_id, Stage.EMBEDDING, enqueue=enqueue_stage)


@celery_app.task(bind=True, name="tasks.extract_metadata")
def extract_metadata(self, document_id: str) -> dict:
    """Describe a document: extract its metadata and tags with the assistant model."""
    return run_stage(document_id, Stage.METADATA, enqueue=enqueue_stage)


#: The task each stage is queued as. `app.processing.queue` reads this, and is the
#: only thing that does; nothing else here decides what runs next.
TASK_FOR = {
    Stage.OCR: process_document,
    Stage.EMBEDDING: generate_embeddings,
    Stage.METADATA: extract_metadata,
}
