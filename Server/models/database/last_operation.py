"""
AlderSync Server - LastOperation Database Model

LastOperation model for tracking the most recent operation for status display.
Specification.md section 6.5
"""

from sqlalchemy import Column, Integer, String, DateTime, CheckConstraint

from models.database.base import Base


class LastOperation(Base):
    """
    Last_operation table - tracks the most recent operation for status display
    Specification.md section 6.5
    Only one row allowed (id=1)
    """
    __tablename__ = "last_operation"

    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=True)
    operation_type = Column(String, nullable=True)
    service_type = Column(String, nullable=True)
    timestamp_utc = Column(DateTime, nullable=True)
    file_count = Column(Integer, nullable=True)

    __table_args__ = (
        CheckConstraint('id = 1', name='single_row_constraint'),
    )
