"""
AlderSync Client - Configuration Manager

Handles loading and saving client configuration from/to config.json.
Manages OS credential store integration for password storage.

Author: AlderSync Project
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# Configure logging
logger = logging.getLogger(__name__)


# Default configuration values
DEFAULT_CONFIG = {
    "server_url": "https://localhost",
    "server_port": 8000,
    "verify_ssl": False,
    "username": None,  # Username stored in config, password in OS credential store
    "documents_path": None,  # None means use OS default Documents folder
    "default_service_type": "Contemporary",
    "log_level": "INFO",
    "log_retention_days": 30,
    "show_log_on_startup": False,
    "confirm_before_push": True,
    "pull_confirmation_size_mb": 100  # Size threshold for pull confirmation (MB)
}


class ConfigManager:
    """
    Manages client configuration and credentials.

    Responsibilities:
    - Load/save config.json next to the executable (same location as logs folder)
    - Store/retrieve password from OS credential store via keyring
    - Provide configuration values to other modules
    """

    def __init__(self):
        """Initialize configuration manager."""
        # Determine base directory (same logic as logs folder)
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            base_dir = Path(sys.executable).parent
        else:
            # Running as script
            base_dir = Path.cwd()

        self.config_file = base_dir / "config.json"
        self.config: Dict[str, Any] = {}

    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from config.json.
        Creates default config if file doesn't exist.

        Returns:
            Configuration dictionary
        """
        # Load config file or create default
        if self.config_file.exists():
            logger.debug(f"Loading configuration from {self.config_file}")
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
            # Merge with defaults for any missing keys
            for key, value in DEFAULT_CONFIG.items():
                if key not in self.config:
                    self.config[key] = value
            logger.info("Configuration loaded successfully")
        else:
            logger.info(f"Configuration file not found, creating default at {self.config_file}")
            self.config = DEFAULT_CONFIG.copy()
            self.save_config()

        return self.config

    def save_config(self):
        """Save current configuration to config.json."""
        logger.debug(f"Saving configuration to {self.config_file}")
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
        logger.debug("Configuration saved successfully")

    def get(self, key: str, default=None) -> Any:
        """
        Get configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value
        """
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        """
        Set configuration value and save to file.

        Args:
            key: Configuration key
            value: Configuration value
        """
        self.config[key] = value
        self.save_config()

    def store_credentials(self, username: str, password: str):
        """
        Store credentials in OS credential store.

        Args:
            username: Username to store
            password: Password to store (securely in OS credential store)
        """
        import keyring

        logger.info(f"Storing credentials for user: {username}")

        # Store username in config.json
        self.set("username", username)

        # Store password in OS credential store
        keyring.set_password("AlderSync", username, password)

        logger.debug("Credentials stored successfully")

    def get_credentials(self) -> Optional[tuple[str, str]]:
        """
        Retrieve credentials from OS credential store.

        Returns:
            Tuple of (username, password) or None if not found
        """
        import keyring

        logger.debug("Retrieving credentials from OS credential store")

        # Get username from config
        username = self.get("username")
        if not username:
            logger.warning("No username found in configuration")
            return None

        # Get password from OS credential store
        password = keyring.get_password("AlderSync", username)
        if not password:
            logger.warning(f"No password found in credential store for user: {username}")
            return None

        logger.debug(f"Credentials retrieved successfully for user: {username}")
        return (username, password)
