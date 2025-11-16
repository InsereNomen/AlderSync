"""
AlderSync Server - Transaction File Operations Endpoints

This module contains endpoints for file operations within transactions
including upload, download, and delete operations.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, File as FastAPIFile, UploadFile, Form
from fastapi.responses import FileResponse

from models.database import User, File
from models.api import FileUploadResponse, FileDeleteRequest, FileDeleteResponse
from auth import GetCurrentActiveUser
from file_storage import CalculateFileHash, GetRevisionPath
from transactions import GetTransaction, IsTransactionCancelled


# Create logger
logger = logging.getLogger(__name__)

# Create router instance
router = APIRouter()


# ==================== Transaction File Operations Endpoints ====================

@router.post("/transaction/{transaction_id}/upload_file", response_model=FileUploadResponse, tags=["Transactions"])
async def upload_file(
    transaction_id: str,
    file: UploadFile = FastAPIFile(...),
    path: str = Form(..., description="Relative path within service storage"),
    current_user: User = Depends(GetCurrentActiveUser)
):
    """
    Upload a file to transaction staging area
    Per Specification.md section 5.1.2

    This endpoint accepts a file upload and stores it in the transaction's staging area.
    Files are not committed to permanent storage until the transaction is committed.

    Args:
        transaction_id: Transaction ID to upload file to
        file: File to upload (multipart/form-data)
        path: Relative path for the file within service storage
        current_user: Currently authenticated user

    Returns:
        FileUploadResponse with success status, file hash, path, and size

    Raises:
        HTTPException: If transaction not found or user doesn't own transaction
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
            detail="Cannot upload to transaction from another user"
        )

    try:
        # Create full path in staging area preserving directory structure
        staged_file_path = transaction.staging_path / path
        staged_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Save uploaded file to staging area
        with open(staged_file_path, 'wb') as f:
            # Read file in chunks to handle large files efficiently
            while chunk := await file.read(8192):
                f.write(chunk)

        # Calculate file hash
        file_hash = CalculateFileHash(staged_file_path)

        # Get file size
        file_size = staged_file_path.stat().st_size

        # Track uploaded file in transaction
        transaction.uploaded_files.append(path)

        logger.info(
            f"User '{current_user.username}' uploaded file '{path}' to transaction {transaction_id} "
            f"(size: {file_size} bytes, hash: {file_hash[:16]}...)"
        )

        return FileUploadResponse(
            success=True,
            file_hash=file_hash,
            path=path,
            size=file_size
        )

    except Exception as e:
        logger.error(f"Error uploading file '{path}' to transaction {transaction_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )


@router.get("/transaction/{transaction_id}/download_file", tags=["Transactions"])
async def download_file_in_transaction(
    transaction_id: str,
    path: str = Query(..., description="Relative path to the file"),
    current_user: User = Depends(GetCurrentActiveUser)
):
    """
    Download a file from storage within a transaction (for Reconcile pulls)
    Per Specification.md section 9.6

    This endpoint allows clients to download files from the server during a Reconcile operation.
    The transaction must be owned by the current user and the file must be in the files_to_pull list.

    Args:
        transaction_id: Transaction ID to download file from
        path: Relative path to the file
        current_user: Currently authenticated user

    Returns:
        FileResponse: Binary file content

    Raises:
        HTTPException: If transaction not found, user doesn't own transaction, or file not found
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
            detail="Cannot download file from transaction of another user"
        )

    try:
        # Find the highest revision (current version) for this file
        session = db_manager.GetSession()
        try:
            file_record = session.query(File).filter(
                File.path == path,
                File.service_type == transaction.service_type
            ).order_by(File.revision.desc()).first()

            if not file_record:
                logger.error(f"File not found in database: {path} ({transaction.service_type})")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File not found: {path}"
                )

            if file_record.is_deleted:
                logger.error(f"File is deleted: {path} ({transaction.service_type})")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File has been deleted: {path}"
                )

            current_revision = file_record.revision

        finally:
            session.close()

        # Get physical file path for the current revision
        file_path = GetRevisionPath(path, current_revision, transaction.service_type)

        # Verify physical file exists
        if not file_path.exists():
            logger.error(f"File exists in database but not on disk: {path} revision {current_revision} ({transaction.service_type})")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {path}"
            )

        # Return file as streaming response
        logger.info(
            f"User '{current_user.username}' downloading file '{path}' revision {current_revision} from transaction {transaction_id} "
            f"(size: {file_path.stat().st_size} bytes)"
        )

        return FileResponse(
            path=str(file_path),
            filename=file_path.name,
            media_type='application/octet-stream'
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error downloading file '{path}' from transaction {transaction_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download file: {str(e)}"
        )


@router.post("/transaction/{transaction_id}/delete_file", response_model=FileDeleteResponse, tags=["Transactions"])
async def delete_file(
    transaction_id: str,
    request: FileDeleteRequest,
    current_user: User = Depends(GetCurrentActiveUser)
):
    """
    Mark a file for deletion within a transaction
    Per Specification.md section 8.3: File Deletion Synchronization

    This endpoint marks a file for deletion within the transaction's context.
    The file is not actually deleted until the transaction is committed.
    On commit, the file will be marked as deleted in the database and moved to a revision.

    Args:
        transaction_id: Transaction ID to delete file in
        request: File deletion request with path
        current_user: Currently authenticated user

    Returns:
        FileDeleteResponse with success status and path

    Raises:
        HTTPException: If transaction not found or user doesn't own transaction
    """
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
            detail="Cannot delete file in transaction from another user"
        )

    try:
        # Track deleted file in transaction
        transaction.deleted_files.append(request.path)

        logger.info(
            f"User '{current_user.username}' marked file '{request.path}' for deletion in transaction {transaction_id}"
        )

        return FileDeleteResponse(
            success=True,
            path=request.path
        )

    except Exception as e:
        logger.error(f"Error marking file '{request.path}' for deletion in transaction {transaction_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark file for deletion: {str(e)}"
        )
