"""The one entry point that turns a stage into queued work.

`enqueue_stage` is the only place in the codebase that reaches a Celery task, so these
tests stand in for the call sites: they check which task a stage names, which options
it carries, and that the Celery result comes back for the routes that report a task id.
"""
from pathlib import Path
from typing import Dict, Iterator, List, Tuple
from unittest.mock import MagicMock, patch

import pytest

from app.processing import Stage
from app.processing.queue import enqueue_stage


@pytest.fixture
def tasks() -> Iterator[Dict[Stage, MagicMock]]:
    """Every stage's task, mocked, keyed by stage."""
    from app.tasks import document_tasks

    mocks = {stage: MagicMock() for stage in Stage}
    with patch.object(document_tasks, "TASK_FOR", mocks):
        yield mocks


def test_ocr_stage_queues_the_document_processing_task(tasks: Dict[Stage, MagicMock]) -> None:
    enqueue_stage("doc-1", Stage.OCR)

    tasks[Stage.OCR].delay.assert_called_once_with("doc-1")


def test_ocr_stage_carries_its_options(tasks: Dict[Stage, MagicMock]) -> None:
    """`force_ocr` and `refresh_cache` are what reprocessing means; both ride along."""
    enqueue_stage("doc-1", Stage.OCR, force_ocr=True, refresh_cache=True)

    tasks[Stage.OCR].delay.assert_called_once_with(
        "doc-1", force_ocr=True, refresh_cache=True
    )


@pytest.mark.parametrize("stage", [Stage.EMBEDDING, Stage.METADATA])
def test_the_later_stages_queue_their_own_task_with_no_options(
    stage: Stage, tasks: Dict[Stage, MagicMock]
) -> None:
    enqueue_stage("doc-1", stage)

    tasks[stage].delay.assert_called_once_with("doc-1")


def test_returns_the_celery_result_so_routes_can_report_a_task_id(
    tasks: Dict[Stage, MagicMock]
) -> None:
    tasks[Stage.EMBEDDING].delay.return_value = MagicMock(id="task-42")

    assert enqueue_stage("doc-1", Stage.EMBEDDING).id == "task-42"


def test_an_option_the_stage_does_not_take_is_refused_here(
    tasks: Dict[Stage, MagicMock]
) -> None:
    """Caught at the call, not inside a worker where the traceback is someone else's."""
    with pytest.raises(ValueError, match="force_ocr"):
        enqueue_stage("doc-1", Stage.EMBEDDING, force_ocr=True)

    tasks[Stage.EMBEDDING].delay.assert_not_called()


def _sources() -> List[Tuple[Path, str]]:
    """Every module of the application, with its text."""
    app = Path(__file__).resolve().parents[1] / "app"
    return [(path.relative_to(app.parent), path.read_text()) for path in sorted(app.rglob("*.py"))]


def test_the_queue_is_the_only_door_from_processing_to_celery() -> None:
    """The rest of `app.processing` stays free of Celery; only this module knocks."""
    importers = [
        str(path)
        for path, text in _sources()
        if path.parts[1] == "processing" and "app.tasks" in text
    ]

    assert importers == ["app/processing/queue.py"]


def test_the_queue_holds_the_only_delay_call_outside_the_tasks() -> None:
    """One entry point means one `.delay()`: a new call site here is a second machine."""
    callers = [
        str(path)
        for path, text in _sources()
        if ".delay(" in text and path.parts[1] not in ("tasks",)
    ]

    assert callers == ["app/processing/queue.py"]


def test_no_api_route_imports_a_celery_task() -> None:
    """Routes name a stage. What runs it is the queue's business, not a route's."""
    importers = [
        str(path) for path, text in _sources() if path.parts[1] == "api" and "app.tasks" in text
    ]

    assert importers == []
