# One service owns every Document intake

HTTP upload, watched-directory import and IMAP attachment import all hand source bytes to one
`DocumentIntakeService`. The service accepts bytes, a filename, an Owner, an optional Uploader
and an optional title; it owns validation, checksum deduplication, storage, the database
transaction, processing-task submission and best-effort creation notification. Source-specific
work such as multipart parsing, stable-file detection, moving imported files and disposing of
email remains in the adapters. This boundary replaces three disagreeing implementations and
makes the complete intake use case testable without FastAPI, a watched directory or IMAP (#16).
Adapters may prefilter unsupported extensions to avoid unnecessary reads, but the service remains
the authority and validates every intake itself.

Bytes are the input boundary because every current source can provide them and they make one
small interface; bounded-memory streaming is deferred until observed file sizes justify a more
complex source abstraction. Intake canonicalizes the filename, rejects empty content and the
central unsupported-extension set, and computes the checksum over the original source bytes.
Images are normally stored as PDFs. A valid image is retained with truthful image metadata when
PDF conversion fails; malformed or mislabeled image content is rejected.

A Duplicate document raises one typed error that each adapter translates: HTTP answers 409,
while directory and IMAP adapters treat it as handled. The pre-insert lookup remains advisory in
this change; making per-Owner checksums database-unique needs a separate migration and existing
data policy. Automated imports have no Uploader, so their `uploaded_by` remains NULL and historic
rows are not backfilled.

The service commits before requesting background processing because the task must be able to
load the Document. A storage or database failure rolls back and removes stored files. A task
submission failure cannot roll back the already committed fact: the service marks the Document
failed and still returns it, allowing explicit reprocessing without encouraging a duplicate
intake. Directory and IMAP sources are consequently handled once Cartulary safely owns the
bytes. `document.created` is published once after that initial status is settled; publication is
best-effort and its payload identifies the Owner separately from the nullable Uploader.
For compatibility with existing event consumers, `owner_id` identifies the Owner while the
nullable `user_id` field identifies the Uploader.

If the database is unavailable while recording a queue failure, intake still returns the already
committed Document and reports it as failed to the caller, but its persisted row may remain
pending. Guaranteeing that compensation requires the durable queue delivery deliberately left
outside this change.

Reliable queue delivery, database-enforced deduplication (#34) and durable retry of individual
failed IMAP attachments (#33) are deliberately outside this boundary. They require persistence
and recovery policies of their own rather than hidden behavior inside intake.
