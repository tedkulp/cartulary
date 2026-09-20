"""Shared pytest fixtures and test environment setup."""
import os
import socket
from typing import Iterator

import pytest

# app.config instantiates Settings at import time, and DATABASE_URL and
# SECRET_KEY have no defaults. Set them before any app module is imported.
#
# The default points at the Postgres compose publishes on localhost, with the
# credentials compose uses, but at its own database: tests create and drop rows
# freely and must never do that to a development database.
_DB_PASSWORD = os.environ.get("DB_PASSWORD", "changeme")
os.environ.setdefault(
    "DATABASE_URL",
    f"postgresql://cartulary:{_DB_PASSWORD}@localhost:5432/cartulary_test",
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


NO_DATABASE = """\
These tests need a real PostgreSQL with pgvector, because a mocked Session cannot
tell you which rows a query returns — and which rows a user may see is the whole
question. See ADR 0005.

Locally: bring the compose stack up, which publishes Postgres on localhost. The test
database is created on first run.
Point DATABASE_URL somewhere else if your database lives elsewhere.

Connection failed for {url}: {error}\
"""


def _create_database_if_missing(url) -> None:
    """
    Create the test database if the server does not have it yet.

    Connects to the `postgres` maintenance database to ask, so a fresh checkout
    against a running Postgres needs no manual setup step.
    """
    from sqlalchemy import create_engine, text

    server = create_engine(
        url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )

    with server.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": url.database},
        ).scalar()

        if not exists:
            connection.execute(text(f'CREATE DATABASE "{url.database}"'))

    server.dispose()


@pytest.fixture(scope="session")
def db_engine():
    """
    An engine against a real PostgreSQL, with every table created.

    Session-scoped: building the schema once is the expensive part, and the
    per-test fixture rolls back rather than rebuilding.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.exc import OperationalError

    # Importing the models registers them on Base.metadata.
    import app.models  # noqa: F401
    from app.config import settings
    from app.database import Base

    url = make_url(str(settings.DATABASE_URL))

    try:
        _create_database_if_missing(url)
    except OperationalError as error:
        pytest.fail(NO_DATABASE.format(url=url, error=error), pytrace=False)

    engine = create_engine(url)

    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(engine)

    yield engine

    engine.dispose()


@pytest.fixture
def db_session(db_engine) -> Iterator["Session"]:  # noqa: F821
    """
    A Session whose every write is rolled back when the test ends.

    The session joins an outer transaction on a single connection, so tests can
    commit freely and still leave the database as they found it.
    """
    from sqlalchemy.orm import Session

    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
