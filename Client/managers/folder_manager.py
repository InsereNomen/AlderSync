"""
AlderSync Client - Folder Manager

Handles ProPresenter folder detection, validation, and swapping between
Contemporary and Traditional service types.

Author: AlderSync Project
"""

import logging
import platform
import psutil
from pathlib import Path
from typing import Optional, Tuple

from models import (
    FolderValidationState,
    get_validation_error_message,
    get_documents_folder
)

# Configure logging
logger = logging.getLogger(__name__)


class FolderManager:
    """
    Manages ProPresenter folder operations.

    Responsibilities:
    - Detect ProPresenter folder location
    - Validate folder state (ensure exactly one active, one alternate)
    - Determine current service type from folder state
    - Swap folders between Contemporary and Traditional
    - Auto-create missing alternate folder when needed
    - Detect if ProPresenter process is running
    """

    def __init__(self, documents_path: Optional[str] = None):
        """
        Initialize folder manager.

        Args:
            documents_path: Optional custom Documents folder path.
                           If None, uses OS default Documents folder.
        """
        if documents_path:
            self.documents_path = Path(documents_path)
        else:
            # Use OS default Documents folder
            # This properly gets the Documents folder from the OS, handling cases
            # where the user has moved their Documents folder (especially on Windows)
            self.documents_path = get_documents_folder()

        self.propresenter_folder = self.documents_path / "ProPresenter"
        self.contemporary_folder = self.documents_path / "ProPresenter - Contemporary"
        self.traditional_folder = self.documents_path / "ProPresenter - Traditional"

    def validate_folder_state(self) -> Tuple[FolderValidationState, Optional[str]]:
        """
        Validate ProPresenter folder state.

        Valid states:
        - ProPresenter/ exists AND exactly one alternate folder exists

        Invalid states:
        - No ProPresenter folder
        - Both alternate folders exist (no active service)
        - Only ProPresenter/ exists (no alternate to swap with)

        Returns:
            Tuple of (validation_state, current_service_type)
            - validation_state: FolderValidationState enum indicating the validation result
            - current_service_type: "Contemporary" or "Traditional" if valid, None otherwise
        """
        logger.debug("Validating ProPresenter folder state")

        # Check folder existence
        propresenter_exists = self.propresenter_folder.exists()
        contemporary_exists = self.contemporary_folder.exists()
        traditional_exists = self.traditional_folder.exists()

        logger.debug(f"Folder state - ProPresenter: {propresenter_exists}, "
                    f"Contemporary: {contemporary_exists}, Traditional: {traditional_exists}")

        # Invalid: No ProPresenter folder exists
        if not propresenter_exists:
            logger.warning("ProPresenter folder missing")
            return (FolderValidationState.PROPRESENTER_MISSING, None)

        # Invalid: Both alternate folders exist (no active service can be determined)
        if contemporary_exists and traditional_exists:
            logger.warning("Both alternate folders exist - cannot determine active service")
            return (FolderValidationState.BOTH_ALTERNATES_EXIST, None)

        # Invalid: Only ProPresenter folder exists (no alternate to swap with)
        if not contemporary_exists and not traditional_exists:
            logger.warning("No alternate folder found")
            return (FolderValidationState.NO_ALTERNATE_FOUND, None)

        # Valid: ProPresenter exists and exactly one alternate exists
        # Determine service type from which alternate folder exists
        if contemporary_exists:
            # Contemporary folder exists as alternate, so Traditional is active
            logger.info("Folder state valid - Traditional service active")
            return (FolderValidationState.VALID, "Traditional")
        else:
            # Traditional folder exists as alternate, so Contemporary is active
            logger.info("Folder state valid - Contemporary service active")
            return (FolderValidationState.VALID, "Contemporary")

    def get_current_service_type(self) -> Optional[str]:
        """
        Determine current service type from folder state.

        Returns:
            "Contemporary" or "Traditional" based on which alternate folder exists,
            or None if folder state is invalid
        """
        validation_state, service_type = self.validate_folder_state()
        return service_type if validation_state == FolderValidationState.VALID else None

    def is_propresenter_running(self) -> bool:
        """
        Check if ProPresenter process is currently running.

        Returns:
            True if ProPresenter is running, False otherwise
        """
        logger.debug("Checking if ProPresenter is running")

        # Determine process name based on platform
        system = platform.system()
        if system == "Windows":
            process_name = "ProPresenter.exe"
        elif system == "Darwin":  # macOS
            process_name = "ProPresenter"
        else:  # Linux (ProPresenter doesn't run on Linux, but handle gracefully)
            logger.debug("Running on Linux - ProPresenter not supported")
            return False

        # Check if process is running using psutil
        for process in psutil.process_iter(['name']):
            try:
                if process.info['name'] == process_name:
                    logger.info("ProPresenter is running")
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Process terminated or we don't have access - skip it
                pass

        logger.debug("ProPresenter is not running")
        return False

    def swap_service_folders(self) -> Tuple[bool, str, Optional[str]]:
        """
        Swap ProPresenter folders between Contemporary and Traditional.

        Process:
        1. Check ProPresenter not running
        2. Validate folder state
        3. Auto-create missing alternate folder if needed
        4. Rename ProPresenter → ProPresenter - [CurrentService]
        5. Rename ProPresenter - [OtherService] → ProPresenter

        Returns:
            Tuple of (success, message, new_service_type)
            - success: True if swap succeeded
            - message: Status or error message
            - new_service_type: The service type after swap (None if failed)
        """
        logger.info("Starting service folder swap operation")

        # Step 1: Check ProPresenter not running
        if self.is_propresenter_running():
            logger.warning("Cannot swap - ProPresenter is running")
            return (False, "ProPresenter is running. Please close it and try again.", None)

        # Step 2: Validate folder state
        validation_state, current_service = self.validate_folder_state()

        # Special handling: If only ProPresenter exists (no alternate), create the missing one
        if validation_state == FolderValidationState.NO_ALTERNATE_FOUND:
            # ProPresenter folder exists but no alternate
            # We need to create an alternate - but which one?
            # Default to creating Traditional alternate (making current service Contemporary)
            # This matches the typical use case
            if self.propresenter_folder.exists():
                # Ask user to specify which service is currently active
                # For now, default to creating Traditional alternate
                # (This means current ProPresenter folder is Contemporary)
                create_message = self.auto_create_alternate_folder("Traditional")
                # Re-validate after creation
                validation_state, current_service = self.validate_folder_state()
                if validation_state != FolderValidationState.VALID:
                    error_message = get_validation_error_message(validation_state)
                    return (False, f"Failed to create alternate folder: {error_message}", None)
            else:
                error_message = get_validation_error_message(validation_state)
                return (False, error_message, None)
        elif validation_state != FolderValidationState.VALID:
            error_message = get_validation_error_message(validation_state)
            return (False, error_message, None)

        # Step 3: Determine target service (the one we're swapping TO)
        if current_service == "Contemporary":
            target_service = "Traditional"
            current_alternate_folder = self.traditional_folder
            target_alternate_folder = self.contemporary_folder
        else:  # Traditional
            target_service = "Contemporary"
            current_alternate_folder = self.contemporary_folder
            target_alternate_folder = self.traditional_folder

        logger.info(f"Swapping from {current_service} to {target_service}")

        # Step 4: Auto-create missing alternate folder if it doesn't exist yet
        # (This shouldn't normally happen since we validated, but handle edge case)
        if not current_alternate_folder.exists():
            logger.warning(f"Alternate folder missing, creating: {target_service}")
            create_message = self.auto_create_alternate_folder(target_service)
            # No return needed here - we'll continue with the swap

        # Step 5 & 6: Perform the swap using temporary name to avoid conflicts
        try:
            # Use a temporary folder name to avoid conflicts during rename
            temp_folder = self.documents_path / "ProPresenter_temp_swap"

            # Make sure temp folder doesn't already exist (cleanup from previous failed swap)
            if temp_folder.exists():
                # Try to remove it - if it fails, we'll get an error
                import shutil
                shutil.rmtree(temp_folder)

            # Rename ProPresenter → temp
            self.propresenter_folder.rename(temp_folder)

            # Rename ProPresenter - [OtherService] → ProPresenter
            current_alternate_folder.rename(self.propresenter_folder)

            # Rename temp → ProPresenter - [CurrentService]
            temp_folder.rename(target_alternate_folder)

            logger.info(f"Successfully swapped to {target_service} service")
            return (True, f"Swapped to {target_service} service", target_service)

        except Exception as e:
            # Try to recover from partial swap
            logger.error(f"Swap operation failed: {str(e)}")
            error_msg = f"Swap failed: {str(e)}"

            # Attempt rollback if temp folder exists
            if temp_folder.exists():
                try:
                    logger.info("Attempting to rollback failed swap")
                    # If ProPresenter folder doesn't exist, restore from temp
                    if not self.propresenter_folder.exists():
                        temp_folder.rename(self.propresenter_folder)
                    logger.info("Rollback successful")
                except Exception as rollback_error:
                    logger.error(f"Rollback also failed: {rollback_error}")
                    error_msg += f" (Rollback also failed: {rollback_error})"

            return (False, error_msg, None)

    def auto_create_alternate_folder(self, service_type: str) -> str:
        """
        Auto-create missing alternate folder if needed.

        Args:
            service_type: "Contemporary" or "Traditional" - which folder to create

        Returns:
            String message describing the folder creation
        """
        if service_type == "Contemporary":
            folder_to_create = self.contemporary_folder
            folder_name = "ProPresenter - Contemporary"
        elif service_type == "Traditional":
            folder_to_create = self.traditional_folder
            folder_name = "ProPresenter - Traditional"
        else:
            raise ValueError(f"Invalid service type: {service_type}")

        # Create the folder
        folder_to_create.mkdir(parents=True, exist_ok=True)

        message = f"Creating '{folder_name}' folder at {folder_to_create}"
        return message
