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
from routes.admin.auth import RequireAdminSession, RequireSession
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
    session: dict = Depends(RequireSession)
):
    """
    Display client downloads management page.

    Allows all authenticated users to view downloads.
    Only admins can upload new client versions and manage existing downloads.
    """
    context = {
        "request": request,
        "show_nav": True,
        "active_page": "downloads",
        "username": session["username"],
        "is_admin": session.get("is_admin", False)
    }
    return templates.TemplateResponse("downloads.html", context)


@router.get("/admin/api/downloads/list", tags=["Admin"])
async def admin_list_client_versions(
    session: dict = Depends(RequireSession)
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
        if platform == "windows" and not (filename_lower.endswith(".exe") or filename_lower.endswith(".zip")):
            raise HTTPException(
                status_code=400,
                detail="Windows client must have .exe or .zip extension"
            )
        elif platform == "macos" and not (filename_lower.endswith(".app") or filename_lower.endswith(".zip")):
            # Note: macOS apps are directories, so .zip is the practical upload format
            raise HTTPException(
                status_code=400,
                detail="macOS client must have .app or .zip extension"
            )

        # Read file data
        file_data = await file.read()

        if len(file_data) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        # Store the executable
        from database import db_manager
        result = StoreClientExecutable(db_manager, file_data, version, platform, file.filename)

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


@router.get("/admin/api/downloads/download/{version}", tags=["Admin"])
async def admin_download_client_version(
    version: str,
    session: dict = Depends(RequireSession)
):
    """
    Download a specific client version file.

    Args:
        version: Version to download
        session: User session from dependency

    Returns:
        FileResponse with the requested file
    """
    try:
        from database import db_manager
        from fastapi.responses import FileResponse

        downloads_path = GetClientDownloadsPath(db_manager)

        # Find the file for this version
        version_file = None
        for file_path in downloads_path.iterdir():
            if file_path.is_file() and f"-{version}" in file_path.name:
                version_file = file_path
                break

        if not version_file or not version_file.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Version {version} file not found"
            )

        logger.info(f"User '{session['username']}' downloaded client version {version}")

        # Return file as download
        return FileResponse(
            path=str(version_file),
            filename=version_file.name,
            media_type='application/octet-stream'
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading client version {version}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to download client version")


@router.delete("/admin/api/downloads/delete/{version}", tags=["Admin"])
async def admin_delete_client_version(
    version: str,
    session: dict = Depends(RequireAdminSession)
):
    """
    Delete a client version.
    If deleting the active version, the active version setting will be cleared.

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
                status_code=404,
                detail=f"Version {version} not found"
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

