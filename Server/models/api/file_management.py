"""
AlderSync Server - File Management API Models

Pydantic models for file management admin endpoints.
"""

from pydantic import BaseModel


class DeleteFileRequest(BaseModel):
    path: str
    service_type: str


class DeleteRevisionRequest(BaseModel):
    path: str
    service_type: str
    revision: int
