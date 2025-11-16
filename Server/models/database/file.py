"""
AlderSync Server - File Database Model

File model for tracking file metadata and revisions.
Specification.md section 6.2
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship

from models.database.base import Base


class File(Base):
    """
    Files table - tracks file metadata and revisions
    Specification.md section 6.2
    """
    __tablename__ = "files"

    file_id = Column(Integer, primary_key=True, autoincrement=True)
    path = Column(String, nullable=False)
    service_type = Column(String, nullable=False)  # 'Contemporary' or 'Traditional'
    file_hash = Column(String, nullable=True)  # SHA-256 hash, NULL if deleted
    size = Column(Integer, nullable=True)  # bytes, NULL if deleted
    is_deleted = Column(Boolean, default=False)
    last_modified_utc = Column(DateTime, nullable=False)
    revision = Column(Integer, default=0)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)  # User who created this revision
    changelist_id = Column(Integer, ForeignKey("changelists.changelist_id", ondelete="SET NULL"), nullable=True)  # Changelist this file belongs to

    # Relationships
    user = relationship("User", back_populates="files")
    changelist = relationship("Changelist", back_populates="files")

    __table_args__ = (
        # Indexes for optimizing common queries
        # Index for ListFiles query - finding current versions by service type
        Index('idx_files_service_path_revision', 'service_type', 'path', 'revision'),
        # Index for is_deleted filtering
        Index('idx_files_deleted', 'is_deleted'),
        # Index for user files query
        Index('idx_files_user', 'user_id'),
        # Index for changelist files query
        Index('idx_files_changelist', 'changelist_id'),
        # Unique constraint on path, service_type, and revision
        # This ensures we can have multiple revisions of the same file
        {"sqlite_autoincrement": True}
    )
