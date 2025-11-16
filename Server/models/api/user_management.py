"""
AlderSync Server - User Management API Models

Pydantic models for user management admin endpoints.
"""

from typing import Optional
from pydantic import BaseModel


class CreateUserRequest(BaseModel):
    """Request model for creating a new user"""
    username: str
    password: str
    role_id: Optional[int] = None  # Optional role assignment, defaults to Standard User


class UpdateUserStatusRequest(BaseModel):
    """Request model for updating user status"""
    is_active: bool


class ResetPasswordRequest(BaseModel):
    """Request model for resetting user password"""
    new_password: str


class UpdateUserRoleRequest(BaseModel):
    """Request model for updating user role"""
    role_id: int
