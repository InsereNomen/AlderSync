"""
AlderSync Client - Auto-Updater Module

Handles checking for updates, downloading new client versions,
and installing updates with automatic restart.

Author: AlderSync Project
"""

import os
import sys
import logging
import tempfile
import subprocess
import time
from pathlib import Path
from typing import Optional, Tuple

from api import AlderSyncAPI
from version import VERSION
from exceptions import AlderSyncServerError

logger = logging.getLogger(__name__)


class ClientUpdater:
    """
    Manages client auto-update functionality.

    Responsibilities:
    - Check if updates are available
    - Download new client executable
    - Replace running executable with new version
    - Restart client application
    """

    def __init__(self, api: AlderSyncAPI):
        """
        Initialize updater.

        Args:
            api: AlderSync API client instance
        """
        self.api = api
        self.current_version = VERSION

    def check_for_updates(self) -> Tuple[bool, Optional[str]]:
        """
        Check if a newer version is available on the server.

        Returns:
            Tuple of (update_available: bool, latest_version: str or None)

        Raises:
            AlderSyncServerError: If version check fails
        """
        logger.info(f"Checking for updates (current version: {self.current_version})")

        try:
            version_info = self.api.check_for_updates(self.current_version)

            update_available = version_info.get("update_available", False)
            latest_version = version_info.get("latest_version")

            if update_available:
                logger.info(f"Update available: {latest_version}")
            else:
                logger.info("No updates available")

            return update_available, latest_version

        except AlderSyncServerError as e:
            logger.error(f"Failed to check for updates: {e}")
            raise

    def download_and_install_update(self) -> bool:
        """
        Download the latest client version and install it.

        This performs the following steps:
        1. Download new executable to temporary location
        2. Create update script to replace current executable
        3. Execute update script and exit current process
        4. Update script replaces executable and restarts client

        Returns:
            True if update process initiated successfully
            (Note: Process will exit before returning if successful)

        Raises:
            AlderSyncServerError: If download fails
        """
        logger.info("Starting update download and installation process")

        # Determine current executable path
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            current_exe = sys.executable
        else:
            # Running as Python script - cannot auto-update
            logger.error("Auto-update not supported when running as Python script")
            raise AlderSyncServerError("Auto-update only works with compiled executable")

        current_exe_path = Path(current_exe)
        logger.info(f"Current executable: {current_exe_path}")

        # Create temporary file for new executable
        temp_dir = tempfile.gettempdir()
        temp_exe_path = Path(temp_dir) / "aldersync_update.exe"

        try:
            # Download new version to temporary location
            logger.info(f"Downloading update to: {temp_exe_path}")
            self.api.download_update(str(temp_exe_path))

            # Verify download succeeded
            if not temp_exe_path.exists():
                raise AlderSyncServerError("Update download failed - file not found")

            logger.info("Update downloaded successfully")

            # Create update script
            update_script = self._create_update_script(
                str(temp_exe_path),
                str(current_exe_path)
            )

            logger.info(f"Created update script: {update_script}")

            # Execute update script and exit
            logger.info("Launching update script and exiting")
            self._execute_update_script(update_script)

            # If we reach here, script execution failed
            return False

        except Exception as e:
            logger.error(f"Update installation failed: {e}")
            # Clean up temp file if it exists
            if temp_exe_path.exists():
                try:
                    temp_exe_path.unlink()
                except:
                    pass
            raise

    def _create_update_script(self, new_exe: str, current_exe: str) -> str:
        """
        Create a batch/shell script to replace the executable and restart.

        Args:
            new_exe: Path to new executable (downloaded)
            current_exe: Path to current executable (to be replaced)

        Returns:
            Path to update script
        """
        if sys.platform == 'win32':
            return self._create_windows_update_script(new_exe, current_exe)
        else:
            return self._create_unix_update_script(new_exe, current_exe)

    def _create_windows_update_script(self, new_exe: str, current_exe: str) -> str:
        """
        Create Windows batch script for update.

        The script:
        1. Waits for current process to exit
        2. Replaces old executable with new one
        3. Restarts the application
        4. Deletes itself

        Args:
            new_exe: Path to new executable
            current_exe: Path to current executable

        Returns:
            Path to batch script
        """
        script_path = Path(tempfile.gettempdir()) / "aldersync_update.bat"

        script_content = f"""@echo off
REM AlderSync Auto-Update Script
REM Wait for current process to exit
timeout /t 2 /nobreak >nul

REM Replace old executable with new one
move /Y "{new_exe}" "{current_exe}"

REM Start the updated application
start "" "{current_exe}"

REM Delete this script
del "%~f0"
"""

        with open(script_path, 'w') as f:
            f.write(script_content)

        return str(script_path)

    def _create_unix_update_script(self, new_exe: str, current_exe: str) -> str:
        """
        Create Unix shell script for update.

        Args:
            new_exe: Path to new executable
            current_exe: Path to current executable

        Returns:
            Path to shell script
        """
        script_path = Path(tempfile.gettempdir()) / "aldersync_update.sh"

        script_content = f"""#!/bin/bash
# AlderSync Auto-Update Script
# Wait for current process to exit
sleep 2

# Replace old executable with new one
mv -f "{new_exe}" "{current_exe}"
chmod +x "{current_exe}"

# Start the updated application
"{current_exe}" &

# Delete this script
rm -f "$0"
"""

        with open(script_path, 'w') as f:
            f.write(script_content)

        # Make script executable
        os.chmod(script_path, 0o755)

        return str(script_path)

    def _execute_update_script(self, script_path: str):
        """
        Execute the update script and exit the current process.

        Args:
            script_path: Path to update script
        """
        if sys.platform == 'win32':
            # Windows: Execute batch file in background
            subprocess.Popen(
                ['cmd', '/c', script_path],
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                close_fds=True
            )
        else:
            # Unix: Execute shell script in background
            subprocess.Popen(
                ['/bin/bash', script_path],
                start_new_session=True,
                close_fds=True
            )

        # Exit current process to allow replacement
        logger.info("Exiting for update...")
        sys.exit(0)
