"""The Celery adapters: what a task hands the runner, and nothing else.

A task names its stage and passes the plumbing — the queue, this attempt's number and
the way to run the stage again. Retrying is the one thing the runner cannot do itself,
because it will not import Celery, so these tests pin the seam. See ADR 0007.
"""
from pathlib import Path
from typing import List
from unittest.mock import MagicMock

import pytest

from app.processing import Stage
from app.processing.queue import enqueue_stage
from app.processing.retry import MAX_RETRIES
from app.providers import ModelError
from app.tasks.document_tasks import TASK_FOR, _plumbing


@pytest.fixture
def task() -> MagicMock:
    """A bound task, as Celery hands one to the function it decorates."""
    stub = MagicMock()
    stub.request.retries = 0
    stub.retry.side_effect = RuntimeError("celery.exceptions.Retry")
    return stub


class TestWhatATaskHandsTheRunner:
    """The queue, the attempt count, and the retry."""

    def test_the_queue_is_the_one_entry_point_not_a_task_of_its_own(
        self, task: MagicMock
    ) -> None:
        assert _plumbing(task)["enqueue"] is enqueue_stage

    def test_the_attempt_is_the_one_celery_is_counting(self, task: MagicMock) -> None:
        task.request.retries = 2

        assert _plumbing(task)["attempt"] == 2

    def test_a_task_that_has_never_retried_is_attempt_zero(self, task: MagicMock) -> None:
        """Outside a worker `request.retries` is None, which is not a missing attempt."""
        task.request.retries = None

        assert _plumbing(task)["attempt"] == 0

    def test_retrying_is_celery_raising_what_the_runner_asked_for(
        self, task: MagicMock
    ) -> None:
        error = ModelError("connection refused")

        with pytest.raises(RuntimeError, match="Retry"):
            _plumbing(task)["retry"](error, 60)

        # `max_retries` is the schedule's, not Celery's default: otherwise a longer
        # schedule would be cut short by a number written somewhere else.
        task.retry.assert_called_once_with(exc=error, countdown=60, max_retries=MAX_RETRIES)


class TestEveryStageIsAnAdapter:
    """Each stage has exactly one task, and no task decides anything."""

    def test_every_stage_has_a_task(self) -> None:
        assert set(TASK_FOR) == set(Stage)

    def test_the_task_names_are_unchanged_so_queued_work_survives_a_deploy(self) -> None:
        assert [TASK_FOR[stage].name for stage in Stage] == [
            "app.tasks.process_document",
            "app.tasks.generate_embeddings",
            "tasks.extract_metadata",
        ]

    def test_no_task_carries_autoretry_configuration(self) -> None:
        """Which failures are worth retrying is the policy's answer, not a decorator's."""
        for stage in Stage:
            assert getattr(TASK_FOR[stage], "autoretry_for", ()) == ()


class TestWorkThatOutlivesAWorker:
    """A retry lives only in the queue, so the queue has to keep it."""

    def test_a_message_is_acked_after_the_work_not_on_receipt(self) -> None:
        """Otherwise a worker restart loses a retry waiting out its countdown, and the
        Document reads `processing` with nothing left to move it. See ADR 0007."""
        from app.tasks.celery_app import celery_app

        assert celery_app.conf.task_acks_late is True
        assert celery_app.conf.task_reject_on_worker_lost is True

    def test_nothing_waits_longer_than_the_broker_will_hold_it(self) -> None:
        """A countdown outlasting the visibility timeout would be redelivered mid-wait."""
        from app.tasks.celery_app import celery_app
        from app.processing.retry import RETRY_DELAYS

        visibility = celery_app.conf.broker_transport_options.get("visibility_timeout", 3600)
        assert max(RETRY_DELAYS) + celery_app.conf.task_time_limit < visibility


def test_the_processing_package_still_knows_nothing_about_celery() -> None:
    """The retry seam is where Celery could leak in. `queue` names it; nothing else may."""
    processing = Path(__file__).resolve().parents[1] / "app" / "processing"
    mentions: List[str] = [
        path.name for path in sorted(processing.rglob("*.py")) if "celery" in path.read_text()
    ]

    assert mentions == ["queue.py"]
