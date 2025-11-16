"""
AlderSync Server - Admin Authentication Endpoints

This module contains admin web interface authentication endpoints including
login, session management, and the dashboard.
"""

import logging
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates

from models.database import User, File, Operation, LastOperation
from auth import AuthenticateUser
from admin_sessions import (
    CreateSession, GetSession, DeleteSession,
    SESSION_COOKIE_NAME, SESSION_LIFETIME_HOURS
)
from transactions import GetActiveLockInfo


# Create logger
logger = logging.getLogger(__name__)

# Create router instance
router = APIRouter()

# Get the directory where server.py is located
script_dir = Path(__file__).parent.parent.parent

# Initialize Jinja2 templates
templates = Jinja2Templates(directory=str(script_dir / "templates"))


# ==================== Helper Functions ====================

def GetAdminSession(request: Request) -> Optional[dict]:
    """
    Dependency to get admin session from cookie
    Returns session info or None if not logged in
    """
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        return None

    session = GetSession(session_id)
    if not session:
        return None

    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "username": session.username
    }


def RequireSession(request: Request) -> dict:
    """
    Dependency to require valid session (any authenticated user)
    Returns session info including is_admin flag
    """
    from database import db_manager

    session = GetAdminSession(request)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            detail="Not authenticated",
            headers={"Location": "/admin/login"}
        )

    # Get user info including admin status
    db_session = db_manager.GetSession()
    try:
        user = db_session.query(User).filter(User.user_id == session['user_id']).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        # Check if user has admin permission
        has_admin = False
        if user.role:
            permissions = [perm.permission_name for perm in user.role.permissions]
            has_admin = 'admin' in permissions

        # Add admin flag to session
        session['is_admin'] = has_admin
        return session

    finally:
        db_session.close()


def RequireAdminSession(request: Request) -> dict:
    """
    Dependency to require admin session with admin permission
    Per Task 8.6 - verifies user has admin permission
    """
    from database import db_manager

    session = GetAdminSession(request)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            detail="Not authenticated",
            headers={"Location": "/admin/login"}
        )

    # Verify user has admin permission
    db_session = db_manager.GetSession()
    try:
        user = db_session.query(User).filter(User.user_id == session['user_id']).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        # Check if user has admin permission
        has_admin = False
        if user.role:
            permissions = [perm.permission_name for perm in user.role.permissions]
            has_admin = 'admin' in permissions

        if not has_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin permission required"
            )

        return session

    finally:
        db_session.close()


# ==================== Admin Authentication Endpoints ====================

@router.api_route("/favicon.ico", methods=["GET", "HEAD"])
async def favicon():
    """
    Serve the SVG favicon for legacy favicon.ico requests
    This prevents 404 errors in logs from browsers requesting favicon.ico
    Handles both GET and HEAD methods
    """
    favicon_path = script_dir / "static" / "favicon.svg"
    return FileResponse(favicon_path, media_type="image/svg+xml")


@router.get("/admin", response_class=RedirectResponse, tags=["Admin"])
async def admin_root(request: Request):
    """Redirect /admin to appropriate page based on user role"""
    from database import db_manager

    session = GetAdminSession(request)
    if not session:
        return RedirectResponse(url="/admin/login", status_code=303)

    # Check if user is admin to determine redirect location
    db_session = db_manager.GetSession()
    try:
        user_record = db_session.query(User).filter(User.user_id == session['user_id']).first()
        is_admin = False
        if user_record and user_record.role:
            permissions = [perm.permission_name for perm in user_record.role.permissions]
            is_admin = 'admin' in permissions

        # Redirect admins to dashboard, non-admins to user docs
        redirect_url = "/admin/dashboard" if is_admin else "/admin/docs/user"
        return RedirectResponse(url=redirect_url, status_code=303)
    finally:
        db_session.close()


@router.get("/admin/login", response_class=HTMLResponse, tags=["Admin"])
async def admin_login_page(request: Request):
    """
    Display admin login page

    Returns:
        HTML login form
    """
    from database import db_manager

    # Check if already logged in
    session = GetAdminSession(request)
    if session:
        # Check if user is admin to determine redirect location
        db_session = db_manager.GetSession()
        try:
            user_record = db_session.query(User).filter(User.user_id == session['user_id']).first()
            is_admin = False
            if user_record and user_record.role:
                permissions = [perm.permission_name for perm in user_record.role.permissions]
                is_admin = 'admin' in permissions

            # Redirect admins to dashboard, non-admins to user docs
            redirect_url = "/admin/dashboard" if is_admin else "/admin/docs/user"
            return RedirectResponse(url=redirect_url, status_code=303)
        finally:
            db_session.close()

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "show_nav": False, "error": None}
    )


@router.post("/admin/login", response_class=HTMLResponse, tags=["Admin"])
async def admin_login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    """
    Process admin login form submission

    Args:
        username: Username from form
        password: Password from form

    Returns:
        Redirect to dashboard on success, login form with error on failure
    """
    from database import db_manager

    # Authenticate user
    user = AuthenticateUser(db_manager, username, password)

    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "show_nav": False, "error": "Invalid username or password"}
        )

    # Create session
    session = CreateSession(user['user_id'], user['username'])

    # Check if user is admin to determine redirect location
    db_session = db_manager.GetSession()
    try:
        user_record = db_session.query(User).filter(User.user_id == user['user_id']).first()
        is_admin = False
        if user_record and user_record.role:
            permissions = [perm.permission_name for perm in user_record.role.permissions]
            is_admin = 'admin' in permissions

        # Redirect admins to dashboard, non-admins to user docs
        redirect_url = "/admin/dashboard" if is_admin else "/admin/docs/user"
    finally:
        db_session.close()

    # Create response with redirect
    response = RedirectResponse(url=redirect_url, status_code=303)

    # Set session cookie
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session.session_id,
        max_age=SESSION_LIFETIME_HOURS * 3600,
        httponly=True,
        samesite="lax"
    )

    return response


@router.post("/admin/logout", tags=["Admin"])
@router.get("/admin/logout", tags=["Admin"])
async def admin_logout(request: Request):
    """
    Logout endpoint - clears session and redirects to login page
    Supports both GET and POST methods
    """
    session = GetAdminSession(request)
    if session:
        # Delete the session from server
        DeleteSession(session['session_id'])

    # Create redirect response
    response = RedirectResponse(url="/admin/login", status_code=303)

    # Clear the session cookie
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        samesite="lax"
    )

    return response


@router.get("/admin/dashboard", response_class=HTMLResponse, tags=["Admin"])
async def admin_dashboard(
    request: Request,
    session: dict = Depends(RequireAdminSession)
):
    """
    Display admin dashboard with server statistics

    Args:
        request: FastAPI request object
        session: Admin session from dependency

    Returns:
        HTML dashboard page
    """
    from database import db_manager

    # Get database session
    db_session = db_manager.GetSession()

    try:
        # Get statistics
        total_users = db_session.query(User).count()
        active_users = db_session.query(User).filter(User.is_active == True).count()

        # Count files by service type (count unique paths with the highest revision)
        from sqlalchemy import func

        # Subquery to find max revision for each file path (Contemporary)
        contemporary_max_revisions = db_session.query(
            File.path,
            func.max(File.revision).label('max_revision')
        ).filter(
            File.service_type == "Contemporary"
        ).group_by(File.path).subquery()

        # Count contemporary files (join with max revisions and exclude deleted)
        contemporary_files = db_session.query(File).join(
            contemporary_max_revisions,
            (File.path == contemporary_max_revisions.c.path) &
            (File.revision == contemporary_max_revisions.c.max_revision)
        ).filter(
            File.service_type == "Contemporary",
            File.is_deleted == False
        ).count()

        # Subquery to find max revision for each file path (Traditional)
        traditional_max_revisions = db_session.query(
            File.path,
            func.max(File.revision).label('max_revision')
        ).filter(
            File.service_type == "Traditional"
        ).group_by(File.path).subquery()

        # Count traditional files (join with max revisions and exclude deleted)
        traditional_files = db_session.query(File).join(
            traditional_max_revisions,
            (File.path == traditional_max_revisions.c.path) &
            (File.revision == traditional_max_revisions.c.max_revision)
        ).filter(
            File.service_type == "Traditional",
            File.is_deleted == False
        ).count()

        # Calculate total sizes (get files at highest revision)
        contemporary_size_result = db_session.query(File).join(
            contemporary_max_revisions,
            (File.path == contemporary_max_revisions.c.path) &
            (File.revision == contemporary_max_revisions.c.max_revision)
        ).filter(
            File.service_type == "Contemporary",
            File.is_deleted == False
        ).all()
        contemporary_size = sum(f.size or 0 for f in contemporary_size_result)

        traditional_size_result = db_session.query(File).join(
            traditional_max_revisions,
            (File.path == traditional_max_revisions.c.path) &
            (File.revision == traditional_max_revisions.c.max_revision)
        ).filter(
            File.service_type == "Traditional",
            File.is_deleted == False
        ).all()
        traditional_size = sum(f.size or 0 for f in traditional_size_result)

        # Helper function to format bytes with appropriate unit
        def format_bytes(size_bytes):
            if size_bytes == 0:
                return "0 B"
            elif size_bytes < 1024:
                return f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.1f} KB"
            else:
                return f"{size_bytes / (1024 * 1024):.1f} MB"

        contemporary_size_formatted = format_bytes(contemporary_size)
        traditional_size_formatted = format_bytes(traditional_size)

        # Calculate total storage used across ALL revisions (actual disk usage)
        contemporary_all_revisions = db_session.query(File).filter(
            File.service_type == "Contemporary",
            File.is_deleted == False
        ).all()
        contemporary_total_storage = sum(f.size or 0 for f in contemporary_all_revisions)
        contemporary_total_storage_formatted = format_bytes(contemporary_total_storage)

        traditional_all_revisions = db_session.query(File).filter(
            File.service_type == "Traditional",
            File.is_deleted == False
        ).all()
        traditional_total_storage = sum(f.size or 0 for f in traditional_all_revisions)
        traditional_total_storage_formatted = format_bytes(traditional_total_storage)

        # Get total operations
        total_operations = db_session.query(Operation).filter(
            Operation.status == "completed"
        ).count()

        # Get recent operations (last 10)
        recent_operations_query = db_session.query(Operation, User).join(
            User, Operation.user_id == User.user_id
        ).filter(
            Operation.status == "completed"
        ).order_by(
            Operation.completed_at_utc.desc()
        ).limit(10)

        recent_operations = []
        for op, user in recent_operations_query:
            recent_operations.append({
                "username": user.username,
                "operation_type": op.operation_type,
                "service_type": op.service_type,
                "completed_at_utc": op.completed_at_utc if op.completed_at_utc else None,
                "files_pulled": op.files_pulled,
                "files_pushed": op.files_pushed,
                "status": op.status
            })

        # Get lock info
        lock_info = GetActiveLockInfo()

        # Get last operation
        last_op_record = db_session.query(LastOperation).first()
        last_operation = None
        if last_op_record:
            last_operation = {
                "user": last_op_record.username,
                "operation": last_op_record.operation_type,
                "service_type": last_op_record.service_type,
                "timestamp": last_op_record.timestamp_utc.strftime("%Y-%m-%d %H:%M:%S UTC") if last_op_record.timestamp_utc else "N/A"
            }

        # Prepare template context
        context = {
            "request": request,
            "show_nav": True,
            "active_page": "dashboard",
            "username": session["username"],
            "stats": {
                "total_users": total_users,
                "active_users": active_users,
                "contemporary_files": contemporary_files,
                "contemporary_size": contemporary_size_formatted,
                "contemporary_total_storage": contemporary_total_storage_formatted,
                "traditional_files": traditional_files,
                "traditional_size": traditional_size_formatted,
                "traditional_total_storage": traditional_total_storage_formatted,
                "total_operations": total_operations
            },
            "recent_operations": recent_operations,
            "lock_info": lock_info,
            "last_operation": last_operation,
            "version": "1.0.0",
            "is_admin": True  # Dashboard requires admin permission
        }

        return templates.TemplateResponse("dashboard.html", context)

    finally:
        db_session.close()
