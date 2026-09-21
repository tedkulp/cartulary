"""Permission checking and authorization helpers."""
import logging
from typing import Optional, List
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import func, or_, select, true
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, Permission, Role
from app.models.document import Document
from app.models.sharing import DocumentShare

logger = logging.getLogger(__name__)


class PermissionLevel:
    """Document permission levels."""

    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


# Permission levels ranked weakest to strongest: a share granting a level also
# grants every level below it.
_LEVEL_RANK = {
    PermissionLevel.READ: 1,
    PermissionLevel.WRITE: 2,
    PermissionLevel.ADMIN: 3,
}


def _levels_satisfying(required_level: str) -> List[str]:
    """Permission levels a share may grant and still satisfy `required_level`."""
    required = _LEVEL_RANK.get(required_level, 0)
    return [level for level, rank in _LEVEL_RANK.items() if rank >= required]


def share_is_live() -> ColumnElement[bool]:
    """
    Whether a Share has not expired.

    The one place expiry is decided. Measured against the database clock, so
    every app container agrees on when a share ends. `expires_at` is
    `timestamptz` and `now()` is an instant, so the comparison needs no zone
    conversion and the database's own `TimeZone` setting cannot move it.
    See ADR 0008.

    Returns:
        A boolean expression over `document_shares`
    """
    return or_(
        DocumentShare.expires_at.is_(None),
        DocumentShare.expires_at > func.now(),
    )


def live_share(user: User, required_level: str = PermissionLevel.READ) -> ColumnElement[bool]:
    """
    Whether a live share grants `user` this level on the Document in the enclosing query.

    Args:
        user: User the share must be with
        required_level: Level the share must grant (read, write, admin)

    Returns:
        A correlated EXISTS expression over `document_shares`
    """
    return (
        select(DocumentShare.id)
        .where(
            DocumentShare.document_id == Document.id,
            DocumentShare.shared_with_user_id == user.id,
            DocumentShare.permission_level.in_(_levels_satisfying(required_level)),
            share_is_live(),
        )
        .correlate(Document)
        .exists()
    )


def accessible_documents(
    user: User, required_level: str = PermissionLevel.READ
) -> ColumnElement[bool]:
    """
    The one filter every read of the `documents` table goes through.

    A Document is accessible to a User when they own it, when it is public (read
    only), or when a live share grants them the level asked for. Superusers reach
    everything. `Document.owner_id` is compared here and nowhere else in `app/` —
    `tests/test_access_filter_is_the_only_rule.py` enforces that. See ADR 0004.

    Args:
        user: User the documents must be accessible to
        required_level: Level the user needs (read, write, admin)

    Returns:
        A boolean expression to hand to `.filter()` / `.where()`
    """
    if user.is_superuser:
        return true()

    clauses = [Document.owner_id == user.id]

    # Public documents are readable by anyone, but confer no write or admin.
    if required_level == PermissionLevel.READ:
        clauses.append(Document.is_public.is_(True))

    clauses.append(live_share(user, required_level))

    return or_(*clauses)


class SystemPermissions:
    """System-level permissions."""

    # Document permissions
    DOCUMENTS_READ = "documents:read"
    DOCUMENTS_WRITE = "documents:write"
    DOCUMENTS_DELETE = "documents:delete"
    DOCUMENTS_SHARE = "documents:share"

    # Tag permissions
    TAGS_READ = "tags:read"
    TAGS_WRITE = "tags:write"
    TAGS_DELETE = "tags:delete"

    # User permissions
    USERS_READ = "users:read"
    USERS_WRITE = "users:write"
    USERS_DELETE = "users:delete"

    # Role permissions
    ROLES_READ = "roles:read"
    ROLES_WRITE = "roles:write"
    ROLES_DELETE = "roles:delete"

    # Admin permissions
    ADMIN_ACCESS = "admin:access"


class PermissionService:
    """Service for checking user permissions."""

    def __init__(self, db: Session):
        self.db = db

    def user_has_permission(self, user: User, permission_name: str) -> bool:
        """
        Check if user has a specific system permission.

        Args:
            user: User to check
            permission_name: Permission name (e.g., 'documents:write')

        Returns:
            True if user has permission, False otherwise
        """
        # Superusers have all permissions
        if user.is_superuser:
            return True

        # Check user's roles for this permission
        for role in user.roles:
            for permission in role.permissions:
                if permission.name == permission_name:
                    return True

        return False

    def user_has_any_permission(self, user: User, permission_names: List[str]) -> bool:
        """
        Check if user has any of the specified permissions.

        Args:
            user: User to check
            permission_names: List of permission names

        Returns:
            True if user has at least one permission, False otherwise
        """
        if user.is_superuser:
            return True

        for permission_name in permission_names:
            if self.user_has_permission(user, permission_name):
                return True

        return False

    def user_has_all_permissions(self, user: User, permission_names: List[str]) -> bool:
        """
        Check if user has all of the specified permissions.

        Args:
            user: User to check
            permission_names: List of permission names

        Returns:
            True if user has all permissions, False otherwise
        """
        if user.is_superuser:
            return True

        for permission_name in permission_names:
            if not self.user_has_permission(user, permission_name):
                return False

        return True

    def can_access_document(
        self,
        user: User,
        document: Document,
        required_level: str = PermissionLevel.READ
    ) -> bool:
        """
        Check if user can access a document with the required permission level.

        Asks the database the same question `accessible_documents()` asks, so a
        single document and a list of documents can never disagree about who may
        see what. See ADR 0004.

        Args:
            user: User to check
            document: Document to check access for
            required_level: Required permission level (read, write, admin)

        Returns:
            True if user has access, False otherwise
        """
        found = (
            self.db.query(Document.id)
            .filter(
                Document.id == document.id,
                accessible_documents(user, required_level),
            )
            .first()
        )

        return found is not None

    def _check_permission_level(self, granted_level: str, required_level: str) -> bool:
        """
        Check if granted permission level satisfies required level.

        Permission hierarchy: admin > write > read

        Args:
            granted_level: Permission level user has
            required_level: Permission level required

        Returns:
            True if granted level satisfies required level
        """
        return _LEVEL_RANK.get(granted_level, 0) >= _LEVEL_RANK.get(required_level, 0)


# Dependency functions for FastAPI

def get_permission_service(db: Session = Depends(get_db)) -> PermissionService:
    """Dependency to get permission service."""
    return PermissionService(db)


def require_permission(permission_name: str):
    """
    Dependency factory to require a specific permission.

    Usage:
        @router.get("/admin")
        async def admin_endpoint(
            user: User = Depends(require_permission(SystemPermissions.ADMIN_ACCESS))
        ):
            ...

    Args:
        permission_name: Required permission name

    Returns:
        Dependency function
    """
    from app.dependencies import get_current_user

    async def check_permission(
        current_user: User = Depends(get_current_user),
        permission_service: PermissionService = Depends(get_permission_service)
    ) -> User:
        if not permission_service.user_has_permission(current_user, permission_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: requires {permission_name}"
            )
        return current_user

    return check_permission


def require_any_permission(permission_names: List[str]):
    """
    Dependency factory to require any of the specified permissions.

    Args:
        permission_names: List of permission names (user needs at least one)

    Returns:
        Dependency function
    """
    from app.dependencies import get_current_user

    async def check_permissions(
        current_user: User = Depends(get_current_user),
        permission_service: PermissionService = Depends(get_permission_service)
    ) -> User:
        if not permission_service.user_has_any_permission(current_user, permission_names):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: requires one of {', '.join(permission_names)}"
            )
        return current_user

    return check_permissions


def require_superuser():
    """
    Dependency to require superuser access.

    Returns:
        User if superuser

    Raises:
        HTTPException: If user is not a superuser
    """
    from app.dependencies import get_current_user

    async def check_superuser(current_user: User = Depends(get_current_user)) -> User:
        if not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Superuser access required"
            )
        return current_user

    return check_superuser


def require_document_access(
    required_level: str = PermissionLevel.READ
):
    """
    Dependency factory to check document access.

    Usage:
        @router.get("/documents/{document_id}")
        async def get_document(
            document_id: UUID,
            document: Document = Depends(require_document_access(PermissionLevel.READ))
        ):
            ...

    Args:
        required_level: Required permission level (read, write, admin)

    Returns:
        Dependency function that returns the document if user has access
    """
    from app.dependencies import get_current_user

    async def check_access(
        document_id: UUID,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        permission_service: PermissionService = Depends(get_permission_service)
    ) -> Document:
        # Get document with eagerly loaded tags
        from sqlalchemy.orm import selectinload

        document = db.query(Document).options(
            selectinload(Document.tags)
        ).filter(Document.id == document_id).first()

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        # Check access
        if not permission_service.can_access_document(current_user, document, required_level):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions for this document (requires {required_level})"
            )

        return document

    return check_access
