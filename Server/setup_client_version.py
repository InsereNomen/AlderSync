"""
AlderSync Server - Client Version Setup Script

Sets up the client version and executable path settings in the database.
This should be run by administrators when a new client version is available.

Usage:
    python setup_client_version.py <version> <executable_path>

Example:
    python setup_client_version.py 1.0.1 "E:/AlderSync/Client/dist/aldersync.exe"
"""

import sys
from pathlib import Path

from database import DatabaseManager, Setting


def setup_client_version(version: str, executable_path: str):
    """
    Set up client version and executable path in database.

    Args:
        version: Version number (e.g., "1.0.1")
        executable_path: Full path to client executable
    """
    print("AlderSync Server - Client Version Setup")
    print("=" * 50)

    # Verify executable path exists
    exe_path = Path(executable_path)
    if not exe_path.exists():
        print(f"WARNING: Executable path does not exist: {exe_path}")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("Aborted.")
            return

    # Initialize database manager
    db_manager = DatabaseManager()
    session = db_manager.GetSession()

    try:
        # Update or create version setting
        version_setting = session.query(Setting).filter(Setting.key == "latest_client_version").first()
        if version_setting:
            old_version = version_setting.value
            version_setting.value = version
            print(f"Updated client version: {old_version} -> {version}")
        else:
            version_setting = Setting(key="latest_client_version", value=version)
            session.add(version_setting)
            print(f"Created client version setting: {version}")

        # Update or create executable path setting
        path_setting = session.query(Setting).filter(Setting.key == "client_executable_path").first()
        if path_setting:
            old_path = path_setting.value
            path_setting.value = str(exe_path.absolute())
            print(f"Updated executable path: {old_path} -> {exe_path.absolute()}")
        else:
            path_setting = Setting(key="client_executable_path", value=str(exe_path.absolute()))
            session.add(path_setting)
            print(f"Created executable path setting: {exe_path.absolute()}")

        # Commit changes
        session.commit()

        print("\n" + "=" * 50)
        print("Client version setup complete!")
        print(f"Version: {version}")
        print(f"Executable: {exe_path.absolute()}")
        print("\nClients will now be notified of this update on startup.")

    except Exception as e:
        session.rollback()
        print(f"\nERROR: Failed to update settings: {e}")
        sys.exit(1)

    finally:
        session.close()


def main():
    """Main entry point."""
    if len(sys.argv) != 3:
        print("Usage: python setup_client_version.py <version> <executable_path>")
        print("Example: python setup_client_version.py 1.0.1 E:/AlderSync/Client/dist/aldersync.exe")
        sys.exit(1)

    version = sys.argv[1]
    executable_path = sys.argv[2]

    setup_client_version(version, executable_path)


if __name__ == "__main__":
    main()
