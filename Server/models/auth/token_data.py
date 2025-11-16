"""
AlderSync Server - Token Data Model

Pydantic model for data stored in JWT tokens.
"""

from typing import Optional
from pydantic import BaseModel


class TokenData(BaseModel):
    """Data stored in JWT token"""
    user_id: int
    username: str
    permissions: Optional[list] = []  # List of permission names
