"""
AlderSync Server - File Storage Management

This module handles file storage operations including:
- Storage directory structure creation and management
- File path resolution
- SHA-256 hash calculation (streaming for large files)
- File metadata management
- Revision numbering system

Per Specification.md sections 5.3 and 8.2
"""

import hashlib
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, List
from sqlalchemy import func

from models.database import File
from managers.database_manager import DatabaseManager
from ignore_patterns import PatternMatcher, LoadPatternsFromDatabase

logger = logging.getLogger(__name__)


# ==================== Storage Configuration ====================

DEFAULT_STORAGE_ROOT = "storage"
SERVICE_TYPES = ["Contemporary", "Traditional"]


# ==================== Storage Directory Management ====================

def InitializeStorage(storage_root: str = DEFAULT_STORAGE_ROOT) -> None:
    """
    Initialize the file storage directory structure
    Creates root storage directory and service type subdirectories

    Per Specification.md section 5.3:
    /root_storage/
      Contemporary/
      Traditional/

    Args:
        storage_root: Root directory for file storage
    """
    storage_path = Path(storage_root)

    try:
        # Create root storage directory if it doesn't exist
        storage_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Storage root directory ready: {storage_path.absolute()}")

        # Create service type subdirectories
        for service_type in SERVICE_TYPES:
            service_path = storage_path / service_type
            service_path.mkdir(exist_ok=True)
            logger.info(f"Service storage directory ready: {service_path.absolute()}")

    except Exception as e:
        logger.error(f"Failed to initialize storage: {str(e)}")
        raise


def GetStoragePath(service_type: str, storage_root: str = DEFAULT_STORAGE_ROOT) -> Path:
    """
    Get the storage path for a specific service type

    Args:
        service_type: 'Contemporary' or 'Traditional'
        storage_root: Root directory for file storage

    Returns:
        Path: Absolute path to service type storage directory

    Raises:
        ValueError: If service_type is invalid
    """
    if service_type not in SERVICE_TYPES:
        raise ValueError(f"Invalid service_type: {service_type}. Must be one of {SERVICE_TYPES}")

    storage_path = Path(storage_root) / service_type
    return storage_path.absolute()


def GetFilePath(relative_path: str, service_type: str, storage_root: str = DEFAULT_STORAGE_ROOT) -> Path:
    """
    Resolve a relative file path to an absolute storage path

    Args:
        relative_path: Relative path within service storage (e.g., "folder/file.txt")
        service_type: 'Contemporary' or 'Traditional'
        storage_root: Root directory for file storage

    Returns:
        Path: Absolute path to file in storage
    """
    storage_path = GetStoragePath(service_type, storage_root)
    file_path = storage_path / relative_path
    return file_path.absolute()


def GetRevisionPath(relative_path: str, revision: int, service_type: str,
                   storage_root: str = DEFAULT_STORAGE_ROOT) -> Path:
    """
    Get the file path for a specific revision

    Revision numbering:
    - Revision 0 (initial version): filename.0.ext
    - Revision 1 (second version): filename.1.ext
    - Revision 2 (third version): filename.2.ext
    - Highest revision number is always the current version

    Args:
        relative_path: Relative path to file
        revision: Revision number (0, 1, 2, 3, ...)
        service_type: 'Contemporary' or 'Traditional'
        storage_root: Root directory for file storage

    Returns:
        Path: Absolute path to revision file
    """
    file_path = GetFilePath(relative_path, service_type, storage_root)

    # All revisions have revision number in filename: filename.N.ext
    stem = file_path.stem  # filename without extension
    suffix = file_path.suffix  # .ext
    parent = file_path.parent  # directory path
    revision_path = parent / f"{stem}.{revision}{suffix}"
    return revision_path


# ==================== File Hash Calculation ====================

def CalculateFileHash(file_path: Path, chunk_size: int = 8192) -> str:
    """
    Calculate SHA-256 hash of a file using streaming/chunked reading

    Per Specification.md section 8.2:
    - Algorithm: SHA-256
    - Method: Streaming/chunked hashing for large files to avoid memory issues

    Args:
        file_path: Path to file to hash
        chunk_size: Size of chunks to read (default 8KB)

    Returns:
        str: Hex-encoded SHA-256 hash

    Raises:
        FileNotFoundError: If file doesn't exist
        IOError: If file cannot be read
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    sha256_hash = hashlib.sha256()

    try:
        with open(file_path, 'rb') as f:
            # Read file in chunks to avoid loading entire file into memory
            while chunk := f.read(chunk_size):
                sha256_hash.update(chunk)

        hash_hex = sha256_hash.hexdigest()
        logger.debug(f"Calculated hash for {file_path.name}: {hash_hex}")
        return hash_hex

    except Exception as e:
        logger.error(f"Failed to calculate hash for {file_path}: {str(e)}")
        raise IOError(f"Failed to calculate hash: {str(e)}")


# ==================== Ignore Pattern Filtering ====================

def FilterIgnoredFiles(db_manager: DatabaseManager, file_list: List[dict]) -> List[dict]:
    """
    Filter out files that match ignore patterns

    Args:
        db_manager: DatabaseManager instance
        file_list: List of file metadata dictionaries

    Returns:
        List of files that should NOT be ignored
    """
    # Load patterns from database
    pattern_strings = LoadPatternsFromDatabase(db_manager)

    if not pattern_strings:
        # No patterns defined, return all files
        return file_list

    # Create pattern matcher
    matcher = PatternMatcher(pattern_strings)

    # Filter files
    filtered = []
    for file_dict in file_list:
        if not matcher.ShouldIgnore(file_dict['path']):
            filtered.append(file_dict)
        else:
            logger.debug(f"Ignoring file due to pattern match: {file_dict['path']}")

    return filtered


# ==================== File Metadata Management ====================

def StoreFileMetadata(db_manager: DatabaseManager, relative_path: str, service_type: str,
                     file_hash: str, size: int, modified_utc: datetime,
                     revision: int = 0, is_deleted: bool = False, user_id: int = None,
                     changelist_id: int = None) -> int:
    """
    Store or update file metadata in database

    Args:
        db_manager: DatabaseManager instance
        relative_path: Relative path to file within service storage
        service_type: 'Contemporary' or 'Traditional'
        file_hash: SHA-256 hash of file (None if deleted)
        size: File size in bytes (None if deleted)
        modified_utc: File modification timestamp (UTC)
        revision: Revision number (0 for current, 1+ for old revisions)
        is_deleted: Whether file is marked as deleted
        user_id: ID of user who created this revision (None if unknown)
        changelist_id: ID of changelist this file belongs to (None if not part of a changelist)

    Returns:
        int: file_id of created/updated record
    """
    session = db_manager.GetSession()

    try:
        # Check if file record already exists for this path, service, and revision
        existing = session.query(File).filter(
            File.path == relative_path,
            File.service_type == service_type,
            File.revision == revision
        ).first()

        if existing:
            # Update existing record
            existing.file_hash = file_hash
            existing.size = size
            existing.is_deleted = is_deleted
            existing.last_modified_utc = modified_utc
            existing.user_id = user_id
            existing.changelist_id = changelist_id
            logger.debug(f"Updated file metadata: {relative_path} (revision {revision})")
            file_id = existing.file_id
        else:
            # Create new record
            new_file = File(
                path=relative_path,
                service_type=service_type,
                file_hash=file_hash,
                size=size,
                is_deleted=is_deleted,
                last_modified_utc=modified_utc,
                revision=revision,
                user_id=user_id,
                changelist_id=changelist_id
            )
            session.add(new_file)
            logger.debug(f"Created file metadata: {relative_path} (revision {revision})")
            session.flush()  # Get the file_id
            file_id = new_file.file_id

        session.commit()
        return file_id

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to store file metadata for {relative_path}: {str(e)}")
        raise
    finally:
        session.close()


def GetFileMetadata(db_manager: DatabaseManager, relative_path: str, service_type: str,
                   revision: int = 0) -> Optional[dict]:
    """
    Retrieve file metadata from database

    Args:
        db_manager: DatabaseManager instance
        relative_path: Relative path to file
        service_type: 'Contemporary' or 'Traditional'
        revision: Revision number (0 for current)

    Returns:
        dict: File metadata or None if not found
              Contains: file_id, path, service_type, file_hash, size, is_deleted,
                       last_modified_utc, revision, user_id
    """
    session = db_manager.GetSession()

    try:
        file_record = session.query(File).filter(
            File.path == relative_path,
            File.service_type == service_type,
            File.revision == revision
        ).first()

        if not file_record:
            return None

        # Convert to dictionary to avoid detached instance issues
        metadata = {
            'file_id': file_record.file_id,
            'path': file_record.path,
            'service_type': file_record.service_type,
            'file_hash': file_record.file_hash,
            'size': file_record.size,
            'is_deleted': file_record.is_deleted,
            'last_modified_utc': file_record.last_modified_utc,
            'revision': file_record.revision,
            'user_id': file_record.user_id
        }

        return metadata

    finally:
        session.close()


def ListFiles(db_manager: DatabaseManager, service_type: str,
             include_deleted: bool = False, apply_ignore_patterns: bool = True) -> List[dict]:
    """
    List all files for a service type (current versions only, not revisions)

    Returns the HIGHEST revision for each file, which is the current version.
    Revision 0 is the initial version; highest revision is current.

    Args:
        db_manager: DatabaseManager instance
        service_type: 'Contemporary' or 'Traditional'
        include_deleted: Whether to include deleted files
        apply_ignore_patterns: Whether to filter out ignored files (default True)

    Returns:
        List[dict]: List of file metadata dictionaries
    """
    from sqlalchemy import func
    session = db_manager.GetSession()

    try:
        # First, find the maximum revision for each file path
        subquery = session.query(
            File.path,
            func.max(File.revision).label('max_revision')
        ).filter(
            File.service_type == service_type
        ).group_by(File.path).subquery()

        # Then join back to get the full file records for those max revisions
        query = session.query(File).join(
            subquery,
            (File.path == subquery.c.path) &
            (File.revision == subquery.c.max_revision) &
            (File.service_type == service_type)
        )

        if not include_deleted:
            query = query.filter(File.is_deleted == False)

        files = query.all()

        # Convert to list of dictionaries
        file_list = []
        for file_record in files:
            file_list.append({
                'file_id': file_record.file_id,
                'path': file_record.path,
                'service_type': file_record.service_type,
                'file_hash': file_record.file_hash,
                'size': file_record.size,
                'is_deleted': file_record.is_deleted,
                'last_modified_utc': file_record.last_modified_utc,
                'revision': file_record.revision,
                'user_id': file_record.user_id
            })

        # Apply ignore patterns if requested
        if apply_ignore_patterns:
            file_list = FilterIgnoredFiles(db_manager, file_list)

        return file_list

    finally:
        session.close()


# ==================== Revision Management ====================

def GetRevisionCount(db_manager: DatabaseManager, relative_path: str,
                    service_type: str) -> int:
    """
    Count number of revisions for a file (excluding current version)

    Args:
        db_manager: DatabaseManager instance
        relative_path: Relative path to file
        service_type: 'Contemporary' or 'Traditional'

    Returns:
        int: Number of old revisions (revision > 0)
    """
    session = db_manager.GetSession()

    try:
        count = session.query(File).filter(
            File.path == relative_path,
            File.service_type == service_type,
            File.revision > 0
        ).count()

        return count

    finally:
        session.close()


def GetAllRevisions(db_manager: DatabaseManager, relative_path: str,
                   service_type: str) -> List[dict]:
    """
    Get all revisions of a file, including current version

    Args:
        db_manager: DatabaseManager instance
        relative_path: Relative path to file
        service_type: 'Contemporary' or 'Traditional'

    Returns:
        List[dict]: List of revision metadata, sorted by revision number (newest first)
    """
    session = db_manager.GetSession()

    try:
        revisions = session.query(File).filter(
            File.path == relative_path,
            File.service_type == service_type
        ).order_by(File.revision.desc()).all()

        revision_list = []
        for rev in revisions:
            revision_list.append({
                'file_id': rev.file_id,
                'path': rev.path,
                'service_type': rev.service_type,
                'file_hash': rev.file_hash,
                'size': rev.size,
                'is_deleted': rev.is_deleted,
                'last_modified_utc': rev.last_modified_utc,
                'revision': rev.revision,
                'user_id': rev.user_id
            })

        return revision_list

    finally:
        session.close()


def GetNextRevisionNumber(db_manager: DatabaseManager, relative_path: str, service_type: str) -> int:
    """
    Get the next revision number for a file.

    Revision numbering:
    - First upload: revision 0
    - Second upload: revision 1
    - Third upload: revision 2
    - Highest revision number is always the current version

    Args:
        db_manager: DatabaseManager instance
        relative_path: Relative path to file
        service_type: 'Contemporary' or 'Traditional'

    Returns:
        int: Next revision number (0 if this is the first upload, otherwise MAX(revision) + 1)
    """
    session = db_manager.GetSession()
    try:
        # Get maximum revision number for this file
        max_revision = session.query(func.max(File.revision)).filter(
            File.path == relative_path,
            File.service_type == service_type
        ).scalar()

        if max_revision is None:
            # First upload - start at revision 0
            return 0
        else:
            # Increment from highest existing revision
            return max_revision + 1
    finally:
        session.close()


def CreateRevision(db_manager: DatabaseManager, relative_path: str, service_type: str,
                  storage_root: str = DEFAULT_STORAGE_ROOT) -> int:
    """
    DEPRECATED: This function uses the old revision system where revision 0 is always current.
    Use GetNextRevisionNumber() instead for the new system where highest revision is current.

    This function is kept for backwards compatibility with deletion logic only.
    """
    # For deletion, we still need to archive the current file
    # Get the current highest revision
    session = db_manager.GetSession()
    try:
        max_revision_record = session.query(File).filter(
            File.path == relative_path,
            File.service_type == service_type
        ).order_by(File.revision.desc()).first()

        if not max_revision_record:
            raise FileNotFoundError(f"No file found in database: {relative_path}")

        current_revision = max_revision_record.revision
        current_metadata = {
            'file_hash': max_revision_record.file_hash,
            'size': max_revision_record.size,
            'last_modified_utc': max_revision_record.last_modified_utc,
            'is_deleted': max_revision_record.is_deleted,
            'user_id': max_revision_record.user_id
        }
    finally:
        session.close()

    # Get next revision number
    new_revision_number = GetNextRevisionNumber(db_manager, relative_path, service_type)

    # Get file paths
    current_file_path = GetRevisionPath(relative_path, current_revision, service_type, storage_root)
    new_revision_file_path = GetRevisionPath(relative_path, new_revision_number, service_type, storage_root)

    try:
        # Copy (not move) physical file if it exists
        if current_file_path.exists():
            # Ensure parent directory exists
            new_revision_file_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file to preserve current version
            shutil.copy2(str(current_file_path), str(new_revision_file_path))
            logger.info(f"Archived revision {current_revision} as revision {new_revision_number}: {relative_path}")

        # Create database record for new revision
        StoreFileMetadata(
            db_manager,
            relative_path,
            service_type,
            current_metadata['file_hash'],
            current_metadata['size'],
            current_metadata['last_modified_utc'],
            revision=new_revision_number,
            is_deleted=current_metadata['is_deleted'],
            user_id=current_metadata['user_id']
        )

        # Check if we need to clean up old revisions
        CleanupOldRevisions(db_manager, relative_path, service_type, storage_root)

        return new_revision_number

    except Exception as e:
        logger.error(f"Failed to create revision for {relative_path}: {str(e)}")
        raise


def CleanupOldRevisions(db_manager: DatabaseManager, relative_path: str, service_type: str,
                       storage_root: str = DEFAULT_STORAGE_ROOT) -> None:
    """
    Delete old revisions exceeding max_revisions setting

    Args:
        db_manager: DatabaseManager instance
        relative_path: Relative path to file
        service_type: 'Contemporary' or 'Traditional'
        storage_root: Root directory for file storage
    """
    # Get max_revisions setting
    session = db_manager.GetSession()

    try:
        from models.database import Setting
        max_revisions_setting = session.query(Setting).filter(Setting.key == "max_revisions").first()
        max_revisions = int(max_revisions_setting.value) if max_revisions_setting else 10
    finally:
        session.close()

    # Get all revisions (excluding current version)
    all_revisions = GetAllRevisions(db_manager, relative_path, service_type)
    old_revisions = [r for r in all_revisions if r['revision'] > 0]

    # If we have more revisions than max_revisions, delete oldest
    if len(old_revisions) > max_revisions:
        revisions_to_delete = old_revisions[max_revisions:]  # Oldest revisions

        for rev in revisions_to_delete:
            revision_number = rev['revision']

            # Delete physical file
            revision_file_path = GetRevisionPath(relative_path, revision_number, service_type, storage_root)
            if revision_file_path.exists():
                revision_file_path.unlink()
                logger.info(f"Deleted old revision file: {revision_file_path}")

            # Delete database record
            session = db_manager.GetSession()
            try:
                file_record = session.query(File).filter(File.file_id == rev['file_id']).first()
                if file_record:
                    session.delete(file_record)
                    session.commit()
                    logger.info(f"Deleted old revision record: {relative_path} (revision {revision_number})")
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to delete revision record: {str(e)}")
            finally:
                session.close()


def CompareFilesForReconcile(db_manager: DatabaseManager, client_files: dict, service_type: str) -> tuple[list[str], list[str]]:
    """
    Compare client file inventory against server files to determine sync needs
    Per Specification.md sections 8.1 and 9.6

    File comparison algorithm:
    1. Compare modification times (UTC)
    2. If same, compare file sizes
    3. If same, compare SHA-256 hashes

    Optimized for large file sets with efficient comparison logic.

    Args:
        db_manager: DatabaseManager instance
        client_files: Dictionary mapping file paths to metadata dicts
                     Each dict should have: 'modified_utc', 'size', 'hash'
        service_type: 'Contemporary' or 'Traditional'

    Returns:
        tuple: (files_to_pull, files_to_push)
               files_to_pull: List of file paths client should download from server
               files_to_push: List of file paths client should upload to server
    """
    files_to_pull = []
    files_to_push = []

    # Get all server files (excluding deleted) - optimized with indexes
    server_files_list = ListFiles(db_manager, service_type, include_deleted=False)
    server_files = {f['path']: f for f in server_files_list}

    # Pre-normalize all client timestamps to avoid repeated conversions in loop
    normalized_client_files = {}
    for client_path, client_meta in client_files.items():
        client_mtime = client_meta.get('modified_utc')

        # Ensure timezone-aware datetime
        if isinstance(client_mtime, str):
            client_mtime = datetime.fromisoformat(client_mtime.replace('Z', '+00:00'))
        if client_mtime and client_mtime.tzinfo is None:
            client_mtime = client_mtime.replace(tzinfo=timezone.utc)

        normalized_client_files[client_path] = {
            'modified_utc': client_mtime,
            'size': client_meta.get('size'),
            'hash': client_meta.get('hash')
        }

    # Track which files we've seen
    seen_files = set()

    # Compare files that exist on both client and server
    for client_path, client_meta in normalized_client_files.items():
        seen_files.add(client_path)

        if client_path in server_files:
            server_meta = server_files[client_path]
            server_mtime = server_meta['last_modified_utc']

            # Ensure server timestamp is timezone-aware
            if server_mtime and server_mtime.tzinfo is None:
                server_mtime = server_mtime.replace(tzinfo=timezone.utc)

            client_mtime = client_meta['modified_utc']

            # Step 1: Compare modification times (with 1 second tolerance for filesystem precision)
            time_diff = abs((server_mtime - client_mtime).total_seconds()) if (server_mtime and client_mtime) else float('inf')

            if time_diff > 1:
                # Times differ significantly - use most recent
                if server_mtime > client_mtime:
                    files_to_pull.append(client_path)
                else:
                    files_to_push.append(client_path)
                continue

            # Step 2: Compare file sizes (quick integer comparison)
            client_size = client_meta['size']
            server_size = server_meta['size']

            if client_size != server_size:
                # Sizes differ - use most recent based on mtime
                if server_mtime >= client_mtime:
                    files_to_pull.append(client_path)
                else:
                    files_to_push.append(client_path)
                continue

            # Step 3: Compare hashes (only if size and time are same)
            client_hash = client_meta['hash']
            server_hash = server_meta['file_hash']

            if client_hash != server_hash:
                # Hashes differ - use most recent based on mtime
                if server_mtime >= client_mtime:
                    files_to_pull.append(client_path)
                else:
                    files_to_push.append(client_path)
                continue

            # Files are identical, no sync needed
        else:
            # File exists on client but not on server - push it
            files_to_push.append(client_path)

    # Files that exist on server but not on client - pull them
    # Use set difference for efficient bulk operation
    server_only_files = set(server_files.keys()) - seen_files
    files_to_pull.extend(server_only_files)

    logger.info(f"Reconcile comparison: {len(files_to_pull)} files to pull, {len(files_to_push)} files to push")

    return files_to_pull, files_to_push


def DeleteFile(db_manager: DatabaseManager, relative_path: str, service_type: str,
              storage_root: str = DEFAULT_STORAGE_ROOT) -> bool:
    """
    Mark a file as deleted in database and move physical file to revision
    Per Specification.md section 8.3: File Deletion Synchronization

    When a file is deleted:
    - Set is_deleted=TRUE in database
    - Set size=NULL, hash=NULL
    - Move physical file to revision number (preserve for recovery)

    Args:
        db_manager: DatabaseManager instance
        relative_path: Relative path to file
        service_type: 'Contemporary' or 'Traditional'
        storage_root: Root directory for file storage

    Returns:
        bool: True if deletion succeeded, False if file doesn't exist

    Raises:
        Exception: If deletion fails
    """
    # Get current file metadata
    current_metadata = GetFileMetadata(db_manager, relative_path, service_type, revision=0)

    if not current_metadata:
        logger.warning(f"Attempted to delete non-existent file: {relative_path}")
        return False

    # If file is already marked as deleted, nothing to do
    if current_metadata['is_deleted']:
        logger.info(f"File already marked as deleted: {relative_path}")
        return True

    try:
        # Get physical file path
        current_file_path = GetFilePath(relative_path, service_type, storage_root)

        # If physical file exists, create a revision (move it to preserve for recovery)
        if current_file_path.exists():
            # Create revision will move the file and create database record
            revision_number = CreateRevision(db_manager, relative_path, service_type, storage_root)
            logger.info(f"Moved deleted file to revision {revision_number}: {relative_path}")

        # Update current file record to mark as deleted
        # Set is_deleted=TRUE, size=NULL, hash=NULL
        StoreFileMetadata(
            db_manager,
            relative_path,
            service_type,
            file_hash=None,
            size=None,
            modified_utc=datetime.now(timezone.utc),
            revision=0,
            is_deleted=True,
            user_id=current_metadata['user_id']
        )

        logger.info(f"Marked file as deleted: {relative_path} ({service_type})")
        return True

    except Exception as e:
        logger.error(f"Failed to delete file {relative_path}: {str(e)}")
        raise
