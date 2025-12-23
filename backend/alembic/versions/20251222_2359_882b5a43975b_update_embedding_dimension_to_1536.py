"""update_embedding_dimension_to_1536

Revision ID: 882b5a43975b
Revises: 003
Create Date: 2025-12-22 23:59:42.005319

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '882b5a43975b'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop existing embeddings (they're for the wrong dimension anyway)
    op.execute("DELETE FROM document_embeddings")

    # Change the vector column dimension from 384 to 1536
    # pgvector doesn't support ALTER COLUMN for dimension changes, so we need to:
    # 1. Drop the column
    # 2. Add it back with new dimension
    op.drop_column('document_embeddings', 'embedding')
    op.execute("ALTER TABLE document_embeddings ADD COLUMN embedding vector(1536)")


def downgrade() -> None:
    # Reverse the change (back to 384 dimensions)
    op.execute("DELETE FROM document_embeddings")
    op.drop_column('document_embeddings', 'embedding')
    op.execute("ALTER TABLE document_embeddings ADD COLUMN embedding vector(384)")
