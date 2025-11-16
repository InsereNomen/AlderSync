# AlderSync Client - Installation and User Guide

Welcome to AlderSync! This guide will help you install and use the AlderSync client to synchronize ProPresenter files with your church's server.

## Table of Contents

1. [What is AlderSync?](#what-is-aldersync)
2. [System Requirements](#system-requirements)
3. [Installation](#installation)
4. [First-Time Setup](#first-time-setup)
5. [Using AlderSync](#using-aldersync)
6. [Command-Line Mode](#command-line-mode)
7. [Troubleshooting](#troubleshooting)
8. [Getting Help](#getting-help)

---

## What is AlderSync?

AlderSync is a file synchronization tool designed specifically for church volunteers who work with ProPresenter. It helps you:

- **Pull** the latest ProPresenter files from the server before working on them
- **Push** your changes back to the server after updating files
- **Reconcile** changes when both you and others have modified files
- **Swap** between Contemporary and Traditional service folders seamlessly

AlderSync ensures everyone is working with the most up-to-date files and prevents conflicts.

---

## System Requirements

- **Operating System**: Windows 10/11 or macOS 10.14+
- **ProPresenter**: ProPresenter 7 or later (optional - only needed if swapping service folders)
- **Disk Space**: At least 500MB free for AlderSync and ProPresenter files
- **Network**: Internet connection to access your church's AlderSync server

---

## Installation

### Windows

1. **Download** the AlderSync zip file from your church's server
2. **Extract** the zip file to a location of your choice
   - Example: `C:\Program Files\AlderSync\`
   - Or: Your Desktop, Documents folder, etc.
3. **Run** `aldersync.exe`
4. **Optional**: Create a desktop shortcut for easy access

### macOS

1. **Download** the AlderSync zip file from your church's server
2. **Extract** the zip file
3. **Move** `AlderSync.app` to your Applications folder (or keep it anywhere you like)
4. **First Run**: Right-click the app and select "Open" (required for unsigned apps)
   - You may see a security warning - click "Open" to proceed
5. **Future Runs**: Double-click to launch normally

**Note**: No installation wizard required - just extract and run!

---

## First-Time Setup

When you run AlderSync for the first time:

1. **Server Connection Dialog** will appear
   - **Server URL**: Enter your church's server address (ask your tech coordinator)
     - Example: `aldersync.mychurch.org` or `192.168.1.100`
   - **Port**: Usually `8000` (ask your tech coordinator if different)
   - **SSL Verification**: Check this if your server uses a valid SSL certificate

2. **Login Dialog** will appear
   - **Username**: Enter the username provided by your church administrator
   - **Password**: Enter the password provided by your church administrator
   - **Save Credentials**: Check this to remember your login (stored securely in your OS)

3. **Service Type Detection**
   - AlderSync will detect which service type you're currently using (Contemporary or Traditional)
   - The main window will show your current service type

4. **Ready to Use!**
   - The Pull, Push, Reconcile, and Swap buttons will now be enabled
   - You're ready to start synchronizing files

---

## Using AlderSync

### Main Window

The AlderSync window shows:
- **Current Service**: Displays whether you're working with Contemporary or Traditional files
- **Operation Buttons**: Pull, Push, Reconcile, Swap
- **Status Bar**: Shows the last operation performed
- **Log Panel**: Toggle view to see detailed operation logs

### Operations

#### Pull - Download Latest Files

**When to use**: Before you start working on ProPresenter files

**What it does**: Downloads all the latest files from the server to your computer

**Steps**:
1. Click the **Pull** button
2. Wait for the download to complete
3. Check the status bar for confirmation
4. Your local files are now up-to-date with the server

**Note**: Pull will overwrite your local files with the server versions. Make sure you've pushed any local changes first!

---

#### Push - Upload Your Changes

**When to use**: After you've made changes to ProPresenter files

**What it does**: Uploads your modified files to the server for others to use

**Steps**:
1. Make your changes to ProPresenter files
2. Close ProPresenter
3. Click the **Push** button
4. Confirm the operation (if confirmation is enabled in settings)
5. Wait for the upload to complete
6. Check the status bar for confirmation

**Note**: Push only uploads files that have changed. Unchanged files are skipped.

---

#### Reconcile - Sync Both Ways

**When to use**: When you're not sure who made the most recent changes

**What it does**: Compares your local files with the server and synchronizes both directions

**Steps**:
1. Click the **Reconcile** button
2. AlderSync will determine which files need to be downloaded and which need to be uploaded
3. If there are conflicts (same file changed locally and on server):
   - You'll see a conflict resolution dialog
   - Choose whether to use the server version, local version, or most recent for each file
4. Wait for the synchronization to complete
5. Check the status bar for confirmation

**Note**: Reconcile is the safest option when in doubt. It ensures you don't lose any changes.

---

#### Swap - Switch Service Types

**When to use**: When switching between Contemporary and Traditional services

**What it does**: Renames your ProPresenter folders to switch which service files ProPresenter sees

**Steps**:
1. **Close ProPresenter** (swap won't work if ProPresenter is running)
2. Click the **Swap** button
3. AlderSync will rename the folders:
   - Current `ProPresenter` folder → `ProPresenter - [Current Service]`
   - `ProPresenter - [Other Service]` folder → `ProPresenter`
4. The service indicator will update to show the new current service
5. Open ProPresenter to work with the other service's files

**Example**: If you're currently on Contemporary:
- `ProPresenter` → `ProPresenter - Contemporary`
- `ProPresenter - Traditional` → `ProPresenter`

**Note**: You can swap back anytime by clicking Swap again.

---

### Settings

Access settings from the menu bar: **Settings** → **Preferences**

**Connection Tab**:
- Server URL and port
- SSL verification toggle

**Service Tab**:
- Default service type (Contemporary or Traditional)

**Paths Tab**:
- Custom Documents folder location (if not using default)

**Logging Tab**:
- Log level (Info, Debug, Warning, Error)
- Log retention days
- Show log panel on startup

**Behavior Tab**:
- Confirm before Push (requires confirmation dialog before uploading)

**Change Password**:
- Change your server password
- Old password required
- New password will be stored securely in your OS credential store

---

## Command-Line Mode

AlderSync can run without the GUI for scheduled tasks (automated nightly sync, etc.)

### Usage

Open Command Prompt (Windows) or Terminal (Mac) and navigate to the AlderSync folder:

**Pull latest files**:
```bash
aldersync.exe pull
```

**Push changes**:
```bash
aldersync.exe push
```

**Reconcile (sync both ways)**:
```bash
aldersync.exe reconcile
```

**Pull specific service type**:
```bash
aldersync.exe pull --service Traditional
```

**Reconcile specific service type**:
```bash
aldersync.exe reconcile --service Contemporary
```

### Exit Codes

- `0` = Success
- `1` = Error occurred (check log file for details)

### Log Files

CLI mode creates timestamped log files next to the executable:
- Example: `aldersync-gui-2024-01-15-14-30-00.log`

### Scheduling Automated Tasks

**Windows Task Scheduler**:
1. Open Task Scheduler
2. Create Basic Task
3. Trigger: Daily at desired time (e.g., 2:00 AM)
4. Action: Start a program
   - Program: `C:\Path\To\aldersync.exe`
   - Arguments: `pull` (or `push`, `reconcile`)
5. Finish and test

**macOS cron or launchd**:
Create a cron job or launchd plist to run the command at desired times.

---

## Troubleshooting

### Cannot Connect to Server

**Problem**: "Failed to connect to server" error

**Solutions**:
1. Check your internet connection
2. Verify the server URL and port in Settings
3. Ask your tech coordinator if the server is running
4. Check if you need to connect to church WiFi or VPN
5. Disable SSL verification if using self-signed certificate

---

### Login Failed

**Problem**: "Invalid username or password" error

**Solutions**:
1. Verify your username and password with church administrator
2. Check for typos (passwords are case-sensitive)
3. Try changing your password via admin or ask admin to reset it
4. Ensure your account is active (not disabled)

---

### ProPresenter Folders Not Found

**Problem**: "ProPresenter folder not found" error

**Solutions**:
1. Ensure ProPresenter is installed
2. Check that ProPresenter folder exists at:
   - Windows: `C:\Users\[YourName]\Documents\ProPresenter`
   - Mac: `/Users/[YourName]/Documents/ProPresenter`
3. If using a custom Documents location, set it in Settings → Paths
4. Create the ProPresenter folder manually if it doesn't exist

---

### Swap Button Disabled

**Problem**: Cannot swap service types

**Solutions**:
1. **Close ProPresenter** - Swap requires ProPresenter to be closed
2. Verify both service folders exist:
   - `ProPresenter` folder
   - One alternate folder (`ProPresenter - Contemporary` or `ProPresenter - Traditional`)
3. Check folder permissions (ensure you can rename folders)

---

### Operation Cancelled by Administrator

**Problem**: "Operation cancelled by administrator" message during sync

**Explanation**: A church administrator cancelled your operation from the server. This might happen if they need to perform maintenance or resolve a conflict.

**Solution**:
- Wait a few minutes and try again
- Contact your tech coordinator if it keeps happening
- Your local changes are safe - no files were lost

---

### Conflicts Detected

**Problem**: Conflict resolution dialog appears during Reconcile

**Explanation**: Both you and someone else modified the same file. AlderSync needs to know which version to keep.

**Solutions**:
1. **View Details**: Look at modified times and file sizes to determine which is newer
2. **Choose Resolution**:
   - "Use Server" - Discard your local changes, use server version
   - "Use Local" - Upload your changes, overwrite server version
   - "Use Most Recent" - Automatically use whichever was modified last
3. **Apply to All**: Use the same resolution for all conflicts (saves time)
4. Click **Proceed** to continue with your choices

**Tip**: If in doubt, choose "Use Most Recent" or "Use Server" to avoid losing others' work.

---

### Slow Performance

**Problem**: Operations take a long time to complete

**Solutions**:
1. Check your internet connection speed
2. Large files or many files will take longer - be patient
3. Progress is shown in the log panel
4. Close other applications using the network
5. Contact your tech coordinator if the server may be slow

---

### Executable Won't Run (macOS)

**Problem**: "App can't be opened because it is from an unidentified developer"

**Solution**:
1. Right-click AlderSync.app
2. Select "Open" from the menu
3. Click "Open" in the security dialog
4. Future runs will work normally by double-clicking

---

### Keyring/Credential Storage Issues

**Problem**: Credentials not saving or "Keyring error" message

**Windows Solutions**:
1. Ensure Windows Credential Manager is functioning
2. Try running AlderSync as administrator once
3. Manually re-enter credentials in Settings

**macOS Solutions**:
1. Ensure Keychain Access is functioning
2. Allow AlderSync to access Keychain when prompted
3. Check Keychain Access app for "AlderSync" entry

---

## Getting Help

If you need additional assistance:

1. **Check the log panel** in AlderSync for error details
2. **Contact your church tech coordinator** - they can help with server-related issues
3. **Check with your church administrator** for:
   - Username/password issues
   - Account status
   - Server connection details
4. **Review this README** for common solutions

---

## Tips for Best Results

1. **Always Pull before starting work** - Get the latest files first
2. **Always Push after finishing** - Share your changes with others
3. **Close ProPresenter before syncing** - Prevents file locking issues
4. **Use Reconcile when unsure** - Safest option to avoid losing changes
5. **Swap with ProPresenter closed** - Required for folder renaming
6. **Keep AlderSync updated** - Download new versions from the server when available
7. **Regular backups** - While AlderSync keeps file revisions, maintain your own backups of important files

---

## Version Information

Check the About dialog or Settings window for your current AlderSync version number. Provide this when requesting support.

---

**AlderSync - Simplifying ProPresenter File Synchronization for Church Volunteers**

Thank you for using AlderSync!
