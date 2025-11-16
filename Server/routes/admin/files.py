"""
AlderSync Server - Admin Files Endpoints
"""

import logging
import shutil
from pathlib import Path
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import HTMLResponse

from fastapi.templating import Jinja2Templates

from models.database import File, User
from models.api import DeleteFileRequest, DeleteRevisionRequest, RestoreRevisionRequest
from routes.admin.auth import RequireAdminSession
from file_storage import GetRevisionPath, StoreFileMetadata, CalculateFileHash, GetNextRevisionNumber

# Create logger
logger = logging.getLogger(__name__)

# Create router instance
router = APIRouter()

# Get the directory where server.py is located
script_dir = Path(__file__).parent.parent.parent

# Initialize Jinja2 templates
templates = Jinja2Templates(directory=str(script_dir / "templates"))



@router.get("/admin/files", response_class=HTMLResponse, tags=["Admin"])
async def admin_files_page(
    request: Request,
    session: dict = Depends(RequireAdminSession)
):
    """
    Display file management page
    Per Specification.md section 5.2 and Task 3.5
    """
    context = {
        "request": request,
        "show_nav": True,
        "active_page": "files",
        "username": session["username"],
        "is_admin": True  # Files page requires admin permission
    }
    return templates.TemplateResponse("files.html", context)


@router.get("/admin/api/files", tags=["Admin"])
async def admin_get_files(
    service_type: str = Query(..., description="Service type: Contemporary or Traditional"),
    session: dict = Depends(RequireAdminSession)
):
    """
    Get list of files for a service type with metadata and revision counts
    Per Specification.md section 5.2 and Task 3.5

    Args:
        service_type: Contemporary or Traditional
        session: Admin session from dependency

    Returns:
        List of files with metadata
    """
    try:
        # Validate service type
        if service_type not in ["Contemporary", "Traditional"]:
            raise HTTPException(status_code=400, detail="Invalid service type")

        # Get all files using SQLAlchemy
        from database import db_manager
        session = db_manager.GetSession()
        try:
            # Get current files (revision = 0) that are not deleted
            current_files = session.query(File).filter(
                File.service_type == service_type,
                File.revision == 0,
                File.is_deleted == 0
            ).order_by(File.path).all()

            files = []
            for file in current_files:
                # Count ALL revisions for this file (including current revision 0)
                revision_count = session.query(File).filter(
                    File.service_type == service_type,
                    File.path == file.path
                ).count()

                # Get username if user_id is set
                username = None
                if file.user_id:
                    user = session.query(User).filter(User.user_id == file.user_id).first()
                    if user:
                        username = user.username

                files.append({
                    "path": file.path,
                    "size": file.size,
                    "username": username,
                    "modified_utc": file.last_modified_utc.isoformat() if file.last_modified_utc else None,
                    "revision_count": revision_count,
                    "changelist_id": file.changelist_id
                })

            return files
        finally:
            session.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting files: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get files")


@router.get("/admin/api/files/revisions", tags=["Admin"])
async def admin_get_file_revisions(
    path: str = Query(..., description="File path"),
    service_type: str = Query(..., description="Service type: Contemporary or Traditional"),
    session: dict = Depends(RequireAdminSession)
):
    """
    Get all revisions for a specific file
    Per Specification.md section 5.2 and Task 3.5

    Args:
        path: File path
        service_type: Contemporary or Traditional
        session: Admin session from dependency

    Returns:
        List of revisions for the file
    """
    try:
        # Validate service type
        if service_type not in ["Contemporary", "Traditional"]:
            raise HTTPException(status_code=400, detail="Invalid service type")

        # Get all revisions for this file using SQLAlchemy
        from database import db_manager
        session = db_manager.GetSession()
        try:
            file_revisions = session.query(File).filter(
                File.service_type == service_type,
                File.path == path
            ).order_by(File.revision.desc()).all()

            revisions = []
            for file in file_revisions:
                # Get username if user_id is set
                username = None
                if file.user_id:
                    user = session.query(User).filter(User.user_id == file.user_id).first()
                    if user:
                        username = user.username

                revisions.append({
                    "revision": file.revision,
                    "size": file.size,
                    "username": username,
                    "modified_utc": file.last_modified_utc.isoformat() if file.last_modified_utc else None,
                    "changelist_id": file.changelist_id
                })

            return revisions
        finally:
            session.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file revisions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get file revisions")




@router.post("/admin/api/files/delete", tags=["Admin"])
async def admin_delete_file(
    request: DeleteFileRequest,
    session: dict = Depends(RequireAdminSession)
):
    """
    Delete a file (mark as deleted, create revision of current version)
    Per Specification.md section 5.2 and Task 3.5

    Args:
        request: Delete file request
        session: Admin session from dependency

    Returns:
        Success message
    """
    try:
        # Validate service type
        if request.service_type not in ["Contemporary", "Traditional"]:
            raise HTTPException(status_code=400, detail="Invalid service type")

        from database import db_manager
        db_session = db_manager.GetSession()
        try:
            # Check if file exists and is not already deleted
            file_record = db_session.query(File).filter(
                File.service_type == request.service_type,
                File.path == request.path,
                File.revision == 0,
                File.is_deleted == 0
            ).first()

            if not file_record:
                raise HTTPException(status_code=404, detail="File not found or already deleted")

            file_id = file_record.file_id
            size = file_record.size
            file_hash = file_record.file_hash

            # Get the physical file path
            from file_storage import GetFilePath
            file_path = GetFilePath(request.service_type, request.path)

            # Create a revision of the current file before marking as deleted
            if file_path.exists():
                # Find the next revision number
                max_revision_result = db_session.query(File.revision).filter(
                    File.service_type == request.service_type,
                    File.path == request.path
                ).order_by(File.revision.desc()).first()

                max_revision = max_revision_result[0] if max_revision_result else 0
                next_revision = max_revision + 1

                # Rename the physical file to revision format
                from file_storage import GetRevisionPath
                from datetime import datetime, timezone
                revision_path = GetRevisionPath(request.service_type, request.path, next_revision)
                revision_path.parent.mkdir(parents=True, exist_ok=True)

                shutil.move(str(file_path), str(revision_path))

                # Insert revision record
                new_revision = File(
                    path=request.path,
                    service_type=request.service_type,
                    file_hash=file_hash,
                    size=size,
                    is_deleted=False,
                    last_modified_utc=datetime.now(timezone.utc),
                    revision=next_revision,
                    user_id=file_record.user_id  # Preserve original user
                )
                db_session.add(new_revision)

            # Mark the current file as deleted (preserve original user)
            file_record.is_deleted = True
            file_record.size = None
            file_record.file_hash = None
            file_record.last_modified_utc = datetime.now(timezone.utc)
            # user_id is preserved from the original file record

            db_session.commit()
        finally:
            db_session.close()

        logger.info(f"Admin '{session['username']}' deleted file: {request.path} ({request.service_type})")

        return {
            "success": True,
            "message": f"File deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")




@router.post("/admin/api/files/delete-revision", tags=["Admin"])
async def admin_delete_revision(
    request: DeleteRevisionRequest,
    session: dict = Depends(RequireAdminSession)
):
    """
    Permanently delete a specific revision of a file
    Per Specification.md section 5.2 and Task 3.5

    Args:
        request: Delete revision request
        session: Admin session from dependency

    Returns:
        Success message
    """
    try:
        # Validate service type
        if request.service_type not in ["Contemporary", "Traditional"]:
            raise HTTPException(status_code=400, detail="Invalid service type")

        from database import db_manager
        db_session = db_manager.GetSession()
        try:
            # Check if revision exists
            revision_record = db_session.query(File).filter(
                File.service_type == request.service_type,
                File.path == request.path,
                File.revision == request.revision
            ).first()

            if not revision_record:
                raise HTTPException(status_code=404, detail="Revision not found")

            # Allow deletion of any revision, including the current one
            # When current revision is deleted, the previous revision becomes current
            max_revision_result = db_session.query(File.revision).filter(
                File.service_type == request.service_type,
                File.path == request.path
            ).order_by(File.revision.desc()).first()

            is_current_revision = max_revision_result and request.revision == max_revision_result[0]

            # Get the physical revision file path
            from file_storage import GetRevisionPath
            revision_path = GetRevisionPath(request.service_type, request.path, request.revision)

            # Delete the physical file
            if revision_path.exists():
                revision_path.unlink()

            # Delete the database record
            db_session.delete(revision_record)
            db_session.commit()
        finally:
            db_session.close()

        logger.info(f"Admin '{session['username']}' deleted revision {request.revision} of file: {request.path} ({request.service_type})")

        return {
            "success": True,
            "message": f"Revision #{request.revision} deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting revision: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete revision: {str(e)}")


@router.post("/admin/api/files/restore-revision", tags=["Admin"])
async def admin_restore_revision(
    request: RestoreRevisionRequest,
    session: dict = Depends(RequireAdminSession)
):
    """
    Restore an old revision of a file (admin endpoint)

    This makes an old revision the current version by:
    1. Creating a revision of the current file (archives current as new revision)
    2. Creating a new revision with the old revision's content
    3. The new revision becomes the current version (highest revision number)

    Args:
        request: Restore request with path, revision number, and service_type
        session: Admin session from dependency

    Returns:
        Success message

    Raises:
        HTTPException: If revision not found or restore fails
    """
    try:
        # Validate service type
        if request.service_type not in ["Contemporary", "Traditional"]:
            raise HTTPException(status_code=400, detail="Invalid service type")

        # Validate revision number
        if request.revision < 0:
            raise HTTPException(status_code=400, detail="Revision number must be >= 0")

        from database import db_manager

        # Get all revisions to find the current (highest) revision
        db_session = db_manager.GetSession()
        try:
            file_revisions = db_session.query(File).filter(
                File.path == request.path,
                File.service_type == request.service_type
            ).order_by(File.revision.desc()).all()

            if not file_revisions:
                raise HTTPException(status_code=404, detail=f"File not found: {request.path}")

            # Get current (highest) revision number
            current_revision = file_revisions[0].revision

            # Validate that we're not trying to restore the current revision
            if request.revision == current_revision:
                raise HTTPException(
                    status_code=400,
                    detail=f"Revision {request.revision} is already the current version"
                )

            # Validate that the requested revision exists
            revision_exists = any(rev.revision == request.revision for rev in file_revisions)
            if not revision_exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Revision {request.revision} not found for file: {request.path}"
                )

        finally:
            db_session.close()

        # Get the revision file path to restore
        revision_file_path = GetRevisionPath(request.service_type, request.path, request.revision)

        # Check if revision file exists on disk
        if not revision_file_path.exists():
            raise HTTPException(
                status_code=500,
                detail=f"Revision {request.revision} exists in database but file is missing on disk"
            )

        # Step 1: Archive current version (copy current revision file to next revision)
        archive_revision = GetNextRevisionNumber(db_manager, request.path, request.service_type)

        # Get current and archive file paths
        current_file_path = GetRevisionPath(request.service_type, request.path, current_revision)
        archive_file_path = GetRevisionPath(request.service_type, request.path, archive_revision)

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
                status_code=500,
                detail=f"Failed to archive current version: {str(e)}"
            )

        # Step 2: Create new revision with old content
        restore_revision = GetNextRevisionNumber(db_manager, request.path, request.service_type)

        # Copy old revision content to new revision file
        restore_file_path = GetRevisionPath(request.service_type, request.path, restore_revision)
        restore_file_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(revision_file_path), str(restore_file_path))

        # Calculate metadata for the restored file
        file_hash = CalculateFileHash(restore_file_path)
        file_size = restore_file_path.stat().st_size
        modified_utc = datetime.now(timezone.utc)

        # Get admin user_id
        admin_user_id = None
        admin_session = db_manager.GetSession()
        try:
            admin_user = admin_session.query(User).filter(User.username == session['username']).first()
            if admin_user:
                admin_user_id = admin_user.user_id
        finally:
            admin_session.close()

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
            user_id=admin_user_id
        )

        logger.info(
            f"Admin '{session['username']}' restored revision {request.revision} "
            f"as new revision {restore_revision} (archived current as {archive_revision}) for '{request.path}' ({request.service_type})"
        )

        return {
            "success": True,
            "message": f"Revision #{request.revision} has been restored as the current version",
            "new_revision": restore_revision
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restoring revision {request.revision} for {request.path}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to restore revision: {str(e)}")


# ==================== Admin Settings Management ====================



