from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_serializer


class ActivityLogBase(BaseModel):
    action: str
    resource_type: str
    resource_id: Optional[UUID] = None
    description: str
    extra_data: Optional[Dict[str, Any]] = None


class ActivityLogCreate(ActivityLogBase):
    user_id: Optional[UUID] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class ActivityLogResponse(ActivityLogBase):
    id: UUID
    user_id: Optional[UUID]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime

    # Optional user email for display
    user_email: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True
    )

    @field_serializer('created_at')
    def serialize_created_at(self, value: datetime) -> str:
        """Serialize datetime to ISO 8601 format string with UTC timezone."""
        if not value:
            return None
        # If naive datetime, assume it's UTC and make it timezone-aware
        if value.tzinfo is None:
            from datetime import timezone
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
