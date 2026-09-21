"""record terminal import failures

An import source that could not take an attachment in had nowhere to say so: a
Document that was never created carries no error, and the source's `last_error`
is overwritten by the next run. The IMAP watcher therefore logged the failure
and marked the message read anyway, which hid an attachment the archive never
stored.

`import_failures` is that missing place. One row per (source, message,
attachment bytes) records an attachment the source will never accept and why,
which is what lets the message carrying it be completed without the failure
being discarded, and what stops the next pass attempting the same bytes.

The unique index is the identity of the attachment: a message is identified by
its Message-Id where it has one and by UIDVALIDITY and UID otherwise, and the
attachment within it by the SHA-256 that intake already deduplicates by. A
second pass over the same message therefore finds its own record rather than
writing another. See ADR 0011.

Revision ID: 009
Revises: 008
Create Date: 2026-09-21 10:00:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None

INDEX_NAME = 'ux_import_failures_source_message_checksum'


def upgrade() -> None:
    op.create_table(
        'import_failures',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            'import_source_id', postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column('message_key', sa.String(length=512), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('checksum', sa.String(length=64), nullable=False),
        sa.Column('error', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['import_source_id'], ['import_sources.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        INDEX_NAME,
        'import_failures',
        ['import_source_id', 'message_key', 'checksum'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name='import_failures')
    op.drop_table('import_failures')
