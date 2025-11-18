"""
AlderSync Server - Admin Ignore Patterns Endpoints
"""

import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, List

from models.database import IgnorePattern
from routes.admin.auth import RequireAdminSession

# Create logger
logger = logging.getLogger(__name__)

# Create router instance
router = APIRouter()

# Get the directory where server.py is located
script_dir = Path(__file__).parent.parent.parent

# Initialize Jinja2 templates
templates = Jinja2Templates(directory=str(script_dir / "templates"))


# ==================== Request/Response Models ====================

class IgnorePatternCreate(BaseModel):
    """Request model for creating an ignore pattern"""
    pattern: str
    description: Optional[str] = None


class IgnorePatternUpdate(BaseModel):
    """Request model for updating an ignore pattern"""
    pattern: str
    description: Optional[str] = None


class IgnorePatternResponse(BaseModel):
    """Response model for ignore pattern"""
    pattern_id: int
    pattern: str
    description: Optional[str]
    created_at: str


# ==================== Admin Ignore Patterns Management ====================


@router.get("/admin/ignore-patterns", response_class=HTMLResponse, tags=["Admin"])
async def admin_ignore_patterns_page(
    request: Request,
    session: dict = Depends(RequireAdminSession)
):
    """
    Display ignore patterns management page
    """
    context = {
        "request": request,
        "show_nav": True,
        "active_page": "ignore_patterns",
        "username": session["username"],
        "is_admin": True
    }
    return templates.TemplateResponse("ignore_patterns.html", context)


@router.get("/admin/api/ignore-patterns", tags=["Admin"])
async def admin_get_ignore_patterns(
    session: dict = Depends(RequireAdminSession)
) -> List[IgnorePatternResponse]:
    """
    Get all ignore patterns

    Returns:
        List of all ignore patterns
    """
    try:
        from database import db_manager
        db_session = db_manager.GetSession()
        try:
            patterns = db_session.query(IgnorePattern).order_by(IgnorePattern.pattern_id).all()
            return [
                IgnorePatternResponse(
                    pattern_id=p.pattern_id,
                    pattern=p.pattern,
                    description=p.description,
                    created_at=p.created_at.isoformat() if p.created_at else ""
                )
                for p in patterns
            ]
        finally:
            db_session.close()
    except Exception as e:
        logger.error(f"Error fetching ignore patterns: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch ignore patterns")


@router.post("/admin/api/ignore-patterns", tags=["Admin"])
async def admin_create_ignore_pattern(
    request: IgnorePatternCreate,
    session: dict = Depends(RequireAdminSession)
):
    """
    Create a new ignore pattern

    Args:
        request: Ignore pattern creation request
        session: Admin session from dependency

    Returns:
        Created ignore pattern
    """
    try:
        # Validate pattern is not empty
        if not request.pattern or not request.pattern.strip():
            raise HTTPException(status_code=400, detail="Pattern cannot be empty")

        from database import db_manager
        from datetime import datetime, timezone

        db_session = db_manager.GetSession()
        try:
            # Check if pattern already exists
            existing = db_session.query(IgnorePattern).filter(
                IgnorePattern.pattern == request.pattern.strip()
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="Pattern already exists")

            # Create new pattern
            new_pattern = IgnorePattern(
                pattern=request.pattern.strip(),
                description=request.description.strip() if request.description else None,
                created_at=datetime.now(timezone.utc)
            )
            db_session.add(new_pattern)
            db_session.commit()
            db_session.refresh(new_pattern)

            logger.info(f"Admin '{session['username']}' added ignore pattern: {new_pattern.pattern}")

            return IgnorePatternResponse(
                pattern_id=new_pattern.pattern_id,
                pattern=new_pattern.pattern,
                description=new_pattern.description,
                created_at=new_pattern.created_at.isoformat()
            )
        finally:
            db_session.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating ignore pattern: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create ignore pattern: {str(e)}")


@router.put("/admin/api/ignore-patterns/{pattern_id}", tags=["Admin"])
async def admin_update_ignore_pattern(
    pattern_id: int,
    request: IgnorePatternUpdate,
    session: dict = Depends(RequireAdminSession)
):
    """
    Update an existing ignore pattern

    Args:
        pattern_id: ID of pattern to update
        request: Updated pattern data
        session: Admin session from dependency

    Returns:
        Updated ignore pattern
    """
    try:
        # Validate pattern is not empty
        if not request.pattern or not request.pattern.strip():
            raise HTTPException(status_code=400, detail="Pattern cannot be empty")

        from database import db_manager
        db_session = db_manager.GetSession()
        try:
            # Find pattern to update
            pattern = db_session.query(IgnorePattern).filter(
                IgnorePattern.pattern_id == pattern_id
            ).first()
            if not pattern:
                raise HTTPException(status_code=404, detail="Pattern not found")

            # Check if new pattern already exists (excluding current pattern)
            existing = db_session.query(IgnorePattern).filter(
                IgnorePattern.pattern == request.pattern.strip(),
                IgnorePattern.pattern_id != pattern_id
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="Pattern already exists")

            # Update pattern
            pattern.pattern = request.pattern.strip()
            pattern.description = request.description.strip() if request.description else None
            db_session.commit()
            db_session.refresh(pattern)

            logger.info(f"Admin '{session['username']}' updated ignore pattern ID {pattern_id}")

            return IgnorePatternResponse(
                pattern_id=pattern.pattern_id,
                pattern=pattern.pattern,
                description=pattern.description,
                created_at=pattern.created_at.isoformat() if pattern.created_at else ""
            )
        finally:
            db_session.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating ignore pattern: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update ignore pattern: {str(e)}")


@router.delete("/admin/api/ignore-patterns/{pattern_id}", tags=["Admin"])
async def admin_delete_ignore_pattern(
    pattern_id: int,
    session: dict = Depends(RequireAdminSession)
):
    """
    Delete an ignore pattern

    Args:
        pattern_id: ID of pattern to delete
        session: Admin session from dependency

    Returns:
        Success message
    """
    try:
        from database import db_manager
        db_session = db_manager.GetSession()
        try:
            # Find pattern to delete
            pattern = db_session.query(IgnorePattern).filter(
                IgnorePattern.pattern_id == pattern_id
            ).first()
            if not pattern:
                raise HTTPException(status_code=404, detail="Pattern not found")

            # Delete pattern
            pattern_str = pattern.pattern
            db_session.delete(pattern)
            db_session.commit()

            logger.info(f"Admin '{session['username']}' deleted ignore pattern: {pattern_str}")

            return {
                "success": True,
                "message": "Pattern deleted successfully"
            }
        finally:
            db_session.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting ignore pattern: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete ignore pattern: {str(e)}")
