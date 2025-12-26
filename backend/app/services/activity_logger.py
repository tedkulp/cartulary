from typing import Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import Request

from app.models.activity_log import ActivityLog
from app.models.user import User


class ActivityLogger:
    """Service for logging user activities."""

    @staticmethod
    def log(
        db: Session,
        action: str,
        resource_type: str,
        description: str,
        user: Optional[User] = None,
        resource_id: Optional[UUID] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
    ) -> ActivityLog:
        """
        Log an activity.

        Args:
            db: Database session
            action: Action performed (e.g., "document.upload", "user.login")
            resource_type: Type of resource (e.g., "document", "user")
            description: Human-readable description
            user: User who performed the action (optional)
            resource_id: ID of the affected resource (optional)
            extra_data: Additional context data (optional)
            request: FastAPI request object for IP/user agent (optional)
        """
        ip_address = None
        user_agent = None

        if request:
            # Get IP address
            ip_address = request.client.host if request.client else None

            # Get user agent
            user_agent = request.headers.get("user-agent")

        log_entry = ActivityLog(
            user_id=user.id if user else None,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            extra_data=extra_data,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)

        return log_entry

    @staticmethod
    def log_document_upload(
        db: Session,
        user: User,
        document_id: UUID,
        filename: str,
        request: Optional[Request] = None,
    ):
        """Log document upload activity."""
        return ActivityLogger.log(
            db=db,
            action="document.upload",
            resource_type="document",
            description=f"Uploaded document: {filename}",
            user=user,
            resource_id=document_id,
            extra_data={"filename": filename},
            request=request,
        )

    @staticmethod
    def log_document_delete(
        db: Session,
        user: User,
        document_id: UUID,
        filename: str,
        request: Optional[Request] = None,
    ):
        """Log document deletion activity."""
        return ActivityLogger.log(
            db=db,
            action="document.delete",
            resource_type="document",
            description=f"Deleted document: {filename}",
            user=user,
            resource_id=document_id,
            extra_data={"filename": filename},
            request=request,
        )

    @staticmethod
    def log_user_login(
        db: Session,
        user: User,
        login_method: str = "password",
        request: Optional[Request] = None,
    ):
        """Log user login activity."""
        return ActivityLogger.log(
            db=db,
            action="user.login",
            resource_type="user",
            description=f"User logged in via {login_method}",
            user=user,
            resource_id=user.id,
            extra_data={"login_method": login_method},
            request=request,
        )

    @staticmethod
    def log_document_share(
        db: Session,
        user: User,
        document_id: UUID,
        shared_with_email: str,
        request: Optional[Request] = None,
    ):
        """Log document sharing activity."""
        return ActivityLogger.log(
            db=db,
            action="document.share",
            resource_type="document",
            description=f"Shared document with {shared_with_email}",
            user=user,
            resource_id=document_id,
            extra_data={"shared_with": shared_with_email},
            request=request,
        )
