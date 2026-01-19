"""OIDC authentication endpoints."""
import logging
import secrets
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
import redis

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


class OIDCTokenRequest(BaseModel):
    """Request body for mobile OIDC token exchange."""
    id_token: str
    access_token: str


class OIDCStateStore:
    """Redis-based state store for OIDC CSRF protection.

    Stores state tokens in Redis with TTL for automatic cleanup.
    Works across container restarts and multiple workers.
    """

    STATE_PREFIX = "oidc:state:"
    STATE_TTL = 600  # 10 minutes

    def __init__(self):
        self._redis: Optional[redis.Redis] = None

    def _get_redis(self) -> redis.Redis:
        """Lazy initialization of Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    def create_state(self) -> str:
        """Create a new state token and store in Redis."""
        state = secrets.token_urlsafe(32)
        key = f"{self.STATE_PREFIX}{state}"
        self._get_redis().setex(key, self.STATE_TTL, "1")
        logger.debug(f"Created OIDC state token: {state[:8]}...")
        return state

    def verify_state(self, state: str) -> bool:
        """Verify and consume a state token (atomic operation)."""
        key = f"{self.STATE_PREFIX}{state}"
        # Use DELETE which returns the number of keys deleted (1 if existed, 0 if not)
        # This is atomic - only one request can successfully delete the key
        deleted = self._get_redis().delete(key)
        result = deleted > 0
        logger.debug(f"Verified OIDC state token: {state[:8]}... = {result}")
        return result


state_store = OIDCStateStore()


@router.get("/config", response_model=OIDCConfigResponse)
async def get_oidc_config():
    """Get OIDC configuration for mobile apps.

    Returns OIDC provider information if enabled.
    Mobile apps get the mobile client ID (public client with PKCE).
    """
    if not settings.OIDC_ENABLED:
        return OIDCConfigResponse(enabled=False)

    # For mobile apps, return mobile client ID (public client, no secret required)
    # Falls back to web client ID if mobile client ID not configured
    mobile_client_id = settings.OIDC_MOBILE_CLIENT_ID or settings.OIDC_CLIENT_ID

    return OIDCConfigResponse(
        enabled=True,
        authorization_url=settings.OIDC_DISCOVERY_URL if settings.OIDC_ENABLED else None,
        client_id=mobile_client_id
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


@router.post("/token", response_model=OIDCCallbackResponse)
async def exchange_oidc_token(
    request: OIDCTokenRequest,
    db: Session = Depends(get_db)
):
    """Exchange OIDC tokens for application JWT tokens (mobile app endpoint).

    Mobile apps handle the OAuth flow natively and send us the OIDC tokens
    to exchange for our application's JWT tokens.
    """
    if not settings.OIDC_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="OIDC authentication is not enabled"
        )

    try:
        logger.info(f"Attempting OIDC token exchange (mobile)")
        logger.debug(f"ID token length: {len(request.id_token)}, Access token length: {len(request.access_token)}")

        # For mobile apps, try to decode and verify the ID token directly first
        # This is more reliable than calling userinfo with a token from a different client
        try:
            import jwt
            from jwt import PyJWKClient

            # Get the JWKS URL from OIDC discovery
            metadata = await oidc_service.get_provider_metadata()
            jwks_uri = metadata.get('jwks_uri')

            if jwks_uri:
                # Verify and decode the ID token
                jwks_client = PyJWKClient(jwks_uri)
                signing_key = jwks_client.get_signing_key_from_jwt(request.id_token)

                userinfo = jwt.decode(
                    request.id_token,
                    signing_key.key,
                    algorithms=["RS256"],
                    audience=settings.OIDC_MOBILE_CLIENT_ID or settings.OIDC_CLIENT_ID,
                    options={"verify_exp": True}
                )
                logger.info(f"Successfully decoded and verified ID token for subject: {userinfo.get('sub')}")
            else:
                # Fallback to userinfo endpoint
                logger.warning("No jwks_uri found, falling back to userinfo endpoint")
                userinfo = await oidc_service.get_userinfo(request.access_token)

        except Exception as jwt_error:
            logger.warning(f"ID token verification failed, trying userinfo endpoint: {jwt_error}")
            # Fallback to userinfo endpoint
            userinfo = await oidc_service.get_userinfo(request.access_token)

        # Get or create user in database
        user = oidc_service.get_or_create_user(userinfo, db)

        # Create JWT tokens for our application
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)

        logger.info(f"OIDC token exchange successful for user: {user.email}")

        return OIDCCallbackResponse(
            access_token=access_token,
            refresh_token=refresh_token
        )

    except Exception as e:
        logger.error(f"OIDC token exchange failed: {e}", exc_info=True)

        # Check if it's a userinfo fetch error
        error_msg = str(e)
        if "401" in error_msg or "Unauthorized" in error_msg:
            logger.error("OIDC provider rejected the access token - check token validity and scopes")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OIDC token exchange failed: {str(e)}"
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
