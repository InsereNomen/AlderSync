"""
AlderSync Client - Sync Operations Module

Implements Pull, Push, and Reconcile synchronization operations.
Handles transaction management, file transfers, and rollback on failure.

Author: AlderSync Project
"""

import os
import shutil
import hashlib
import logging
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
from datetime import datetime

from exceptions import AlderSyncAdminCancelledError

# Configure logging
logger = logging.getLogger(__name__)


class SyncOperations:
    """
    Handles file synchronization operations with server.

    Responsibilities:
    - Execute Pull operation (download files from server)
    - Execute Push operation (upload files to server)
    - Execute Reconcile operation (bidirectional sync)
    - Manage transactions (begin, commit, rollback)
    - Create local backups before operations
    - Restore from backup on failure
    - Report progress via callbacks
    """

    def __init__(self, api_client, folder_manager, config_manager):
        """
        Initialize sync operations handler.

        Args:
            api_client: AlderSyncAPI instance for server communication
            folder_manager: FolderManager instance for folder operations
            config_manager: ConfigManager instance for configuration
        """
        self.api = api_client
        self.folder_mgr = folder_manager
        self.config = config_manager
        self.transaction_id: Optional[str] = None
        self.cancel_requested: bool = False
        self.backup_path: Optional[Path] = None

    def pull(self, service_type: str, progress_callback: Optional[Callable] = None) -> bool:
        """
        Pull files from server (download newer files).

        Process:
        1. Begin transaction with server
        2. Create local backup of files to be modified
        3. Download files from server
        4. Verify file hashes
        5. Commit transaction on success, rollback on failure
        6. Delete backup on success, restore on failure

        Args:
            service_type: "Contemporary" or "Traditional"
            progress_callback: Optional callback for progress updates
                             Called with (message: str, current: int, total: int)

        Returns:
            True if pull succeeded, False otherwise
        """
        self.cancel_requested = False
        logger.info(f"Starting Pull operation for {service_type} service")

        if progress_callback:
            progress_callback("Initializing Pull operation...", 0, 100)

        try:
            # Step 1: Begin transaction with server
            logger.info("Beginning transaction with server")
            if progress_callback:
                progress_callback("Acquiring server lock...", 5, 100)

            tx_response = self.api.begin_transaction("Pull", service_type)
            self.transaction_id = tx_response.get("transaction_id")

            if not tx_response.get("lock_acquired"):
                logger.error("Failed to acquire server lock")
                if progress_callback:
                    progress_callback("Failed to acquire lock", 0, 100)
                return False

            logger.info(f"Transaction started: {self.transaction_id}")

            # Step 2: Get list of files from server
            if progress_callback:
                progress_callback("Fetching file list from server...", 10, 100)

            server_files = self.api.list_files(service_type)
            logger.info(f"Server has {len(server_files)} files")

            # Get ProPresenter folder path
            propresenter_folder = self.folder_mgr.propresenter_folder

            # Step 3: Determine which files need to be downloaded or deleted
            files_to_download = []
            files_to_delete = []

            for file_meta in server_files:
                file_path = file_meta["path"]
                is_deleted = file_meta.get("is_deleted", False)

                if is_deleted:
                    # File deleted on server - mark for local deletion
                    local_file = propresenter_folder / file_path
                    if local_file.exists():
                        files_to_delete.append(file_path)
                else:
                    # File exists on server - check if we need to download
                    local_file = propresenter_folder / file_path
                    needs_download = False

                    if not local_file.exists():
                        # File doesn't exist locally - download it
                        needs_download = True
                    else:
                        # File exists - compare to see if server version is newer
                        local_hash = self._calculate_file_hash(local_file)
                        server_hash = file_meta.get("hash")

                        if local_hash != server_hash:
                            # Hashes differ - download server version
                            needs_download = True

                    if needs_download:
                        files_to_download.append(file_meta)

            total_operations = len(files_to_download) + len(files_to_delete)
            logger.info(f"Need to download {len(files_to_download)} files, delete {len(files_to_delete)} files")

            if total_operations == 0:
                # Nothing to sync
                logger.info("No files need to be pulled - already in sync")
                if progress_callback:
                    progress_callback("Already synchronized", 100, 100)
                self.api.commit_transaction(self.transaction_id)
                self.transaction_id = None
                return True

            # Step 3.5: Check disk space before proceeding
            if progress_callback:
                progress_callback("Checking disk space...", 12, 100)

            # Determine files that need backup
            files_to_backup = [f["path"] for f in files_to_download if
                             (propresenter_folder / f["path"]).exists()]
            files_to_backup.extend(files_to_delete)

            # Check if we have enough disk space
            has_space, space_message = self._check_disk_space(
                files_to_download,
                files_to_backup,
                propresenter_folder
            )

            if not has_space:
                logger.error(f"Aborting pull due to insufficient disk space")
                if progress_callback:
                    progress_callback(f"Insufficient disk space", 0, 100)
                # Rollback transaction
                self.api.rollback_transaction(self.transaction_id)
                self.transaction_id = None
                raise Exception(space_message)

            # Step 4: Create backup of files that will be modified or deleted
            if progress_callback:
                progress_callback("Creating backup...", 15, 100)

            if files_to_backup:
                self.backup_path = self._create_backup(files_to_backup, propresenter_folder)
                logger.info(f"Created backup at {self.backup_path}")

            # Step 5: Download files from server
            current_file = 0
            for file_meta in files_to_download:
                if self.cancel_requested:
                    logger.warning("Pull operation cancelled by user")
                    raise Exception("Operation cancelled by user")

                file_path = file_meta["path"]
                current_file += 1
                progress_pct = 15 + int((current_file / total_operations) * 75)

                if progress_callback:
                    progress_callback(f"Downloading {file_path}...", progress_pct, 100)

                logger.info(f"Downloading file {current_file}/{len(files_to_download)}: {file_path}")

                # Download file from server
                file_data = self.api.download_file_in_transaction(self.transaction_id, file_path)

                # Verify hash
                downloaded_hash = self._calculate_hash_from_bytes(file_data)
                expected_hash = file_meta.get("hash")

                if downloaded_hash != expected_hash:
                    logger.error(f"Hash mismatch for {file_path}: expected {expected_hash}, got {downloaded_hash}")
                    raise Exception(f"Hash verification failed for {file_path}")

                # Write file to disk
                local_file = propresenter_folder / file_path

                # Create parent directories if needed
                local_file.parent.mkdir(parents=True, exist_ok=True)

                # Write file
                with open(local_file, 'wb') as f:
                    f.write(file_data)

                # Set file modified time to match server's recorded time
                modified_utc = file_meta.get("modified_utc")
                if modified_utc:
                    try:
                        # Parse ISO format datetime string
                        from datetime import datetime
                        if modified_utc.endswith('Z'):
                            modified_utc = modified_utc[:-1] + '+00:00'
                        dt = datetime.fromisoformat(modified_utc)
                        # Convert to timestamp
                        timestamp = dt.timestamp()
                        # Set both access time and modification time
                        os.utime(local_file, (timestamp, timestamp))
                    except Exception as e:
                        # Log but don't fail if timestamp setting fails
                        logger.warning(f"Failed to set file timestamp for {file_path}: {e}")

                logger.info(f"Successfully downloaded {file_path}")

            # Step 6: Delete files that were deleted on server
            for file_path in files_to_delete:
                if self.cancel_requested:
                    logger.warning("Pull operation cancelled by user")
                    raise Exception("Operation cancelled by user")

                current_file += 1
                progress_pct = 15 + int((current_file / total_operations) * 75)

                if progress_callback:
                    progress_callback(f"Deleting {file_path}...", progress_pct, 100)

                logger.info(f"Deleting local file: {file_path}")
                local_file = propresenter_folder / file_path

                if local_file.exists():
                    local_file.unlink()

            # Step 7: Commit transaction
            if progress_callback:
                progress_callback("Committing changes...", 95, 100)

            logger.info("Committing transaction")
            commit_result = self.api.commit_transaction(self.transaction_id)
            logger.info(f"Transaction committed successfully: {commit_result}")

            # Step 8: Delete backup on success
            if self.backup_path and self.backup_path.exists():
                logger.info(f"Deleting backup at {self.backup_path}")
                shutil.rmtree(self.backup_path)
                self.backup_path = None

            if progress_callback:
                progress_callback(f"Pull completed: {total_operations} files synchronized", 100, 100)

            logger.info("Pull operation completed successfully")
            self.transaction_id = None
            return True

        except AlderSyncAdminCancelledError as e:
            logger.warning(f"Pull operation cancelled by administrator: {e}")

            # Perform local rollback (server has already rolled back)
            # Restore from backup
            if self.backup_path and self.backup_path.exists():
                try:
                    logger.info("Restoring from backup after admin cancellation")
                    self._restore_from_backup(self.backup_path, propresenter_folder)
                    logger.info("Successfully restored from backup")
                except Exception as restore_error:
                    logger.error(f"Failed to restore from backup: {restore_error}")

            if progress_callback:
                progress_callback("Operation cancelled by administrator", 0, 100)

            self.transaction_id = None
            return False

        except Exception as e:
            logger.error(f"Pull operation failed: {e}")

            # Rollback on failure
            if self.transaction_id:
                try:
                    logger.info("Rolling back transaction on server")
                    self.api.rollback_transaction(self.transaction_id)
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback transaction: {rollback_error}")

            # Restore from backup
            if self.backup_path and self.backup_path.exists():
                try:
                    logger.info("Restoring from backup")
                    self._restore_from_backup(self.backup_path, propresenter_folder)
                    logger.info("Successfully restored from backup")
                except Exception as restore_error:
                    logger.error(f"Failed to restore from backup: {restore_error}")

            if progress_callback:
                progress_callback(f"Pull failed: {str(e)}", 0, 100)

            self.transaction_id = None
            return False

    def push(self, service_type: str, progress_callback: Optional[Callable] = None) -> bool:
        """
        Push files to server (upload newer/different files).

        Process:
        1. Begin transaction with server
        2. Compare local files to server inventory
        3. Upload newer/different files to server staging area
        4. Commit transaction (server moves staged files to storage)
        5. Rollback on failure (server deletes staging area)

        Args:
            service_type: "Contemporary" or "Traditional"
            progress_callback: Optional callback for progress updates

        Returns:
            True if push succeeded, False otherwise
        """
        self.cancel_requested = False
        logger.info(f"Starting Push operation for {service_type} service")

        if progress_callback:
            progress_callback("Initializing Push operation...", 0, 100)

        try:
            # Step 1: Begin transaction with server
            logger.info("Beginning transaction with server")
            if progress_callback:
                progress_callback("Acquiring server lock...", 5, 100)

            tx_response = self.api.begin_transaction("Push", service_type)
            self.transaction_id = tx_response.get("transaction_id")

            if not tx_response.get("lock_acquired"):
                logger.error("Failed to acquire server lock")
                if progress_callback:
                    progress_callback("Failed to acquire lock", 0, 100)
                return False

            logger.info(f"Transaction started: {self.transaction_id}")

            # Step 2: Get list of files from server
            if progress_callback:
                progress_callback("Fetching file list from server...", 10, 100)

            server_files = self.api.list_files(service_type)
            logger.info(f"Server has {len(server_files)} files")

            # Build server file inventory (path -> metadata)
            server_file_map = {}
            for file_meta in server_files:
                if not file_meta.get("is_deleted", False):
                    server_file_map[file_meta["path"]] = file_meta

            # Step 3: Get list of local files from ProPresenter folder
            propresenter_folder = self.folder_mgr.propresenter_folder

            if progress_callback:
                progress_callback("Scanning local files...", 15, 100)

            # Get all local files recursively
            local_files = []
            for file_path in propresenter_folder.rglob("*"):
                if file_path.is_file():
                    # Calculate relative path from ProPresenter folder
                    rel_path = file_path.relative_to(propresenter_folder)
                    # Convert to forward slashes for consistency with server
                    rel_path_str = str(rel_path).replace("\\", "/")
                    local_files.append((rel_path_str, file_path))

            logger.info(f"Found {len(local_files)} local files")

            # Step 4: Determine which files need to be uploaded or deleted
            files_to_upload = []
            files_to_delete = []

            # Check local files against server
            for rel_path_str, file_path in local_files:
                if rel_path_str in server_file_map:
                    # File exists on both sides - compare
                    server_meta = server_file_map[rel_path_str]
                    local_hash = self._calculate_file_hash(file_path)
                    server_hash = server_meta.get("hash")

                    if local_hash != server_hash:
                        # Hashes differ - upload local version
                        files_to_upload.append((rel_path_str, file_path))
                else:
                    # File exists locally but not on server - upload it
                    files_to_upload.append((rel_path_str, file_path))

            # Check for files on server but not locally (deletions)
            local_path_set = {rel_path for rel_path, _ in local_files}
            for server_path in server_file_map.keys():
                if server_path not in local_path_set:
                    # File on server but not locally - mark for deletion
                    files_to_delete.append(server_path)

            total_operations = len(files_to_upload) + len(files_to_delete)
            logger.info(f"Need to upload {len(files_to_upload)} files, delete {len(files_to_delete)} files")

            if total_operations == 0:
                # Nothing to sync
                logger.info("No files need to be pushed - already in sync")
                if progress_callback:
                    progress_callback("Already synchronized", 100, 100)
                self.api.commit_transaction(self.transaction_id)
                self.transaction_id = None
                return True

            # Step 5: Upload files to server staging area
            current_file = 0
            for rel_path_str, file_path in files_to_upload:
                if self.cancel_requested:
                    logger.warning("Push operation cancelled by user")
                    raise Exception("Operation cancelled by user")

                current_file += 1
                progress_pct = 15 + int((current_file / total_operations) * 75)

                if progress_callback:
                    progress_callback(f"Uploading {rel_path_str}...", progress_pct, 100)

                logger.info(f"Uploading file {current_file}/{len(files_to_upload)}: {rel_path_str}")

                # Read file data
                with open(file_path, 'rb') as f:
                    file_data = f.read()

                # Calculate hash for verification
                file_hash = self._calculate_hash_from_bytes(file_data)
                logger.debug(f"File hash for {rel_path_str}: {file_hash}")

                # Upload file to server
                upload_result = self.api.upload_file_in_transaction(
                    self.transaction_id,
                    rel_path_str,
                    file_data
                )

                # Verify server received correct hash
                server_hash = upload_result.get("file_hash")
                if server_hash != file_hash:
                    logger.error(f"Hash mismatch for {rel_path_str}: expected {file_hash}, server got {server_hash}")
                    raise Exception(f"Hash verification failed for {rel_path_str}")

                logger.info(f"Successfully uploaded {rel_path_str}")

            # Step 6: Push deletions to server
            # Note: This requires a new API endpoint to mark files as deleted in a transaction
            # For now, we'll log this as a TODO
            if files_to_delete:
                logger.info(f"Skipping deletion of {len(files_to_delete)} files - deletion API not yet implemented")
                # TODO: Implement deletion push when server endpoint is available

            # Step 7: Commit transaction
            if progress_callback:
                progress_callback("Committing changes...", 95, 100)

            logger.info("Committing transaction")
            commit_result = self.api.commit_transaction(self.transaction_id)
            logger.info(f"Transaction committed successfully: {commit_result}")

            if progress_callback:
                progress_callback(f"Push completed: {len(files_to_upload)} files synchronized", 100, 100)

            logger.info("Push operation completed successfully")
            self.transaction_id = None
            return True

        except AlderSyncAdminCancelledError as e:
            logger.warning(f"Push operation cancelled by administrator: {e}")

            # Server has already rolled back (staging area deleted)
            # No local rollback needed for push (no local files modified)

            if progress_callback:
                progress_callback("Operation cancelled by administrator", 0, 100)

            self.transaction_id = None
            return False

        except Exception as e:
            logger.error(f"Push operation failed: {e}")

            # Rollback on failure
            if self.transaction_id:
                try:
                    logger.info("Rolling back transaction on server")
                    self.api.rollback_transaction(self.transaction_id)
                    logger.info("Server rollback completed (staging area deleted)")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback transaction: {rollback_error}")

            if progress_callback:
                progress_callback(f"Push failed: {str(e)}", 0, 100)

            self.transaction_id = None
            return False

    def reconcile(self, service_type: str, progress_callback: Optional[Callable] = None) -> bool:
        """
        Reconcile files bidirectionally (pull AND push in single transaction).

        When files are modified on both client and server, the newest version always wins.

        Process:
        1. Begin Reconcile transaction
        2. Server determines files_to_pull and files_to_push (newest wins)
        3. Create local backup
        4. Download files from files_to_pull list
        5. Upload files from files_to_push list
        6. Commit on success (both operations), rollback on failure

        Args:
            service_type: "Contemporary" or "Traditional"
            progress_callback: Optional callback for progress updates

        Returns:
            True if reconcile succeeded, False otherwise
        """
        self.cancel_requested = False
        logger.info(f"Starting Reconcile operation for {service_type} service")

        if progress_callback:
            progress_callback("Initializing Reconcile operation...", 0, 100)

        try:
            # Get ProPresenter folder path
            propresenter_folder = self.folder_mgr.propresenter_folder

            # Step 1: Scan local files and prepare metadata for server
            if progress_callback:
                progress_callback("Scanning local files...", 3, 100)

            logger.info("Scanning local files for Reconcile operation")
            local_files = {}
            for file_path in propresenter_folder.rglob("*"):
                if file_path.is_file():
                    # Calculate relative path from ProPresenter folder
                    rel_path = file_path.relative_to(propresenter_folder)
                    # Convert to forward slashes for consistency with server
                    rel_path_str = str(rel_path).replace("\\", "/")

                    # Get file metadata
                    file_stat = file_path.stat()
                    file_size = file_stat.st_size
                    file_hash = self._calculate_file_hash(file_path)
                    file_mtime = file_stat.st_mtime

                    # Convert timestamp to ISO format string
                    from datetime import datetime
                    mtime_iso = datetime.fromtimestamp(file_mtime).isoformat()

                    # Store as dict with path as key
                    local_files[rel_path_str] = {
                        "size": file_size,
                        "hash": file_hash,
                        "modified_utc": mtime_iso
                    }

            logger.info(f"Found {len(local_files)} local files")

            # Step 2: Begin Reconcile transaction with server, sending client files
            logger.info("Beginning Reconcile transaction with server")
            if progress_callback:
                progress_callback("Acquiring server lock...", 5, 100)

            tx_response = self.api.begin_transaction("Reconcile", service_type, client_files=local_files)
            self.transaction_id = tx_response.get("transaction_id")

            if not tx_response.get("lock_acquired"):
                logger.error("Failed to acquire server lock")
                if progress_callback:
                    progress_callback("Failed to acquire lock", 0, 100)
                return False

            logger.info(f"Transaction started: {self.transaction_id}")

            # Step 3: Get files_to_pull and files_to_push lists from server
            files_to_pull_paths = tx_response.get("files_to_pull", [])
            files_to_push_paths = tx_response.get("files_to_push", [])

            pull_count = len(files_to_pull_paths)
            push_count = len(files_to_push_paths)
            total_operations = pull_count + push_count

            logger.info(f"Reconcile: {pull_count} files to pull, {push_count} files to push")

            if total_operations == 0:
                # Nothing to sync
                logger.info("No files need reconciling - already in sync")
                if progress_callback:
                    progress_callback("Already synchronized", 100, 100)
                self.api.commit_transaction(self.transaction_id)
                self.transaction_id = None
                return True

            # Step 3: Get full file metadata from server for verification
            server_files = self.api.list_files(service_type)
            server_file_map = {f["path"]: f for f in server_files}

            # Step 4: Check disk space before proceeding
            if progress_callback:
                progress_callback("Checking disk space...", 8, 100)

            # Determine files that need backup
            files_to_backup = []

            # Add files that will be overwritten by pull
            for file_path in files_to_pull_paths:
                local_file = propresenter_folder / file_path
                if local_file.exists():
                    files_to_backup.append(file_path)

            # Add files that exist locally and will be pushed (backup in case upload fails)
            for file_path_str in files_to_push_paths:
                local_file = propresenter_folder / file_path_str
                if local_file.exists():
                    files_to_backup.append(file_path_str)

            # Build list of files to download with metadata for space check
            files_to_download_metadata = []
            for file_path in files_to_pull_paths:
                if file_path in server_file_map:
                    files_to_download_metadata.append(server_file_map[file_path])
                else:
                    # File not in server map, skip (shouldn't happen but be safe)
                    logger.warning(f"File {file_path} in pull list but not in server file map")

            # Check if we have enough disk space
            has_space, space_message = self._check_disk_space(
                files_to_download_metadata,
                files_to_backup,
                propresenter_folder
            )

            if not has_space:
                logger.error(f"Aborting reconcile due to insufficient disk space")
                if progress_callback:
                    progress_callback(f"Insufficient disk space", 0, 100)
                # Rollback transaction
                self.api.rollback_transaction(self.transaction_id)
                self.transaction_id = None
                raise Exception(space_message)

            # Step 4: Create backup of files that will be modified
            if progress_callback:
                progress_callback("Creating backup...", 10, 100)

            if files_to_backup:
                self.backup_path = self._create_backup(files_to_backup, propresenter_folder)
                logger.info(f"Created backup at {self.backup_path}")

            # Step 5: Download files from files_to_pull
            current_operation = 0
            for file_path in files_to_pull_paths:
                if self.cancel_requested:
                    logger.warning("Reconcile operation cancelled by user")
                    raise Exception("Operation cancelled by user")

                current_operation += 1
                progress_pct = 10 + int((current_operation / total_operations) * 75)

                if progress_callback:
                    progress_callback(f"Downloading {file_path}...", progress_pct, 100)

                logger.info(f"Downloading file {current_operation}/{total_operations}: {file_path}")

                # Download file from server
                file_data = self.api.download_file_in_transaction(self.transaction_id, file_path)

                # Verify hash if we have the file metadata
                if file_path in server_file_map:
                    downloaded_hash = self._calculate_hash_from_bytes(file_data)
                    expected_hash = server_file_map[file_path].get("hash")

                    if downloaded_hash != expected_hash:
                        logger.error(f"Hash mismatch for {file_path}: expected {expected_hash}, got {downloaded_hash}")
                        raise Exception(f"Hash verification failed for {file_path}")

                # Write file to disk
                local_file = propresenter_folder / file_path

                # Create parent directories if needed
                local_file.parent.mkdir(parents=True, exist_ok=True)

                # Write file
                with open(local_file, 'wb') as f:
                    f.write(file_data)

                # Set file modified time to match server's recorded time
                if file_path in server_file_map:
                    modified_utc = server_file_map[file_path].get("modified_utc")
                    if modified_utc:
                        try:
                            # Parse ISO format datetime string
                            from datetime import datetime
                            if modified_utc.endswith('Z'):
                                modified_utc = modified_utc[:-1] + '+00:00'
                            dt = datetime.fromisoformat(modified_utc)
                            # Convert to timestamp
                            timestamp = dt.timestamp()
                            # Set both access time and modification time
                            os.utime(local_file, (timestamp, timestamp))
                        except Exception as e:
                            # Log but don't fail if timestamp setting fails
                            logger.warning(f"Failed to set file timestamp for {file_path}: {e}")

                logger.info(f"Successfully downloaded {file_path}")

            # Step 6: Upload files from files_to_push
            for file_path_str in files_to_push_paths:
                if self.cancel_requested:
                    logger.warning("Reconcile operation cancelled by user")
                    raise Exception("Operation cancelled by user")

                current_operation += 1
                progress_pct = 10 + int((current_operation / total_operations) * 75)

                if progress_callback:
                    progress_callback(f"Uploading {file_path_str}...", progress_pct, 100)

                logger.info(f"Uploading file {current_operation}/{total_operations}: {file_path_str}")

                # Get local file path
                file_path = propresenter_folder / file_path_str

                if not file_path.exists():
                    logger.error(f"Local file not found: {file_path_str}")
                    raise Exception(f"Local file not found: {file_path_str}")

                # Read file data
                with open(file_path, 'rb') as f:
                    file_data = f.read()

                # Calculate hash for verification
                file_hash = self._calculate_hash_from_bytes(file_data)
                logger.debug(f"File hash for {file_path_str}: {file_hash}")

                # Upload file to server
                upload_result = self.api.upload_file_in_transaction(
                    self.transaction_id,
                    file_path_str,
                    file_data
                )

                # Verify server received correct hash
                server_hash = upload_result.get("file_hash")
                if server_hash != file_hash:
                    logger.error(f"Hash mismatch for {file_path_str}: expected {file_hash}, server got {server_hash}")
                    raise Exception(f"Hash verification failed for {file_path_str}")

                logger.info(f"Successfully uploaded {file_path_str}")

            # Step 7: Commit transaction
            if progress_callback:
                progress_callback("Committing changes...", 95, 100)

            logger.info("Committing transaction")
            commit_result = self.api.commit_transaction(self.transaction_id)
            logger.info(f"Transaction committed successfully: {commit_result}")

            # Step 8: Delete backup on success
            if self.backup_path and self.backup_path.exists():
                logger.info(f"Deleting backup at {self.backup_path}")
                shutil.rmtree(self.backup_path)
                self.backup_path = None

            if progress_callback:
                progress_callback(f"Reconcile completed: {pull_count} pulled, {push_count} pushed", 100, 100)

            logger.info(f"Reconcile operation completed successfully: {pull_count} pulled, {push_count} pushed")
            self.transaction_id = None
            return True

        except AlderSyncAdminCancelledError as e:
            logger.warning(f"Reconcile operation cancelled by administrator: {e}")

            # Perform local rollback (server has already rolled back)
            # Restore from backup
            if self.backup_path and self.backup_path.exists():
                try:
                    logger.info("Restoring from backup after admin cancellation")
                    self._restore_from_backup(self.backup_path, propresenter_folder)
                    logger.info("Successfully restored from backup")
                except Exception as restore_error:
                    logger.error(f"Failed to restore from backup: {restore_error}")

            if progress_callback:
                progress_callback("Operation cancelled by administrator", 0, 100)

            self.transaction_id = None
            return False

        except Exception as e:
            logger.error(f"Reconcile operation failed: {e}")

            # Rollback on failure
            if self.transaction_id:
                try:
                    logger.info("Rolling back transaction on server")
                    self.api.rollback_transaction(self.transaction_id)
                    logger.info("Server rollback completed")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback transaction: {rollback_error}")

            # Restore from backup
            if self.backup_path and self.backup_path.exists():
                try:
                    logger.info("Restoring from backup")
                    self._restore_from_backup(self.backup_path, propresenter_folder)
                    logger.info("Successfully restored from backup")
                except Exception as restore_error:
                    logger.error(f"Failed to restore from backup: {restore_error}")

            if progress_callback:
                progress_callback(f"Reconcile failed: {str(e)}", 0, 100)

            self.transaction_id = None
            return False

    def cancel_operation(self):
        """
        Cancel current operation and rollback.

        Triggers:
        - User clicks Cancel button
        - Ctrl+C in CLI mode
        - Admin cancels from web interface
        """
        logger.info("Cancel requested for current operation")
        self.cancel_requested = True

    def _create_backup(self, files_to_backup: List[str], base_folder: Path) -> Path:
        """
        Create backup of files before modifying.

        Args:
            files_to_backup: List of relative file paths to backup
            base_folder: Base folder path (e.g., ProPresenter folder)

        Returns:
            Path to backup directory
        """
        # Create backup directory with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = base_folder.parent / f"aldersync_backup_{timestamp}"
        backup_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Creating backup in {backup_dir}")

        # Copy files to backup
        for file_path in files_to_backup:
            source_file = base_folder / file_path
            if not source_file.exists():
                continue

            dest_file = backup_dir / file_path

            # Create parent directories
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(source_file, dest_file)
            logger.debug(f"Backed up: {file_path}")

        logger.info(f"Backup created with {len(files_to_backup)} files")
        return backup_dir

    def _restore_from_backup(self, backup_path: Path, base_folder: Path):
        """
        Restore files from backup directory.

        Args:
            backup_path: Path to backup directory
            base_folder: Base folder to restore to (e.g., ProPresenter folder)
        """
        logger.info(f"Restoring files from backup: {backup_path}")

        if not backup_path.exists():
            logger.warning(f"Backup directory does not exist: {backup_path}")
            return

        # Restore all files from backup
        for backup_file in backup_path.rglob("*"):
            if backup_file.is_file():
                # Calculate relative path from backup dir
                rel_path = backup_file.relative_to(backup_path)
                dest_file = base_folder / rel_path

                # Create parent directories
                dest_file.parent.mkdir(parents=True, exist_ok=True)

                # Restore file
                shutil.copy2(backup_file, dest_file)
                logger.debug(f"Restored: {rel_path}")

        # Clean up backup after successful restore
        shutil.rmtree(backup_path)
        logger.info("Backup restored and cleaned up")

    def _calculate_file_hash(self, file_path: Path) -> str:
        """
        Calculate SHA-256 hash of a file.

        Args:
            file_path: Path to file

        Returns:
            Hex string of SHA-256 hash
        """
        sha256_hash = hashlib.sha256()

        with open(file_path, "rb") as f:
            # Read file in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        return sha256_hash.hexdigest()

    def _calculate_hash_from_bytes(self, data: bytes) -> str:
        """
        Calculate SHA-256 hash from bytes.

        Args:
            data: Binary data

        Returns:
            Hex string of SHA-256 hash
        """
        return hashlib.sha256(data).hexdigest()

    def _check_disk_space(self, files_to_download: List[Dict[str, Any]],
                          files_to_backup: List[str],
                          base_folder: Path,
                          buffer_percent: float = 0.10) -> tuple[bool, str]:
        """
        Check if there is enough disk space for the operation.

        The operation requires space for:
        1. Backup copies of files being modified/deleted
        2. Downloaded files (which may be larger than current versions)
        3. A buffer (default 10%) to avoid completely filling the drive

        Args:
            files_to_download: List of file metadata dicts with 'path' and 'size'
            files_to_backup: List of relative paths to files that need backup
            base_folder: Base folder path (e.g., ProPresenter folder)
            buffer_percent: Additional buffer percentage (default 0.10 = 10%)

        Returns:
            Tuple of (has_enough_space: bool, message: str)
        """
        try:
            # Get disk usage for the drive containing the ProPresenter folder
            disk_usage = shutil.disk_usage(base_folder)
            available_bytes = disk_usage.free

            # Calculate space needed for backups
            backup_bytes_needed = 0
            for file_path in files_to_backup:
                file_full_path = base_folder / file_path
                if file_full_path.exists():
                    backup_bytes_needed += file_full_path.stat().st_size

            # Calculate space needed for downloads
            download_bytes_needed = 0
            for file_meta in files_to_download:
                file_size = file_meta.get("size", 0)
                download_bytes_needed += file_size

            # Total space needed (backup + downloads)
            total_bytes_needed = backup_bytes_needed + download_bytes_needed

            # Add buffer (default 10%)
            total_with_buffer = total_bytes_needed * (1 + buffer_percent)

            # Log the calculation
            logger.info(f"Disk space check:")
            logger.info(f"  Available: {self._format_bytes(available_bytes)}")
            logger.info(f"  Backup space needed: {self._format_bytes(backup_bytes_needed)}")
            logger.info(f"  Download space needed: {self._format_bytes(download_bytes_needed)}")
            logger.info(f"  Total needed: {self._format_bytes(total_bytes_needed)}")
            logger.info(f"  Total with {buffer_percent*100:.0f}% buffer: {self._format_bytes(total_with_buffer)}")

            # Check if we have enough space
            if available_bytes < total_with_buffer:
                shortage = total_with_buffer - available_bytes
                message = (
                    f"Insufficient disk space. "
                    f"Need {self._format_bytes(total_with_buffer)} "
                    f"({self._format_bytes(backup_bytes_needed)} for backup + "
                    f"{self._format_bytes(download_bytes_needed)} for downloads + "
                    f"{buffer_percent*100:.0f}% buffer), "
                    f"but only {self._format_bytes(available_bytes)} available. "
                    f"Short by {self._format_bytes(shortage)}."
                )
                logger.error(message)
                return False, message

            # We have enough space
            message = f"Disk space check passed: {self._format_bytes(available_bytes)} available"
            logger.info(message)
            return True, message

        except Exception as e:
            # If disk space check fails, log warning but don't block operation
            logger.warning(f"Failed to check disk space: {e}")
            return True, f"Disk space check skipped: {e}"

    def _format_bytes(self, bytes_value: int) -> str:
        """
        Format byte count into human-readable string.

        Args:
            bytes_value: Number of bytes

        Returns:
            Formatted string (e.g., "1.5 GB", "250 MB")
        """
        if bytes_value < 1024:
            return f"{bytes_value} B"
        elif bytes_value < 1024 * 1024:
            return f"{bytes_value / 1024:.1f} KB"
        elif bytes_value < 1024 * 1024 * 1024:
            return f"{bytes_value / (1024 * 1024):.1f} MB"
        else:
            return f"{bytes_value / (1024 * 1024 * 1024):.2f} GB"
