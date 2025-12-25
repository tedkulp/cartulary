"""OIDC authentication endpoints."""
import logging
import secrets
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.config import settings
from app.services.oidc_service import oidc_service
from app.core.security import create_access_token, create_refresh_token

logger = logging.getLogger(__name__)

router = APIRouter()


class OIDCConfigResponse(BaseModel):
    """OIDC configuration response."""
    enabled: bool
    authorization_url: Optional[str] = None
    client_id: Optional[str] = None


class OIDCCallbackResponse(BaseModel):
    """OIDC callback response with tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class OIDCStateStore:
    """Simple in-memory state store for OIDC CSRF protection.

    In production, use Redis or database for distributed systems.
    """

    def __init__(self):
        self._states: dict[str, bool] = {}

    def create_state(self) -> str:
        """Create a new state token."""
        state = secrets.token_urlsafe(32)
        self._states[state] = True
        return state

    def verify_state(self, state: str) -> bool:
        """Verify and consume a state token."""
        return self._states.pop(state, False)


state_store = OIDCStateStore()


@router.get("/config", response_model=OIDCConfigResponse)
async def get_oidc_config():
    """Get OIDC configuration for frontend.

    Returns OIDC provider information if enabled.
    """
    if not settings.OIDC_ENABLED:
        return OIDCConfigResponse(enabled=False)

    return OIDCConfigResponse(
        enabled=True,
        client_id=settings.OIDC_CLIENT_ID
    )


@router.get("/login")
async def oidc_login():
    """Initiate OIDC login flow.

    Redirects user to OIDC provider's authorization endpoint.
    """
    if not settings.OIDC_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="OIDC authentication is not enabled"
        )

    try:
        # Generate state for CSRF protection
        state = state_store.create_state()

        # Get authorization URL
        authorization_url, _ = oidc_service.get_authorization_url(state)

        logger.info(f"Redirecting to OIDC provider: {authorization_url}")

        return RedirectResponse(url=authorization_url)

    except Exception as e:
        logger.error(f"OIDC login failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate OIDC login: {str(e)}"
        )


@router.get("/callback", response_model=OIDCCallbackResponse)
async def oidc_callback(
    code: str = Query(..., description="Authorization code from OIDC provider"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    db: Session = Depends(get_db)
):
    """Handle OIDC callback from provider.

    Exchanges authorization code for tokens and creates/updates user.
    """
    if not settings.OIDC_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="OIDC authentication is not enabled"
        )

    # Verify state to prevent CSRF
    if not state_store.verify_state(state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter"
        )

    try:
        # Exchange code for token
        token = await oidc_service.exchange_code_for_token(code)

        # Get user info from OIDC provider
        userinfo = await oidc_service.get_userinfo(token['access_token'])

        # Get or create user in database
        user = oidc_service.get_or_create_user(userinfo, db)

        # Create JWT tokens for our application
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)

        logger.info(f"OIDC authentication successful for user: {user.email}")

        return OIDCCallbackResponse(
            access_token=access_token,
            refresh_token=refresh_token
        )

    except Exception as e:
        logger.error(f"OIDC callback failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OIDC authentication failed: {str(e)}"
        )


@router.post("/logout")
async def oidc_logout():
    """Handle OIDC logout.

    In a full implementation, this would also call the OIDC provider's
    logout endpoint to end the session there as well.
    """
    # For now, just return success
    # The frontend will clear tokens
    # In production, you might want to:
    # 1. Invalidate refresh tokens in database
    # 2. Call OIDC provider's end_session_endpoint
    # 3. Redirect to post_logout_redirect_uri

    return {"message": "Logged out successfully"}
