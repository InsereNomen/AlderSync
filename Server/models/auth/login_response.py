"""
AlderSync Server - Login Response Model

Pydantic model for login endpoint response.
"""

from pydantic import BaseModel


class LoginResponse(BaseModel):
    """Response model for login endpoint"""
    token: str
    expires_in: int  # Seconds until token expiration
