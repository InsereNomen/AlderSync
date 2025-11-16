"""
AlderSync Server - Change Password Response Model

Pydantic model for change password endpoint response.
"""

from pydantic import BaseModel


class ChangePasswordResponse(BaseModel):
    """Response model for change password endpoint"""
    success: bool
    message: str
