"""index document_shares by sharee and document

Every read of the documents table now runs a correlated EXISTS over
document_shares, filtering on shared_with_user_id and document_id together. The
two single-column indexes each match half of that. Sharee first matches the
query's shape: pin the user, then probe the document.

Revision ID: 006
Revises: 005
Create Date: 2026-09-20 10:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        'ix_document_shares_sharee_document',
        'document_shares',
        ['shared_with_user_id', 'document_id'],
    )


def downgrade():
    op.drop_index('ix_document_shares_sharee_document', table_name='document_shares')
