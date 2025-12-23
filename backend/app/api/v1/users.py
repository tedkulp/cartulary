"""User and role management API endpoints."""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.core.permissions import (
    SystemPermissions,
    require_permission,
    get_permission_service,
    PermissionService
)
from app.core.security import get_password_hash
from app.dependencies import get_current_user
from app.database import get_db
from app.models.user import User, Role, Permission, UserGroup
from app.schemas.user import (
    UserResponse,
    UserCreate,
    UserUpdate,
    RoleResponse,
    RoleCreate,
    RoleUpdate,
    PermissionResponse,
    UserGroupResponse,
    UserGroupCreate,
    UserGroupUpdate
)

router = APIRouter()


# ===== User Management =====

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_permission(SystemPermissions.USERS_READ)),
    db: Session = Depends(get_db)
):
    """List all users (requires users:read permission)."""
    users = db.query(User).options(selectinload(User.roles)).offset(skip).limit(limit).all()
    return users


@router.get("/users/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current user's information."""
    return current_user


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user: User = Depends(require_permission(SystemPermissions.USERS_READ)),
    db: Session = Depends(get_db)
):
    """Get a specific user by ID."""
    user = db.query(User).options(selectinload(User.roles)).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(require_permission(SystemPermissions.USERS_WRITE)),
    db: Session = Depends(get_db)
):
    """Create a new user (requires users:write permission)."""
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create user
    db_user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        is_active=user_data.is_active if user_data.is_active is not None else True,
        is_superuser=user_data.is_superuser if user_data.is_superuser is not None else False
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    current_user: User = Depends(require_permission(SystemPermissions.USERS_WRITE)),
    db: Session = Depends(get_db)
):
    """Update a user (requires users:write permission)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Update fields if provided
    if user_data.email is not None:
        # Check if new email is already taken
        existing = db.query(User).filter(
            User.email == user_data.email,
            User.id != user_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        user.email = user_data.email

    if user_data.full_name is not None:
        user.full_name = user_data.full_name

    if user_data.password is not None:
        user.hashed_password = get_password_hash(user_data.password)

    if user_data.is_active is not None:
        user.is_active = user_data.is_active

    if user_data.is_superuser is not None:
        # Only superusers can change superuser status
        if not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only superusers can change superuser status"
            )
        user.is_superuser = user_data.is_superuser

    db.commit()
    db.refresh(user)

    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    current_user: User = Depends(require_permission(SystemPermissions.USERS_DELETE)),
    db: Session = Depends(get_db)
):
    """Delete a user (requires users:delete permission)."""
    # Prevent self-deletion
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own user account"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    db.delete(user)
    db.commit()


# ===== Role Management =====

@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(
    current_user: User = Depends(require_permission(SystemPermissions.ROLES_READ)),
    db: Session = Depends(get_db)
):
    """List all roles (requires roles:read permission)."""
    roles = db.query(Role).all()
    return roles


@router.get("/roles/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: UUID,
    current_user: User = Depends(require_permission(SystemPermissions.ROLES_READ)),
    db: Session = Depends(get_db)
):
    """Get a specific role by ID."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    return role


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    current_user: User = Depends(require_permission(SystemPermissions.ROLES_WRITE)),
    db: Session = Depends(get_db)
):
    """Create a new role (requires roles:write permission)."""
    # Check if role name already exists
    existing_role = db.query(Role).filter(Role.name == role_data.name).first()
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role name already exists"
        )

    # Create role
    db_role = Role(
        name=role_data.name,
        description=role_data.description
    )

    db.add(db_role)
    db.commit()
    db.refresh(db_role)

    return db_role


@router.patch("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: UUID,
    role_data: RoleUpdate,
    current_user: User = Depends(require_permission(SystemPermissions.ROLES_WRITE)),
    db: Session = Depends(get_db)
):
    """Update a role (requires roles:write permission)."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    # Update fields if provided
    if role_data.name is not None:
        # Check if new name is already taken
        existing = db.query(Role).filter(
            Role.name == role_data.name,
            Role.id != role_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role name already exists"
            )
        role.name = role_data.name

    if role_data.description is not None:
        role.description = role_data.description

    db.commit()
    db.refresh(role)

    return role


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: UUID,
    current_user: User = Depends(require_permission(SystemPermissions.ROLES_DELETE)),
    db: Session = Depends(get_db)
):
    """Delete a role (requires roles:delete permission)."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    db.delete(role)
    db.commit()


# ===== Permission Management =====

@router.get("/permissions", response_model=List[PermissionResponse])
async def list_permissions(
    current_user: User = Depends(require_permission(SystemPermissions.ROLES_READ)),
    db: Session = Depends(get_db)
):
    """List all available permissions."""
    permissions = db.query(Permission).all()
    return permissions


# ===== Role-Permission Assignments =====

@router.post("/roles/{role_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_permission_to_role(
    role_id: UUID,
    permission_id: UUID,
    current_user: User = Depends(require_permission(SystemPermissions.ROLES_WRITE)),
    db: Session = Depends(get_db)
):
    """Add a permission to a role."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    permission = db.query(Permission).filter(Permission.id == permission_id).first()
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found"
        )

    # Add permission to role if not already present
    if permission not in role.permissions:
        role.permissions.append(permission)
        db.commit()


@router.delete("/roles/{role_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_permission_from_role(
    role_id: UUID,
    permission_id: UUID,
    current_user: User = Depends(require_permission(SystemPermissions.ROLES_WRITE)),
    db: Session = Depends(get_db)
):
    """Remove a permission from a role."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    permission = db.query(Permission).filter(Permission.id == permission_id).first()
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found"
        )

    # Remove permission from role
    if permission in role.permissions:
        role.permissions.remove(permission)
        db.commit()


# ===== User-Role Assignments =====

@router.post("/users/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def assign_role_to_user(
    user_id: UUID,
    role_id: UUID,
    current_user: User = Depends(require_permission(SystemPermissions.USERS_WRITE)),
    db: Session = Depends(get_db)
):
    """Assign a role to a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    # Add role to user if not already assigned
    if role not in user.roles:
        user.roles.append(role)
        db.commit()


@router.delete("/users/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_role_from_user(
    user_id: UUID,
    role_id: UUID,
    current_user: User = Depends(require_permission(SystemPermissions.USERS_WRITE)),
    db: Session = Depends(get_db)
):
    """Remove a role from a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    # Remove role from user
    if role in user.roles:
        user.roles.remove(role)
        db.commit()


# ===== User Group Management =====

@router.get("/groups", response_model=List[UserGroupResponse])
async def list_groups(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all user groups."""
    groups = db.query(UserGroup).all()
    return groups


@router.get("/groups/{group_id}", response_model=UserGroupResponse)
async def get_group(
    group_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific user group by ID."""
    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    return group


@router.post("/groups", response_model=UserGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    group_data: UserGroupCreate,
    current_user: User = Depends(require_permission(SystemPermissions.USERS_WRITE)),
    db: Session = Depends(get_db)
):
    """Create a new user group."""
    # Check if group name already exists
    existing_group = db.query(UserGroup).filter(UserGroup.name == group_data.name).first()
    if existing_group:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Group name already exists"
        )

    # Create group
    db_group = UserGroup(
        name=group_data.name,
        description=group_data.description
    )

    db.add(db_group)
    db.commit()
    db.refresh(db_group)

    return db_group


@router.patch("/groups/{group_id}", response_model=UserGroupResponse)
async def update_group(
    group_id: UUID,
    group_data: UserGroupUpdate,
    current_user: User = Depends(require_permission(SystemPermissions.USERS_WRITE)),
    db: Session = Depends(get_db)
):
    """Update a user group."""
    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )

    # Update fields if provided
    if group_data.name is not None:
        # Check if new name is already taken
        existing = db.query(UserGroup).filter(
            UserGroup.name == group_data.name,
            UserGroup.id != group_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Group name already exists"
            )
        group.name = group_data.name

    if group_data.description is not None:
        group.description = group_data.description

    db.commit()
    db.refresh(group)

    return group


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: UUID,
    current_user: User = Depends(require_permission(SystemPermissions.USERS_WRITE)),
    db: Session = Depends(get_db)
):
    """Delete a user group."""
    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )

    db.delete(group)
    db.commit()


# ===== Group Membership =====

@router.post("/groups/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_user_to_group(
    group_id: UUID,
    user_id: UUID,
    current_user: User = Depends(require_permission(SystemPermissions.USERS_WRITE)),
    db: Session = Depends(get_db)
):
    """Add a user to a group."""
    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Add user to group if not already a member
    if user not in group.members:
        group.members.append(user)
        db.commit()


@router.delete("/groups/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user_from_group(
    group_id: UUID,
    user_id: UUID,
    current_user: User = Depends(require_permission(SystemPermissions.USERS_WRITE)),
    db: Session = Depends(get_db)
):
    """Remove a user from a group."""
    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Remove user from group
    if user in group.members:
        group.members.remove(user)
        db.commit()
