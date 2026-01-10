"""User schemas."""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True


class UserCreate(UserBase):
    """Schema for creating a user."""

    password: str
    is_superuser: Optional[bool] = False


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None
    is_superuser: Optional[bool] = None


class UserInDB(UserBase):
    """Schema for user in database."""

    id: UUID
    is_superuser: bool
    oidc_sub: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserResponse(UserBase):
    """Schema for user response (without sensitive data)."""

    id: UUID
    is_superuser: bool
    created_at: datetime
    roles: List['RoleResponse'] = []

    class Config:
        from_attributes = True


# ===== Role Schemas =====

class RoleBase(BaseModel):
    """Base role schema."""

    name: str
    description: Optional[str] = None


class RoleCreate(RoleBase):
    """Schema for creating a role."""

    pass


class RoleUpdate(BaseModel):
    """Schema for updating a role."""

    name: Optional[str] = None
    description: Optional[str] = None


class RoleResponse(RoleBase):
    """Schema for role response."""

    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# ===== Permission Schemas =====

class PermissionBase(BaseModel):
    """Base permission schema."""

    name: str
    description: Optional[str] = None


class PermissionResponse(PermissionBase):
    """Schema for permission response."""

    id: UUID

    class Config:
        from_attributes = True


# ===== User Group Schemas =====

class UserGroupBase(BaseModel):
    """Base user group schema."""

    name: str
    description: Optional[str] = None


class UserGroupCreate(UserGroupBase):
    """Schema for creating a user group."""

    pass


class UserGroupUpdate(BaseModel):
    """Schema for updating a user group."""

    name: Optional[str] = None
    description: Optional[str] = None


class UserGroupResponse(UserGroupBase):
    """Schema for user group response."""

    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True
