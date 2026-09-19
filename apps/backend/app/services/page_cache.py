"""The page cache port, its Redis adapter, and the builder that picks one from settings.

A page cache remembers the text OCR produced for one rendered page image, so an identical
page read again — a document reprocessed, a letterhead shared across documents — costs a
lookup instead of both model passes. Keys are built by the OCR service and already carry
the models and prompts that produced the text, so entries never outlive what made them.
"""
import logging
from functools import lru_cache
from typing import Optional, Protocol

import redis

from app.config import settings

logger = logging.getLogger(__name__)


class PageCache(Protocol):
    """Remembers one page's OCR text under a key the OCR service builds.

    Structural, like the model ports: anything with these methods fits. A cache is a
    speed-up and never a source of truth, so neither method may raise.
    """

    def get(self, key: str) -> Optional[str]:
        """The text stored under this key, or None if there is none."""
        ...

    def set(self, key: str, text: str) -> None:
        """Store this text under this key."""
        ...


class RedisPageCache:
    """Page cache backed by Redis, with every entry expiring after the same TTL.

    Redis being down, slow or full only costs the cache: every failure is logged and
    reported as a miss, so OCR falls back to reading the page again.
    """

    def __init__(self, client: "redis.Redis", ttl_seconds: int) -> None:
        if ttl_seconds < 1:
            raise ValueError(f"ttl_seconds must be at least 1, got {ttl_seconds}")
        self.client = client
        self.ttl_seconds = ttl_seconds

    def __repr__(self) -> str:
        return f"RedisPageCache(ttl_seconds={self.ttl_seconds})"

    def get(self, key: str) -> Optional[str]:
        """The text stored under this key, or None on a miss or any Redis failure."""
        try:
            text = self.client.get(key)
        except redis.RedisError as e:
            logger.warning(f"Page cache lookup failed for {key}: {type(e).__name__}: {e}")
            return None
        if text is None:
            return None
        return text.decode() if isinstance(text, bytes) else text

    def set(self, key: str, text: str) -> None:
        """Store this text under this key until the TTL expires. Failures are only logged."""
        try:
            self.client.setex(key, self.ttl_seconds, text)
        except redis.RedisError as e:
            logger.warning(f"Page cache store failed for {key}: {type(e).__name__}: {e}")


# How long a lookup or a store may wait on Redis before it counts as a failure. Short,
# because waiting longer than this costs more than reading the page again.
SOCKET_TIMEOUT_SECONDS = 2.0


@lru_cache(maxsize=None)
def get_page_cache() -> Optional[PageCache]:
    """The page cache OCR should use, or None when caching is off. Cached per process.

    A cache that cannot be built is no cache at all: OCR reads every page instead, rather
    than the whole document failing over a speed-up.
    """
    if not settings.OCR_PAGE_CACHE_ENABLED:
        return None
    try:
        client = redis.from_url(
            settings.REDIS_URL,
            socket_timeout=SOCKET_TIMEOUT_SECONDS,
            socket_connect_timeout=SOCKET_TIMEOUT_SECONDS,
        )
    except (ValueError, redis.RedisError) as e:
        logger.warning(f"Page cache disabled, Redis unusable: {type(e).__name__}: {e}")
        return None
    cache = RedisPageCache(client=client, ttl_seconds=settings.OCR_PAGE_CACHE_TTL_SECONDS)
    logger.info(f"Page cache: {cache!r}")
    return cache
