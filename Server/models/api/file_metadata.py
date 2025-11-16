"""
AlderSync Server - File Metadata API Model

Pydantic model for file metadata responses.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class FileMetadata(BaseModel):
    """Response model for file metadata"""
    path: str
    size: Optional[int]
    hash: Optional[str]
    modified_utc: datetime
