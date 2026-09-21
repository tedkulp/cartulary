"""Celery tasks for document processing.

Each task is an adapter: it names a stage and hands it to the runner, which owns the
session, the models, the transaction, the status event and what comes next. The whole
machine lives in `app/processing/`; nothing about processing is decided here.

Task names are unchanged, so work already queued survives a deploy. There is no
`autoretry_for` either: which failures are worth another attempt is decided by
`app.processing.retry`, and the runner asks it. All Celery contributes is `self.retry`,
the one thing the runner cannot import, handed over here as a callable. See ADR 0007.
"""
from typing import Any, Dict, NoReturn

from celery import Task

from app.processing import Stage
from app.processing.queue import enqueue_stage
from app.processing.retry import MAX_RETRIES
from app.processing.runner import run_stage
from app.tasks.celery_app import celery_app


def _plumbing(task: Task) -> Dict[str, Any]:
    """What every stage task hands the runner: the queue, and this attempt's way back.

    `max_retries` is the schedule's length rather than Celery's default, so the two
    can never disagree about when a failure has run out of attempts.
    """

    def retry(error: BaseException, countdown: int) -> NoReturn:
        raise task.retry(exc=error, countdown=countdown, max_retries=MAX_RETRIES)

    return {
        "enqueue": enqueue_stage,
        "retry": retry,
        "attempt": task.request.retries or 0,
    }


@celery_app.task(bind=True, name="app.tasks.process_document")
def process_document(
    self, document_id: str, force_ocr: bool = False, refresh_cache: bool = False
) -> dict:
    """Read a document: OCR its file and record what it says."""
    return run_stage(
        document_id,
        Stage.OCR,
        force_ocr=force_ocr,
        refresh_cache=refresh_cache,
        **_plumbing(self),
    )


@celery_app.task(bind=True, name="app.tasks.generate_embeddings")
def generate_embeddings(self, document_id: str) -> dict:
    """Make a document searchable: chunk its text and embed the chunks."""
    return run_stage(document_id, Stage.EMBEDDING, **_plumbing(self))


@celery_app.task(bind=True, name="tasks.extract_metadata")
def extract_metadata(self, document_id: str) -> dict:
    """Describe a document: extract its metadata and tags with the assistant model."""
    return run_stage(document_id, Stage.METADATA, **_plumbing(self))


#: The task each stage is queued as. `app.processing.queue` reads this, and is the
#: only thing that does; nothing else here decides what runs next.
TASK_FOR = {
    Stage.OCR: process_document,
    Stage.EMBEDDING: generate_embeddings,
    Stage.METADATA: extract_metadata,
}
