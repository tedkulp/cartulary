from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from uuid import UUID

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.activity_log import ActivityLog
from app.schemas.activity_log import ActivityLogResponse

router = APIRouter()


@router.get("/", response_model=List[ActivityLogResponse])
def list_activity_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    resource_type: Optional[str] = None,
    resource_id: Optional[UUID] = None,
    action: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve activity logs with optional filtering.

    Regular users see only their own activities.
    Superusers see all activities.
    """
    query = select(ActivityLog).order_by(desc(ActivityLog.created_at))

    # Filter by user for non-superusers
    if not current_user.is_superuser:
        query = query.where(ActivityLog.user_id == current_user.id)

    # Apply filters
    if resource_type:
        query = query.where(ActivityLog.resource_type == resource_type)
    if resource_id:
        query = query.where(ActivityLog.resource_id == resource_id)
    if action:
        query = query.where(ActivityLog.action == action)

    # Pagination
    query = query.offset(skip).limit(limit)

    result = db.execute(query)
    logs = result.scalars().all()

    # Convert to response format with user email
    response = []
    for log in logs:
        log_dict = {
            "id": log.id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "description": log.description,
            "extra_data": log.extra_data,
            "user_id": log.user_id,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "created_at": log.created_at,
            "user_email": log.user.email if log.user else None
        }
        response.append(ActivityLogResponse(**log_dict))

    return response


@router.get("/me", response_model=List[ActivityLogResponse])
def get_my_activity_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get activity logs for the current user."""
    query = (
        select(ActivityLog)
        .where(ActivityLog.user_id == current_user.id)
        .order_by(desc(ActivityLog.created_at))
        .offset(skip)
        .limit(limit)
    )

    result = db.execute(query)
    logs = result.scalars().all()

    # Convert to response format
    response = []
    for log in logs:
        log_dict = {
            "id": log.id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "description": log.description,
            "extra_data": log.extra_data,
            "user_id": log.user_id,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "created_at": log.created_at,
            "user_email": current_user.email
        }
        response.append(ActivityLogResponse(**log_dict))

    return response
