"""
AlderSync Client - Managers Package

Contains manager classes for configuration and folder operations.

Author: AlderSync Project
"""

from .config_manager import ConfigManager, DEFAULT_CONFIG
from .folder_manager import FolderManager

__all__ = [
    'ConfigManager',
    'DEFAULT_CONFIG',
    'FolderManager'
]
