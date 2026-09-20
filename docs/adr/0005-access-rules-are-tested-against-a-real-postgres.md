# Access rules are tested against a real Postgres

`tests/test_document_access.py` runs against a live PostgreSQL with pgvector, supplied by the `db_session` fixture and, in CI, by a `pgvector/pgvector:pg16` service container. Every other test in this repo mocks the `Session`, so this file needs a reason.

The reason is that a mocked session cannot answer the question being asked. Mocking a `Session` records that `.filter()` was called with an expression; it cannot say which rows come back. For OCR, embeddings and the provider adapters that is fine — the interesting behaviour is in the Python around the query. For access control the interesting behaviour *is* the query: whether a correlated `EXISTS` matches, whether an expired share is excluded, whether a public document confers write, whether two shares duplicate a row. A test that asserts the code calls `accessible_documents()` proves only that the code calls `accessible_documents()`, and the defect this replaces (#15) was precisely a query that looked reasonable and returned the wrong rows.

Compiling the query and asserting on the rendered SQL was considered. It is infrastructure-free, and it tests the string rather than the result — the same class of test, one step further from the truth.

The fixture builds the schema once per session from `Base.metadata`, and each test runs inside a transaction that is rolled back, so tests neither see each other's rows nor need the schema rebuilt. When the database is unreachable the fixture fails with an explicit message rather than skipping: a silently skipped access-control test is the failure this whole change exists to prevent.

## Consequences

- `just test-backend` now needs the Postgres that compose publishes on localhost. A contributor without the stack up gets a clear failure naming the fixture and how to satisfy it, not a mystery.
- CI gained a service container and roughly 10–15 seconds of startup on every run.
- There are now two kinds of backend test. The distinction is not "unit vs integration" but "does the assertion depend on what the database returns." Tests that do belong in a `db_session` file; the rest stay mocked, which keeps the suite fast.
- The fixture is general — any future rule whose truth lives in a query can use it rather than inventing another way to fake a database.
