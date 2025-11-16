"""
AlderSync Server - Admin Downloads Endpoints
"""

import logging
from pathlib import Path
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request, File as FastAPIFile, UploadFile, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from models.database import Setting
from routes.admin.auth import RequireAdminSession
from client_downloads import (
    GetClientDownloadsPath, StoreClientExecutable,
    ListClientVersions, GetCurrentClientVersion, DeleteClientVersion, SetActiveClientVersion
)

# Create logger
logger = logging.getLogger(__name__)

# Create router instance
router = APIRouter()

# Get the directory where server.py is located
script_dir = Path(__file__).parent.parent.parent

# Initialize Jinja2 templates
templates = Jinja2Templates(directory=str(script_dir / "templates"))


@router.get("/admin/downloads", response_class=HTMLResponse, tags=["Admin"])
async def admin_downloads_page(
    request: Request,
    session: dict = Depends(RequireAdminSession)
):
    """
    Display client downloads page
    Per Specification.md section 12.1 and Task 7.3

    Shows available client builds for Windows, Mac, and Linux with download links
    and installation instructions.
    """
    context = {
        "request": request,
        "show_nav": True,
        "active_page": "downloads",
        "username": session["username"],
        "is_admin": True  # Downloads page requires admin permission
    }
    return templates.TemplateResponse("downloads.html", context)


@router.get("/admin/api/downloads", tags=["Admin"])
async def admin_get_downloads(
    session: dict = Depends(RequireAdminSession)
):
    """
    Get list of available client downloads
    Per Specification.md section 12.1 and Task 7.3

    Scans the downloads directory for available client build files and returns
    metadata including filename, size, and platform.

    Returns:
        List of available downloads with metadata
    """
    try:
        from pathlib import Path
        import os

        # Define downloads directory path
        downloads_dir = Path("downloads")

        # Create directory if it doesn't exist
        downloads_dir.mkdir(exist_ok=True)

        # Define expected download files and their platforms
        platform_mapping = {
            'aldersync-windows.zip': 'windows',
            'aldersync-mac.zip': 'mac',
            'aldersync-linux.zip': 'linux'
        }

        downloads = []

        # Check for each expected file
        for filename, platform in platform_mapping.items():
            file_path = downloads_dir / filename
            if file_path.exists() and file_path.is_file():
                # Get file size
                file_size = file_path.stat().st_size

                downloads.append({
                    'filename': filename,
                    'platform': platform,
                    'size': file_size
                })

        logger.info(f"Admin '{session['username']}' viewed downloads page ({len(downloads)} files available)")

        return downloads

    except Exception as e:
        logger.error(f"Error getting downloads: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve downloads")


@router.get("/admin/downloads/file/{filename}", tags=["Admin"])
async def admin_download_file(
    filename: str,
    session: dict = Depends(RequireAdminSession)
):
    """
    Download a client build file
    Per Specification.md section 12.1 and Task 7.3

    Serves the requested client build file for download.

    Args:
        filename: Name of the file to download
        session: Admin session from dependency

    Returns:
        FileResponse with the requested file

    Raises:
        HTTPException: If file not found or invalid filename
    """
    try:
        from pathlib import Path

        # Validate filename to prevent directory traversal attacks
        allowed_files = ['aldersync-windows.zip', 'aldersync-mac.zip', 'aldersync-linux.zip']
        if filename not in allowed_files:
            raise HTTPException(status_code=400, detail="Invalid filename")

        # Define downloads directory path
        downloads_dir = Path("downloads")
        file_path = downloads_dir / filename

        # Check if file exists
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")

        logger.info(f"Admin '{session['username']}' downloaded client build: {filename}")

        # Return file as download
        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type='application/zip'
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file '{filename}': {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to download file")


# ==================== Admin Client Downloads Endpoints ====================

@router.get("/admin/downloads", response_class=HTMLResponse, tags=["Admin"])
async def admin_downloads_page(
    request: Request,
    session: dict = Depends(RequireAdminSession)
):
    """
    Display client downloads management page.

    Allows admins to upload new client versions and manage existing downloads.
    """
    context = {
        "request": request,
        "show_nav": True,
        "active_page": "downloads",
        "username": session["username"],
        "is_admin": True  # Downloads page requires admin permission
    }
    return templates.TemplateResponse("downloads.html", context)


@router.get("/admin/api/downloads/list", tags=["Admin"])
async def admin_list_client_versions(
    session: dict = Depends(RequireAdminSession)
):
    """
    List all available client versions.

    Returns:
        List of client version information
    """
    try:
        from database import db_manager
        versions = ListClientVersions(db_manager)
        current_version = GetCurrentClientVersion(db_manager)

        # Mark the current version
        for version in versions:
            version["is_current"] = version["version"] == current_version

        return {
            "versions": versions,
            "current_version": current_version
        }

    except Exception as e:
        logger.error(f"Error listing client versions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list client versions")


@router.post("/admin/api/downloads/upload", tags=["Admin"])
async def admin_upload_client(
    file: UploadFile = FastAPIFile(...),
    version: str = Form(...),
    platform: str = Form(default="windows"),
    session: dict = Depends(RequireAdminSession)
):
    """
    Upload a new client executable.

    Args:
        file: The executable file
        version: Version string (e.g., "1.0.1")
        platform: Platform identifier ("windows", "macos", or "linux")
        session: Admin session from dependency

    Returns:
        Success status and version information
    """
    try:
        # Validate version format (basic check for X.Y.Z format)
        version_parts = version.split(".")
        if len(version_parts) != 3 or not all(part.isdigit() for part in version_parts):
            raise HTTPException(
                status_code=400,
                detail="Version must be in format X.Y.Z (e.g., 1.0.1)"
            )

        # Validate platform
        if platform not in ["windows", "macos", "linux"]:
            raise HTTPException(
                status_code=400,
                detail="Platform must be 'windows', 'macos', or 'linux'"
            )

        # Validate file extension matches platform
        filename_lower = file.filename.lower()
        if platform == "windows" and not filename_lower.endswith(".exe"):
            raise HTTPException(
                status_code=400,
                detail="Windows executable must have .exe extension"
            )
        elif platform == "macos" and not filename_lower.endswith(".app"):
            # Note: macOS apps are actually directories, but for simplicity we accept .app files
            raise HTTPException(
                status_code=400,
                detail="macOS executable must have .app extension"
            )

        # Read file data
        file_data = await file.read()

        if len(file_data) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        # Store the executable
        from database import db_manager
        result = StoreClientExecutable(db_manager, file_data, version, platform)

        logger.info(f"Admin '{session['username']}' uploaded client version {version} ({platform})")

        return {
            "success": True,
            "message": f"Client version {version} uploaded successfully",
            "version": result["version"],
            "filename": result["filename"],
            "size": result["size"],
            "platform": result["platform"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading client: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload client: {str(e)}")


@router.post("/admin/api/downloads/set_active", tags=["Admin"])
async def admin_set_active_version(
    version: str = Form(...),
    session: dict = Depends(RequireAdminSession)
):
    """
    Set a specific version as the active/latest client version.

    Args:
        version: Version to set as active
        session: Admin session from dependency

    Returns:
        Success status
    """
    try:
        from database import db_manager
        success = SetActiveClientVersion(db_manager, version)

        if not success:
            raise HTTPException(status_code=404, detail=f"Version {version} not found")

        logger.info(f"Admin '{session['username']}' set active client version to {version}")

        return {
            "success": True,
            "message": f"Active client version set to {version}",
            "version": version
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting active version: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to set active version")


@router.delete("/admin/api/downloads/delete/{version}", tags=["Admin"])
async def admin_delete_client_version(
    version: str,
    session: dict = Depends(RequireAdminSession)
):
    """
    Delete a client version (if it's not the current version).

    Args:
        version: Version to delete
        session: Admin session from dependency

    Returns:
        Success status
    """
    try:
        from database import db_manager
        success = DeleteClientVersion(db_manager, version)

        if not success:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the current active version"
            )

        logger.info(f"Admin '{session['username']}' deleted client version {version}")

        return {
            "success": True,
            "message": f"Client version {version} deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting client version: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete client version")

