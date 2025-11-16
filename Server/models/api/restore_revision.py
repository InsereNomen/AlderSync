"""
AlderSync Server - Restore Revision API Models

Pydantic models for file revision restoration endpoints.
"""

from pydantic import BaseModel


class RestoreRevisionRequest(BaseModel):
    path: str
    revision: int
    service_type: str


class RestoreRevisionResponse(BaseModel):
    success: bool
