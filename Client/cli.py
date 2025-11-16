"""
AlderSync Client - CLI Mode Module

Implements command-line interface mode for headless/automated operations.
Uses stored credentials, executes operations without GUI, and logs to timestamped file.

Author: AlderSync Project
"""

import sys
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from managers import ConfigManager, FolderManager
from models import FolderValidationState
from api import AlderSyncAPI
from exceptions import AlderSyncAPIError
from operations import SyncOperations


# Exit codes
EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_CONFIG_ERROR = 2
EXIT_AUTH_ERROR = 3
EXIT_INVALID_STATE = 4


def setup_cli_logging(config_manager: ConfigManager) -> Path:
    """
    Setup logging for CLI mode with timestamped log file.

    Creates log file with format: aldersync-YYYY-MM-DD-HH-MM-SS.log
    in a "logs" subdirectory next to the executable or in the current directory.

    Args:
        config_manager: ConfigManager instance for log settings

    Returns:
        Path to the created log file
    """
    # Get log level from config
    log_level = config_manager.get("log_level", "INFO")

    # Create timestamped log filename
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    log_filename = f"aldersync-{timestamp}.log"

    # Place log file in logs subdirectory
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        base_dir = Path(sys.executable).parent
    else:
        # Running as script
        base_dir = Path.cwd()

    # Create logs subdirectory if it doesn't exist
    log_dir = base_dir / "logs"
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / log_filename

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)  # Also output to console
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info(f"AlderSync CLI Mode - Log file: {log_file}")
    logger.info(f"Log level: {log_level}")

    return log_file


def cleanup_old_logs(config_manager: ConfigManager, current_log: Path):
    """
    Delete log files older than retention period.

    Args:
        config_manager: ConfigManager instance for retention settings
        current_log: Path to current log file (don't delete this)
    """
    logger = logging.getLogger(__name__)
    retention_days = config_manager.get("log_retention_days", 30)

    if retention_days <= 0:
        return  # Retention disabled

    logger.info(f"Cleaning up log files older than {retention_days} days")

    log_dir = current_log.parent
    cutoff_time = datetime.now().timestamp() - (retention_days * 86400)

    deleted_count = 0
    for log_file in log_dir.glob("aldersync-*.log"):
        if log_file == current_log:
            continue  # Don't delete current log

        try:
            if log_file.stat().st_mtime < cutoff_time:
                log_file.unlink()
                deleted_count += 1
        except Exception as e:
            logger.warning(f"Failed to delete old log file {log_file}: {e}")

    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} old log file(s)")


def determine_service_type(config_manager: ConfigManager, service_override: Optional[str]) -> Optional[str]:
    """
    Determine which service type to use.

    Priority: command-line argument > config setting

    Args:
        config_manager: ConfigManager instance
        service_override: Optional service type from --service argument

    Returns:
        Service type string or None if not specified
    """
    if service_override:
        return service_override

    return config_manager.get("default_service_type")


def run_cli_operation(operation: str, service_override: Optional[str] = None) -> int:
    """
    Execute CLI operation without GUI.

    Process:
    1. Setup logging to timestamped file
    2. Load configuration
    3. Retrieve stored credentials
    4. Validate folder state
    5. Determine service type
    6. Login to server
    7. Execute requested operation
    8. Return appropriate exit code

    Args:
        operation: Operation to perform ("pull", "push", or "reconcile")
        service_override: Optional service type override from --service argument

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    logger = None

    try:
        # Setup logging
        config_mgr = ConfigManager()
        config_mgr.load_config()
        log_file = setup_cli_logging(config_mgr)
        logger = logging.getLogger(__name__)

        # Cleanup old logs
        cleanup_old_logs(config_mgr, log_file)

        logger.info("=" * 60)
        logger.info(f"Starting AlderSync CLI: {operation.upper()}")
        logger.info("=" * 60)

        # Get stored credentials
        logger.info("Loading stored credentials")
        credentials = config_mgr.get_credentials()
        if not credentials:
            logger.error("No stored credentials found. Please run GUI mode once to configure.")
            return EXIT_AUTH_ERROR

        username, password = credentials
        logger.info(f"Loaded credentials for user: {username}")

        # Determine service type
        service_type = determine_service_type(config_mgr, service_override)
        if not service_type:
            logger.error("Service type not specified. Set default_service_type in config or use --service argument.")
            return EXIT_CONFIG_ERROR

        logger.info(f"Service type: {service_type}")

        # Initialize folder manager and validate state
        logger.info("Validating folder state")
        documents_path = config_mgr.get("documents_path")
        folder_mgr = FolderManager(documents_path)
        folder_state, detected_service = folder_mgr.validate_folder_state()

        if folder_state == FolderValidationState.PROPRESENTER_MISSING:
            logger.error("ProPresenter folder missing. Please open ProPresenter at least once.")
            return EXIT_INVALID_STATE
        elif folder_state == FolderValidationState.NO_ALTERNATE_FOUND:
            logger.info("No alternate folder found - will create if needed during operation")
        elif folder_state == FolderValidationState.BOTH_ALTERNATES_EXIST:
            logger.error("Both alternate folders exist. Cannot determine active service.")
            return EXIT_INVALID_STATE

        # Verify detected service type matches requested if valid
        if detected_service and detected_service != service_type:
            logger.warning(f"Current folder state indicates {detected_service} but {service_type} was requested")
            logger.info(f"Operating on {service_type} service as requested")

        # Initialize API client
        logger.info("Initializing API client")
        server_url = config_mgr.get("server_url")
        server_port = config_mgr.get("server_port")
        verify_ssl = config_mgr.get("verify_ssl", False)

        api_client = AlderSyncAPI(server_url, server_port, verify_ssl)

        # Login to server
        logger.info(f"Logging in to server: {server_url}:{server_port}")
        if not api_client.login(username, password):
            logger.error("Login failed. Please verify credentials and server connection.")
            return EXIT_AUTH_ERROR

        logger.info("Login successful")

        # Initialize sync operations
        sync_ops = SyncOperations(api_client, folder_mgr, config_mgr)

        # Create simple progress callback for CLI
        def cli_progress_callback(message: str, current: int, total: int):
            if total > 0:
                percentage = (current / total) * 100
                logger.info(f"[{percentage:5.1f}%] {message}")
            else:
                logger.info(message)

        # Execute requested operation
        logger.info(f"Starting {operation} operation for {service_type} service")

        success = False
        if operation == "pull":
            success = sync_ops.pull(service_type, cli_progress_callback)
        elif operation == "push":
            success = sync_ops.push(service_type, cli_progress_callback)
        elif operation == "reconcile":
            success = sync_ops.reconcile(service_type, cli_progress_callback)
        else:
            logger.error(f"Unknown operation: {operation}")
            return EXIT_FAILURE

        # Report result
        if success:
            logger.info("=" * 60)
            logger.info(f"{operation.upper()} COMPLETED SUCCESSFULLY")
            logger.info("=" * 60)
            return EXIT_SUCCESS
        else:
            logger.error("=" * 60)
            logger.error(f"{operation.upper()} FAILED")
            logger.error("=" * 60)
            return EXIT_FAILURE

    except AlderSyncAPIError as e:
        if logger:
            logger.error(f"API Error: {e}")
        else:
            print(f"API Error: {e}", file=sys.stderr)
        return EXIT_FAILURE

    except KeyboardInterrupt:
        if logger:
            logger.warning("Operation cancelled by user (Ctrl+C)")
        else:
            print("\nOperation cancelled by user", file=sys.stderr)
        return EXIT_FAILURE

    except Exception as e:
        if logger:
            logger.exception(f"Unexpected error: {e}")
        else:
            print(f"Unexpected error: {e}", file=sys.stderr)
        return EXIT_FAILURE
