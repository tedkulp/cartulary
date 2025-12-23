"""add extracted_document_type

Revision ID: 004
Revises: 882b5a43975b
Create Date: 2025-12-23 02:13:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '882b5a43975b'
branch_labels = None
depends_on = None


def upgrade():
    # Add extracted_document_type column to documents table
    op.add_column('documents', sa.Column('extracted_document_type', sa.String(length=100), nullable=True))


def downgrade():
    # Remove extracted_document_type column from documents table
    op.drop_column('documents', 'extracted_document_type')
