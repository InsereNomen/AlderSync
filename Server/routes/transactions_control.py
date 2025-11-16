"""
AlderSync Server - Transaction Control Endpoints

This module contains endpoints for controlling transactions including
begin, commit, and rollback operations.
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status

from models.database import User, Operation, LastOperation, Setting
from models.api import (
    TransactionBeginRequest, TransactionBeginResponse,
    TransactionCommitResponse, TransactionRollbackResponse
)
from auth import GetCurrentActiveUser, UserHasPermission
from file_storage import ListFiles, CompareFilesForReconcile
from transactions import (
    AcquireLock, ReleaseLock, CreateTransaction, GetTransaction,
    CommitTransaction, RollbackTransaction, IsTransactionCancelled
)


# Create logger
logger = logging.getLogger(__name__)

# Create router instance
router = APIRouter()


# ==================== Transaction Control Endpoints ====================

@router.post("/transaction/begin", response_model=TransactionBeginResponse, tags=["Transactions"])
async def begin_transaction(
    request: TransactionBeginRequest,
    current_user: User = Depends(GetCurrentActiveUser)
):
    """
    Begin a new transaction and acquire exclusive server lock
    Per Specification.md sections 5.1.2 and 9.3

    Args:
        request: Operation type and service type
        current_user: Currently authenticated user

    Returns:
        TransactionBeginResponse with transaction_id and lock status

    Raises:
        HTTPException: If lock cannot be acquired or parameters are invalid
    """
    from database import db_manager

    # Validate operation type
    valid_operations = ["Pull", "Push", "Reconcile"]
    if request.operation_type not in valid_operations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid operation_type. Must be one of: {', '.join(valid_operations)}"
        )

    # Validate service type
    valid_service_types = ["Contemporary", "Traditional"]
    if request.service_type not in valid_service_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid service_type. Must be one of: {', '.join(valid_service_types)}"
        )

    # Check permissions based on operation type
    if request.operation_type == "Push":
        if not UserHasPermission(current_user, "can_push", db_manager):
            logger.warning(f"User {current_user.username} denied Push operation - missing can_push permission")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform Push operations"
            )
    elif request.operation_type == "Reconcile":
        if not UserHasPermission(current_user, "can_reconcile", db_manager):
            logger.warning(f"User {current_user.username} denied Reconcile operation - missing can_reconcile permission")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform Reconcile operations"
            )
    # Pull operations are allowed for all authenticated users (no additional permission check needed)

    # Get lock timeout settings
    session = db_manager.GetSession()
    try:
        timeout_setting = session.query(Setting).filter(Setting.key == "lock_timeout_seconds").first()
        default_timeout_seconds = int(timeout_setting.value) if timeout_setting else 300  # Default 5 minutes

        min_timeout_setting = session.query(Setting).filter(Setting.key == "min_lock_timeout_seconds").first()
        min_timeout_seconds = int(min_timeout_setting.value) if min_timeout_setting else 300  # Default 5 minutes

        # For Reconcile operations, calculate files to pull/push and dynamic timeout
        files_to_pull = None
        files_to_push = None
        timeout_seconds = default_timeout_seconds

        if request.operation_type == "Reconcile":
            # Validate that client_files is provided for Reconcile
            if not request.client_files:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="client_files is required for Reconcile operations"
                )

            # Convert Pydantic models to dictionaries for comparison
            client_files_dict = {
                path: {
                    'modified_utc': meta.modified_utc,
                    'size': meta.size,
                    'hash': meta.hash
                }
                for path, meta in request.client_files.items()
            }

            # Compare files to determine what needs to be synced
            files_to_pull, files_to_push = CompareFilesForReconcile(
                db_manager,
                client_files_dict,
                request.service_type
            )

            # Calculate dynamic timeout based on file count and size
            # Per Specification.md section 9.6.4:
            # timeout = max(min_lock_timeout_seconds, (total_size_mb / 1) + (file_count * 2))
            total_file_count = len(files_to_pull) + len(files_to_push)

            # Calculate total size (estimate from metadata)
            total_size_bytes = 0
            server_files_list = ListFiles(db_manager, request.service_type, include_deleted=False)
            server_files = {f['path']: f for f in server_files_list}

            for path in files_to_pull:
                if path in server_files:
                    total_size_bytes += server_files[path]['size'] or 0

            for path in files_to_push:
                if path in client_files_dict:
                    total_size_bytes += client_files_dict[path]['size'] or 0

            total_size_mb = total_size_bytes / (1024 * 1024)  # Convert to MB

            # Calculate dynamic timeout
            calculated_timeout = int((total_size_mb / 1) + (total_file_count * 2))
            timeout_seconds = max(min_timeout_seconds, calculated_timeout)

            logger.info(
                f"Reconcile dynamic timeout: {timeout_seconds}s "
                f"({total_file_count} files, {total_size_mb:.2f} MB)"
            )

        # Attempt to acquire lock
        lock_acquired, error_message = AcquireLock(
            user_id=current_user.user_id,
            username=current_user.username,
            operation_type=request.operation_type,
            timeout_seconds=timeout_seconds
        )

        if not lock_acquired:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_message
            )

        # Create operation record in database
        new_operation = Operation(
            user_id=current_user.user_id,
            operation_type=request.operation_type,
            service_type=request.service_type,
            locked_at_utc=datetime.now(timezone.utc),
            status="active"
        )
        session.add(new_operation)
        session.commit()
        session.refresh(new_operation)
        operation_id = new_operation.operation_id

        # Create transaction
        transaction = CreateTransaction(
            user_id=current_user.user_id,
            username=current_user.username,
            operation_type=request.operation_type,
            service_type=request.service_type,
            operation_id=operation_id,
            timeout_seconds=timeout_seconds,
            files_to_pull=files_to_pull or [],
            files_to_push=files_to_push or [],
            description=request.description
        )

        logger.info(
            f"User '{current_user.username}' began {request.operation_type} transaction "
            f"on {request.service_type} service (transaction_id: {transaction.transaction_id})"
        )

        return TransactionBeginResponse(
            transaction_id=transaction.transaction_id,
            lock_acquired=True,
            files_to_pull=files_to_pull,
            files_to_push=files_to_push,
            timeout_seconds=timeout_seconds
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Error beginning transaction: {str(e)}")
        # Release lock if we acquired it
        ReleaseLock()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to begin transaction"
        )
    finally:
        session.close()


@router.post("/transaction/{transaction_id}/commit", response_model=TransactionCommitResponse, tags=["Transactions"])
async def commit_transaction(
    transaction_id: str,
    current_user: User = Depends(GetCurrentActiveUser)
):
    """
    Commit a transaction and release lock
    Per Specification.md sections 5.1.2 and 9.3

    Args:
        transaction_id: Transaction ID to commit
        current_user: Currently authenticated user

    Returns:
        TransactionCommitResponse with file counts

    Raises:
        HTTPException: If transaction not found or cannot be committed
    """
    from database import db_manager

    # Get transaction
    transaction = GetTransaction(transaction_id)
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction {transaction_id} not found"
        )

    # Check if transaction was cancelled by admin
    if IsTransactionCancelled(transaction_id, db_manager):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Operation cancelled by administrator"
        )

    # Verify transaction belongs to current user
    if transaction.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot commit transaction from another user"
        )

    session = db_manager.GetSession()
    try:
        # Update operation record in database
        operation = session.query(Operation).filter(Operation.operation_id == transaction.operation_id).first()
        if operation:
            operation.status = "completed"
            operation.completed_at_utc = datetime.now(timezone.utc)
            # For Reconcile operations, track file counts
            if transaction.operation_type == "Reconcile":
                operation.files_pulled = len(transaction.files_to_pull)
                operation.files_pushed = len(transaction.files_to_push)
            session.commit()

        # Update last operation tracking
        last_op = session.query(LastOperation).filter(LastOperation.id == 1).first()
        if last_op:
            last_op.username = current_user.username
            last_op.operation_type = transaction.operation_type
            last_op.service_type = transaction.service_type
            last_op.timestamp_utc = datetime.now(timezone.utc)
            last_op.file_count = len(transaction.uploaded_files) if transaction.operation_type == "Push" else 0
            session.commit()

        # Commit transaction (moves files to storage, releases lock, cleans up staging)
        success = CommitTransaction(transaction_id, db_manager)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to commit transaction"
            )

        logger.info(
            f"User '{current_user.username}' committed transaction {transaction_id} "
            f"({transaction.operation_type} on {transaction.service_type})"
        )

        # Calculate file counts for response
        files_pulled = len(transaction.files_to_pull) if transaction.operation_type == "Reconcile" else None
        files_pushed = len(transaction.files_to_push) if transaction.operation_type == "Reconcile" else None
        files_total = len(transaction.uploaded_files)

        return TransactionCommitResponse(
            success=True,
            files_pulled=files_pulled,
            files_pushed=files_pushed,
            files_total=files_total
        )

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Error committing transaction {transaction_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to commit transaction"
        )
    finally:
        session.close()


@router.post("/transaction/{transaction_id}/rollback", response_model=TransactionRollbackResponse, tags=["Transactions"])
async def rollback_transaction(
    transaction_id: str,
    current_user: User = Depends(GetCurrentActiveUser)
):
    """
    Rollback a transaction and release lock
    Per Specification.md sections 5.1.2 and 9.3

    Args:
        transaction_id: Transaction ID to rollback
        current_user: Currently authenticated user

    Returns:
        TransactionRollbackResponse indicating success

    Raises:
        HTTPException: If transaction not found or cannot be rolled back
    """
    from database import db_manager

    # Get transaction
    transaction = GetTransaction(transaction_id)
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction {transaction_id} not found"
        )

    # Verify transaction belongs to current user
    if transaction.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot rollback transaction from another user"
        )

    session = db_manager.GetSession()
    try:
        # Update operation record in database
        operation = session.query(Operation).filter(Operation.operation_id == transaction.operation_id).first()
        if operation:
            operation.status = "rolled_back"
            operation.completed_at_utc = datetime.now(timezone.utc)
            session.commit()

        # Rollback transaction (releases lock and cleans up staging)
        success = RollbackTransaction(transaction_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to rollback transaction"
            )

        logger.info(
            f"User '{current_user.username}' rolled back transaction {transaction_id} "
            f"({transaction.operation_type} on {transaction.service_type})"
        )

        return TransactionRollbackResponse(success=True)

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Error rolling back transaction {transaction_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to rollback transaction"
        )
    finally:
        session.close()
