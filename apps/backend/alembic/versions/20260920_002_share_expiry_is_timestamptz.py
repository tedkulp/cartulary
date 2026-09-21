"""document_shares.expires_at stores an instant

`expires_at` was `timestamp without time zone`. Every writer meant UTC, but the
column did not say so, and `share_is_live()` held the convention up by
converting the database clock down to naive UTC before comparing. Three places
agreeing is not a schema. As `timestamptz` the column carries the zone itself,
the comparison is `expires_at > now()`, and the server's `TimeZone` setting
cannot move when a share ends.

The `USING` clause is the whole point of the migration: without it Postgres
reads the stored values in the server's `TimeZone`, which silently shifts every
existing expiry on a deployment that is not set to UTC.

Revision ID: 007
Revises: 006
Create Date: 2026-09-20 12:00:00.000000

"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'document_shares',
        'expires_at',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_nullable=True,
        postgresql_using="expires_at AT TIME ZONE 'UTC'",
    )


def downgrade():
    op.alter_column(
        'document_shares',
        'expires_at',
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="expires_at AT TIME ZONE 'UTC'",
    )
