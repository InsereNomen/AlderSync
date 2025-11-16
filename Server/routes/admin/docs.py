"""
AlderSync Server - Documentation Endpoints

This module contains admin web interface documentation endpoints for
user guides, administrative guides, and technical documentation.
"""

import logging
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from routes.admin.auth import RequireAdminSession, GetAdminSession
from models.database import User


# Create logger
logger = logging.getLogger(__name__)

# Create router instance
router = APIRouter()

# Get the directory where server.py is located
script_dir = Path(__file__).parent.parent.parent

# Initialize Jinja2 templates
templates = Jinja2Templates(directory=str(script_dir / "templates"))


# ==================== Helper Functions ====================

def IsUserAdmin(session: dict) -> bool:
    """
    Check if the current user has admin permission

    Args:
        session: Session dictionary from GetAdminSession

    Returns:
        bool: True if user has admin permission, False otherwise
    """
    from database import db_manager

    db_session = db_manager.GetSession()
    try:
        user = db_session.query(User).filter(User.user_id == session['user_id']).first()
        if not user or not user.role:
            return False

        permissions = [perm.permission_name for perm in user.role.permissions]
        return 'admin' in permissions
    finally:
        db_session.close()


# ==================== Documentation Routes ====================

@router.get("/admin/docs/user", response_class=HTMLResponse)
async def UserDocsPage(request: Request):
    """
    User documentation page - accessible by all authenticated users
    Provides documentation on how to use the AlderSync Client and website
    """
    session = GetAdminSession(request)
    if not session:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            detail="Not authenticated",
            headers={"Location": "/admin/login"}
        )

    # Extract host and port from the request
    server_host = request.url.hostname or "localhost"
    server_port = request.url.port or 8000

    # Check if user is admin
    is_admin = IsUserAdmin(session)

    context = {
        "request": request,
        "username": session["username"],
        "show_nav": True,
        "active_page": "docs",
        "server_host": server_host,
        "server_port": server_port,
        "is_admin": is_admin
    }

    return templates.TemplateResponse("docs_user.html", context)


@router.get("/admin/docs/admin", response_class=HTMLResponse)
async def AdminDocsPage(request: Request, session: dict = None):
    """
    Administrative documentation page - accessible by admins only
    Provides documentation on server deployment, admin pages, and updates
    """
    if session is None:
        session = RequireAdminSession(request)

    context = {
        "request": request,
        "username": session["username"],
        "show_nav": True,
        "active_page": "docs",
        "is_admin": True  # This page requires admin, so always true
    }

    return templates.TemplateResponse("docs_admin.html", context)


@router.get("/admin/docs/technical", response_class=HTMLResponse)
async def TechnicalDocsPage(request: Request, session: dict = None):
    """
    Technical documentation page - accessible by admins only
    Provides documentation on tech stack, code structure, and development
    """
    if session is None:
        session = RequireAdminSession(request)

    context = {
        "request": request,
        "username": session["username"],
        "show_nav": True,
        "active_page": "docs",
        "is_admin": True  # This page requires admin, so always true
    }

    return templates.TemplateResponse("docs_technical.html", context)
