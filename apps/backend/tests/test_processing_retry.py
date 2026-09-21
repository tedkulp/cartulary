"""The retry policy: which failures come round again, and how long they wait.

Pure, so there are no fixtures, no broker and no model server — the same shape as
`test_processing_machine.py`. See ADR 0007.
"""
import pytest

from app.processing.retry import (
    MAX_RETRIES,
    RETRY_DELAYS,
    retry_delay,
    worth_retrying,
)
from app.providers import ModelConfigurationError, ModelError


class TestWorthRetrying:
    """`ModelError` is the one failure that might come out differently next time."""

    def test_a_model_error_is_worth_retrying(self) -> None:
        assert worth_retrying(ModelError("connection refused")) is True

    def test_a_subclass_of_model_error_is_worth_retrying(self) -> None:
        class RateLimited(ModelError):
            pass

        assert worth_retrying(RateLimited("slow down")) is True

    def test_a_configuration_fault_is_not_worth_retrying(self) -> None:
        """No key and no SDK read the same on the fourth attempt as on the first.

        It is a `ModelError` so every caller still handles it, but waiting five minutes
        does not install a library. See ADR 0007.
        """
        assert worth_retrying(ModelConfigurationError("OPENAI_API_KEY is required")) is False

    @pytest.mark.parametrize(
        "error",
        [
            FileNotFoundError("the file is gone"),
            ValueError("that is not a date"),
            TypeError("a programming error"),
            RuntimeError("something else entirely"),
            Exception("a bare exception"),
        ],
    )
    def test_everything_else_is_terminal(self, error: Exception) -> None:
        assert worth_retrying(error) is False


class TestRetryDelay:
    """The schedule, and the None that ends it."""

    def test_each_attempt_waits_longer_than_the_one_before(self) -> None:
        assert list(RETRY_DELAYS) == sorted(RETRY_DELAYS)
        assert len(set(RETRY_DELAYS)) == len(RETRY_DELAYS)

    @pytest.mark.parametrize("attempt, delay", list(enumerate(RETRY_DELAYS)))
    def test_an_attempt_within_the_schedule_waits_that_long(
        self, attempt: int, delay: int
    ) -> None:
        assert retry_delay(attempt) == delay

    def test_the_schedule_runs_out_and_the_failure_becomes_terminal(self) -> None:
        assert retry_delay(MAX_RETRIES) is None
        assert retry_delay(MAX_RETRIES + 1) is None

    def test_a_negative_attempt_is_not_a_free_extra_try(self) -> None:
        assert retry_delay(-1) is None

    def test_the_count_is_written_only_in_the_schedule(self) -> None:
        assert MAX_RETRIES == len(RETRY_DELAYS)
