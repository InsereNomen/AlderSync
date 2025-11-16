"""
AlderSync Server - Transaction Management

This module manages transaction state, locking, and staging area for file operations.
Per Specification.md sections 8.4, 9.3, and 9.5
"""

import uuid
import logging
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Optional, List

from models.infrastructure import Transaction, TransactionLock

logger = logging.getLogger(__name__)

# Storage paths
STAGING_ROOT = Path("staging")

# Transaction storage (in-memory only for MVP)
_active_transactions: Dict[str, Transaction] = {}
_current_lock: Optional[TransactionLock] = None


def InitializeStagingArea() -> None:
    """
    Initialize the staging area directory structure
    Called during server startup
    """
    STAGING_ROOT.mkdir(parents=True, exist_ok=True)
    logger.info(f"Staging area initialized: {STAGING_ROOT.absolute()}")


def GetCurrentLock() -> Optional[TransactionLock]:
    """Get the current active lock, if any (checking for expiration)"""
    global _current_lock

    if _current_lock is None:
        return None

    # Check if lock expired
    if _current_lock.IsExpired():
        logger.info(f"Lock expired for user '{_current_lock.username}' after {_current_lock.timeout_seconds}s")
        _current_lock = None
        return None

    return _current_lock


def AcquireLock(user_id: int, username: str, operation_type: str, timeout_seconds: int) -> tuple[bool, Optional[str]]:
    """
    Attempt to acquire exclusive server lock

    Returns:
        (success: bool, error_message: Optional[str])
    """
    global _current_lock

    # Check if lock already exists and is not expired
    current_lock = GetCurrentLock()
    if current_lock is not None:
        elapsed = current_lock.ElapsedSeconds()
        error_msg = (
            f"Server is busy - {current_lock.username} is currently "
            f"{current_lock.operation_type} files (started {elapsed} seconds ago)"
        )
        return False, error_msg

    # Acquire new lock
    _current_lock = TransactionLock(
        user_id=user_id,
        username=username,
        operation_type=operation_type,
        locked_at_utc=datetime.now(timezone.utc),
        timeout_seconds=timeout_seconds
    )

    logger.info(f"Lock acquired by user '{username}' for {operation_type} operation (timeout: {timeout_seconds}s)")
    return True, None


def ReleaseLock() -> None:
    """Release the current server lock"""
    global _current_lock

    if _current_lock:
        logger.info(f"Lock released for user '{_current_lock.username}'")
        _current_lock = None


def CreateTransaction(
    user_id: int,
    username: str,
    operation_type: str,
    service_type: str,
    operation_id: int,
    timeout_seconds: int,
    files_to_pull: Optional[List[str]] = None,
    files_to_push: Optional[List[str]] = None,
    description: str = ""
) -> Transaction:
    """
    Create a new transaction

    Args:
        user_id: User ID performing the operation
        username: Username for logging
        operation_type: 'Pull', 'Push', or 'Reconcile'
        service_type: 'Contemporary' or 'Traditional'
        operation_id: ID from Operations table
        timeout_seconds: Lock timeout duration
        files_to_pull: List of files to pull (for Reconcile)
        files_to_push: List of files to push (for Reconcile)
        description: Description for changelist (empty string by default)

    Returns:
        Transaction object
    """
    # Generate unique transaction ID
    transaction_id = str(uuid.uuid4())

    # Create staging directory for this transaction
    staging_path = STAGING_ROOT / transaction_id
    staging_path.mkdir(parents=True, exist_ok=True)

    # Create transaction object
    transaction = Transaction(
        transaction_id=transaction_id,
        user_id=user_id,
        username=username,
        operation_type=operation_type,
        service_type=service_type,
        created_at_utc=datetime.now(timezone.utc),
        operation_id=operation_id,
        staging_path=staging_path,
        files_to_pull=files_to_pull or [],
        files_to_push=files_to_push or [],
        uploaded_files=[],
        deleted_files=[],
        description=description
    )

    # Store in active transactions
    _active_transactions[transaction_id] = transaction

    logger.info(f"Transaction {transaction_id} created for {username} ({operation_type} on {service_type})")

    return transaction


def GetTransaction(transaction_id: str) -> Optional[Transaction]:
    """Get a transaction by ID"""
    return _active_transactions.get(transaction_id)


def IsTransactionCancelled(transaction_id: str, db_manager) -> bool:
    """
    Check if a transaction has been cancelled by admin
    Per Specification.md section 9.6.5

    Args:
        transaction_id: Transaction ID to check
        db_manager: DatabaseManager instance to query operation status

    Returns:
        True if transaction is cancelled, False otherwise
    """
    transaction = _active_transactions.get(transaction_id)
    if not transaction:
        return False

    # Query database to check if operation was cancelled
    db_session = db_manager.GetSession()
    try:
        from models.database import Operation
        operation = db_session.query(Operation).filter_by(operation_id=transaction.operation_id).first()
        if operation and operation.status == 'cancelled_by_admin':
            return True
        return False
    finally:
        db_session.close()


def CommitTransaction(transaction_id: str, db_manager=None) -> bool:
    """
    Commit a transaction (finalize changes)
    Moves staged files to permanent storage, creates revisions if needed, and updates database

    Args:
        transaction_id: Transaction ID to commit
        db_manager: DatabaseManager instance for file metadata operations

    Returns:
        True if successful, False otherwise
    """
    transaction = _active_transactions.get(transaction_id)
    if not transaction:
        logger.warning(f"Attempted to commit non-existent transaction: {transaction_id}")
        return False

    try:
        # Import here to avoid circular import
        from file_storage import GetFilePath, GetRevisionPath, CalculateFileHash, StoreFileMetadata, GetNextRevisionNumber, GetFileMetadata, DeleteFile
        from managers.database_manager import DatabaseManager as DB
        from models.database import Changelist
        from datetime import datetime, timezone

        # Use provided db_manager or create new instance
        if db_manager is None:
            db_manager = DB()

        # Create changelist if files are being uploaded
        changelist_id = None
        if transaction.uploaded_files:
            session = db_manager.GetSession()
            try:
                changelist = Changelist(
                    user_id=transaction.user_id,
                    created_at_utc=datetime.now(timezone.utc),
                    operation_type=transaction.operation_type,
                    description=transaction.description
                )
                session.add(changelist)
                session.commit()
                changelist_id = changelist.changelist_id
                logger.info(f"Created changelist {changelist_id} for transaction {transaction_id}")
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to create changelist: {str(e)}")
                # Continue without changelist_id
            finally:
                session.close()

        # Process deleted files first
        for relative_path in transaction.deleted_files:
            try:
                DeleteFile(db_manager, relative_path, transaction.service_type)
                logger.info(f"Deleted file as part of transaction: {relative_path}")
            except Exception as e:
                logger.error(f"Failed to delete file {relative_path}: {str(e)}")
                # Continue with other files

        # Move files from staging to storage
        for relative_path in transaction.uploaded_files:
            staged_file_path = transaction.staging_path / relative_path

            if not staged_file_path.exists():
                logger.warning(f"Staged file not found: {staged_file_path}")
                continue

            # Get next revision number (0 for first upload, increments from there)
            next_revision = GetNextRevisionNumber(db_manager, relative_path, transaction.service_type)
            logger.info(f"Next revision number for {relative_path}: {next_revision}")

            # Get destination path with revision number
            storage_file_path = GetRevisionPath(relative_path, next_revision, transaction.service_type)

            # Ensure destination directory exists
            storage_file_path.parent.mkdir(parents=True, exist_ok=True)

            # Move file from staging to storage with revision number
            shutil.move(str(staged_file_path), str(storage_file_path))
            logger.info(f"Moved file from staging to storage as revision {next_revision}: {relative_path}")

            # Calculate file metadata
            file_hash = CalculateFileHash(storage_file_path)
            file_size = storage_file_path.stat().st_size
            modified_utc = datetime.now(timezone.utc)

            # Store file metadata in database with revision number
            StoreFileMetadata(
                db_manager,
                relative_path,
                transaction.service_type,
                file_hash,
                file_size,
                modified_utc,
                revision=next_revision,
                is_deleted=False,
                user_id=transaction.user_id,
                changelist_id=changelist_id
            )
            logger.info(f"Stored metadata for file: {relative_path} (revision {next_revision})")

    except Exception as e:
        logger.error(f"Error committing transaction {transaction_id}: {str(e)}")
        # Don't return False here - we still want to clean up staging and release lock
        # The error will be logged but transaction will be marked as committed

    # Clean up staging area
    if transaction.staging_path.exists():
        shutil.rmtree(transaction.staging_path)
        logger.info(f"Removed staging area for transaction {transaction_id}")

    # Remove from active transactions
    del _active_transactions[transaction_id]

    # Release lock
    ReleaseLock()

    logger.info(f"Transaction {transaction_id} committed successfully")
    return True


def RollbackTransaction(transaction_id: str) -> bool:
    """
    Rollback a transaction (discard all changes)

    Args:
        transaction_id: Transaction ID to rollback

    Returns:
        True if successful, False otherwise
    """
    transaction = _active_transactions.get(transaction_id)
    if not transaction:
        logger.warning(f"Attempted to rollback non-existent transaction: {transaction_id}")
        return False

    # Delete staging area and all staged files
    if transaction.staging_path.exists():
        shutil.rmtree(transaction.staging_path)
        logger.info(f"Removed staging area for transaction {transaction_id} (rollback)")

    # Remove from active transactions
    del _active_transactions[transaction_id]

    # Release lock
    ReleaseLock()

    logger.info(f"Transaction {transaction_id} rolled back successfully")
    return True


def GetActiveLockInfo() -> Optional[Dict]:
    """
    Get information about the current active lock
    Per Specification.md section 5.1.4

    Returns:
        Dictionary with lock info, or None if no lock active
    """
    lock = GetCurrentLock()
    if not lock:
        return None

    return {
        "locked": True,
        "user": lock.username,
        "operation": lock.operation_type,
        "started_ago_seconds": lock.ElapsedSeconds()
    }


def GetAllActiveTransactions() -> List[Dict]:
    """
    Get information about all active transactions
    Used by admin interface to display active operations

    Returns:
        List of dictionaries with transaction info
    """
    transactions_info = []

    for transaction_id, transaction in _active_transactions.items():
        duration_seconds = int((datetime.now(timezone.utc) - transaction.created_at_utc).total_seconds())

        transactions_info.append({
            "transaction_id": transaction_id,
            "username": transaction.username,
            "operation_type": transaction.operation_type,
            "service_type": transaction.service_type,
            "duration_seconds": duration_seconds,
            "files_to_pull": len(transaction.files_to_pull) if transaction.files_to_pull else None,
            "files_to_push": len(transaction.files_to_push) if transaction.files_to_push else None,
        })

    return transactions_info


def CancelTransaction(transaction_id: str, db_manager) -> tuple[bool, str]:
    """
    Cancel a transaction by admin
    Per Specification.md section 9.6.5

    Args:
        transaction_id: Transaction ID to cancel
        db_manager: DatabaseManager instance to update operation status

    Returns:
        (success: bool, message: str)
    """
    transaction = _active_transactions.get(transaction_id)
    if not transaction:
        return False, "Transaction not found or already completed"

    try:
        # Update operation status in database to 'cancelled_by_admin'
        db_session = db_manager.GetSession()
        try:
            from models.database import Operation
            operation = db_session.query(Operation).filter_by(operation_id=transaction.operation_id).first()
            if operation:
                operation.status = 'cancelled_by_admin'
                operation.completed_at_utc = datetime.now(timezone.utc)
                db_session.commit()
                logger.info(f"Marked operation {transaction.operation_id} as cancelled_by_admin")
        finally:
            db_session.close()

        # Rollback the transaction (deletes staging area)
        if transaction.staging_path.exists():
            shutil.rmtree(transaction.staging_path)
            logger.info(f"Removed staging area for cancelled transaction {transaction_id}")

        # Remove from active transactions
        del _active_transactions[transaction_id]

        # Release lock
        ReleaseLock()

        logger.info(f"Transaction {transaction_id} cancelled by admin successfully")
        return True, "Operation cancelled successfully"

    except Exception as e:
        logger.error(f"Error cancelling transaction {transaction_id}: {str(e)}")
        return False, f"Error cancelling operation: {str(e)}"
