"""
AlderSync Server - User Database Model

User model for authentication and authorization.
Stores user credentials and role assignments.
Specification.md section 6.1
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from models.database.base import Base


class User(Base):
    """
    Users table - stores user credentials and authentication info
    Specification.md section 6.1
    """
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role_id = Column(Integer, ForeignKey("roles.role_id"), nullable=True)  # NULL for backward compatibility
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

    # Relationship to role
    role = relationship("Role", back_populates="users")
    # Relationship to operations
    operations = relationship("Operation", back_populates="user")
    # Relationship to files
    files = relationship("File", back_populates="user")
    # Relationship to changelists
    changelists = relationship("Changelist", back_populates="user")
