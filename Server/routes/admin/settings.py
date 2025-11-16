"""
AlderSync Server - Admin Settings Endpoints
"""

import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from models.database import Setting
from models.api import SettingsUpdateRequest
from routes.admin.auth import RequireAdminSession

# Create logger
logger = logging.getLogger(__name__)

# Create router instance
router = APIRouter()

# Get the directory where server.py is located
script_dir = Path(__file__).parent.parent.parent

# Initialize Jinja2 templates
templates = Jinja2Templates(directory=str(script_dir / "templates"))



# ==================== Admin Settings Management ====================



@router.get("/admin/settings", response_class=HTMLResponse, tags=["Admin"])
async def admin_settings_page(
    request: Request,
    session: dict = Depends(RequireAdminSession)
):
    """
    Display settings management page
    Per Specification.md section 5.2 and Task 3.6
    """
    context = {
        "request": request,
        "show_nav": True,
        "active_page": "settings",
        "username": session["username"],
        "is_admin": True  # Settings page requires admin permission
    }
    return templates.TemplateResponse("settings.html", context)


@router.get("/admin/api/settings", tags=["Admin"])
async def admin_get_settings(
    session: dict = Depends(RequireAdminSession)
):
    """
    Get current server settings
    Per Specification.md section 5.2 and Task 3.6

    Returns:
        Dictionary of all server settings
    """
    try:
        from database import db_manager
        db_session = db_manager.GetSession()
        try:
            # Fetch all settings from database
            settings_records = db_session.query(Setting).all()

            # Convert to dictionary
            settings = {}
            for setting in settings_records:
                # Convert to appropriate type (all stored as strings in DB)
                if setting.key in ['lock_timeout_seconds', 'min_lock_timeout_seconds',
                                   'max_revisions', 'jwt_expiration_hours', 'log_retention_days']:
                    settings[setting.key] = int(setting.value)
                else:
                    settings[setting.key] = setting.value

            return settings
        finally:
            db_session.close()
    except Exception as e:
        logger.error(f"Error fetching settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch settings")


@router.post("/admin/api/settings", tags=["Admin"])
async def admin_update_settings(
    request: SettingsUpdateRequest,
    session: dict = Depends(RequireAdminSession)
):
    """
    Update server settings
    Per Specification.md section 5.2 and Task 3.6

    Args:
        request: Settings update request
        session: Admin session from dependency

    Returns:
        Success message
    """
    try:
        # Validate settings values
        if request.lock_timeout_seconds < 60 or request.lock_timeout_seconds > 3600:
            raise HTTPException(status_code=400, detail="lock_timeout_seconds must be between 60 and 3600")

        if request.min_lock_timeout_seconds < 60 or request.min_lock_timeout_seconds > 3600:
            raise HTTPException(status_code=400, detail="min_lock_timeout_seconds must be between 60 and 3600")

        if request.max_revisions < 1 or request.max_revisions > 100:
            raise HTTPException(status_code=400, detail="max_revisions must be between 1 and 100")

        if request.jwt_expiration_hours < 1 or request.jwt_expiration_hours > 168:
            raise HTTPException(status_code=400, detail="jwt_expiration_hours must be between 1 and 168")

        if request.log_retention_days < 1 or request.log_retention_days > 365:
            raise HTTPException(status_code=400, detail="log_retention_days must be between 1 and 365")

        # Update settings in database
        from database import db_manager
        db_session = db_manager.GetSession()
        try:
            settings_to_update = {
                'lock_timeout_seconds': str(request.lock_timeout_seconds),
                'min_lock_timeout_seconds': str(request.min_lock_timeout_seconds),
                'max_revisions': str(request.max_revisions),
                'jwt_expiration_hours': str(request.jwt_expiration_hours),
                'log_retention_days': str(request.log_retention_days)
            }

            for key, value in settings_to_update.items():
                setting_record = db_session.query(Setting).filter(Setting.key == key).first()
                if setting_record:
                    setting_record.value = value
                else:
                    # Create if doesn't exist
                    new_setting = Setting(key=key, value=value)
                    db_session.add(new_setting)

            db_session.commit()
        finally:
            db_session.close()

        logger.info(f"Admin '{session['username']}' updated server settings")

        return {
            "success": True,
            "message": "Settings updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating settings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {str(e)}")


# ==================== Admin Downloads Page ====================

