"""
AlderSync Server - File Operations Endpoints

This module contains endpoints for file operations including listing,
downloading, and managing file revisions.
"""

import logging
import shutil
from datetime import datetime, timezone
from typing import List
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse

from models.database import User, File
from models.api import FileMetadata, RestoreRevisionRequest, RestoreRevisionResponse
from auth import GetCurrentActiveUser
from file_storage import (
    ListFiles, GetFilePath, GetRevisionPath, CalculateFileHash,
    StoreFileMetadata, CreateRevision
)


# Create logger
logger = logging.getLogger(__name__)

# Create router instance
router = APIRouter()


# ==================== File Operations Endpoints ====================

@router.get("/files/list", response_model=List[FileMetadata], tags=["Files"])
async def list_files(
    service_type: str = Query(..., description="Service type: Contemporary or Traditional"),
    current_user: User = Depends(GetCurrentActiveUser)
):
    """
    List all files for a service type
    Per Specification.md section 5.1.3

    Returns list of current files (revision 0) that are not deleted.
    Excludes deleted files and old revisions.

    Args:
        service_type: 'Contemporary' or 'Traditional'
        current_user: Currently authenticated user (from JWT token)

    Returns:
        List[FileMetadata]: List of file metadata objects

    Raises:
        HTTPException: If service_type is invalid
    """
    from database import db_manager

    # Validate service type
    valid_service_types = ["Contemporary", "Traditional"]
    if service_type not in valid_service_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid service_type. Must be one of: {', '.join(valid_service_types)}"
        )

    try:
        # Get list of files from database (excludes deleted files and old revisions)
        files = ListFiles(db_manager, service_type, include_deleted=False)

        # Convert to response format
        file_list = []
        for file_data in files:
            file_list.append(FileMetadata(
                path=file_data['path'],
                size=file_data['size'],
                hash=file_data['file_hash'],
                modified_utc=file_data['last_modified_utc']
            ))

        logger.info(f"User '{current_user.username}' listed {len(file_list)} files for {service_type} service")

        return file_list

    except Exception as e:
        logger.error(f"Error listing files for {service_type}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve file list"
        )


@router.get("/files/download", tags=["Files"])
async def download_file(
    path: str = Query(..., description="Relative path to the file"),
    service_type: str = Query(..., description="Service type: Contemporary or Traditional"),
    current_user: User = Depends(GetCurrentActiveUser)
):
    """
    Download a file from the server
    Per Specification.md section 5.1.3

    Streams file content as binary response.
    Validates file exists and is not deleted before allowing download.

    Args:
        path: Relative path to the file (e.g., "sermon_notes.txt")
        service_type: 'Contemporary' or 'Traditional'
        current_user: Currently authenticated user (from JWT token)

    Returns:
        FileResponse: Binary file content with appropriate headers

    Raises:
        HTTPException: If service_type is invalid, file not found, or file is deleted
    """
    from database import db_manager

    # Validate service type
    valid_service_types = ["Contemporary", "Traditional"]
    if service_type not in valid_service_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid service_type. Must be one of: {', '.join(valid_service_types)}"
        )

    try:
        # Check if file exists in database and is not deleted
        # Get the file with the highest revision number (current version)
        session = db_manager.GetSession()
        try:
            file_record = session.query(File).filter(
                File.path == path,
                File.service_type == service_type
            ).order_by(File.revision.desc()).first()

            if not file_record:
                logger.warning(f"User '{current_user.username}' attempted to download non-existent file: {path} ({service_type})")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File not found: {path}"
                )

            if file_record.is_deleted:
                logger.warning(f"User '{current_user.username}' attempted to download deleted file: {path} ({service_type})")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File has been deleted: {path}"
                )

            current_revision = file_record.revision

        finally:
            session.close()

        # Get physical file path for the current revision
        file_path = GetRevisionPath(path, current_revision, service_type)

        # Verify physical file exists
        if not file_path.exists():
            logger.error(f"File exists in database but not on disk: {path} revision {current_revision} ({service_type})")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="File metadata exists but file is missing on disk"
            )

        # Return file as streaming response
        logger.info(f"User '{current_user.username}' downloading file: {path} revision {current_revision} ({service_type}, {file_path.stat().st_size} bytes)")

        return FileResponse(
            path=str(file_path),
            filename=file_path.name,
            media_type='application/octet-stream'
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error downloading file {path} ({service_type}): {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download file"
        )


@router.get("/files/download_revision", tags=["Files"])
async def download_file_revision(
    path: str = Query(..., description="Relative path to the file"),
    revision: int = Query(..., description="Revision number to download"),
    service_type: str = Query(..., description="Service type: Contemporary or Traditional"),
    current_user: User = Depends(GetCurrentActiveUser)
):
    """
    Download a specific revision of a file without affecting the database

    This endpoint allows downloading any revision of a file for viewing or
    recovery purposes without changing the current file state or creating
    new revisions in the database.

    Args:
        path: Relative path to the file (e.g., "sermon_notes.txt")
        revision: Revision number (0 = initial version, highest = current version)
        service_type: 'Contemporary' or 'Traditional'
        current_user: Currently authenticated user (from JWT token)

    Returns:
        FileResponse: Binary file content with appropriate headers

    Raises:
        HTTPException: If service_type is invalid, revision not found, or file doesn't exist
    """
    from database import db_manager

    # Validate service type
    valid_service_types = ["Contemporary", "Traditional"]
    if service_type not in valid_service_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid service_type. Must be one of: {', '.join(valid_service_types)}"
        )

    # Validate revision number
    if revision < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Revision number must be >= 0"
        )

    try:
        # Check if revision exists in database
        session = db_manager.GetSession()
        try:
            file_record = session.query(File).filter(
                File.path == path,
                File.service_type == service_type,
                File.revision == revision
            ).first()

            if not file_record:
                logger.warning(f"User '{current_user.username}' attempted to download non-existent revision: {path} rev {revision} ({service_type})")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Revision {revision} not found for file: {path}"
                )
        finally:
            session.close()

        # Get physical file path for this revision
        file_path = GetRevisionPath(path, revision, service_type)

        # Verify physical file exists
        if not file_path.exists():
            logger.error(f"Revision exists in database but not on disk: {path} rev {revision} ({service_type})")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Revision metadata exists but file is missing on disk"
            )

        # Return file as streaming response
        logger.info(f"User '{current_user.username}' downloading revision {revision} of file: {path} ({service_type}, {file_path.stat().st_size} bytes)")

        return FileResponse(
            path=str(file_path),
            filename=file_path.name,
            media_type='application/octet-stream'
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error downloading revision {revision} of file {path} ({service_type}): {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download file revision"
        )


@router.get("/files/revisions", tags=["Files"])
async def get_file_revisions(
    path: str = Query(..., description="Relative path to the file"),
    service_type: str = Query(..., description="Service type: Contemporary or Traditional"),
    current_user: User = Depends(GetCurrentActiveUser)
):
    """
    Get all revisions of a file
    Per Specification.md section 5.1.3

    Returns a list of all revisions for the specified file, sorted by revision number
    (newest first). Revision 0 is the initial version, and the highest revision
    number is always the current version.

    Args:
        path: Relative path to file
        service_type: Service type (Contemporary or Traditional)
        current_user: Currently authenticated user

    Returns:
        List of revision metadata (revision, size, modified_utc, hash, username, changelist_id)

    Raises:
        HTTPException: If service_type is invalid or error occurs
    """
    from database import db_manager

    # Validate service type
    valid_service_types = ["Contemporary", "Traditional"]
    if service_type not in valid_service_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid service_type. Must be one of: {', '.join(valid_service_types)}"
        )

    try:
        # Get all revisions from database using SQLAlchemy to include username
        session = db_manager.GetSession()
        try:
            file_revisions = session.query(File).filter(
                File.service_type == service_type,
                File.path == path
            ).order_by(File.revision.desc()).all()

            response = []
            for file in file_revisions:
                # Get username if user_id is set
                username = None
                if file.user_id:
                    user = session.query(User).filter(User.user_id == file.user_id).first()
                    if user:
                        username = user.username

                response.append({
                    "revision": file.revision,
                    "size": file.size,
                    "modified_utc": file.last_modified_utc.isoformat() if file.last_modified_utc else None,
                    "hash": file.file_hash,
                    "username": username,
                    "changelist_id": file.changelist_id
                })

            logger.info(f"User '{current_user.username}' listed {len(response)} revisions for '{path}' ({service_type})")
            return response
        finally:
            session.close()

    except Exception as e:
        logger.error(f"Error getting revisions for {path} ({service_type}): {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get file revisions"
        )


@router.post("/files/restore_revision", response_model=RestoreRevisionResponse, tags=["Files"])
async def restore_file_revision(
    request: RestoreRevisionRequest,
    current_user: User = Depends(GetCurrentActiveUser)
):
    """
    Restore an old revision of a file
    Per Specification.md section 5.1.3

    This makes an old revision the current version by:
    1. Creating a revision of the current file (archives current as new revision)
    2. Creating a new revision with the old revision's content
    3. The new revision becomes the current version (highest revision number)

    Args:
        request: Restore request with path, revision number, and service_type
        current_user: Currently authenticated user

    Returns:
        RestoreRevisionResponse indicating success

    Raises:
        HTTPException: If revision not found or restore fails
    """
    from database import db_manager
    from file_storage import GetNextRevisionNumber

    # Validate service type
    valid_service_types = ["Contemporary", "Traditional"]
    if request.service_type not in valid_service_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid service_type. Must be one of: {', '.join(valid_service_types)}"
        )

    # Validate revision number
    if request.revision < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Revision number must be >= 0"
        )

    try:
        # Get all revisions to find the current (highest) revision
        session = db_manager.GetSession()
        try:
            file_revisions = session.query(File).filter(
                File.path == request.path,
                File.service_type == request.service_type
            ).order_by(File.revision.desc()).all()

            if not file_revisions:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File not found: {request.path}"
                )

            # Get current (highest) revision number
            current_revision = file_revisions[0].revision

            # Validate that we're not trying to restore the current revision
            if request.revision == current_revision:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Revision {request.revision} is already the current version"
                )

            # Validate that the requested revision exists
            revision_exists = any(rev.revision == request.revision for rev in file_revisions)
            if not revision_exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Revision {request.revision} not found for file: {request.path}"
                )

        finally:
            session.close()

        # Get the revision file path to restore
        revision_file_path = GetRevisionPath(request.path, request.revision, request.service_type)

        # Check if revision file exists on disk
        if not revision_file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Revision {request.revision} exists in database but file is missing on disk"
            )

        # Step 1: Archive current version (copy current revision file to next revision)
        # Get next revision number for archiving current version
        archive_revision = GetNextRevisionNumber(db_manager, request.path, request.service_type)

        # Get current and archive file paths
        current_file_path = GetRevisionPath(request.path, current_revision, request.service_type)
        archive_file_path = GetRevisionPath(request.path, archive_revision, request.service_type)

        # Copy current file to archive
        try:
            archive_file_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(current_file_path), str(archive_file_path))

            # Get metadata from current revision for archiving
            current_hash = CalculateFileHash(archive_file_path)
            current_size = archive_file_path.stat().st_size

            # Get current revision metadata for user_id
            current_metadata = None
            session2 = db_manager.GetSession()
            try:
                current_record = session2.query(File).filter(
                    File.path == request.path,
                    File.service_type == request.service_type,
                    File.revision == current_revision
                ).first()
                if current_record:
                    current_metadata = {
                        'last_modified_utc': current_record.last_modified_utc,
                        'user_id': current_record.user_id
                    }
            finally:
                session2.close()

            # Store metadata for archived version
            StoreFileMetadata(
                db_manager,
                request.path,
                request.service_type,
                current_hash,
                current_size,
                current_metadata['last_modified_utc'] if current_metadata else datetime.now(timezone.utc),
                revision=archive_revision,
                is_deleted=False,
                user_id=current_metadata['user_id'] if current_metadata else None
            )

            logger.info(f"Archived current revision {current_revision} as revision {archive_revision}: {request.path}")
        except Exception as e:
            logger.error(f"Failed to archive current revision before restore: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to archive current version: {str(e)}"
            )

        # Step 2: Create new revision with old content
        # Get next revision number for the restored content
        restore_revision = GetNextRevisionNumber(db_manager, request.path, request.service_type)

        # Copy old revision content to new revision file
        restore_file_path = GetRevisionPath(request.path, restore_revision, request.service_type)
        restore_file_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(revision_file_path), str(restore_file_path))

        # Calculate metadata for the restored file
        file_hash = CalculateFileHash(restore_file_path)
        file_size = restore_file_path.stat().st_size
        modified_utc = datetime.now(timezone.utc)

        # Store metadata for the restored revision (which is now the current version)
        StoreFileMetadata(
            db_manager,
            request.path,
            request.service_type,
            file_hash,
            file_size,
            modified_utc,
            revision=restore_revision,
            is_deleted=False,
            user_id=current_user.user_id
        )

        logger.info(
            f"User '{current_user.username}' restored revision {request.revision} "
            f"as new revision {restore_revision} (archived current as {archive_revision}) for '{request.path}' ({request.service_type})"
        )

        return RestoreRevisionResponse(success=True)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restoring revision {request.revision} for {request.path}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restore revision: {str(e)}"
        )
