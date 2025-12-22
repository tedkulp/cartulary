"""add description and uploaded_by to documents

Revision ID: 003
Revises: 002
Create Date: 2025-12-22 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add description column
    op.add_column('documents', sa.Column('description', sa.Text(), nullable=True))

    # Add uploaded_by column (nullable for automated imports)
    op.add_column('documents', sa.Column('uploaded_by', UUID(as_uuid=True), nullable=True))

    # Add foreign key constraint for uploaded_by
    op.create_foreign_key(
        'fk_documents_uploaded_by',
        'documents',
        'users',
        ['uploaded_by'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Drop foreign key constraint
    op.drop_constraint('fk_documents_uploaded_by', 'documents', type_='foreignkey')

    # Drop columns
    op.drop_column('documents', 'uploaded_by')
    op.drop_column('documents', 'description')
