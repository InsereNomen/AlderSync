#!/usr/bin/env python3
"""
AlderSync Server - Setup and Deployment Script

This script initializes the AlderSync server for deployment:
1. Creates SQLite database with schema
2. Creates default admin user
3. Initializes storage directory structure
4. Populates default settings

Run this script on the server/NAS to set up AlderSync for the first time.

Usage:
    python setup_server.py

Author: AlderSync Project
"""

import sys
from pathlib import Path

# Ensure we can import from the same directory
sys.path.insert(0, str(Path(__file__).parent))

from database import DatabaseManager
from file_storage import InitializeStorage, DEFAULT_STORAGE_ROOT


def print_header():
    """Print script header"""
    print("=" * 70)
    print("AlderSync Server - Setup and Deployment Script")
    print("=" * 70)
    print()


def print_section(title):
    """Print section header"""
    print()
    print("-" * 70)
    print(f"  {title}")
    print("-" * 70)


def initialize_database():
    """
    Initialize the SQLite database with schema and default data

    Returns:
        str or None: Admin password if created, None otherwise
    """
    print_section("Database Initialization")

    db_path = Path("database/aldersync.db")

    # Check if database already exists
    if db_path.exists():
        print(f"[OK] Database file found at: {db_path.absolute()}")
        print("  Existing database will be updated with any missing tables/settings.")
    else:
        print(f"-> Creating new database at: {db_path.absolute()}")
        # Ensure database directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)

    print()

    # Initialize database
    try:
        db_manager = DatabaseManager()
        admin_password = db_manager.InitializeDatabase()

        print()
        print("[OK] Database initialization complete!")

        return admin_password

    except Exception as e:
        print(f"[ERROR] Database initialization failed: {str(e)}")
        raise


def initialize_storage():
    """Initialize the file storage directory structure"""
    print_section("Storage Directory Initialization")

    storage_path = Path(DEFAULT_STORAGE_ROOT)

    print(f"-> Initializing storage at: {storage_path.absolute()}")
    print()

    try:
        InitializeStorage(DEFAULT_STORAGE_ROOT)

        print()
        print("[OK] Storage directories created:")
        print(f"  - {(storage_path / 'Contemporary').absolute()}")
        print(f"  - {(storage_path / 'Traditional').absolute()}")

    except Exception as e:
        print(f"[ERROR] Storage initialization failed: {str(e)}")
        raise


def print_admin_credentials(password):
    """
    Print admin credentials prominently

    Args:
        password: Generated admin password
    """
    print()
    print("!" * 70)
    print("!" + " " * 68 + "!")
    print("!  IMPORTANT: SAVE THESE CREDENTIALS - PASSWORD SHOWN ONLY ONCE!  !")
    print("!" + " " * 68 + "!")
    print("!" * 70)
    print()
    print(f"  Admin Username: admin")
    print(f"  Admin Password: {password}")
    print()
    print("!" * 70)
    print()
    print("  -> Log in to the admin web interface to change the password")
    print("  -> Or use the /user/change_password API endpoint")


def print_next_steps():
    """Print next steps for server deployment"""
    print_section("Next Steps")

    print("""
1. Configure Auto-Start (Optional but Recommended):

   Linux (systemd):
     a. Copy aldersync.service to /etc/systemd/system/
     b. Edit paths in the service file to match your installation
     c. Enable: sudo systemctl enable aldersync
     d. Start: sudo systemctl start aldersync
     e. Check status: sudo systemctl status aldersync

   macOS (launchd):
     a. Copy com.aldersync.server.plist to ~/Library/LaunchAgents/
     b. Edit paths in the plist file to match your installation
     c. Load: launchctl load ~/Library/LaunchAgents/com.aldersync.server.plist
     d. Check status: launchctl list | grep aldersync

2. Start the Server Manually (for testing):

   python server.py

   Or with uvicorn directly:

   uvicorn server:app --host 0.0.0.0 --port 8000

3. Configure Network Access:

   a. Firewall: Allow inbound connections on port 8000 (or your configured port)
   b. Port Forwarding: Forward external port to server port on your NAS
   c. IMPORTANT: Use HTTPS in production (see SSL certificate setup below)

4. SSL Certificate Setup (Recommended for Production):

   Option A - Self-Signed Certificate (for home/church use):
     openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

   Option B - Let's Encrypt (if you have a domain):
     Use certbot to obtain free SSL certificates

   Then configure uvicorn to use SSL:
     uvicorn server:app --host 0.0.0.0 --port 8000 --ssl-keyfile key.pem --ssl-certfile cert.pem

5. Access the Admin Interface:

   Open your browser to: http://localhost:8000/admin
   (Or https:// if using SSL)

   Log in with the admin credentials shown above.

6. Create User Accounts:

   Use the admin web interface to create accounts for volunteers.

7. Test Client Connection:

   Install the AlderSync client on a test machine and configure it to
   connect to your server URL and port.

""")


def main():
    """Main setup script entry point"""
    print_header()

    print("This script will set up the AlderSync server for deployment.")
    print("It will initialize the database, create storage directories,")
    print("and configure default settings.")
    print()

    # Confirm before proceeding
    try:
        response = input("Continue with setup? (Y/n): ")
        if response.lower() == 'n':
            print("\nSetup cancelled.")
            sys.exit(0)
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        sys.exit(0)

    # Initialize database
    try:
        admin_password = initialize_database()
    except Exception:
        print("\n[ERROR] Setup failed during database initialization")
        sys.exit(1)

    # Initialize storage
    try:
        initialize_storage()
    except Exception:
        print("\n[ERROR] Setup failed during storage initialization")
        sys.exit(1)

    # Print success message
    print()
    print("=" * 70)
    print("[OK] AlderSync Server Setup Complete!")
    print("=" * 70)

    # Display admin credentials if this was first-time setup
    if admin_password:
        print_admin_credentials(admin_password)
    else:
        print()
        print("  Database already contained users - no new admin account created.")
        print()

    # Print next steps
    print_next_steps()

    print("=" * 70)
    print("Setup complete! Review the next steps above to finish deployment.")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
