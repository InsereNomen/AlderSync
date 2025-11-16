"""
AlderSync Server - API Models Package

This package contains Pydantic models for all API endpoints.
"""

from models.api.file_metadata import FileMetadata
from models.api.restore_revision import RestoreRevisionRequest, RestoreRevisionResponse
from models.api.client_file_metadata import ClientFileMetadata
from models.api.transaction import (
    TransactionBeginRequest,
    TransactionBeginResponse,
    TransactionCommitResponse,
    TransactionRollbackResponse
)
from models.api.file_operations import (
    FileUploadResponse,
    FileDeleteRequest,
    FileDeleteResponse
)
from models.api.user_management import (
    CreateUserRequest,
    UpdateUserStatusRequest,
    ResetPasswordRequest,
    UpdateUserRoleRequest
)
from models.api.role_management import (
    CreateRoleRequest,
    UpdateRoleRequest,
    SetRolePermissionsRequest
)
from models.api.file_management import (
    DeleteFileRequest,
    DeleteRevisionRequest
)
from models.api.settings import SettingsUpdateRequest
from models.api.version import VersionCheckResponse, VersionInfoResponse

__all__ = [
    'FileMetadata',
    'RestoreRevisionRequest',
    'RestoreRevisionResponse',
    'ClientFileMetadata',
    'TransactionBeginRequest',
    'TransactionBeginResponse',
    'TransactionCommitResponse',
    'TransactionRollbackResponse',
    'FileUploadResponse',
    'FileDeleteRequest',
    'FileDeleteResponse',
    'CreateUserRequest',
    'UpdateUserStatusRequest',
    'ResetPasswordRequest',
    'UpdateUserRoleRequest',
    'CreateRoleRequest',
    'UpdateRoleRequest',
    'SetRolePermissionsRequest',
    'DeleteFileRequest',
    'DeleteRevisionRequest',
    'SettingsUpdateRequest',
    'VersionCheckResponse',
    'VersionInfoResponse',
]
