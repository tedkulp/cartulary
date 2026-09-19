"""Shared pytest fixtures and test environment setup."""
import os
import socket
from typing import Iterator

import pytest

# app.config instantiates Settings at import time, and DATABASE_URL and
# SECRET_KEY have no defaults. Set them before any app module is imported.
os.environ.setdefault(
    "DATABASE_URL", "postgresql://cartulary:test@localhost:5432/cartulary_test"
)
os.environ.setdefault("SECRET_KEY", "test-secret-key")


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Run contract tests marked 'live' against real model providers.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list) -> None:
    if config.getoption("--live"):
        return
    skip_live = pytest.mark.skip(reason="live contract test; run with --live")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture
def unused_port() -> int:
    """A local port with nothing listening on it."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def silent_server() -> Iterator[str]:
    """A local server that accepts connections but never replies."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        yield f"http://127.0.0.1:{sock.getsockname()[1]}"
