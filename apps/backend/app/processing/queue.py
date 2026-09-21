"""Where processing meets the broker: the one place a stage becomes queued work.

Everything that starts processing — the upload and reprocess routes, the tag routes,
the intake service, the runner handing a Document to its next stage — names a `Stage`
and calls `enqueue_stage`. Which Celery task that is, and what it may be given, is
decided here and nowhere else.

This is the only module in `app.processing` that imports `app.tasks`, so the machine,
the stage functions, the chunker and the runner all stay free of Celery and run in a
test with no broker.
"""
import logging
from typing import TYPE_CHECKING, Any, Dict, FrozenSet

from app.processing.stages import Stage

if TYPE_CHECKING:  # Naming the result is not worth importing Celery to do it.
    from celery.result import AsyncResult

logger = logging.getLogger(__name__)

#: What each stage's task accepts beyond the document id. Only reading a Document takes
#: anything: whether to OCR pages that already hold text, and whether to read them with
#: the models again rather than reuse the page cache.
STAGE_OPTIONS: Dict[Stage, FrozenSet[str]] = {
    Stage.OCR: frozenset({"force_ocr", "refresh_cache"}),
    Stage.EMBEDDING: frozenset(),
    Stage.METADATA: frozenset(),
}


def enqueue_stage(document_id: str, stage: Stage, **options: Any) -> "AsyncResult":
    """Queue `stage` for a Document, and return the Celery result.

    The result is returned rather than dropped because the reprocess and regenerate
    routes answer with its `task_id`. An option the stage does not take raises here,
    where the caller can see it, rather than inside a worker.
    """
    unknown = sorted(set(options) - STAGE_OPTIONS[stage])
    if unknown:
        raise ValueError(f"{stage} takes no {', '.join(unknown)}")

    # Imported at call time, not at module scope: `app.tasks.document_tasks` imports
    # this module to hand the runner its way back here, so importing it at the top
    # would close the circle.
    from app.tasks import document_tasks

    logger.info(f"Enqueuing {stage} for document {document_id}")
    return document_tasks.TASK_FOR[stage].delay(document_id, **options)
