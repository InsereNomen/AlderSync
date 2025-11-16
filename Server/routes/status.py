"""
AlderSync Server - Status Endpoints

This module contains status-related endpoints including health checks,
last operation tracking, and server lock status.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends

from models.database import LastOperation, User
from auth import GetCurrentActiveUser
from transactions import GetActiveLockInfo


# Create router instance
router = APIRouter()


# ==================== Health Check Endpoint ====================

@router.get("/health", tags=["Status"])
async def health_check():
    """
    Health check endpoint to verify server is running

    Returns:
        dict: Server status information
    """
    return {
        "status": "healthy",
        "service": "AlderSync Server",
        "version": "1.0.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat()
    }


# ==================== Status Endpoints ====================

@router.get("/status/last_operation", tags=["Status"])
async def get_last_operation(current_user: User = Depends(GetCurrentActiveUser)):
    """
    Get information about the most recent operation
    Per Specification.md section 5.1.4

    Args:
        current_user: Authenticated user (from JWT token)

    Returns:
        dict: Last operation details including user, type, service, timestamp, and file counts
    """
    from database import db_manager

    session = db_manager.GetSession()

    try:
        # Get the last operation record (there's only one row with id=1)
        last_op = session.query(LastOperation).filter(LastOperation.id == 1).first()

        if not last_op or not last_op.timestamp_utc:
            # No operation recorded yet
            return {
                "user": None,
                "operation": None,
                "service_type": None,
                "timestamp_utc": None,
                "file_count": 0,
                "files_pulled": None,
                "files_pushed": None,
                "started_ago_seconds": None
            }

        # Calculate how long ago the operation started
        now = datetime.now(timezone.utc)
        # Ensure timestamp_utc is timezone-aware
        if last_op.timestamp_utc.tzinfo is None:
            timestamp_aware = last_op.timestamp_utc.replace(tzinfo=timezone.utc)
        else:
            timestamp_aware = last_op.timestamp_utc

        started_ago = (now - timestamp_aware).total_seconds()

        return {
            "user": last_op.username,
            "operation": last_op.operation_type,
            "service_type": last_op.service_type,
            "timestamp_utc": last_op.timestamp_utc.isoformat() if last_op.timestamp_utc else None,
            "file_count": last_op.file_count or 0,
            "files_pulled": None,  # TODO: Add these fields to LastOperation table in future
            "files_pushed": None,  # TODO: Add these fields to LastOperation table in future
            "started_ago_seconds": int(started_ago)
        }

    finally:
        session.close()


@router.get("/status/lock", tags=["Status"])
async def get_lock_status(current_user: User = Depends(GetCurrentActiveUser)):
    """
    Get current server lock status
    Per Specification.md section 5.1.4

    Args:
        current_user: Authenticated user (from JWT token)

    Returns:
        Lock information or indication that server is unlocked
    """
    lock_info = GetActiveLockInfo()

    if lock_info is None:
        return {
            "locked": False,
            "user": None,
            "operation": None,
            "started_ago_seconds": None
        }

    return lock_info
