"""
AlderSync Server - Transaction API Models

Pydantic models for transaction-related endpoints.
"""

from typing import Optional, List
from pydantic import BaseModel

from models.api.client_file_metadata import ClientFileMetadata


class TransactionBeginRequest(BaseModel):
    """Request model for beginning a transaction"""
    operation_type: str  # 'Pull', 'Push', or 'Reconcile'
    service_type: str  # 'Contemporary' or 'Traditional'
    client_files: Optional[dict[str, ClientFileMetadata]] = None  # For Reconcile operations
    description: str = ""  # Description for changelist (empty string by default)


class TransactionBeginResponse(BaseModel):
    """Response model for transaction/begin"""
    transaction_id: str
    lock_acquired: bool
    files_to_pull: Optional[List[str]] = None  # For Reconcile operations
    files_to_push: Optional[List[str]] = None  # For Reconcile operations
    timeout_seconds: int  # Lock timeout duration


class TransactionCommitResponse(BaseModel):
    """Response model for transaction/commit"""
    success: bool
    files_pulled: Optional[int] = None
    files_pushed: Optional[int] = None
    files_total: int


class TransactionRollbackResponse(BaseModel):
    """Response model for transaction/rollback"""
    success: bool
