"""Shared pytest fixtures and test environment setup."""
import os

# app.config instantiates Settings at import time, and DATABASE_URL and
# SECRET_KEY have no defaults. Set them before any app module is imported.
os.environ.setdefault(
    "DATABASE_URL", "postgresql://cartulary:test@localhost:5432/cartulary_test"
)
os.environ.setdefault("SECRET_KEY", "test-secret-key")
