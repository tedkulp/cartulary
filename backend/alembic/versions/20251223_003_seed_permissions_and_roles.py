"""Seed permissions and default roles

Revision ID: 003
Revises: 002
Create Date: 2025-12-23 16:45:00.000000

"""
from typing import Sequence, Union
from datetime import datetime
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Get connection for data operations
    connection = op.get_bind()

    # Define all system permissions
    permissions = [
        # Document permissions
        {'name': 'documents:read', 'description': 'Read documents'},
        {'name': 'documents:write', 'description': 'Create and edit documents'},
        {'name': 'documents:delete', 'description': 'Delete documents'},
        {'name': 'documents:share', 'description': 'Share documents with other users'},

        # Tag permissions
        {'name': 'tags:read', 'description': 'Read tags'},
        {'name': 'tags:write', 'description': 'Create and edit tags'},
        {'name': 'tags:delete', 'description': 'Delete tags'},

        # User permissions
        {'name': 'users:read', 'description': 'View users'},
        {'name': 'users:write', 'description': 'Create and edit users'},
        {'name': 'users:delete', 'description': 'Delete users'},

        # Role permissions
        {'name': 'roles:read', 'description': 'View roles'},
        {'name': 'roles:write', 'description': 'Create and edit roles'},
        {'name': 'roles:delete', 'description': 'Delete roles'},

        # Admin permissions
        {'name': 'admin:access', 'description': 'Access admin panel'},
    ]

    # Insert permissions and store their IDs
    permission_ids = {}
    for perm in permissions:
        perm_id = str(uuid.uuid4())
        connection.execute(
            sa.text(
                "INSERT INTO permissions (id, name, description) "
                "VALUES (:id, :name, :description)"
            ),
            {'id': perm_id, 'name': perm['name'], 'description': perm['description']}
        )
        permission_ids[perm['name']] = perm_id

    # Define default roles
    roles = [
        {
            'name': 'user',
            'description': 'Standard user with basic permissions',
            'permissions': [
                'documents:read',
                'documents:write',
                'documents:delete',
                'documents:share',
                'tags:read',
                'tags:write',
                'tags:delete',
            ]
        },
        {
            'name': 'admin',
            'description': 'Administrator with elevated permissions',
            'permissions': [
                'documents:read',
                'documents:write',
                'documents:delete',
                'documents:share',
                'tags:read',
                'tags:write',
                'tags:delete',
                'users:read',
                'users:write',
                'roles:read',
                'admin:access',
            ]
        },
        {
            'name': 'superuser',
            'description': 'Superuser with all permissions',
            'permissions': list(permission_ids.keys())  # All permissions
        }
    ]

    # Insert roles and role_permissions
    for role in roles:
        role_id = str(uuid.uuid4())
        connection.execute(
            sa.text(
                "INSERT INTO roles (id, name, description, created_at) "
                "VALUES (:id, :name, :description, :created_at)"
            ),
            {
                'id': role_id,
                'name': role['name'],
                'description': role['description'],
                'created_at': datetime.utcnow()
            }
        )

        # Insert role_permissions associations
        for perm_name in role['permissions']:
            connection.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id) "
                    "VALUES (:role_id, :permission_id)"
                ),
                {
                    'role_id': role_id,
                    'permission_id': permission_ids[perm_name]
                }
            )


def downgrade() -> None:
    # Get connection for data operations
    connection = op.get_bind()

    # Delete all role_permissions associations
    connection.execute(sa.text("DELETE FROM role_permissions"))

    # Delete all roles
    connection.execute(sa.text("DELETE FROM roles"))

    # Delete all permissions
    connection.execute(sa.text("DELETE FROM permissions"))
