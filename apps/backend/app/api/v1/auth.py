"""Authentication API endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, DuplicateError
from app.core.security import decode_token
from app.dependencies import get_auth_service, get_current_user, get_db
from app.models.user import User
from app.schemas.auth import Token, TokenRefresh, UserLogin, UserRegister
from app.schemas.user import UserResponse, UserProfileUpdate
from app.core.security import get_password_hash
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Register a new user.

    Args:
        user_data: User registration data
        auth_service: Authentication service

    Returns:
        Created user

    Raises:
        HTTPException: If email or username already exists
    """
    try:
        user = auth_service.register_user(user_data)
        return user
    except DuplicateError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message
        )


@router.post("/login", response_model=Token)
async def login(
    login_data: UserLogin,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Login and get access/refresh tokens.

    Args:
        login_data: User login credentials
        auth_service: Authentication service

    Returns:
        Access and refresh tokens

    Raises:
        HTTPException: If credentials are invalid
    """
    try:
        tokens = auth_service.authenticate_user(login_data)
        return tokens
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_data: TokenRefresh,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Refresh access token using refresh token.

    Args:
        token_data: Refresh token
        auth_service: Authentication service

    Returns:
        New access and refresh tokens

    Raises:
        HTTPException: If refresh token is invalid
    """
    # Decode refresh token
    payload = decode_token(token_data.refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check token type
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user ID from token
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        tokens = auth_service.refresh_access_token(user_id)
        return tokens
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user information.

    Args:
        current_user: Current authenticated user

    Returns:
        Current user data
    """
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    user_data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update the current user's own profile (name, email, password).

    OIDC-provisioned users cannot update their profile here — identity
    is managed by the external provider.
    """
    if current_user.oidc_sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile is managed by your identity provider and cannot be changed here"
        )

    if user_data.email is not None:
        existing = db.query(User).filter(
            User.email == user_data.email,
            User.id != current_user.id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        current_user.email = user_data.email

    if user_data.full_name is not None:
        current_user.full_name = user_data.full_name

    if user_data.password is not None:
        current_user.hashed_password = get_password_hash(user_data.password)

    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)
