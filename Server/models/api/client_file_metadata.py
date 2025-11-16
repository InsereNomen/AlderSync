"""
AlderSync Server - Client File Metadata API Model

Pydantic model for client file metadata in Reconcile operations.
"""

from pydantic import BaseModel


class ClientFileMetadata(BaseModel):
    """Client file metadata for Reconcile operations"""
    modified_utc: str  # ISO format datetime
    size: int
    hash: str
