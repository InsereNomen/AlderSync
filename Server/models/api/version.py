"""
AlderSync Server - Version Management API Models

Models for client version checking and auto-update functionality.
"""

from pydantic import BaseModel


class VersionCheckResponse(BaseModel):
    """
    Response model for version check endpoint.

    Returns the latest available client version and whether an update is available.
    """
    current_version: str  # The version the client reported
    latest_version: str   # The latest version available on server
    update_available: bool  # Whether an update is available
    download_url: str  # URL to download the update (if available)


class VersionInfoResponse(BaseModel):
    """
    Response model for getting current version info from server.

    Returns just the latest version without comparison.
    """
    latest_version: str
    download_url: str
