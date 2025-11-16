"""
AlderSync Server - Authentication Endpoints

This module contains authentication-related endpoints including login
and password management.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from models.database import User, Setting
from models.auth import LoginRequest, LoginResponse, ChangePasswordRequest, ChangePasswordResponse
from auth import AuthenticateUser, CreateAccessToken, GetCurrentActiveUser


# Create logger
logger = logging.getLogger(__name__)

# Create router instance
router = APIRouter()


# ==================== Authentication Endpoints ====================

@router.post("/auth/login", response_model=LoginResponse, tags=["Authentication"])
async def login(login_request: LoginRequest):
    """
    Authenticate user and return JWT token
    Per Specification.md section 5.1.1 and 7.2.1

    Args:
        login_request: Username and password

    Returns:
        LoginResponse: JWT token and expiration time

    Raises:
        HTTPException: If credentials are invalid
    """
    from database import db_manager

    # Authenticate user (returns dict or None)
    user_data = AuthenticateUser(db_manager, login_request.username, login_request.password)

    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get JWT expiration from settings
    session = db_manager.GetSession()
    try:
        expiration_setting = session.query(Setting).filter(Setting.key == "jwt_expiration_hours").first()
        expiration_hours = int(expiration_setting.value) if expiration_setting else 24
    finally:
        session.close()

    # Create access token with permissions
    token_data = {
        "user_id": user_data['user_id'],
        "username": user_data['username'],
        "permissions": user_data.get('permissions', [])
    }
    access_token = CreateAccessToken(token_data, db_manager)

    # Return token and expiration time in seconds
    expires_in = expiration_hours * 3600  # Convert hours to seconds

    logger.info(f"User '{user_data['username']}' logged in successfully")

    return LoginResponse(
        token=access_token,
        expires_in=expires_in
    )


@router.post("/user/change_password", response_model=ChangePasswordResponse, tags=["User"])
async def change_password(
    password_request: ChangePasswordRequest,
    current_user: User = Depends(GetCurrentActiveUser)
):
    """
    Change the password for the currently authenticated user
    Per Specification.md section 5.1.1

    Args:
        password_request: Current and new passwords
        current_user: Currently authenticated user (from JWT token)

    Returns:
        ChangePasswordResponse: Success status and message

    Raises:
        HTTPException: If current password is incorrect
    """
    from database import db_manager

    # Verify current password
    if not db_manager.VerifyPassword(password_request.current_password, current_user.password_hash):
        logger.warning(f"Failed password change attempt for user '{current_user.username}' - incorrect current password")
        return ChangePasswordResponse(
            success=False,
            message="Current password is incorrect"
        )

    # Hash new password
    new_password_hash = db_manager.HashPassword(password_request.new_password)

    # Update password in database
    session = db_manager.GetSession()
    try:
        user = session.query(User).filter(User.user_id == current_user.user_id).first()
        user.password_hash = new_password_hash
        session.commit()

        logger.info(f"User '{current_user.username}' changed password successfully")

        return ChangePasswordResponse(
            success=True,
            message="Password changed successfully"
        )

    except Exception as e:
        session.rollback()
        logger.error(f"Error changing password for user '{current_user.username}': {str(e)}")
        return ChangePasswordResponse(
            success=False,
            message="An error occurred while changing password"
        )

    finally:
        session.close()
