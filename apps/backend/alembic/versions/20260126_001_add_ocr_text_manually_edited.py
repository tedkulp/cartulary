"""add ocr_text_manually_edited field

Revision ID: 005
Revises: 004
Create Date: 2026-01-26 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    # Add ocr_text_manually_edited column to documents table
    op.add_column('documents', sa.Column('ocr_text_manually_edited', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    # Remove ocr_text_manually_edited column
    op.drop_column('documents', 'ocr_text_manually_edited')
