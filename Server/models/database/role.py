"""
AlderSync Server - Role Database Model

Role model for RBAC (Role-Based Access Control).
Stores role definitions and their relationships with users and permissions.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship

from models.database.base import Base


class Role(Base):
    """
    Roles table - stores role definitions for RBAC
    """
    __tablename__ = "roles"

    role_id = Column(Integer, primary_key=True, autoincrement=True)
    role_name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    is_system_role = Column(Boolean, default=False)  # True for default roles that cannot be deleted

    # Relationship to users
    users = relationship("User", back_populates="role")
    # Relationship to permissions through junction table
    permissions = relationship("Permission", secondary="role_permissions", back_populates="roles")
