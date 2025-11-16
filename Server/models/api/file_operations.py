"""
AlderSync Server - File Operations API Models

Pydantic models for file upload and delete operations.
"""

from pydantic import BaseModel


class FileUploadResponse(BaseModel):
    success: bool
    file_hash: str
    path: str
    size: int


class FileDeleteRequest(BaseModel):
    path: str


class FileDeleteResponse(BaseModel):
    success: bool
    path: str
