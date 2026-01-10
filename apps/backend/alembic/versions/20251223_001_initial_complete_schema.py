"""Initial complete schema

Revision ID: 001
Revises:
Create Date: 2025-12-23 16:00:00.000000

"""
from typing import Sequence, Union
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Get embedding dimension from environment variable, default to 1536
EMBEDDING_DIMENSION = int(os.getenv('EMBEDDING_DIMENSION', '1536'))


def upgrade() -> None:
    # Create extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create enum types
    op.execute("CREATE TYPE role AS ENUM ('user', 'admin', 'superuser')")
    op.execute("CREATE TYPE importsourcetype AS ENUM ('directory', 'imap')")
    op.execute("CREATE TYPE importsourcestatus AS ENUM ('active', 'paused', 'error')")

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('role', postgresql.ENUM('user', 'admin', 'superuser', name='role', create_type=False), nullable=False, server_default='user'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('oidc_sub', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_oidc_sub', 'users', ['oidc_sub'], unique=True)

    # Create tags table
    op.create_table(
        'tags',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('color', sa.String(length=7), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL')
    )
    op.create_index('ix_tags_name', 'tags', ['name'], unique=True)

    # Create categories table
    op.create_table(
        'categories',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['parent_id'], ['categories.id'], ondelete='CASCADE')
    )
    op.create_index('ix_categories_name', 'categories', ['name'], unique=True)

    # Create documents table
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('original_filename', sa.String(length=500), nullable=False),
        sa.Column('file_path', sa.String(length=1000), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('checksum', sa.String(length=64), nullable=False),
        sa.Column('ocr_text', sa.Text(), nullable=True),
        sa.Column('ocr_language', sa.String(length=10), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('extracted_title', sa.String(length=500), nullable=True),
        sa.Column('extracted_date', sa.Date(), nullable=True),
        sa.Column('extracted_correspondent', sa.String(length=255), nullable=True),
        sa.Column('extracted_document_type', sa.String(length=100), nullable=True),
        sa.Column('extracted_summary', sa.Text(), nullable=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('processing_status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('document_date', sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='SET NULL')
    )
    op.create_index('ix_documents_owner_id', 'documents', ['owner_id'])
    op.create_index('ix_documents_checksum', 'documents', ['checksum'])
    op.create_index('ix_documents_processing_status', 'documents', ['processing_status'])

    # Create document_tags association table
    op.create_table(
        'document_tags',
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tag_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('is_auto_tagged', sa.Boolean(), server_default='false'),
        sa.Column('tagged_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('document_id', 'tag_id'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE')
    )

    # Create document_categories association table
    op.create_table(
        'document_categories',
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint('document_id', 'category_id'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='CASCADE')
    )

    # Create document_versions table
    op.create_table(
        'document_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(length=1000), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL')
    )
    op.create_index('ix_document_versions_document_id', 'document_versions', ['document_id'])

    # Create custom_fields table
    op.create_table(
        'custom_fields',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('field_type', sa.String(length=50), nullable=False),
        sa.Column('options', postgresql.JSONB(), nullable=True),
        sa.Column('is_required', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create document_custom_fields table
    op.create_table(
        'document_custom_fields',
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('field_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('value', postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint('document_id', 'field_id'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['field_id'], ['custom_fields.id'], ondelete='CASCADE')
    )

    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=True),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('details', postgresql.JSONB(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL')
    )
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])

    # Create document_embeddings table (without embedding column initially)
    op.create_table(
        'document_embeddings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=True),
        sa.Column('chunk_text', sa.Text(), nullable=True),
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=True),  # Temporary placeholder
        sa.Column('embedding_model', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE')
    )
    # Convert embedding column to proper vector type with dimension
    op.execute(f'ALTER TABLE document_embeddings ALTER COLUMN embedding TYPE vector({EMBEDDING_DIMENSION})')
    op.create_index('ix_document_embeddings_document_id', 'document_embeddings', ['document_id'])

    # Create document_shares table
    op.create_table(
        'document_shares',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('shared_with_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('shared_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('permission_level', sa.String(length=20), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['shared_with_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['shared_by_user_id'], ['users.id'], ondelete='SET NULL')
    )
    op.create_index('ix_document_shares_document_id', 'document_shares', ['document_id'])
    op.create_index('ix_document_shares_shared_with_user_id', 'document_shares', ['shared_with_user_id'])

    # Create import_sources table
    op.create_table(
        'import_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('source_type', postgresql.ENUM('directory', 'imap', name='importsourcetype', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM('active', 'paused', 'error', name='importsourcestatus', create_type=False), nullable=False),

        # Directory-specific fields
        sa.Column('watch_path', sa.Text(), nullable=True),
        sa.Column('move_after_import', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('move_to_path', sa.Text(), nullable=True),
        sa.Column('delete_after_import', sa.Boolean(), nullable=False, server_default='false'),

        # IMAP-specific fields
        sa.Column('imap_server', sa.String(length=255), nullable=True),
        sa.Column('imap_port', sa.Integer(), nullable=True),
        sa.Column('imap_username', sa.String(length=255), nullable=True),
        sa.Column('imap_password', sa.String(length=255), nullable=True),
        sa.Column('imap_use_ssl', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('imap_mailbox', sa.String(length=255), nullable=True, server_default='INBOX'),
        sa.Column('imap_processed_folder', sa.String(length=255), nullable=True),

        # Common fields
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('last_run', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_import_sources_owner_id', 'import_sources', ['owner_id'])
    op.create_index('ix_import_sources_status', 'import_sources', ['status'])


def downgrade() -> None:
    # Drop tables in reverse order (respecting foreign key dependencies)
    op.drop_index('ix_import_sources_status', table_name='import_sources')
    op.drop_index('ix_import_sources_owner_id', table_name='import_sources')
    op.drop_table('import_sources')

    op.drop_index('ix_document_shares_shared_with_user_id', table_name='document_shares')
    op.drop_index('ix_document_shares_document_id', table_name='document_shares')
    op.drop_table('document_shares')

    op.drop_index('ix_document_embeddings_document_id', table_name='document_embeddings')
    op.drop_table('document_embeddings')

    op.drop_index('ix_audit_logs_created_at', table_name='audit_logs')
    op.drop_table('audit_logs')

    op.drop_table('document_custom_fields')
    op.drop_table('custom_fields')

    op.drop_index('ix_document_versions_document_id', table_name='document_versions')
    op.drop_table('document_versions')

    op.drop_table('document_categories')
    op.drop_table('document_tags')

    op.drop_index('ix_documents_processing_status', table_name='documents')
    op.drop_index('ix_documents_checksum', table_name='documents')
    op.drop_index('ix_documents_owner_id', table_name='documents')
    op.drop_table('documents')

    op.drop_index('ix_categories_name', table_name='categories')
    op.drop_table('categories')

    op.drop_index('ix_tags_name', table_name='tags')
    op.drop_table('tags')

    op.drop_index('ix_users_oidc_sub', table_name='users')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')

    # Drop enum types
    op.execute('DROP TYPE importsourcestatus')
    op.execute('DROP TYPE importsourcetype')
    op.execute('DROP TYPE role')
