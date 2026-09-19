"""Tests for the Redis page cache and the builder that picks one from settings."""
from typing import Dict, List, Optional, Tuple

import pytest
import redis

from app.config import settings
from app.services import page_cache as page_cache_module
from app.services.page_cache import RedisPageCache, get_page_cache

KEY = "cartulary:ocr:page:abc123"
TEXT = "# The page, as markdown"


class FakeRedis:
    """The slice of a Redis client the page cache uses, over an in-memory dict."""

    def __init__(self, entries: Optional[Dict[str, bytes]] = None) -> None:
        self.entries: Dict[str, bytes] = dict(entries or {})
        self.calls: List[Tuple[str, int, str]] = []

    def get(self, key: str) -> Optional[bytes]:
        return self.entries.get(key)

    def setex(self, key: str, ttl_seconds: int, text: str) -> None:
        self.calls.append((key, ttl_seconds, text))
        self.entries[key] = text.encode()


class BrokenRedis:
    """A Redis client that is down: every call raises."""

    def get(self, key: str) -> Optional[bytes]:
        raise redis.ConnectionError("connection refused")

    def setex(self, key: str, ttl_seconds: int, text: str) -> None:
        raise redis.ConnectionError("connection refused")


class TestRedisPageCache:
    def test_stores_and_returns_text(self):
        cache = RedisPageCache(client=FakeRedis(), ttl_seconds=60)

        cache.set(KEY, TEXT)

        assert cache.get(KEY) == TEXT

    def test_stores_with_the_configured_ttl(self):
        client = FakeRedis()

        RedisPageCache(client=client, ttl_seconds=86400).set(KEY, TEXT)

        assert client.calls == [(KEY, 86400, TEXT)]

    def test_unknown_key_is_a_miss(self):
        assert RedisPageCache(client=FakeRedis(), ttl_seconds=60).get(KEY) is None

    def test_decodes_text_stored_as_bytes(self):
        """A client without decode_responses returns bytes; callers still get text."""
        client = FakeRedis({KEY: TEXT.encode()})

        assert RedisPageCache(client=client, ttl_seconds=60).get(KEY) == TEXT

    def test_lookup_against_a_down_redis_is_a_miss(self):
        """A cache is a speed-up, never a source of truth: its failures stay inside it."""
        assert RedisPageCache(client=BrokenRedis(), ttl_seconds=60).get(KEY) is None

    def test_store_against_a_down_redis_is_ignored(self):
        RedisPageCache(client=BrokenRedis(), ttl_seconds=60).set(KEY, TEXT)

    def test_rejects_a_ttl_below_one_second(self):
        with pytest.raises(ValueError):
            RedisPageCache(client=FakeRedis(), ttl_seconds=0)


class TestGetPageCache:
    @pytest.fixture(autouse=True)
    def fresh_builder(self, monkeypatch):
        monkeypatch.setattr(settings, "OCR_PAGE_CACHE_ENABLED", True)
        monkeypatch.setattr(settings, "OCR_PAGE_CACHE_TTL_SECONDS", 1234)
        get_page_cache.cache_clear()
        yield
        get_page_cache.cache_clear()

    def test_builds_a_redis_cache_from_settings(self, monkeypatch):
        monkeypatch.setattr(page_cache_module.redis, "from_url", lambda url, **kwargs: FakeRedis())

        cache = get_page_cache()

        assert isinstance(cache, RedisPageCache)
        assert cache.ttl_seconds == 1234

    def test_is_cached_per_process(self, monkeypatch):
        monkeypatch.setattr(page_cache_module.redis, "from_url", lambda url, **kwargs: FakeRedis())

        assert get_page_cache() is get_page_cache()

    def test_returns_no_cache_when_caching_is_disabled(self, monkeypatch):
        monkeypatch.setattr(settings, "OCR_PAGE_CACHE_ENABLED", False)

        assert get_page_cache() is None

    def test_gives_the_client_socket_timeouts(self, monkeypatch):
        """A hung Redis must fail as a miss, so no call may wait on it indefinitely."""
        captured = {}

        def from_url(url, **kwargs):
            captured.update(kwargs)
            return FakeRedis()

        monkeypatch.setattr(page_cache_module.redis, "from_url", from_url)
        get_page_cache()

        assert captured["socket_timeout"] > 0
        assert captured["socket_connect_timeout"] > 0

    def test_an_unusable_redis_url_yields_no_cache(self, monkeypatch):
        """A cache that cannot be built costs the speed-up, never the document."""

        def from_url(url, **kwargs):
            raise ValueError(f"Invalid URL {url!r}")

        monkeypatch.setattr(page_cache_module.redis, "from_url", from_url)

        assert get_page_cache() is None
