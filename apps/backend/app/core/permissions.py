"""Permission checking and authorization helpers."""
import logging
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from fastapi import Depends, HTTPException, status
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

        Args:
            user: User to check
            document: Document to check access for
            required_level: Required permission level (read, write, admin)

        Returns:
            True if user has access, False otherwise
        """
        # Superusers have all access
        if user.is_superuser:
            return True

        # Owner has all access
        if document.owner_id == user.id:
            return True

        # Check if document is public (read-only)
        if document.is_public and required_level == PermissionLevel.READ:
            return True

        # Check document shares
        share = (
            self.db.query(DocumentShare)
            .filter(
                DocumentShare.document_id == document.id,
                DocumentShare.shared_with_user_id == user.id
            )
            .first()
        )

        if share:
            # Check if share has expired
            if share.expires_at and share.expires_at < datetime.utcnow():
                return False

            # Check permission level hierarchy
            return self._check_permission_level(share.permission_level, required_level)

        return False

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
        hierarchy = {
            PermissionLevel.READ: 1,
            PermissionLevel.WRITE: 2,
            PermissionLevel.ADMIN: 3
        }

        return hierarchy.get(granted_level, 0) >= hierarchy.get(required_level, 0)

    def get_accessible_documents_query(self, user: User):
        """
        Get SQLAlchemy query for documents user can access.

        Args:
            user: User to get documents for

        Returns:
            SQLAlchemy query object
        """
        from sqlalchemy import or_
        from sqlalchemy.orm import joinedload

        from sqlalchemy.orm import selectinload

        # Superusers see all documents
        if user.is_superuser:
            return self.db.query(Document).options(selectinload(Document.tags))

        # Get documents where user is owner, document is public, or document is shared with user
        return (
            self.db.query(Document)
            .options(selectinload(Document.tags))
            .outerjoin(DocumentShare, Document.id == DocumentShare.document_id)
            .filter(
                or_(
                    Document.owner_id == user.id,
                    Document.is_public == True,
                    DocumentShare.shared_with_user_id == user.id
                )
            )
            .distinct()
        )


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
