"""
AlderSync Server - Transaction Model

Dataclass for representing active transactions.
Per Specification.md section 9.3
"""

from datetime import datetime
from pathlib import Path
from typing import List
from dataclasses import dataclass


@dataclass
class Transaction:
    """
    Represents an active transaction
    Per Specification.md section 9.3
    """
    transaction_id: str
    user_id: int
    username: str
    operation_type: str  # 'Pull', 'Push', or 'Reconcile'
    service_type: str  # 'Contemporary' or 'Traditional'
    created_at_utc: datetime
    operation_id: int  # Foreign key to Operations table
    staging_path: Path
    files_to_pull: List[str]  # For Reconcile operations
    files_to_push: List[str]  # For Reconcile operations
    uploaded_files: List[str]  # Track uploaded files for rollback
    deleted_files: List[str]  # Track deleted files for commit
    description: str = ""  # Description for changelist (empty string by default)

    def IsActive(self) -> bool:
        """Check if transaction is still active (not expired)"""
        # Transactions inherit lock timeout
        from transactions import GetCurrentLock
        _current_lock = GetCurrentLock()
        if _current_lock and _current_lock.IsExpired():
            return False
        return True
