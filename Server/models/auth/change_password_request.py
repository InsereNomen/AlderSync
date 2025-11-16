"""
AlderSync Server - Change Password Request Model

Pydantic model for change password endpoint request.
"""

from pydantic import BaseModel


class ChangePasswordRequest(BaseModel):
    """Request model for change password endpoint"""
    current_password: str
    new_password: str
