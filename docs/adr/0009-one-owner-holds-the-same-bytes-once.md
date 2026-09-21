# One Owner holds the same bytes once, and Postgres is what says so

A Duplicate document is a source file whose original bytes match a Document already in the
same Owner's archive. Intake decided that by looking the checksum up before inserting. Two
intakes of the same bytes that overlap — an HTTP upload while the directory watcher reads the
file it was dropped into, the same attachment delivered twice — both pass that lookup and both
insert, so the archive ends up with the pair the rule forbids.

A unique index on `(owner_id, checksum)` makes the rule the database's. The lookup stays: it
is what names the existing Document in the 409, it costs one indexed read, and it keeps the
common duplicate from ever reaching storage. What changes is that it is no longer the only
thing standing between concurrent intake and two Documents. When the index refuses an insert,
intake rolls back, removes the file it had stored, asks for the Document that won the race and
raises the same `DuplicateError` the lookup raises — so a caller cannot tell which of the two
answered, and HTTP still answers 409 while the directory and IMAP adapters still treat it as
handled (ADR 0006).

The index is partial on `owner_id IS NOT NULL`. Deleting a User sets its Documents' `owner_id`
to NULL rather than removing them, and a Document that belongs to no archive cannot be a
duplicate within one. Postgres would treat those NULLs as distinct without being told; the
predicate says why, and keeps them out of the index. `checksum` is NOT NULL in the schema —
intake computes it for every Document — so it needs no such clause. The model said the column
was nullable and the schema had always said otherwise; the model now agrees with the database.

Existing duplicate groups are not resolved by the migration. Each copy may carry versions,
embeddings, tags, shares and custom fields, and merging or discarding an archived Document is
the archive's decision. The upgrade refuses to run while a group exists and names the
Documents in each, so they are resolved deliberately and the upgrade re-run. A migration that
picked a survivor would be making that decision quietly, and a migration that deleted the
later copies would destroy what the archive is for.

The alternative was serializing intake per `(owner_id, checksum)` in the application — an
advisory lock, or a queue. That is a second mechanism to keep correct, it only holds while
every writer goes through it, and it leaves the table able to hold a state the domain calls
impossible. The index holds regardless of who writes: a repair script, a future importer, a
psql session.

Closes #34.
