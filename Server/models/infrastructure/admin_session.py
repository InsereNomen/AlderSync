"""
AlderSync Server - Admin Session Model

Dataclass for representing active admin sessions.
"""

from datetime import datetime, timezone
from dataclasses import dataclass


@dataclass
class AdminSession:
    """Represents an active admin session"""
    session_id: str
    user_id: int
    username: str
    created_at_utc: datetime
    expires_at_utc: datetime

    def IsExpired(self) -> bool:
        """Check if session has expired"""
        return datetime.now(timezone.utc) >= self.expires_at_utc
