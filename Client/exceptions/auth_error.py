"""
AlderSync Client - Authentication Error Exception

Exception raised for authentication-related errors.

Author: AlderSync Project
"""

from .api_error import AlderSyncAPIError


class AlderSyncAuthError(AlderSyncAPIError):
    """Exception for authentication errors."""
    pass
