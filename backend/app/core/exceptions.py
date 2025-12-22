"""Custom exceptions for the application."""


class TrapperException(Exception):
    """Base exception for Trapper application."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
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

    def __init__(self, message: str = "Resource already exists"):
        super().__init__(message, status_code=409)
