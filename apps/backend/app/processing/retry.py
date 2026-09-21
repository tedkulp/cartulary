"""Which stage failures are worth running again, and how long to wait before each try.

Pure, like `stages`: no Celery, no settings, no session. The runner asks these two
questions of a failure it caught; the task adapter, which is the only thing that knows
what Celery is, acts on the answer. See ADR 0007.
"""
from typing import Optional

from app.providers.ports import ModelConfigurationError, ModelError

#: Seconds to wait before each retry, in order. Its length is how many retries there
#: are, so the schedule is the only place the count is written.
#:
#: Ten seconds covers a model server that is restarting; a minute covers one that is
#: still coming up or briefly rate-limited; five minutes is the last ask before the
#: Document is left for a person. Both ends of the transient range are reachable
#: without a subclass of `ModelError` telling them apart.
RETRY_DELAYS: tuple[int, ...] = (10, 60, 300)

#: How many retries the schedule allows. Celery is told this at the seam, so its own
#: `max_retries` can never disagree with the schedule.
MAX_RETRIES: int = len(RETRY_DELAYS)


def worth_retrying(error: BaseException) -> bool:
    """Whether this failure might come out differently on another attempt.

    `ModelError` is how every adapter reports a provider failure — an unreachable
    host, a rate limit, a read that went quiet for `MODEL_TIMEOUT_SECONDS` — and much
    of that class is transient. Everything else, a missing file or a bad row or a
    programming error, fails the same way however often it runs.

    `ModelConfigurationError` is the part of `ModelError` that is not transient: no
    API key, no SDK installed, a model asked for something it cannot do. Waiting five
    minutes does not install a library, so it fails at once and the operator reads the
    answer in `processing_error` rather than six minutes later.
    """
    return isinstance(error, ModelError) and not isinstance(error, ModelConfigurationError)


def retry_delay(attempt: int) -> Optional[int]:
    """Seconds to wait before the attempt after `attempt`, or None when there are none left.

    `attempt` counts the retries already made: 0 during the first run, 1 during the
    first retry. Returning None is what makes a failure terminal after the schedule
    is spent.
    """
    if attempt < 0 or attempt >= len(RETRY_DELAYS):
        return None
    return RETRY_DELAYS[attempt]
