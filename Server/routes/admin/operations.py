"""
AlderSync Server - Admin Operations Endpoints
"""

import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from models.database import Operation, User
from routes.admin.auth import RequireAdminSession
from transactions import CancelTransaction

# Create logger
logger = logging.getLogger(__name__)

# Create router instance
router = APIRouter()

# Get the directory where server.py is located
script_dir = Path(__file__).parent.parent.parent

# Initialize Jinja2 templates
templates = Jinja2Templates(directory=str(script_dir / "templates"))



@router.get("/admin/operations", response_class=HTMLResponse, tags=["Admin"])
async def admin_operations_page(
    request: Request,
    session: dict = Depends(RequireAdminSession)
):
    """
    Display active operations page
    Per Specification.md section 5.2 and Task 3.4
    """
    context = {
        "request": request,
        "show_nav": True,
        "active_page": "operations",
        "username": session["username"],
        "is_admin": True  # Operations page requires admin permission
    }
    return templates.TemplateResponse("operations.html", context)


@router.get("/admin/api/operations/active", tags=["Admin"])
async def admin_get_active_operations(
    session: dict = Depends(RequireAdminSession)
):
    """
    Get list of all active operations
    Per Specification.md section 5.2 and Task 3.4

    Returns:
        List of active operations with details
    """
    try:
        from transactions import GetAllActiveTransactions
        operations = GetAllActiveTransactions()

        logger.info(f"Admin '{session['username']}' viewed active operations")

        return {
            "success": True,
            "operations": operations
        }

    except Exception as e:
        logger.error(f"Error getting active operations: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve active operations")


@router.post("/admin/api/operations/{transaction_id}/cancel", tags=["Admin"])
async def admin_cancel_operation(
    transaction_id: str,
    session: dict = Depends(RequireAdminSession)
):
    """
    Cancel an active operation
    Per Specification.md section 9.6.5 and Task 3.4

    Args:
        transaction_id: Transaction ID to cancel
        session: Admin session from dependency

    Returns:
        Success message
    """
    try:
        from transactions import CancelTransaction

        success, message = CancelTransaction(transaction_id, db_manager)

        if not success:
            raise HTTPException(status_code=404, detail=message)

        logger.info(f"Admin '{session['username']}' cancelled transaction {transaction_id}")

        return {
            "success": True,
            "message": message
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling operation: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to cancel operation")


# ==================== Admin Files Management ====================

