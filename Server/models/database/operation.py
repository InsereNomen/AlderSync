"""
AlderSync Server - Operation Database Model

Operation model for tracking sync operations and transaction history.
Specification.md section 6.3
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from models.database.base import Base


class Operation(Base):
    """
    Operations table - tracks all sync operations and locks
    Specification.md section 6.3
    """
    __tablename__ = "operations"

    operation_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    operation_type = Column(String, nullable=False)  # 'Pull', 'Push', or 'Reconcile'
    service_type = Column(String, nullable=False)  # 'Contemporary' or 'Traditional'
    locked_at_utc = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at_utc = Column(DateTime, nullable=True)
    files_pulled = Column(Integer, nullable=True)  # For Reconcile operations
    files_pushed = Column(Integer, nullable=True)  # For Reconcile operations
    status = Column(String, nullable=False)  # 'active', 'completed', 'rolled_back', 'cancelled_by_admin'

    # Relationship to user (preserves operations when user is deleted)
    user = relationship("User", back_populates="operations")
