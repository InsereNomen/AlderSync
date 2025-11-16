"""
AlderSync Server - Settings API Models

Pydantic models for settings management endpoints.
"""

from pydantic import BaseModel


class SettingsUpdateRequest(BaseModel):
    lock_timeout_seconds: int
    min_lock_timeout_seconds: int
    max_revisions: int
    jwt_expiration_hours: int
