"""Authentication service."""
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, DuplicateError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import Token, UserLogin, UserRegister
from app.schemas.user import UserResponse


class AuthService:
    """Service for handling authentication operations."""

    def __init__(self, db: Session):
        """Initialize auth service with database session."""
        self.db = db

    def register_user(self, user_data: UserRegister) -> UserResponse:
        """
        Register a new user.

        Args:
            user_data: User registration data

        Returns:
            Created user

        Raises:
            DuplicateError: If email or username already exists
        """
        # Check if user already exists
        existing_user = self.db.query(User).filter(
            (User.email == user_data.email) | (User.username == user_data.username)
        ).first()

        if existing_user:
            if existing_user.email == user_data.email:
                raise DuplicateError("Email already registered")
            else:
                raise DuplicateError("Username already taken")

        # Create new user
        hashed_password = get_password_hash(user_data.password)
        db_user = User(
            email=user_data.email,
            username=user_data.username,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            is_active=True,
            is_superuser=False,
        )

        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)

        return UserResponse.model_validate(db_user)

    def authenticate_user(self, login_data: UserLogin) -> Token:
        """
        Authenticate a user and return tokens.

        Args:
            login_data: User login credentials

        Returns:
            Access and refresh tokens

        Raises:
            AuthenticationError: If credentials are invalid
        """
        # Find user by email
        user = self.db.query(User).filter(User.email == login_data.email).first()

        if not user:
            raise AuthenticationError("Incorrect email or password")

        # Verify password
        if not user.hashed_password or not verify_password(login_data.password, user.hashed_password):
            raise AuthenticationError("Incorrect email or password")

        # Check if user is active
        if not user.is_active:
            raise AuthenticationError("User account is disabled")

        # Generate tokens
        access_token = create_access_token(subject=str(user.id))
        refresh_token = create_refresh_token(subject=str(user.id))

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )

    def refresh_access_token(self, user_id: UUID) -> Token:
        """
        Generate new access and refresh tokens.

        Args:
            user_id: User ID from validated refresh token

        Returns:
            New access and refresh tokens

        Raises:
            AuthenticationError: If user not found or inactive
        """
        user = self.db.query(User).filter(User.id == user_id).first()

        if not user:
            raise AuthenticationError("User not found")

        if not user.is_active:
            raise AuthenticationError("User account is disabled")

        # Generate new tokens
        access_token = create_access_token(subject=str(user.id))
        refresh_token = create_refresh_token(subject=str(user.id))

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )

    def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """
        Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User or None if not found
        """
        return self.db.query(User).filter(User.id == user_id).first()
