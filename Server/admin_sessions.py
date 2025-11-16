"""
AlderSync Server - Admin Session Management

Simple cookie-based session management for admin web interface.
Sessions stored in-memory only (no persistence across restarts for MVP).
"""

import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict

from models.infrastructure import AdminSession

logger = logging.getLogger(__name__)

# In-memory session storage
_sessions: Dict[str, AdminSession] = {}

# Session configuration
SESSION_COOKIE_NAME = "admin_session"
SESSION_LIFETIME_HOURS = 24


def CreateSession(user_id: int, username: str) -> AdminSession:
    """
    Create a new admin session

    Args:
        user_id: User ID
        username: Username

    Returns:
        AdminSession object with new session ID
    """
    # Generate secure random session ID
    session_id = secrets.token_urlsafe(32)

    # Calculate expiration time
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=SESSION_LIFETIME_HOURS)

    # Create session object
    session = AdminSession(
        session_id=session_id,
        user_id=user_id,
        username=username,
        created_at_utc=now,
        expires_at_utc=expires_at
    )

    # Store in memory
    _sessions[session_id] = session

    logger.info(f"Created admin session for user '{username}' (expires in {SESSION_LIFETIME_HOURS} hours)")

    return session


def GetSession(session_id: str) -> Optional[AdminSession]:
    """
    Get an active session by ID

    Args:
        session_id: Session ID from cookie

    Returns:
        AdminSession if valid and not expired, None otherwise
    """
    if not session_id:
        return None

    session = _sessions.get(session_id)
    if not session:
        return None

    # Check if expired
    if session.IsExpired():
        logger.info(f"Session {session_id} expired for user '{session.username}'")
        del _sessions[session_id]
        return None

    return session


def DeleteSession(session_id: str) -> None:
    """
    Delete a session (logout)

    Args:
        session_id: Session ID to delete
    """
    if session_id in _sessions:
        session = _sessions[session_id]
        logger.info(f"Deleted admin session for user '{session.username}'")
        del _sessions[session_id]


def CleanupExpiredSessions() -> int:
    """
    Remove all expired sessions from memory

    Returns:
        Number of sessions cleaned up
    """
    expired_ids = [
        session_id
        for session_id, session in _sessions.items()
        if session.IsExpired()
    ]

    for session_id in expired_ids:
        del _sessions[session_id]

    if expired_ids:
        logger.info(f"Cleaned up {len(expired_ids)} expired admin sessions")

    return len(expired_ids)
