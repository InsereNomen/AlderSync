"""
AlderSync Server - Transaction Lock Model

Dataclass for representing exclusive server locks.
Per Specification.md section 8.4
"""

from datetime import datetime, timezone
from dataclasses import dataclass


@dataclass
class TransactionLock:
    """
    Represents an exclusive lock on the server
    Per Specification.md section 8.4
    """
    user_id: int
    username: str
    operation_type: str  # 'Pull', 'Push', or 'Reconcile'
    locked_at_utc: datetime
    timeout_seconds: int

    def IsExpired(self) -> bool:
        """Check if lock has expired based on timeout"""
        now = datetime.now(timezone.utc)
        elapsed = (now - self.locked_at_utc).total_seconds()
        return elapsed >= self.timeout_seconds

    def ElapsedSeconds(self) -> int:
        """Get elapsed time since lock was acquired"""
        now = datetime.now(timezone.utc)
        return int((now - self.locked_at_utc).total_seconds())
