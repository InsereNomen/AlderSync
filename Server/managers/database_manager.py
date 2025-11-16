"""
AlderSync Server - Database Manager

This module manages database connection, initialization, and operations.
Extracted from database.py for better code organization.
"""

import secrets
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import bcrypt

from models.database import (
    Base, Role, Permission, RolePermission,
    User, File, Operation, Setting, LastOperation
)


class DatabaseManager:
    """
    Manages database connection, initialization, and operations
    """

    def __init__(self, db_path: str = "database/aldersync.db"):
        """
        Initialize database manager

        Args:
            db_path: Path to SQLite database file
        """
        from pathlib import Path

        self.db_path = db_path

        # Ensure database directory exists
        db_dir = Path(db_path).parent
        if db_dir and str(db_dir) != '.':
            db_dir.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine, expire_on_commit=False)

    def InitializeDatabase(self) -> Optional[str]:
        """
        Initialize the database with all tables and default data
        Creates tables if they don't exist, populates default settings,
        and creates a default admin user on first run.

        Returns:
            str: Generated admin password if admin user was created, None otherwise
        """
        # Create all tables
        Base.metadata.create_all(bind=self.engine)

        # Get a session
        session = self.SessionLocal()
        admin_password = None

        try:
            # Check if this is first run (no users exist)
            user_count = session.query(User).count()
            is_first_run = user_count == 0

            # Populate default roles and permissions (always, even if not first run)
            self.PopulateDefaultRolesAndPermissions(session)

            if is_first_run:
                # Get the Admin role
                admin_role = session.query(Role).filter(Role.role_name == "Admin").first()

                # Create default admin user with Admin role
                admin_password = self.GenerateRandomPassword()
                admin_user = User(
                    username="admin",
                    password_hash=self.HashPassword(admin_password),
                    role_id=admin_role.role_id if admin_role else None,
                    created_at=datetime.now(timezone.utc),
                    is_active=True
                )
                session.add(admin_user)
                print(f"Created default admin user")
                print(f"Username: admin")
                print(f"Password: {admin_password}")
                print(f"IMPORTANT: Change this password after first login!")

            # Populate default settings if not present
            self.PopulateDefaultSettings(session)

            # Initialize last_operation table with empty row if not present
            last_op_count = session.query(LastOperation).count()
            if last_op_count == 0:
                last_op = LastOperation(id=1)
                session.add(last_op)

            # Commit all changes
            session.commit()

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

        return admin_password

    def PopulateDefaultRolesAndPermissions(self, session):
        """
        Populate default roles and permissions for RBAC
        Only adds roles and permissions that don't already exist

        Args:
            session: SQLAlchemy session
        """
        # Define default permissions
        default_permissions = {
            "admin": "Full administrative access to all server functions",
            "can_push": "Can upload files to server via Push operations",
            "can_pull": "Can download files from server via Pull operations",
            "can_reconcile": "Can perform bidirectional sync via Reconcile operations",
            "can_view_files": "Can view file listings and metadata"
        }

        # Create permissions if they don't exist
        permission_objs = {}
        for perm_name, description in default_permissions.items():
            existing = session.query(Permission).filter(Permission.permission_name == perm_name).first()
            if not existing:
                perm = Permission(permission_name=perm_name, description=description)
                session.add(perm)
                session.flush()  # Flush to get the permission_id
                permission_objs[perm_name] = perm
                print(f"Added default permission: {perm_name}")
            else:
                permission_objs[perm_name] = existing

        # Define default roles with their permissions
        default_roles = {
            "Admin": {
                "description": "Full administrative access",
                "permissions": ["admin", "can_push", "can_pull", "can_reconcile", "can_view_files"],
                "is_system": True
            },
            "Standard User": {
                "description": "Can sync files but cannot manage server",
                "permissions": ["can_push", "can_pull", "can_reconcile", "can_view_files"],
                "is_system": True
            },
            "Read-Only": {
                "description": "Can only view and download files",
                "permissions": ["can_pull", "can_view_files"],
                "is_system": True
            }
        }

        # Create roles if they don't exist and assign permissions
        for role_name, role_config in default_roles.items():
            existing_role = session.query(Role).filter(Role.role_name == role_name).first()

            if not existing_role:
                # Create the role
                role = Role(
                    role_name=role_name,
                    description=role_config["description"],
                    is_system_role=role_config["is_system"]
                )
                session.add(role)
                session.flush()  # Flush to get the role_id
                print(f"Added default role: {role_name}")

                # Assign permissions to the role
                for perm_name in role_config["permissions"]:
                    if perm_name in permission_objs:
                        role_perm = RolePermission(
                            role_id=role.role_id,
                            permission_id=permission_objs[perm_name].permission_id
                        )
                        session.add(role_perm)
            else:
                # Role exists - check if permissions need to be added
                existing_perm_names = [p.permission_name for p in existing_role.permissions]
                for perm_name in role_config["permissions"]:
                    if perm_name not in existing_perm_names and perm_name in permission_objs:
                        role_perm = RolePermission(
                            role_id=existing_role.role_id,
                            permission_id=permission_objs[perm_name].permission_id
                        )
                        session.add(role_perm)
                        print(f"Added permission '{perm_name}' to role '{role_name}'")

    def PopulateDefaultSettings(self, session):
        """
        Populate default settings from Specification.md section 5.4
        Only adds settings that don't already exist

        Args:
            session: SQLAlchemy session
        """
        default_settings = {
            "lock_timeout_seconds": "300",  # 5 minutes for Pull/Push
            "min_lock_timeout_seconds": "300",  # 5 minutes minimum for Reconcile
            "max_revisions": "10",
            "jwt_expiration_hours": "24",
            "log_retention_days": "30"
        }

        for key, value in default_settings.items():
            # Check if setting already exists
            existing = session.query(Setting).filter(Setting.key == key).first()
            if not existing:
                setting = Setting(key=key, value=value)
                session.add(setting)
                print(f"Added default setting: {key} = {value}")

    @staticmethod
    def GenerateRandomPassword(length: int = 12) -> str:
        """
        Generate a secure random password

        Args:
            length: Password length (default 12)

        Returns:
            str: Generated password
        """
        # Use a mix of uppercase, lowercase, digits, and special characters
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        return password

    @staticmethod
    def HashPassword(password: str) -> str:
        """
        Hash a password using bcrypt
        Truncates to 72 bytes to comply with bcrypt's maximum password length

        Args:
            password: Plain text password

        Returns:
            str: Hashed password (as string)
        """
        # Bcrypt has a maximum password length of 72 bytes
        # Encode password to bytes and truncate if necessary
        password_bytes = password.encode('utf-8')[:72]

        # Generate salt and hash the password
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)

        # Return as string for database storage
        return hashed.decode('utf-8')

    @staticmethod
    def VerifyPassword(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against a hash
        Truncates to 72 bytes to comply with bcrypt's maximum password length

        Args:
            plain_password: Plain text password to verify
            hashed_password: Stored password hash (as string)

        Returns:
            bool: True if password matches, False otherwise
        """
        # Bcrypt has a maximum password length of 72 bytes
        # Truncate if necessary to match how we hashed it
        password_bytes = plain_password.encode('utf-8')[:72]
        hashed_bytes = hashed_password.encode('utf-8')

        # Verify password against hash
        return bcrypt.checkpw(password_bytes, hashed_bytes)

    def GetSession(self):
        """
        Get a new database session

        Returns:
            Session: SQLAlchemy session
        """
        return self.SessionLocal()

    # ==================== Role Management Utility Functions ====================

    def GetUserRole(self, session, user_id: int = None, username: str = None) -> Optional[Role]:
        """
        Get a user's role

        Args:
            session: SQLAlchemy session
            user_id: User ID (optional)
            username: Username (optional)

        Returns:
            Role: User's role object, or None if user not found or has no role
        """
        if user_id:
            user = session.query(User).filter(User.user_id == user_id).first()
        elif username:
            user = session.query(User).filter(User.username == username).first()
        else:
            return None

        if user and user.role:
            return user.role
        return None

    def GetRolePermissions(self, session, role_id: int = None, role_name: str = None) -> list:
        """
        Get all permissions for a role

        Args:
            session: SQLAlchemy session
            role_id: Role ID (optional)
            role_name: Role name (optional)

        Returns:
            list: List of permission names
        """
        if role_id:
            role = session.query(Role).filter(Role.role_id == role_id).first()
        elif role_name:
            role = session.query(Role).filter(Role.role_name == role_name).first()
        else:
            return []

        if role:
            return [perm.permission_name for perm in role.permissions]
        return []

    def UserHasPermission(self, session, user_id: int, permission_name: str) -> bool:
        """
        Check if a user has a specific permission

        Args:
            session: SQLAlchemy session
            user_id: User ID
            permission_name: Permission name to check

        Returns:
            bool: True if user has the permission, False otherwise
        """
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user or not user.role:
            return False

        # Check if user has the specific permission
        permission_names = [perm.permission_name for perm in user.role.permissions]

        # Admin permission grants all access
        if "admin" in permission_names:
            return True

        return permission_name in permission_names

    def GetUsersWithRole(self, session, role_id: int = None, role_name: str = None) -> list:
        """
        Get all users with a specific role

        Args:
            session: SQLAlchemy session
            role_id: Role ID (optional)
            role_name: Role name (optional)

        Returns:
            list: List of User objects
        """
        if role_id:
            users = session.query(User).filter(User.role_id == role_id).all()
        elif role_name:
            role = session.query(Role).filter(Role.role_name == role_name).first()
            if role:
                users = session.query(User).filter(User.role_id == role.role_id).all()
            else:
                users = []
        else:
            users = []

        return users

    def GetAllRoles(self, session) -> list:
        """
        Get all roles

        Args:
            session: SQLAlchemy session

        Returns:
            list: List of Role objects
        """
        return session.query(Role).all()

    def GetAllPermissions(self, session) -> list:
        """
        Get all permissions

        Args:
            session: SQLAlchemy session

        Returns:
            list: List of Permission objects
        """
        return session.query(Permission).all()
