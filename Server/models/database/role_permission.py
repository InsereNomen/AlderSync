"""
AlderSync Server - RolePermission Database Model

Junction table for many-to-many relationship between roles and permissions.
"""

from sqlalchemy import Column, Integer, ForeignKey

from models.database.base import Base


class RolePermission(Base):
    """
    RolePermissions junction table - maps roles to permissions (many-to-many)
    """
    __tablename__ = "role_permissions"

    role_id = Column(Integer, ForeignKey("roles.role_id"), primary_key=True)
    permission_id = Column(Integer, ForeignKey("permissions.permission_id"), primary_key=True)
