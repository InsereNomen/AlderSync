"""
AlderSync Client - API Communication Module

Handles all communication with the AlderSync server via REST API.
Manages authentication, JWT tokens, and API requests.

Author: AlderSync Project
"""

import json
import logging
import requests
from typing import Optional, Dict, Any, List

from exceptions import (
    AlderSyncAPIError,
    AlderSyncAuthError,
    AlderSyncServerError,
    AlderSyncAdminCancelledError
)

# Configure logging
logger = logging.getLogger(__name__)


class AlderSyncAPI:
    """
    API client for communicating with AlderSync server.

    Responsibilities:
    - Authenticate with server (login)
    - Store and manage JWT token
    - Make authenticated API requests
    - Handle errors and token expiration
    """

    def __init__(self, server_url: str, server_port: int, verify_ssl: bool = True):
        """
        Initialize API client.

        Args:
            server_url: Base URL of server (e.g., "https://church-nas.local")
            server_port: Server port number (e.g., 443)
            verify_ssl: Whether to verify SSL certificates
        """
        self.base_url = f"{server_url}:{server_port}"
        self.verify_ssl = verify_ssl
        self.token: Optional[str] = None
        self.token_expires_in: Optional[int] = None
        # Use session for connection pooling to avoid TCP handshake overhead on each request
        self.session = requests.Session()
        logger.debug(f"Initialized API client for {self.base_url} (SSL verification: {self.verify_ssl})")

    def close(self):
        """
        Close the session and release resources.

        Should be called when done using the API client.
        """
        if hasattr(self, 'session') and self.session:
            self.session.close()
            logger.debug("API client session closed")

    def __del__(self):
        """Cleanup on deletion."""
        self.close()

    def login(self, username: str, password: str) -> bool:
        """
        Authenticate with server and receive JWT token.

        Args:
            username: User's username
            password: User's password

        Returns:
            True if authentication successful, False otherwise

        Raises:
            AlderSyncAuthError: If authentication fails
            AlderSyncServerError: If server error occurs
        """
        logger.info(f"Attempting login for user: {username}")
        url = f"{self.base_url}/auth/login"
        payload = {
            "username": username,
            "password": password
        }

        try:
            response = self.session.post(
                url,
                json=payload,
                verify=self.verify_ssl,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                self.token = data.get("token")
                self.token_expires_in = data.get("expires_in")
                logger.info(f"Login successful for user: {username}")
                return True
            elif response.status_code == 401:
                logger.warning(f"Login failed for user {username}: Invalid credentials")
                raise AlderSyncAuthError("Invalid username or password")
            else:
                logger.error(f"Login failed with status {response.status_code}: {response.text}")
                raise AlderSyncServerError(f"Login failed with status {response.status_code}: {response.text}")

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Cannot connect to server at {self.base_url}: {e}")
            raise AlderSyncServerError(f"Cannot connect to server at {self.base_url}")
        except requests.exceptions.Timeout:
            raise AlderSyncServerError("Connection to server timed out")
        except requests.exceptions.RequestException as e:
            raise AlderSyncServerError(f"Request error: {str(e)}")

    def change_password(self, current_password: str, new_password: str) -> bool:
        """
        Change user's password on server.

        Args:
            current_password: User's current password
            new_password: New password to set

        Returns:
            True if password changed successfully, False otherwise

        Raises:
            AlderSyncAuthError: If current password is incorrect or not logged in
            AlderSyncServerError: If server error occurs
        """
        if not self.token:
            raise AlderSyncAuthError("Must be logged in to change password")

        payload = {
            "current_password": current_password,
            "new_password": new_password
        }

        response_data = self._make_request("POST", "/user/change_password", json=payload)

        if response_data.get("success"):
            return True
        else:
            raise AlderSyncServerError(response_data.get("message", "Password change failed"))

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Any:
        """
        Make an authenticated API request.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/files/list")
            **kwargs: Additional arguments for request

        Returns:
            Response data (parsed JSON or raw data)

        Raises:
            AlderSyncAuthError: If authentication fails (token invalid/expired)
            AlderSyncServerError: If server error occurs
        """
        if not self.token:
            logger.error("Attempted API request without authentication")
            raise AlderSyncAuthError("Not authenticated - call login() first")

        # Build full URL
        url = f"{self.base_url}{endpoint}"
        logger.debug(f"API request: {method} {endpoint}")

        # Add Authorization header
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.token}"

        # Add verify_ssl and timeout if not specified
        if "verify" not in kwargs:
            kwargs["verify"] = self.verify_ssl
        if "timeout" not in kwargs:
            kwargs["timeout"] = 30

        try:
            # Make request using session for connection pooling
            response = self.session.request(method, url, headers=headers, **kwargs)

            # Handle authentication errors
            if response.status_code == 401:
                # Token expired or invalid
                self.token = None
                logger.warning("Authentication token expired or invalid")
                raise AlderSyncAuthError("Authentication token expired or invalid - please login again")

            # Handle admin cancellation (HTTP 409 Conflict with specific error)
            if response.status_code == 409:
                try:
                    error_data = response.json()
                    if error_data.get("error") == "transaction_cancelled_by_admin":
                        logger.warning("Operation cancelled by administrator")
                        raise AlderSyncAdminCancelledError(
                            error_data.get("message", "Operation cancelled by administrator")
                        )
                except AlderSyncAdminCancelledError:
                    # Re-raise admin cancelled error
                    raise
                except json.JSONDecodeError:
                    # Not JSON response - treat as generic error below
                    pass

            # Handle server errors
            if response.status_code >= 500:
                logger.error(f"Server error {response.status_code}: {response.text}")
                raise AlderSyncServerError(f"Server error {response.status_code}: {response.text}")

            # Handle client errors (4xx)
            if response.status_code >= 400:
                error_message = response.text
                try:
                    error_data = response.json()
                    error_message = error_data.get("message", error_message)
                except:
                    pass
                logger.error(f"Request failed with status {response.status_code}: {error_message}")
                raise AlderSyncServerError(f"Request failed with status {response.status_code}: {error_message}")

            # Try to parse JSON response
            try:
                return response.json()
            except json.JSONDecodeError:
                # Return raw content if not JSON
                return response.content

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Cannot connect to server at {self.base_url}: {e}")
            raise AlderSyncServerError(f"Cannot connect to server at {self.base_url}")
        except requests.exceptions.Timeout:
            logger.error("Request timed out")
            raise AlderSyncServerError("Request timed out")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            raise AlderSyncServerError(f"Request error: {str(e)}")

    # ==================== Transaction Endpoints ====================

    def begin_transaction(self, operation_type: str, service_type: str,
                         client_files: Optional[List[Dict[str, Any]]] = None,
                         description: str = "") -> Dict[str, Any]:
        """
        Begin a new transaction and acquire server lock.

        Args:
            operation_type: "Pull", "Push", or "Reconcile"
            service_type: "Contemporary" or "Traditional"
            client_files: For Reconcile operations, list of client file metadata
                         Each dict should have: path, size, hash, modified_utc
            description: Description for changelist (empty string by default)

        Returns:
            Transaction data including transaction_id, lock_acquired,
            and for Reconcile: files_to_pull, files_to_push

        Raises:
            AlderSyncServerError: If lock cannot be acquired or server error
        """
        payload = {
            "operation_type": operation_type,
            "service_type": service_type,
            "description": description
        }
        if client_files is not None:
            payload["client_files"] = client_files
        return self._make_request("POST", "/transaction/begin", json=payload)

    def commit_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """
        Commit a transaction (finalize changes).

        Args:
            transaction_id: ID of transaction to commit

        Returns:
            Commit result with success status and file counts

        Raises:
            AlderSyncServerError: If commit fails
        """
        return self._make_request("POST", f"/transaction/{transaction_id}/commit")

    def rollback_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """
        Rollback a transaction (discard changes).

        Args:
            transaction_id: ID of transaction to rollback

        Returns:
            Rollback result with success status

        Raises:
            AlderSyncServerError: If rollback fails
        """
        return self._make_request("POST", f"/transaction/{transaction_id}/rollback")

    def check_transaction_status(self, transaction_id: str) -> Dict[str, Any]:
        """
        Check the status of a transaction.

        Used for periodic polling to detect admin cancellation.

        Args:
            transaction_id: ID of transaction to check

        Returns:
            Transaction status information

        Raises:
            AlderSyncAdminCancelledError: If transaction was cancelled by admin
            AlderSyncServerError: If status check fails
        """
        return self._make_request("GET", f"/transaction/{transaction_id}/status")

    def download_file_in_transaction(self, transaction_id: str, file_path: str) -> bytes:
        """
        Download a file within a transaction.

        Args:
            transaction_id: ID of active transaction
            file_path: Path of file to download (relative to service folder)

        Returns:
            File binary data

        Raises:
            AlderSyncServerError: If download fails
        """
        params = {"path": file_path}
        return self._make_request(
            "GET",
            f"/transaction/{transaction_id}/download_file",
            params=params
        )

    def upload_file_in_transaction(self, transaction_id: str, file_path: str,
                                   file_data: bytes) -> Dict[str, Any]:
        """
        Upload a file within a transaction.

        Args:
            transaction_id: ID of active transaction
            file_path: Path of file to upload (relative to service folder)
            file_data: Binary file data

        Returns:
            Upload result with success status and file hash

        Raises:
            AlderSyncServerError: If upload fails
        """
        files = {"file": (file_path, file_data)}
        data = {"path": file_path}
        return self._make_request(
            "POST",
            f"/transaction/{transaction_id}/upload_file",
            files=files,
            data=data
        )

    # ==================== File Operations ====================

    def list_files(self, service_type: str) -> list:
        """
        List all files on server for a service type.

        Args:
            service_type: "Contemporary" or "Traditional"

        Returns:
            List of file metadata dictionaries with path, size, hash, modified_utc

        Raises:
            AlderSyncServerError: If request fails
        """
        params = {"service_type": service_type}
        return self._make_request("GET", "/files/list", params=params)

    def download_file(self, file_path: str, service_type: str) -> bytes:
        """
        Download a file directly (not in transaction).

        Args:
            file_path: Path of file to download
            service_type: "Contemporary" or "Traditional"

        Returns:
            File binary data

        Raises:
            AlderSyncServerError: If download fails
        """
        params = {"path": file_path, "service_type": service_type}
        return self._make_request("GET", "/files/download", params=params)

    def download_file_revision(self, file_path: str, revision: int, service_type: str) -> bytes:
        """
        Download a specific revision of a file without affecting the database.

        This allows downloading any revision for viewing or recovery purposes
        without changing the current file state or creating new revisions.

        Args:
            file_path: Path of file to download
            revision: Revision number to download (0 = initial version, highest = current version)
            service_type: "Contemporary" or "Traditional"

        Returns:
            File binary data

        Raises:
            AlderSyncServerError: If download fails or revision not found
        """
        params = {"path": file_path, "revision": revision, "service_type": service_type}
        return self._make_request("GET", "/files/download_revision", params=params)

    def get_file_revisions(self, file_path: str, service_type: str) -> List[Dict[str, Any]]:
        """
        Get all revisions for a file.

        Args:
            file_path: Path of file to get revisions for
            service_type: "Contemporary" or "Traditional"

        Returns:
            List of revision metadata dictionaries with revision, size, modified_utc, hash, username
            Sorted by revision number (newest first). Revision 0 is the initial version,
            and the highest revision number is the current version.

        Raises:
            AlderSyncServerError: If request fails
        """
        params = {"path": file_path, "service_type": service_type}
        return self._make_request("GET", "/files/revisions", params=params)

    def restore_revision(self, file_path: str, revision: int, service_type: str) -> bool:
        """
        Restore an old revision of a file.

        This makes an old revision the current version by:
        1. Creating a revision of the current file (if exists)
        2. Copying the old revision to become the current file
        3. Updating database metadata

        Args:
            file_path: Path of file to restore
            revision: Revision number to restore (must not be the current/highest revision)
            service_type: "Contemporary" or "Traditional"

        Returns:
            True if restoration successful

        Raises:
            AlderSyncServerError: If revision not found or restore fails
        """
        payload = {
            "path": file_path,
            "revision": revision,
            "service_type": service_type
        }
        response = self._make_request("POST", "/files/restore_revision", json=payload)
        return response.get("success", False)

    # ==================== Version Management ====================

    def check_for_updates(self, current_version: str) -> Dict[str, Any]:
        """
        Check if a client update is available.

        Args:
            current_version: Current client version (e.g., "1.0.0")

        Returns:
            Dict with version information:
            - current_version: The version provided
            - latest_version: Latest version available on server
            - update_available: True if update available
            - download_url: URL to download update (relative)

        Raises:
            AlderSyncServerError: If request fails
        """
        params = {"client_version": current_version}
        # This endpoint does not require authentication
        # So we'll use a direct request instead of _make_request
        url = f"{self.base_url}/api/version/check"

        try:
            response = self.session.get(
                url,
                params=params,
                verify=self.verify_ssl,
                timeout=10
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Version check failed with status {response.status_code}")
                raise AlderSyncServerError(f"Version check failed: {response.text}")

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Cannot connect to server at {self.base_url}: {e}")
            raise AlderSyncServerError(f"Cannot connect to server at {self.base_url}")
        except requests.exceptions.Timeout:
            raise AlderSyncServerError("Connection to server timed out")
        except requests.exceptions.RequestException as e:
            raise AlderSyncServerError(f"Request error: {str(e)}")

    def download_update(self, download_path: str) -> bool:
        """
        Download the latest client update to the specified path.

        Args:
            download_path: Full path where to save the downloaded executable

        Returns:
            True if download successful

        Raises:
            AlderSyncServerError: If download fails
        """
        url = f"{self.base_url}/api/version/download"

        try:
            logger.info(f"Downloading client update to: {download_path}")

            response = self.session.get(
                url,
                verify=self.verify_ssl,
                timeout=300,  # 5 minute timeout for large file
                stream=True  # Stream download for large files
            )

            if response.status_code == 200:
                # Write file in chunks to handle large files
                with open(download_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                logger.info(f"Client update downloaded successfully to: {download_path}")
                return True
            else:
                logger.error(f"Update download failed with status {response.status_code}")
                raise AlderSyncServerError(f"Update download failed: {response.text}")

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Cannot connect to server at {self.base_url}: {e}")
            raise AlderSyncServerError(f"Cannot connect to server at {self.base_url}")
        except requests.exceptions.Timeout:
            raise AlderSyncServerError("Download timed out")
        except requests.exceptions.RequestException as e:
            raise AlderSyncServerError(f"Download error: {str(e)}")
        except IOError as e:
            raise AlderSyncServerError(f"Failed to write update file: {str(e)}")
