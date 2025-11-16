"""
AlderSync Server - Role Management API Models

Pydantic models for role management admin endpoints.
"""

from typing import Optional, List
from pydantic import BaseModel


class CreateRoleRequest(BaseModel):
    """Request model for creating a new role"""
    role_name: str
    description: Optional[str] = None
    permissions: List[str] = []


class UpdateRoleRequest(BaseModel):
    """Request model for updating a role"""
    role_name: Optional[str] = None
    description: Optional[str] = None


class SetRolePermissionsRequest(BaseModel):
    """Request model for setting role permissions"""
    permissions: List[str]
