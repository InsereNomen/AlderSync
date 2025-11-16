"""
AlderSync Server - Client Downloads Module

Manages client executable downloads and versioning.
Stores client executables in a configurable folder separate from the Docker image.

Author: AlderSync Project
"""

import logging
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Default client downloads folder
DEFAULT_CLIENT_DOWNLOADS_PATH = Path("client_downloads")


def InitializeClientDownloads(db_manager) -> Path:
    """
    Initialize client downloads folder structure.

    Creates the client downloads folder if it doesn't exist and ensures
    the path is stored in settings.

    Args:
        db_manager: DatabaseManager instance

    Returns:
        Path to client downloads folder
    """
    from models.database import Setting

    session = db_manager.GetSession()
    try:
        # Get or create client_downloads_path setting
        path_setting = session.query(Setting).filter(
            Setting.key == "client_downloads_path"
        ).first()

        if path_setting:
            downloads_path = Path(path_setting.value)
        else:
            # Create default setting
            downloads_path = DEFAULT_CLIENT_DOWNLOADS_PATH
            path_setting = Setting(
                key="client_downloads_path",
                value=str(downloads_path)
            )
            session.add(path_setting)
            session.commit()
            logger.info(f"Created client_downloads_path setting: {downloads_path}")

        # Create folder if it doesn't exist
        downloads_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Client downloads folder initialized: {downloads_path.absolute()}")

        return downloads_path

    finally:
        session.close()


def GetClientDownloadsPath(db_manager) -> Path:
    """
    Get the configured client downloads folder path.

    Args:
        db_manager: DatabaseManager instance

    Returns:
        Path to client downloads folder
    """
    from models.database import Setting

    session = db_manager.GetSession()
    try:
        path_setting = session.query(Setting).filter(
            Setting.key == "client_downloads_path"
        ).first()

        if path_setting:
            return Path(path_setting.value)
        else:
            # Return default if not configured
            return DEFAULT_CLIENT_DOWNLOADS_PATH

    finally:
        session.close()


def StoreClientExecutable(db_manager, file_data: bytes, version: str,
                         platform: str = "windows", original_filename: str = None) -> Dict[str, Any]:
    """
    Store a new client executable and update version settings.

    Args:
        db_manager: DatabaseManager instance
        file_data: Binary data of the executable
        version: Version string (e.g., "1.0.1")
        platform: Platform identifier (default: "windows")
        original_filename: Original uploaded filename (to preserve extension)

    Returns:
        Dict with success status, file path, and metadata
    """
    from models.database import Setting

    logger.info(f"Storing client executable: version={version}, platform={platform}")

    # Get downloads folder
    downloads_path = GetClientDownloadsPath(db_manager)

    # Determine file extension from original filename if provided
    file_extension = None
    if original_filename:
        original_lower = original_filename.lower()
        if original_lower.endswith('.zip'):
            file_extension = '.zip'
        elif original_lower.endswith('.exe'):
            file_extension = '.exe'
        elif original_lower.endswith('.app'):
            file_extension = '.app'

    # If no extension determined from filename, use platform default
    if not file_extension:
        if platform == "windows":
            file_extension = ".exe"
        elif platform == "macos":
            file_extension = ".app"
        elif platform == "linux":
            file_extension = ""  # No extension for Linux
        else:
            file_extension = ".exe"  # Default to windows

    filename = f"aldersync-{version}{file_extension}"
    file_path = downloads_path / filename

    # Write file to disk
    try:
        with open(file_path, 'wb') as f:
            f.write(file_data)

        logger.info(f"Wrote client executable to: {file_path.absolute()}")

        # Update database settings
        session = db_manager.GetSession()
        try:
            # Update latest_client_version
            version_setting = session.query(Setting).filter(
                Setting.key == "latest_client_version"
            ).first()

            if version_setting:
                old_version = version_setting.value
                version_setting.value = version
                logger.info(f"Updated latest_client_version: {old_version} -> {version}")
            else:
                version_setting = Setting(key="latest_client_version", value=version)
                session.add(version_setting)
                logger.info(f"Created latest_client_version setting: {version}")

            # Update client_executable_path
            path_setting = session.query(Setting).filter(
                Setting.key == "client_executable_path"
            ).first()

            if path_setting:
                old_path = path_setting.value
                path_setting.value = str(file_path.absolute())
                logger.info(f"Updated client_executable_path: {old_path} -> {file_path.absolute()}")
            else:
                path_setting = Setting(
                    key="client_executable_path",
                    value=str(file_path.absolute())
                )
                session.add(path_setting)
                logger.info(f"Created client_executable_path setting: {file_path.absolute()}")

            # Store upload timestamp (include platform to allow multiple platforms per version)
            timestamp_key = f"client_version_{version}_{platform}_uploaded"
            timestamp_setting = Setting(
                key=timestamp_key,
                value=datetime.now(timezone.utc).isoformat()
            )
            session.add(timestamp_setting)

            session.commit()

            return {
                "success": True,
                "version": version,
                "path": str(file_path.absolute()),
                "filename": filename,
                "size": len(file_data),
                "platform": platform
            }

        except Exception as e:
            session.rollback()
            logger.error(f"Database error storing client version: {e}")
            # Clean up file if database update failed
            if file_path.exists():
                file_path.unlink()
            raise

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Error storing client executable: {e}")
        raise


def ListClientVersions(db_manager) -> List[Dict[str, Any]]:
    """
    List all available client versions.

    Args:
        db_manager: DatabaseManager instance

    Returns:
        List of client version info dicts
    """
    downloads_path = GetClientDownloadsPath(db_manager)

    if not downloads_path.exists():
        return []

    versions = []

    # Scan downloads folder for executables
    for file_path in downloads_path.iterdir():
        if file_path.is_file() and file_path.name.startswith("aldersync-"):
            # Extract version from filename
            # Format: aldersync-X.Y.Z.exe or aldersync-X.Y.Z.app or aldersync-X.Y.Z
            name_without_ext = file_path.stem
            if "-" in name_without_ext:
                version = name_without_ext.split("-", 1)[1]

                # Get file stats
                stat = file_path.stat()

                # Determine platform from extension
                if file_path.suffix == ".exe":
                    platform = "Windows"
                elif file_path.suffix == ".app":
                    platform = "macOS"
                else:
                    platform = "Linux"

                versions.append({
                    "version": version,
                    "filename": file_path.name,
                    "path": str(file_path.absolute()),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    "platform": platform
                })

    # Sort by version (newest first)
    versions.sort(key=lambda x: x["version"], reverse=True)

    return versions


def GetCurrentClientVersion(db_manager) -> Optional[str]:
    """
    Get the currently active client version.

    Args:
        db_manager: DatabaseManager instance

    Returns:
        Current version string or None
    """
    from models.database import Setting

    session = db_manager.GetSession()
    try:
        version_setting = session.query(Setting).filter(
            Setting.key == "latest_client_version"
        ).first()

        return version_setting.value if version_setting else None

    finally:
        session.close()


def DeleteClientVersion(db_manager, version: str) -> bool:
    """
    Delete a client version file.
    If deleting the current active version, clears the active version setting.

    Args:
        db_manager: DatabaseManager instance
        version: Version to delete

    Returns:
        True if deleted successfully, False otherwise
    """
    from models.database import Setting

    current_version = GetCurrentClientVersion(db_manager)
    downloads_path = GetClientDownloadsPath(db_manager)

    # Find and delete all files matching this version
    deleted = False
    for file_path in downloads_path.iterdir():
        if file_path.is_file() and f"-{version}" in file_path.name:
            logger.info(f"Deleting client version file: {file_path}")
            file_path.unlink()
            deleted = True

    # If we deleted the current version, clear the active version setting
    if deleted and version == current_version:
        logger.warning(f"Deleted current active client version: {version}. Clearing active version setting.")
        session = db_manager.GetSession()
        try:
            version_setting = session.query(Setting).filter(
                Setting.key == "latest_client_version"
            ).first()
            if version_setting:
                session.delete(version_setting)
                session.commit()
        finally:
            session.close()

    return deleted


def SetActiveClientVersion(db_manager, version: str) -> bool:
    """
    Set a specific version as the active/latest client version.

    Args:
        db_manager: DatabaseManager instance
        version: Version to set as active

    Returns:
        True if successful, False if version file not found
    """
    from models.database import Setting

    downloads_path = GetClientDownloadsPath(db_manager)

    # Find the file for this version
    version_file = None
    for file_path in downloads_path.iterdir():
        if file_path.is_file() and f"-{version}" in file_path.name:
            version_file = file_path
            break

    if not version_file:
        logger.error(f"Client version file not found: {version}")
        return False

    session = db_manager.GetSession()
    try:
        # Update latest_client_version
        version_setting = session.query(Setting).filter(
            Setting.key == "latest_client_version"
        ).first()

        if version_setting:
            version_setting.value = version
        else:
            version_setting = Setting(key="latest_client_version", value=version)
            session.add(version_setting)

        # Update client_executable_path
        path_setting = session.query(Setting).filter(
            Setting.key == "client_executable_path"
        ).first()

        if path_setting:
            path_setting.value = str(version_file.absolute())
        else:
            path_setting = Setting(
                key="client_executable_path",
                value=str(version_file.absolute())
            )
            session.add(path_setting)

        session.commit()

        logger.info(f"Set active client version to: {version}")
        return True

    except Exception as e:
        session.rollback()
        logger.error(f"Error setting active client version: {e}")
        return False

    finally:
        session.close()
