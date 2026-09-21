"""one Document per Owner and checksum

Intake deduplicated by looking for the checksum before inserting, which two
concurrent intakes of the same bytes can both pass. A unique index makes the
domain rule — the same original bytes appear at most once in one Owner's
archive — the database's to keep, so the loser of that race is refused instead
of stored twice.

The index is partial on `owner_id IS NOT NULL`. Deleting a User sets its
Documents' `owner_id` to NULL, and a Document that belongs to nobody cannot be
a duplicate within an archive. `checksum` is NOT NULL, so every Document that
has an Owner takes part. Postgres already treats NULL owners as distinct; the
clause says why rather than leaving it to that default.

Existing duplicates are not resolved here. Each copy may carry versions,
embeddings, tags, shares and custom fields, and which copy to keep is the
archive's decision, not a migration's. The upgrade therefore refuses to run
while any group exists and names the Documents, so they can be merged or
deleted deliberately and the upgrade re-run.

The index is built in the migration's transaction rather than CONCURRENTLY, which
holds a write lock on `documents` for the build. That is what makes the refusal
above mean anything: a concurrent build takes no such lock, so an intake could
insert the duplicate between the check and the build, and leave an index marked
invalid behind. Should the table grow past what a brief lock can cover, the
replacement is a concurrent build plus a validation step, not dropping the check.

Revision ID: 008
Revises: 007
Create Date: 2026-09-20 14:00:00.000000

"""
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None

DUPLICATE_GROUPS = text(
    """
    SELECT owner_id, checksum, array_agg(id ORDER BY created_at, id) AS documents
    FROM documents
    WHERE owner_id IS NOT NULL
    GROUP BY owner_id, checksum
    HAVING count(*) > 1
    ORDER BY owner_id, checksum
    """
)

STILL_DUPLICATED = """\
{count} group(s) of Documents share an Owner and a checksum, which this \
migration is about to forbid. Keep one Document of each group and remove the \
others — each may carry versions, embeddings, tags, shares and custom fields, \
so which one survives is yours to decide — then run the upgrade again.

{groups}\
"""


def upgrade():
    groups = op.get_bind().execute(DUPLICATE_GROUPS).all()
    if groups:
        listed = "\n".join(
            f"  owner {owner_id} checksum {checksum}: "
            + ", ".join(str(document_id) for document_id in documents)
            for owner_id, checksum, documents in groups
        )
        raise RuntimeError(STILL_DUPLICATED.format(count=len(groups), groups=listed))

    op.create_index(
        'uq_documents_owner_checksum',
        'documents',
        ['owner_id', 'checksum'],
        unique=True,
        postgresql_where=text('owner_id IS NOT NULL'),
    )


def downgrade():
    op.drop_index('uq_documents_owner_checksum', table_name='documents')
