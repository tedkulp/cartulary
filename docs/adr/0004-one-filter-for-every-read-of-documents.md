# Every read of the documents table goes through one filter

"Which Documents can this user see" is answered in exactly one place: `accessible_documents(user, required_level)` in `app/core/permissions.py`, a boolean SQLAlchemy expression handed to `.filter()`. A Document is accessible when the user owns it, when it is public (read level only), or when a **live share** — one that has not expired — grants the level asked for. Superusers reach everything.

Before this, the question had two answers. `get_accessible_documents_query` honoured `is_public` and `DocumentShare`, and had a single call site: the document list. Full-text search, semantic search, hybrid search, RAG chat and the four `DocumentService` read methods all filtered on `owner_id` alone. Sharing arrived in Phase 5 and search was never updated for it, so a document shared with you appeared in your list and could not be found by any of the three search modes (#15).

Expiry had fared worse: three answers. `can_access_document` compared `expires_at` to the app's clock, `GET /shared-with-me` compared it to the app's clock again in its own query, and the list query did not check it at all — so a lapsed share still listed a document that 403'd when opened. Expiry is now one expression, `share_is_live()`, which `accessible_documents` and `/shared-with-me` both call.

Three shapes were considered. Exporting both an expression and a matching SQL string for the raw pgvector query keeps two representations of one rule, which is the duplication being removed. A Postgres view or function gives both callers one definition but moves the access rules into migrations, away from the tests that check them. The third — the one taken — is a single expression, which required the semantic search to stop being raw SQL.

That rewrite was the price and turned out to be a refund. `document_embeddings.embedding` is already a `pgvector.sqlalchemy.Vector` column, so `cosine_distance()` composes in the ORM and the `DISTINCT ON` shape survives unchanged. The query embedding becomes a bound parameter instead of an f-string, and semantic hits are now real `Document` entities rather than objects rebuilt from twelve selected columns — which had been silently dropping `owner_id`, `is_public`, tags and the extracted metadata from every semantic result.

The filter is an `EXISTS` over `document_shares`, not a join. A join needs `DISTINCT` to stop two shares duplicating a document, and `DISTINCT` fights both `DISTINCT ON` in the semantic query and `OFFSET`/`LIMIT` pagination in the list. Expiry is measured against the database clock (`timezone('UTC', now())`), so app containers cannot disagree about when a share ends.

## Consequences

- One rule reaches six read paths, so searching now finds documents shared with you and public documents — including in RAG chat, where the assistant will quote them. That is a visible behaviour change, not just a bug fix.
- Access rules get one test file instead of five scattered assertions, and `tests/test_access_filter_is_the_only_rule.py` fails the moment `Document.owner_id ==` or `DocumentShare.expires_at` appears under `app/` outside this module. A line that is not an access check — per-owner deduplication on upload and on import — opts out with a trailing `# not an access check:` comment.
- Services take a `User` rather than a `user_id`, because the expression needs `is_superuser`. The signature change is the enforcement: a read path cannot be written against an id that carries no access information.
- `can_access_document` now asks the database instead of inspecting a loaded `Document`, which costs one small query per permission-checked request. That is the price of the two answers being one answer.
- The four uncalled `DocumentService` read methods were deleted rather than fixed. They duplicated what the `require_document_access` dependency already does.
- `document_shares.expires_at` remains a naive `DateTime`. The comparison converts `now()` to UTC to match it; making the column `timestamptz` is the real fix and is deliberately left out of this change.
