"""
AlderSync Client - Folder Validation State Model

Contains the FolderValidationState enum and helper functions for
folder validation and OS-specific path handling.

Author: AlderSync Project
"""

import platform
from enum import Enum
from pathlib import Path
from typing import Optional


class FolderValidationState(Enum):
    """
    Enum representing the possible validation states for ProPresenter folders.

    States:
    - VALID: Folder state is valid (ProPresenter + exactly one alternate)
    - PROPRESENTER_MISSING: ProPresenter folder does not exist
    - BOTH_ALTERNATES_EXIST: Both Contemporary and Traditional alternates exist
    - NO_ALTERNATE_FOUND: ProPresenter exists but no alternate folder exists
    """
    VALID = "valid"
    PROPRESENTER_MISSING = "propresenter_missing"
    BOTH_ALTERNATES_EXIST = "both_alternates_exist"
    NO_ALTERNATE_FOUND = "no_alternate_found"


def get_validation_error_message(state: FolderValidationState) -> Optional[str]:
    """
    Convert a FolderValidationState enum to its corresponding error message.

    Args:
        state: The validation state enum

    Returns:
        Error message string for invalid states, None for VALID state
    """
    if state == FolderValidationState.VALID:
        return None
    elif state == FolderValidationState.PROPRESENTER_MISSING:
        return "ProPresenter folder missing. Please open ProPresenter at least once before using AlderSync."
    elif state == FolderValidationState.BOTH_ALTERNATES_EXIST:
        return ("Both 'ProPresenter - Contemporary' and 'ProPresenter - Traditional' folders exist. "
                "Cannot determine active service. Please remove one of the alternate folders.")
    elif state == FolderValidationState.NO_ALTERNATE_FOUND:
        return ("No alternate service folder found. Please use the Swap button to create one, "
                "or manually create either 'ProPresenter - Contemporary' or 'ProPresenter - Traditional'.")
    else:
        return f"Unknown validation state: {state}"


def get_documents_folder() -> Path:
    """
    Get the user's Documents folder path from the OS.

    This properly handles Windows where the Documents folder can be
    set to any arbitrary location by the user.

    Returns:
        Path to the user's Documents folder
    """
    system = platform.system()

    if system == "Windows":
        # On Windows, use ctypes to call Windows API to get the actual Documents folder
        # This handles cases where the user has moved their Documents folder
        try:
            import ctypes
            from ctypes import windll, wintypes

            # Define GUID structure for FOLDERID_Documents
            # {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
            class GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", wintypes.DWORD),
                    ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD),
                    ("Data4", wintypes.BYTE * 8)
                ]

            # FOLDERID_Documents GUID
            FOLDERID_Documents = GUID(
                0xFDD39AD0,
                0x238F,
                0x46AF,
                (wintypes.BYTE * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7)
            )

            # SHGetKnownFolderPath function
            _SHGetKnownFolderPath = windll.shell32.SHGetKnownFolderPath
            _SHGetKnownFolderPath.argtypes = [
                ctypes.POINTER(GUID),
                wintypes.DWORD,
                wintypes.HANDLE,
                ctypes.POINTER(ctypes.c_wchar_p)
            ]

            path_ptr = ctypes.c_wchar_p()
            result = _SHGetKnownFolderPath(
                ctypes.byref(FOLDERID_Documents),
                0,  # KF_FLAG_DEFAULT
                None,  # No user token
                ctypes.byref(path_ptr)
            )

            if result == 0:  # S_OK
                path = path_ptr.value
                # Free the memory allocated by Windows
                windll.ole32.CoTaskMemFree(path_ptr)
                return Path(path)
            else:
                # Fallback if API call fails
                return Path.home() / "Documents"

        except Exception:
            # If anything goes wrong with the Windows API call, fall back to default
            return Path.home() / "Documents"

    elif system == "Darwin":  # macOS
        # On macOS, Documents is typically at ~/Documents
        return Path.home() / "Documents"

    else:  # Linux and other Unix-like systems
        # On Linux, check XDG_DOCUMENTS_DIR first
        # This respects the user's XDG user directories configuration
        xdg_config = Path.home() / ".config" / "user-dirs.dirs"
        if xdg_config.exists():
            try:
                with open(xdg_config, 'r') as f:
                    for line in f:
                        if line.strip().startswith('XDG_DOCUMENTS_DIR='):
                            # Extract path from XDG_DOCUMENTS_DIR="$HOME/Documents"
                            docs_path = line.split('=', 1)[1].strip().strip('"')
                            # Replace $HOME with actual home directory
                            docs_path = docs_path.replace('$HOME', str(Path.home()))
                            return Path(docs_path)
            except Exception:
                pass

        # Fallback to ~/Documents
        return Path.home() / "Documents"
