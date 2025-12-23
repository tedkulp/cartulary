"""Document and related models."""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.database import Base


class Document(Base):
    """Document model."""

    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # File information
    title = Column(String(500), nullable=False)
    description = Column(Text)  # Optional user description
    original_filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    mime_type = Column(String(100))
    checksum = Column(String(64), index=True)  # SHA-256 hash for deduplication

    # Extracted content
    ocr_text = Column(Text)  # Full OCR extracted text
    ocr_language = Column(String(10))  # Detected language
    page_count = Column(Integer)

    # LLM-extracted metadata
    extracted_title = Column(String(500))
    extracted_date = Column(Date)
    extracted_correspondent = Column(String(255))
    extracted_document_type = Column(String(100))
    extracted_summary = Column(Text)

    # Ownership and permissions
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))  # Who uploaded (may differ from owner)
    is_public = Column(Boolean, default=False, nullable=False)

    # Processing status
    processing_status = Column(
        String(50),
        default="pending",
        nullable=False,
        index=True
    )  # pending, processing, ocr_complete, embedding_complete, llm_complete, failed
    processing_error = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    document_date = Column(Date)  # User-specified or extracted date

    # Full-text search vector (populated via trigger or application code)
    # search_vector = Column(TSVector)  # Will be added in migration

    # Relationships
    owner = relationship("User", back_populates="owned_documents", foreign_keys=[owner_id])
    uploader = relationship("User", foreign_keys=[uploaded_by])
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")
    embeddings = relationship("DocumentEmbedding", back_populates="document", cascade="all, delete-orphan")
    tags = relationship("Tag", secondary="document_tags", back_populates="documents")
    categories = relationship("Category", secondary="document_categories", back_populates="documents")
    shares = relationship("DocumentShare", back_populates="document", cascade="all, delete-orphan")
    custom_field_values = relationship("DocumentCustomField", back_populates="document", cascade="all, delete-orphan")


class DocumentVersion(Base):
    """Document version model for tracking file versions."""

    __tablename__ = "document_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    document = relationship("Document", back_populates="versions")


class DocumentEmbedding(Base):
    """Document embedding model for semantic search."""

    __tablename__ = "document_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer)  # For chunked documents
    chunk_text = Column(Text)  # The text that was embedded
    # Import settings to get configured dimension
    from app.config import settings
    embedding = Column(Vector(settings.EMBEDDING_DIMENSION))  # Dynamic dimension based on provider
    embedding_model = Column(String(100))  # Track which model generated this
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    document = relationship("Document", back_populates="embeddings")


class CustomField(Base):
    """Custom field definition for flexible metadata."""

    __tablename__ = "custom_fields"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    field_type = Column(String(50), nullable=False)  # text, number, date, boolean, select
    options = Column(JSONB)  # For select type fields
    is_required = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    document_values = relationship("DocumentCustomField", back_populates="field", cascade="all, delete-orphan")


class DocumentCustomField(Base):
    """Custom field values for documents."""

    __tablename__ = "document_custom_fields"

    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    field_id = Column(UUID(as_uuid=True), ForeignKey("custom_fields.id", ondelete="CASCADE"), primary_key=True)
    value = Column(JSONB, nullable=False)

    # Relationships
    document = relationship("Document", back_populates="custom_field_values")
    field = relationship("CustomField", back_populates="document_values")


class ImportSource(Base):
    """Import source configuration for automated document ingestion."""

    __tablename__ = "import_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type = Column(String(50), nullable=False)  # directory_watch, imap, api_upload
    name = Column(String(255), nullable=False)
    config = Column(JSONB, nullable=False)  # Store path, IMAP settings, etc.
    is_active = Column(Boolean, default=True, nullable=False)
    last_check = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AuditLog(Base):
    """Audit log for tracking document operations."""

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    action = Column(String(100), nullable=False)  # view, download, edit, delete, share
    resource_type = Column(String(50))  # document, tag, user
    resource_id = Column(UUID(as_uuid=True))
    details = Column(JSONB)
    ip_address = Column(String(45))  # IPv6 compatible
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
