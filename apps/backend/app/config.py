"""Application configuration using Pydantic Settings."""
import json
from typing import Any, List, Optional

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # Application
    APP_NAME: str = "Cartulary"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: PostgresDsn

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Storage
    STORAGE_TYPE: str = "local"  # local or s3
    LOCAL_STORAGE_PATH: str = "/data/documents"
    S3_ENDPOINT: Optional[str] = None
    S3_BUCKET: Optional[str] = None
    S3_ACCESS_KEY: Optional[str] = None
    S3_SECRET_KEY: Optional[str] = None

    # Authentication
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> List[str]:
        """Parse CORS origins from JSON string or list."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        return []

    # OCR (Phase 2)
    OCR_ENABLED: bool = False
    OCR_PROVIDER: str = "auto"  # auto, paddleocr, easyocr (auto defaults to paddleocr on x86/ARM detection)
    OCR_LANGUAGES: List[str] = ["en"]
    OCR_USE_GPU: bool = False  # Enable GPU acceleration for OCR if available

    @field_validator("OCR_LANGUAGES", mode="before")
    @classmethod
    def parse_ocr_languages(cls, v: Any) -> List[str]:
        """Parse OCR languages from JSON string or list."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [i.strip() for i in v.split(",")]
        return v

    # Embeddings (Phase 3)
    EMBEDDING_ENABLED: bool = False  # Enable/disable automatic embedding generation
    EMBEDDING_PROVIDER: str = "local"  # local, openai
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"  # For local: all-MiniLM-L6-v2, For OpenAI: text-embedding-3-small
    EMBEDDING_DIMENSION: int = 384  # 384 for MiniLM, 1536 for OpenAI text-embedding-3-small
    EMBEDDING_CHUNK_SIZE: int = 500
    EMBEDDING_CHUNK_OVERLAP: int = 50
    OPENAI_API_KEY: Optional[str] = None  # Required if EMBEDDING_PROVIDER=openai

    # LLM (Phase 4 - Optional)
    LLM_ENABLED: bool = False
    LLM_PROVIDER: str = "openai"  # openai, gemini, ollama
    LLM_MODEL: str = "gpt-4o-mini"  # gpt-4o-mini, gemini-pro, llama2
    LLM_BASE_URL: Optional[str] = None  # For Ollama (default: http://localhost:11434)
    GEMINI_API_KEY: Optional[str] = None  # Required if LLM_PROVIDER=gemini

    # OIDC (Phase 7 - Optional)
    OIDC_ENABLED: bool = False
    OIDC_DISCOVERY_URL: Optional[str] = None  # e.g., https://auth.example.com/.well-known/openid-configuration
    OIDC_CLIENT_ID: Optional[str] = None  # Web client (confidential - requires secret)
    OIDC_CLIENT_SECRET: Optional[str] = None
    OIDC_MOBILE_CLIENT_ID: Optional[str] = None  # Mobile client (public - uses PKCE, no secret)
    OIDC_REDIRECT_URI: str = "http://localhost:8080/auth/callback"  # Frontend callback URL
    OIDC_SCOPES: List[str] = ["openid", "profile", "email"]
    OIDC_AUTO_PROVISION_USERS: bool = True  # Auto-create users on first OIDC login
    OIDC_DEFAULT_ROLE: str = "user"  # Default role for auto-provisioned users
    OIDC_CLAIM_EMAIL: str = "email"  # OIDC claim for email
    OIDC_CLAIM_NAME: str = "name"  # OIDC claim for full name
    OIDC_CLAIM_GROUPS: Optional[str] = None  # Optional OIDC claim for groups/roles

    @field_validator("OIDC_SCOPES", mode="before")
    @classmethod
    def parse_oidc_scopes(cls, v: Any) -> List[str]:
        """Parse OIDC scopes from JSON string or list."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [i.strip() for i in v.split(",") if i.strip()]
        return v or ["openid", "profile", "email"]

    # Import Sources (Phase 6)
    WATCH_DIRECTORIES: List[str] = []
    IMAP_ENABLED: bool = False
    IMAP_SERVER: Optional[str] = None
    IMAP_PORT: int = 993
    IMAP_USERNAME: Optional[str] = None
    IMAP_PASSWORD: Optional[str] = None
    IMAP_FOLDER: str = "INBOX"
    IMAP_PROCESSED_FOLDER: str = "Processed"

    @field_validator("WATCH_DIRECTORIES", mode="before")
    @classmethod
    def parse_watch_directories(cls, v: Any) -> List[str]:
        """Parse watch directories from JSON string or list."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [i.strip() for i in v.split(",") if i.strip()]
        return v or []


settings = Settings()
