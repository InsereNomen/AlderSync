"""
AlderSync Client - Exceptions Package

Contains all exception classes for the AlderSync client.

Author: AlderSync Project
"""

from .api_error import AlderSyncAPIError
from .auth_error import AlderSyncAuthError
from .server_error import AlderSyncServerError
from .admin_cancelled_error import AlderSyncAdminCancelledError

__all__ = [
    'AlderSyncAPIError',
    'AlderSyncAuthError',
    'AlderSyncServerError',
    'AlderSyncAdminCancelledError'
]
