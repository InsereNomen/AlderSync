"""
AlderSync Server - Permission Database Model

Permission model for RBAC.
Stores available permissions that can be assigned to roles.
"""

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from models.database.base import Base


class Permission(Base):
    """
    Permissions table - stores available permissions
    """
    __tablename__ = "permissions"

    permission_id = Column(Integer, primary_key=True, autoincrement=True)
    permission_name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)

    # Relationship to roles through junction table
    roles = relationship("Role", secondary="role_permissions", back_populates="permissions")
