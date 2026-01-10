"""OIDC authentication service."""
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import httpx
from authlib.integrations.starlette_client import OAuth
from authlib.oauth2.rfc6749 import OAuth2Token

from app.config import settings
from app.models.user import User
from sqlalchemy.orm import Session
import uuid

logger = logging.getLogger(__name__)


class OIDCService:
    """Service for handling OIDC authentication."""

    def __init__(self):
        """Initialize OIDC service."""
        self.enabled = settings.OIDC_ENABLED
        self.discovery_url = settings.OIDC_DISCOVERY_URL
        self.client_id = settings.OIDC_CLIENT_ID
        self.client_secret = settings.OIDC_CLIENT_SECRET
        self.redirect_uri = settings.OIDC_REDIRECT_URI
        self.scopes = " ".join(settings.OIDC_SCOPES)

        self._metadata: Optional[Dict[str, Any]] = None
        self.oauth = None

        if self.enabled:
            self._initialize_oauth()

    def _initialize_oauth(self):
        """Initialize OAuth client."""
        try:
            # Create OAuth instance
            self.oauth = OAuth()

            # Register OIDC provider
            self.oauth.register(
                name='oidc',
                client_id=self.client_id,
                client_secret=self.client_secret,
                server_metadata_url=self.discovery_url,
                client_kwargs={
                    'scope': self.scopes
                }
            )

            logger.info(f"OIDC service initialized with discovery URL: {self.discovery_url}")
        except Exception as e:
            logger.error(f"Failed to initialize OIDC service: {e}", exc_info=True)
            self.enabled = False

    async def get_provider_metadata(self) -> Dict[str, Any]:
        """Fetch OIDC provider metadata from discovery endpoint.

        Returns:
            Provider metadata dictionary
        """
        if self._metadata:
            return self._metadata

        if not self.discovery_url:
            raise ValueError("OIDC discovery URL not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.discovery_url)
                response.raise_for_status()
                self._metadata = response.json()
                logger.info("OIDC provider metadata fetched successfully")
                return self._metadata
        except Exception as e:
            logger.error(f"Failed to fetch OIDC provider metadata: {e}", exc_info=True)
            raise

    def get_authorization_url(self, state: str) -> tuple[str, str]:
        """Generate authorization URL for OIDC login.

        Args:
            state: Random state parameter for CSRF protection

        Returns:
            Tuple of (authorization_url, state)
        """
        if not self.enabled:
            raise ValueError("OIDC is not enabled")

        # Get provider metadata synchronously for URL construction
        # Note: In production, this should be cached
        try:
            # Build authorization URL manually
            metadata = self._get_metadata_sync()
            auth_endpoint = metadata.get('authorization_endpoint')

            if not auth_endpoint:
                raise ValueError("Authorization endpoint not found in provider metadata")

            # Build query parameters
            params = {
                'client_id': self.client_id,
                'redirect_uri': self.redirect_uri,
                'response_type': 'code',
                'scope': self.scopes,
                'state': state
            }

            # Construct URL
            query_string = '&'.join(f"{k}={v}" for k, v in params.items())
            authorization_url = f"{auth_endpoint}?{query_string}"

            return authorization_url, state
        except Exception as e:
            logger.error(f"Failed to generate authorization URL: {e}", exc_info=True)
            raise

    def _get_metadata_sync(self) -> Dict[str, Any]:
        """Fetch provider metadata synchronously.

        Returns:
            Provider metadata dictionary
        """
        if self._metadata:
            return self._metadata

        try:
            response = httpx.get(self.discovery_url, timeout=10)
            response.raise_for_status()
            self._metadata = response.json()
            return self._metadata
        except Exception as e:
            logger.error(f"Failed to fetch provider metadata: {e}", exc_info=True)
            raise

    async def exchange_code_for_token(self, code: str) -> OAuth2Token:
        """Exchange authorization code for access token.

        Args:
            code: Authorization code from OIDC provider

        Returns:
            OAuth2 token with access_token and id_token
        """
        if not self.enabled:
            raise ValueError("OIDC is not enabled")

        try:
            metadata = await self.get_provider_metadata()
            token_endpoint = metadata.get('token_endpoint')

            if not token_endpoint:
                raise ValueError("Token endpoint not found in provider metadata")

            # Exchange code for token
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    token_endpoint,
                    data={
                        'grant_type': 'authorization_code',
                        'code': code,
                        'redirect_uri': self.redirect_uri,
                        'client_id': self.client_id,
                        'client_secret': self.client_secret
                    },
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
                response.raise_for_status()
                token_data = response.json()

                logger.info("Successfully exchanged code for token")
                return OAuth2Token(token_data)
        except Exception as e:
            logger.error(f"Failed to exchange code for token: {e}", exc_info=True)
            raise

    async def get_userinfo(self, access_token: str) -> Dict[str, Any]:
        """Fetch user information from OIDC provider.

        Args:
            access_token: Access token from OIDC provider

        Returns:
            User information dictionary
        """
        if not self.enabled:
            raise ValueError("OIDC is not enabled")

        try:
            metadata = await self.get_provider_metadata()
            userinfo_endpoint = metadata.get('userinfo_endpoint')

            if not userinfo_endpoint:
                raise ValueError("Userinfo endpoint not found in provider metadata")

            # Fetch user info
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    userinfo_endpoint,
                    headers={'Authorization': f'Bearer {access_token}'}
                )
                response.raise_for_status()
                userinfo = response.json()

                logger.info(f"Fetched user info for subject: {userinfo.get('sub')}")
                return userinfo
        except Exception as e:
            logger.error(f"Failed to fetch user info: {e}", exc_info=True)
            raise

    def get_or_create_user(
        self,
        userinfo: Dict[str, Any],
        db: Session
    ) -> User:
        """Get existing user or create new one from OIDC userinfo.

        Args:
            userinfo: User information from OIDC provider
            db: Database session

        Returns:
            User instance
        """
        # Get OIDC subject (unique identifier)
        oidc_sub = userinfo.get('sub')
        if not oidc_sub:
            raise ValueError("OIDC subject (sub) not found in userinfo")

        # Get email from userinfo
        email = userinfo.get(settings.OIDC_CLAIM_EMAIL)
        if not email:
            raise ValueError(f"Email claim '{settings.OIDC_CLAIM_EMAIL}' not found in userinfo")

        # Try to find existing user by OIDC subject
        user = db.query(User).filter(User.oidc_sub == oidc_sub).first()

        if user:
            # Update user information from latest OIDC data
            full_name = userinfo.get(settings.OIDC_CLAIM_NAME)

            if email and user.email != email:
                user.email = email
            if full_name and user.full_name != full_name:
                user.full_name = full_name

            user.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(user)

            logger.info(f"Updated existing user from OIDC: {user.email}")
            return user

        # Try to find existing user by email (in case they registered before OIDC was enabled)
        user = db.query(User).filter(User.email == email).first()

        if user:
            # Link existing user account to OIDC
            user.oidc_sub = oidc_sub

            # Update user information from OIDC data
            full_name = userinfo.get(settings.OIDC_CLAIM_NAME)
            if full_name:
                user.full_name = full_name

            user.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(user)

            logger.info(f"Linked existing user to OIDC: {user.email}")
            return user

        # Auto-provision new user if enabled
        if not settings.OIDC_AUTO_PROVISION_USERS:
            raise ValueError(
                f"User with email {email} does not exist and "
                "auto-provisioning is disabled"
            )

        # Create new user
        full_name = userinfo.get(settings.OIDC_CLAIM_NAME, email)

        # Determine is_superuser from groups claim if configured
        is_superuser = (settings.OIDC_DEFAULT_ROLE.lower() == 'superuser')
        if settings.OIDC_CLAIM_GROUPS:
            groups = userinfo.get(settings.OIDC_CLAIM_GROUPS, [])
            if isinstance(groups, list):
                # Map groups to superuser status (customize as needed)
                groups_lower = [g.lower() for g in groups]
                if 'superuser' in groups_lower or 'admin' in groups_lower:
                    is_superuser = True

        user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password="",  # No password for OIDC users
            full_name=full_name,
            is_active=True,
            is_superuser=is_superuser,
            oidc_sub=oidc_sub,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        logger.info(f"Auto-provisioned new user from OIDC: {user.email} (superuser={is_superuser})")
        return user


# Global OIDC service instance
oidc_service = OIDCService()
