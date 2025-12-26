from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class ActivityLog(Base):
    """Activity/Audit log for tracking user actions."""
    __tablename__ = "activity_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False, index=True)  # e.g., "document.upload", "document.delete"
    resource_type = Column(String(50), nullable=False, index=True)  # e.g., "document", "user", "role"
    resource_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # ID of the affected resource
    description = Column(Text, nullable=False)  # Human-readable description
    extra_data = Column(JSON, nullable=True)  # Additional context data
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(String(500), nullable=True)  # Browser/client info
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self):
        return f"<ActivityLog {self.action} by user {self.user_id} at {self.created_at}>"
