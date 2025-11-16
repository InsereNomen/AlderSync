"""
AlderSync Server - Admin Users Endpoints
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import joinedload

from models.database import User, Role
from models.api import (
    CreateUserRequest, UpdateUserStatusRequest, ResetPasswordRequest, UpdateUserRoleRequest
)
from routes.admin.auth import RequireAdminSession

# Create logger
logger = logging.getLogger(__name__)

# Create router instance
router = APIRouter()

# Get the directory where server.py is located
script_dir = Path(__file__).parent.parent.parent

# Initialize Jinja2 templates
templates = Jinja2Templates(directory=str(script_dir / "templates"))



@router.get("/admin/users", response_class=HTMLResponse, tags=["Admin"])
async def admin_users_page(
    request: Request,
    session: dict = Depends(RequireAdminSession)
):
    """
    Display user management page

    Args:
        request: FastAPI request object
        session: Admin session from dependency

    Returns:
        HTML user management page
    """
    from database import db_manager
    db_session = db_manager.GetSession()

    try:
        # Get all users with role information, ordered by created_at
        from sqlalchemy.orm import joinedload
        users = db_session.query(User).options(
            joinedload(User.role).joinedload(Role.permissions)
        ).order_by(User.created_at.desc()).all()

        # Get all roles for the role dropdown
        roles = db_session.query(Role).order_by(Role.role_name).all()

        context = {
            "request": request,
            "show_nav": True,
            "active_page": "users",
            "username": session["username"],
            "users": users,
            "roles": roles,
            "is_admin": True  # Users page requires admin permission
        }

        return templates.TemplateResponse("users.html", context)

    finally:
        db_session.close()




@router.post("/admin/api/users", tags=["Admin"])
async def admin_create_user(
    request_data: CreateUserRequest,
    session: dict = Depends(RequireAdminSession)
):
    """
    Create a new user

    Args:
        request_data: User creation data (username, password)
        session: Admin session from dependency

    Returns:
        Success message with username
    """
    from database import db_manager
    db_session = db_manager.GetSession()

    try:
        # Validate username format
        import re
        if not re.match(r'^[a-zA-Z0-9_]{3,50}$', request_data.username):
            raise HTTPException(
                status_code=400,
                detail="Username must be 3-50 characters and contain only letters, numbers, and underscores"
            )

        # Check if user already exists
        existing_user = db_session.query(User).filter(User.username == request_data.username).first()
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail=f"User '{request_data.username}' already exists"
            )

        # Hash password
        password_hash = db_manager.HashPassword(request_data.password)

        # Determine role_id
        role_id = request_data.role_id
        if role_id is None:
            # Default to Standard User role
            standard_role = db_session.query(Role).filter(Role.role_name == "Standard User").first()
            if standard_role:
                role_id = standard_role.role_id
        else:
            # Validate that the provided role_id exists
            role = db_session.query(Role).filter(Role.role_id == role_id).first()
            if not role:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid role_id: {role_id}"
                )

        # Create new user
        new_user = User(
            username=request_data.username,
            password_hash=password_hash,
            role_id=role_id,
            created_at=datetime.now(timezone.utc),
            is_active=True
        )

        db_session.add(new_user)
        db_session.commit()

        logger.info(f"Admin '{session['username']}' created new user '{request_data.username}' with role_id {role_id}")

        return {
            "success": True,
            "username": request_data.username,
            "message": f"User '{request_data.username}' created successfully"
        }

    except HTTPException:
        db_session.rollback()
        raise
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error creating user: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create user")
    finally:
        db_session.close()




@router.put("/admin/api/users/{username}/status", tags=["Admin"])
async def admin_update_user_status(
    username: str,
    request_data: UpdateUserStatusRequest,
    session: dict = Depends(RequireAdminSession)
):
    """
    Enable or disable a user

    Args:
        username: Username to update
        request_data: Status update data (is_active)
        session: Admin session from dependency

    Returns:
        Success message
    """
    from database import db_manager
    db_session = db_manager.GetSession()

    try:
        # Find user
        user = db_session.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail=f"User '{username}' not found")

        # Prevent disabling own account
        if username == session['username'] and not request_data.is_active:
            raise HTTPException(status_code=400, detail="Cannot disable your own account")

        # Update status
        user.is_active = request_data.is_active
        db_session.commit()

        action = "enabled" if request_data.is_active else "disabled"
        logger.info(f"Admin '{session['username']}' {action} user '{username}'")

        return {
            "success": True,
            "username": username,
            "is_active": request_data.is_active,
            "message": f"User '{username}' {action} successfully"
        }

    except HTTPException:
        db_session.rollback()
        raise
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error updating user status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update user status")
    finally:
        db_session.close()




@router.post("/admin/api/users/{username}/reset-password", tags=["Admin"])
async def admin_reset_user_password(
    username: str,
    request_data: ResetPasswordRequest,
    session: dict = Depends(RequireAdminSession)
):
    """
    Reset a user's password

    Args:
        username: Username to reset password for
        request_data: New password data
        session: Admin session from dependency

    Returns:
        Success message
    """
    from database import db_manager
    db_session = db_manager.GetSession()

    try:
        # Find user
        user = db_session.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail=f"User '{username}' not found")

        # Validate password length
        if len(request_data.new_password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

        # Hash new password
        password_hash = db_manager.HashPassword(request_data.new_password)

        # Update password
        user.password_hash = password_hash
        db_session.commit()

        logger.info(f"Admin '{session['username']}' reset password for user '{username}'")

        return {
            "success": True,
            "username": username,
            "message": f"Password reset for user '{username}'"
        }

    except HTTPException:
        db_session.rollback()
        raise
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error resetting password: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to reset password")
    finally:
        db_session.close()




@router.put("/admin/api/users/{user_id}/role", tags=["Admin"])
async def admin_update_user_role(
    user_id: int,
    request_data: UpdateUserRoleRequest,
    session: dict = Depends(RequireAdminSession)
):
    """
    Update a user's role
    Per Task 8.6

    Args:
        user_id: User ID to update
        request_data: Role update data (role_id)
        session: Admin session from dependency

    Returns:
        Success message
    """
    from database import db_manager
    db_session = db_manager.GetSession()

    try:
        # Find user
        user = db_session.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found")

        # Validate role exists
        role = db_session.query(Role).filter(Role.role_id == request_data.role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail=f"Role with ID {request_data.role_id} not found")

        # Prevent removing admin role from own account
        if user.username == session['username']:
            # Check if user currently has admin permission
            current_permissions = [perm.permission_name for perm in user.role.permissions] if user.role else []
            new_permissions = [perm.permission_name for perm in role.permissions]

            if 'admin' in current_permissions and 'admin' not in new_permissions:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot remove admin role from your own account"
                )

        # Update role
        old_role_name = user.role.role_name if user.role else "None"
        user.role_id = request_data.role_id
        db_session.commit()

        logger.info(f"Admin '{session['username']}' changed role for user '{user.username}' from '{old_role_name}' to '{role.role_name}'")

        return {
            "success": True,
            "user_id": user_id,
            "username": user.username,
            "role_id": request_data.role_id,
            "role_name": role.role_name,
            "message": f"Role updated for user '{user.username}' to '{role.role_name}'"
        }

    except HTTPException:
        db_session.rollback()
        raise
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error updating user role: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update user role")
    finally:
        db_session.close()


@router.delete("/admin/api/users/{user_id}", tags=["Admin"])
async def admin_delete_user(
    user_id: int,
    session: dict = Depends(RequireAdminSession)
):
    """
    Delete a user

    Args:
        user_id: ID of the user to delete
        session: Admin session from dependency

    Returns:
        Success message
    """
    from database import db_manager
    db_session = db_manager.GetSession()

    try:
        # Get the user
        user = db_session.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found")

        # Prevent deleting your own account
        if user.username == session['username']:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete your own account"
            )

        username = user.username

        # Delete the user
        db_session.delete(user)
        db_session.commit()

        logger.info(f"Admin '{session['username']}' deleted user '{username}'")

        return {
            "success": True,
            "message": f"User '{username}' deleted successfully"
        }

    except HTTPException:
        db_session.rollback()
        raise
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error deleting user: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete user")
    finally:
        db_session.close()

