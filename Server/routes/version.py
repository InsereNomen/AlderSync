"""
AlderSync Server - Version Management Endpoints

This module contains endpoints for client version checking and updates.
"""

import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, status, Query
from fastapi.responses import FileResponse

from models.database import Setting


# Create logger
logger = logging.getLogger(__name__)

# Create router instance
router = APIRouter()


# ==================== Version Management Endpoints ====================

@router.get("/api/version/check", response_model=dict, tags=["Version"])
async def check_version(client_version: str = Query(..., description="Current client version")):
    """
    Check if a client update is available.

    Compares the provided client version against the latest version stored on the server.

    Args:
        client_version: The version of the client making the request

    Returns:
        dict: Version information including whether an update is available
    """
    from database import db_manager

    session = db_manager.GetSession()

    try:
        # Get latest version from settings
        latest_version_setting = session.query(Setting).filter(Setting.key == "latest_client_version").first()

        if not latest_version_setting:
            # No version configured - return current version as latest
            logger.warning("No latest_client_version setting found in database")
            return {
                "current_version": client_version,
                "latest_version": client_version,
                "update_available": False,
                "download_url": ""
            }

        latest_version = latest_version_setting.value

        # Simple version comparison (assumes semantic versioning like "1.0.0")
        # Returns True if latest > current
        update_available = latest_version != client_version

        # Build download URL
        download_url = "/api/version/download" if update_available else ""

        logger.info(f"Version check: client={client_version}, latest={latest_version}, update_available={update_available}")

        return {
            "current_version": client_version,
            "latest_version": latest_version,
            "update_available": update_available,
            "download_url": download_url
        }

    finally:
        session.close()


@router.get("/api/version/info", tags=["Version"])
async def get_version_info():
    """
    Get the latest client version information.

    Returns information about the latest available client version without
    requiring a version comparison.

    Returns:
        dict: Latest version and download URL
    """
    from database import db_manager

    session = db_manager.GetSession()

    try:
        # Get latest version from settings
        latest_version_setting = session.query(Setting).filter(Setting.key == "latest_client_version").first()

        if not latest_version_setting:
            logger.warning("No latest_client_version setting found in database")
            return {
                "latest_version": "unknown",
                "download_url": ""
            }

        return {
            "latest_version": latest_version_setting.value,
            "download_url": "/api/version/download"
        }

    finally:
        session.close()


@router.get("/api/version/download", tags=["Version"])
async def download_client_update():
    """
    Download the latest client executable.

    Returns the latest client executable file for auto-update.
    The file path is configured in the server settings.

    Returns:
        FileResponse: The client executable file

    Raises:
        HTTPException: If the client file is not found or not configured
    """
    from database import db_manager

    session = db_manager.GetSession()

    try:
        # Get client executable path from settings
        client_path_setting = session.query(Setting).filter(Setting.key == "client_executable_path").first()

        if not client_path_setting:
            logger.error("No client_executable_path setting found in database")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client executable not configured on server"
            )

        client_path = Path(client_path_setting.value)

        # Verify file exists
        if not client_path.exists():
            logger.error(f"Client executable not found at path: {client_path}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client executable file not found on server"
            )

        # Get the latest version for logging
        latest_version_setting = session.query(Setting).filter(Setting.key == "latest_client_version").first()
        version = latest_version_setting.value if latest_version_setting else "unknown"

        logger.info(f"Serving client update download: version={version}, path={client_path}")

        # Return the file
        return FileResponse(
            path=client_path,
            media_type="application/octet-stream",
            filename="aldersync.exe"
        )

    finally:
        session.close()
