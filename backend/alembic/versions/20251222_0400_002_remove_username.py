"""remove username from users

Revision ID: 002_remove_username
Revises: 001_initial_schema
Create Date: 2025-12-22 04:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_remove_username'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the unique constraint on username first
    op.drop_constraint('users_username_key', 'users', type_='unique')

    # Drop the username column
    op.drop_column('users', 'username')


def downgrade() -> None:
    # Add username column back
    op.add_column('users', sa.Column('username', sa.String(length=100), nullable=True))

    # Populate username with email prefix for existing users
    op.execute("UPDATE users SET username = split_part(email, '@', 1) WHERE username IS NULL")

    # Make username non-nullable
    op.alter_column('users', 'username', nullable=False)

    # Recreate unique constraint
    op.create_unique_constraint('users_username_key', 'users', ['username'])
