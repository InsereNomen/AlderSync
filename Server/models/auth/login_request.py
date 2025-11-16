"""
AlderSync Server - Login Request Model

Pydantic model for login endpoint request.
"""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    """Request model for login endpoint"""
    username: str
    password: str
