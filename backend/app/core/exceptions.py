"""Custom exceptions for the application."""
from typing import Any, Optional


class TrapperException(Exception):
    """Base exception for Trapper application."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        detail: Optional[dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}
        super().__init__(self.message)


class AuthenticationError(TrapperException):
    """Exception raised for authentication errors."""

    def __init__(self, message: str = "Could not validate credentials"):
        super().__init__(message, status_code=401)


class PermissionDeniedError(TrapperException):
    """Exception raised when user doesn't have permission."""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, status_code=403)


class NotFoundError(TrapperException):
    """Exception raised when resource is not found."""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class DuplicateError(TrapperException):
    """Exception raised when trying to create duplicate resource."""

    def __init__(
        self,
        message: str = "Resource already exists",
        detail: Optional[dict[str, Any]] = None
    ):
        super().__init__(message, status_code=409, detail=detail)
