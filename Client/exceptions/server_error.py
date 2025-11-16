"""
AlderSync Client - Server Error Exception

Exception raised for server-related errors.

Author: AlderSync Project
"""

from .api_error import AlderSyncAPIError


class AlderSyncServerError(AlderSyncAPIError):
    """Exception for server errors."""
    pass
