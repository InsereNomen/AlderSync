"""
AlderSync Server - Database Models Package

This package contains all SQLAlchemy database model definitions.
All models share a common declarative base for proper table relationships.
"""

# Import Base first
from models.database.base import Base

# Import all models
from models.database.role import Role
from models.database.permission import Permission
from models.database.role_permission import RolePermission
from models.database.user import User
from models.database.file import File
from models.database.changelist import Changelist
from models.database.operation import Operation
from models.database.setting import Setting
from models.database.last_operation import LastOperation
from models.database.ignore_pattern import IgnorePattern

# Export all models and Base
__all__ = [
    'Base',
    'Role',
    'Permission',
    'RolePermission',
    'User',
    'File',
    'Changelist',
    'Operation',
    'Setting',
    'LastOperation',
    'IgnorePattern',
]
