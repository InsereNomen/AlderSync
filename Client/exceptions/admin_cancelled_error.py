"""
AlderSync Client - Admin Cancelled Error Exception

Exception raised when an operation is cancelled by an administrator.

Author: AlderSync Project
"""

from .api_error import AlderSyncAPIError


class AlderSyncAdminCancelledError(AlderSyncAPIError):
    """Exception raised when operation is cancelled by administrator."""
    pass
