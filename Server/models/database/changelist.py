"""
AlderSync Server - Changelist Database Model

Changelist model for tracking groups of files uploaded together in a single transaction.
Allows tracking all files/revisions that were added in a single operation.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from models.database.base import Base


class Changelist(Base):
    """
    Changelists table - tracks groups of files uploaded together
    Each transaction that uploads files creates one changelist
    """
    __tablename__ = "changelists"

    changelist_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    created_at_utc = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    operation_type = Column(String, nullable=False)  # 'Pull', 'Push', or 'Reconcile'
    description = Column(Text, nullable=False, default="")  # User-provided description

    # Relationships
    user = relationship("User", back_populates="changelists")
    files = relationship("File", back_populates="changelist")

    __table_args__ = (
        {"sqlite_autoincrement": True}
    )
