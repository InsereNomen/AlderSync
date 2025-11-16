"""
AlderSync Server - Authentication Utilities

This module provides authentication functionality including:
- JWT token generation and validation
- Authentication dependency for protected routes
- Token expiration handling

Security Requirements:
- Never store passwords as plain text (handled in database.py)
- Use proper bcrypt hashing for stored credentials (handled in database.py)
- Implement JWT token-based authentication
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from models.database import User
from models.auth import (
    LoginRequest,
    LoginResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    TokenData
)
from managers.database_manager import DatabaseManager

# JWT Configuration
# In production, this should be loaded from environment variables or a secure config file
SECRET_KEY = secrets.token_urlsafe(32)  # Generate a random secret key
ALGORITHM = "HS256"

# Security scheme for FastAPI
security = HTTPBearer()


# ==================== JWT Token Functions ====================

def CreateAccessToken(data: dict, db_manager: DatabaseManager, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token

    Args:
        data: Dictionary containing user data (user_id, username, permissions)
        db_manager: DatabaseManager instance to get JWT expiration setting
        expires_delta: Optional custom expiration time

    Returns:
        str: Encoded JWT token
    """
    to_encode = data.copy()

    # Get JWT expiration from settings, or use delta if provided
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Get jwt_expiration_hours from database settings
        session = db_manager.GetSession()
        try:
            from models.database import Setting
            expiration_setting = session.query(Setting).filter(Setting.key == "jwt_expiration_hours").first()
            expiration_hours = int(expiration_setting.value) if expiration_setting else 24
        finally:
            session.close()

        expire = datetime.now(timezone.utc) + timedelta(hours=expiration_hours)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def DecodeAccessToken(token: str) -> Optional[TokenData]:
    """
    Decode and validate a JWT access token

    Args:
        token: JWT token string

    Returns:
        TokenData: Token data if valid, None if invalid

    Raises:
        HTTPException: If token is invalid or expired
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        username: str = payload.get("username")
        permissions: list = payload.get("permissions", [])

        if user_id is None or username is None:
            raise credentials_exception

        return TokenData(user_id=user_id, username=username, permissions=permissions)

    except JWTError:
        raise credentials_exception


# ==================== Authentication Dependencies ====================

def GetCurrentUser(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    FastAPI dependency to get the current authenticated user
    Validates the JWT token and returns the user object

    Args:
        credentials: HTTP Bearer token from Authorization header

    Returns:
        User: The authenticated user object

    Raises:
        HTTPException: If authentication fails
    """
    # Decode the token
    token_data = DecodeAccessToken(credentials.credentials)

    # Get the database manager from the global scope (set in database.py)
    from database import db_manager

    # Get the user from database
    session = db_manager.GetSession()
    try:
        user = session.query(User).filter(User.user_id == token_data.user_id).first()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is disabled",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user

    finally:
        session.close()


def GetCurrentActiveUser(current_user: User = Depends(GetCurrentUser)) -> User:
    """
    FastAPI dependency to get the current authenticated and active user
    Additional check for user active status

    Args:
        current_user: User from GetCurrentUser dependency

    Returns:
        User: The authenticated and active user object

    Raises:
        HTTPException: If user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


# ==================== Authentication Helper Functions ====================

def AuthenticateUser(db_manager: DatabaseManager, username: str, password: str) -> Optional[dict]:
    """
    Authenticate a user with username and password

    Args:
        db_manager: DatabaseManager instance
        username: Username
        password: Plain text password

    Returns:
        dict: User data dictionary if authentication successful, None otherwise
              Contains: user_id, username, password_hash, is_active, created_at, last_login
    """
    session = db_manager.GetSession()

    try:
        # Get user from database
        user = session.query(User).filter(User.username == username).first()

        if not user:
            return None

        # Verify password
        if not db_manager.VerifyPassword(password, user.password_hash):
            return None

        # Check if user is active
        if not user.is_active:
            return None

        # Update last login timestamp
        user.last_login = datetime.now(timezone.utc)
        session.commit()

        # Get user permissions
        permissions = []
        if user.role:
            permissions = [perm.permission_name for perm in user.role.permissions]

        # Return user data as dictionary to avoid SQLAlchemy session issues
        user_data = {
            'user_id': user.user_id,
            'username': user.username,
            'password_hash': user.password_hash,
            'is_active': user.is_active,
            'created_at': user.created_at,
            'last_login': user.last_login,
            'permissions': permissions
        }

        return user_data

    finally:
        session.close()


# ==================== Permission Checking ====================

def UserHasPermission(user: User, permission_name: str, db_manager: DatabaseManager = None) -> bool:
    """
    Check if a user has a specific permission

    Args:
        user: User object (from GetCurrentUser)
        permission_name: Name of the permission to check (e.g., 'admin', 'can_push', 'can_reconcile')
        db_manager: Optional DatabaseManager instance (uses global if not provided)

    Returns:
        bool: True if user has the permission or is admin, False otherwise
    """
    # Import here to avoid circular dependency
    if db_manager is None:
        from database import db_manager as global_db_manager
        db_manager = global_db_manager

    session = db_manager.GetSession()
    try:
        # Refresh the user object to ensure we have the latest data
        from models.database import User as UserModel, Permission
        user_obj = session.query(UserModel).filter(UserModel.user_id == user.user_id).first()

        if not user_obj or not user_obj.role:
            return False

        # Check if user has the admin permission (admin has all permissions)
        user_permissions = [perm.permission_name for perm in user_obj.role.permissions]

        if 'admin' in user_permissions:
            return True

        # Check for the specific permission
        return permission_name in user_permissions

    finally:
        session.close()


def RequirePermission(permission_name: str):
    """
    Dependency factory to create a permission checking dependency

    Args:
        permission_name: Name of the permission required

    Returns:
        Dependency function that checks for the permission

    Usage:
        @app.post("/something")
        async def some_endpoint(user: User = Depends(RequirePermission("can_push"))):
            ...
    """
    def permission_checker(current_user: User = Depends(GetCurrentActiveUser)) -> User:
        """
        Check if current user has the required permission

        Raises:
            HTTPException: 403 Forbidden if user lacks permission
        """
        from database import db_manager

        if not UserHasPermission(current_user, permission_name, db_manager):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required permission: {permission_name}"
            )

        return current_user

    return permission_checker


# Convenience dependencies for common permissions
RequireAdmin = RequirePermission("admin")
RequireCanPush = RequirePermission("can_push")
RequireCanReconcile = RequirePermission("can_reconcile")
