"""
AlderSync Server - IgnorePattern Database Model

IgnorePattern model for storing file ignore patterns (similar to .gitignore).
These patterns are applied to all file operations on the server side.
"""

from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime, timezone

from models.database.base import Base


class IgnorePattern(Base):
    """
    IgnorePattern table - stores file ignore patterns for the server

    Patterns follow .gitignore syntax:
    - Wildcards: *, ?, [abc], etc.
    - Directory patterns: trailing /
    - Negation: ! prefix
    - Comments: # prefix (stored but ignored during matching)
    """
    __tablename__ = "ignore_patterns"

    pattern_id = Column(Integer, primary_key=True, autoincrement=True)
    pattern = Column(String, nullable=False)  # The ignore pattern (e.g., "*.tmp", "logs/")
    description = Column(String, nullable=True)  # Optional description/comment
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
