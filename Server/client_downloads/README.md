# AlderSync Client Version Management

This README documents the client version management system implemented in AlderSync.

## Overview

AlderSync uses a web-based admin interface for managing client executables. Administrators can upload new client versions through the web interface, and clients automatically check for updates on startup.

## Architecture

### Storage Location
Client executables are stored in the `client_downloads/` folder (configurable via database settings). This folder is separate from the Docker image and is treated as persistent data.

### Version Management
- **Admin Interface**: `/admin/downloads` - Web interface for uploading and managing client versions (admin-only)
- **Version Check**: `/api/version/check` - Public endpoint for clients to check for updates
- **Download**: `/api/version/download` - Public endpoint for clients to download the current version

### File Naming Convention
Client executables are stored with version numbers:
- Windows: `aldersync-{version}.exe` (e.g., `aldersync-1.0.1.exe`)
- macOS: `aldersync-{version}.app` (e.g., `aldersync-1.0.2.app`)
- Linux: `aldersync-{version}` (e.g., `aldersync-1.0.3`)

## Uploading New Client Versions

### Via Web Interface (Recommended)

1. Log in as an administrator
2. Navigate to **Admin > Downloads**
3. Fill in the upload form:
   - **Version**: Enter version number in X.Y.Z format (e.g., "1.0.1")
   - **Platform**: Select Windows, macOS, or Linux
   - **File**: Choose the client executable file
4. Click **Upload Version**
5. The new version becomes active immediately

### Building Client Executables

To create client executables for upload:

1. Navigate to the `Client/` directory
2. Activate the virtual environment
3. Build the executable using PyInstaller:

**Windows**:
```bash
cd Client
Client\venv\Scripts\activate
Client\venv\Scripts\pyinstaller.exe --onefile --windowed --name aldersync aldersync_gui.py
```

**macOS/Linux**:
```bash
cd Client
source venv/bin/activate
pyinstaller --onefile --windowed --name aldersync aldersync_gui.py
```

4. The executable will be in `Client/dist/aldersync` (or `aldersync.exe` on Windows)
5. Upload through the admin web interface

## Version Management Features

### Admin Capabilities (Admin Session Required)
- Upload new client versions with version number and platform
- View all uploaded versions with metadata (size, upload date, platform)
- Set any version as the active version
- Delete old versions (cannot delete currently active version)

### Client Capabilities (No Authentication Required)
- Check for available updates via `/api/version/check`
- Download the current active version via `/api/version/download`
- Automatic update prompts on startup

## Security

### Admin Operations (Authentication Required)
- `/admin/downloads` - Admin web interface
- `/admin/api/downloads/upload` - Upload new version
- `/admin/api/downloads/set_active` - Change active version
- `/admin/api/downloads/delete/{version}` - Delete old version
- `/admin/api/downloads/list` - List all versions

### Public Operations (No Authentication)
- `/api/version/check` - Check if update is available
- `/api/version/download` - Download current active version
- `/api/version/info` - Get current version information

This design ensures that:
- Only administrators can upload and manage client versions
- All users (authenticated or not) can download the client and check for updates
- The auto-update mechanism works seamlessly without authentication barriers

## Database Settings

The system uses these database settings:
- `client_downloads_path` - Path to client downloads folder (default: `client_downloads/`)
- `latest_client_version` - Current active version (e.g., "1.0.1")
- `client_executable_path` - Full path to current active executable
- `client_version_{version}_uploaded` - Timestamp for each uploaded version

## Auto-Update Workflow

1. Client starts up and checks `/api/version/check?client_version={current}`
2. Server compares with `latest_client_version` setting
3. If update available, client shows prompt to user
4. If user accepts, client downloads from `/api/version/download`
5. Client replaces executable and restarts automatically

## Notes

- The `client_downloads/` folder is created automatically on server startup
- Version validation enforces X.Y.Z format (semantic versioning)
- Platform validation ensures correct file extensions (.exe for Windows, etc.)
- Active version cannot be deleted (safety feature)
- All version operations are logged for audit trail
