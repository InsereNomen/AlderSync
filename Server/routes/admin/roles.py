"""
AlderSync Server - Admin Roles Endpoints
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func

from models.database import Role, Permission, RolePermission, User
from models.api import CreateRoleRequest, UpdateRoleRequest, SetRolePermissionsRequest
from routes.admin.auth import RequireAdminSession

# Create logger
logger = logging.getLogger(__name__)

# Create router instance
router = APIRouter()



# ==================== Admin - Role Management ====================

@router.get("/admin/api/roles", tags=["Admin"])
async def admin_list_roles(
    session: dict = Depends(RequireAdminSession)
):
    """
    List all roles with their permissions
    Per Task 8.5

    Args:
        session: Admin session from dependency

    Returns:
        List of roles with their permissions
    """
    from database import db_manager
    db_session = db_manager.GetSession()

    try:
        # Get all roles using database utility function
        roles = db_manager.GetAllRoles(db_session)

        # Build response with role details and permissions
        roles_data = []
        for role in roles:
            permissions = db_manager.GetRolePermissions(db_session, role_id=role.role_id)
            user_count = len(db_manager.GetUsersWithRole(db_session, role_id=role.role_id))

            roles_data.append({
                "role_id": role.role_id,
                "role_name": role.role_name,
                "description": role.description,
                "is_system_role": role.is_system_role,
                "created_at": role.created_at.isoformat() if role.created_at else None,
                "permissions": permissions,
                "user_count": user_count
            })

        logger.info(f"Admin '{session['username']}' listed all roles")

        return {
            "success": True,
            "roles": roles_data
        }

    except Exception as e:
        logger.error(f"Error listing roles: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list roles")
    finally:
        db_session.close()




@router.post("/admin/api/roles", tags=["Admin"])
async def admin_create_role(
    request_data: CreateRoleRequest,
    session: dict = Depends(RequireAdminSession)
):
    """
    Create a new role with specified permissions
    Per Task 8.5

    Args:
        request_data: Role creation data (role_name, description, permissions)
        session: Admin session from dependency

    Returns:
        Success message with role details
    """
    db_session = db_manager.GetSession()

    try:
        # Validate role name format
        import re
        if not re.match(r'^[a-zA-Z0-9_\- ]{3,50}$', request_data.role_name):
            raise HTTPException(
                status_code=400,
                detail="Role name must be 3-50 characters and contain only letters, numbers, spaces, hyphens, and underscores"
            )

        # Check if role already exists
        existing_role = db_session.query(Role).filter(Role.role_name == request_data.role_name).first()
        if existing_role:
            raise HTTPException(
                status_code=400,
                detail=f"Role '{request_data.role_name}' already exists"
            )

        # Validate permissions exist
        all_permissions = db_manager.GetAllPermissions(db_session)
        valid_permission_names = [p.permission_name for p in all_permissions]

        for perm_name in request_data.permissions:
            if perm_name not in valid_permission_names:
                raise HTTPException(
                    status_code=400,
                    detail=f"Permission '{perm_name}' does not exist"
                )

        # Create new role
        new_role = Role(
            role_name=request_data.role_name,
            description=request_data.description,
            created_at=datetime.now(timezone.utc),
            is_system_role=False
        )

        db_session.add(new_role)
        db_session.flush()  # Get the role_id

        # Add permissions to role
        for perm_name in request_data.permissions:
            permission = db_session.query(Permission).filter(Permission.permission_name == perm_name).first()
            if permission:
                role_permission = RolePermission(
                    role_id=new_role.role_id,
                    permission_id=permission.permission_id
                )
                db_session.add(role_permission)

        db_session.commit()

        logger.info(f"Admin '{session['username']}' created new role '{request_data.role_name}' with permissions: {request_data.permissions}")

        return {
            "success": True,
            "role_id": new_role.role_id,
            "role_name": new_role.role_name,
            "message": f"Role '{request_data.role_name}' created successfully"
        }

    except HTTPException:
        db_session.rollback()
        raise
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error creating role: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create role")
    finally:
        db_session.close()




@router.put("/admin/api/roles/{role_id}", tags=["Admin"])
async def admin_update_role(
    role_id: int,
    request_data: UpdateRoleRequest,
    session: dict = Depends(RequireAdminSession)
):
    """
    Update a role's name and/or description
    Per Task 8.5

    Args:
        role_id: Role ID to update
        request_data: Update data (role_name, description)
        session: Admin session from dependency

    Returns:
        Success message
    """
    from database import db_manager
    db_session = db_manager.GetSession()

    try:
        # Find role
        role = db_session.query(Role).filter(Role.role_id == role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail=f"Role with ID {role_id} not found")

        # Prevent updating system roles
        if role.is_system_role:
            raise HTTPException(
                status_code=403,
                detail="Cannot modify system roles"
            )

        old_name = role.role_name

        # Update role name if provided
        if request_data.role_name is not None:
            # Validate role name format
            import re
            if not re.match(r'^[a-zA-Z0-9_\- ]{3,50}$', request_data.role_name):
                raise HTTPException(
                    status_code=400,
                    detail="Role name must be 3-50 characters and contain only letters, numbers, spaces, hyphens, and underscores"
                )

            # Check if new name already exists
            existing_role = db_session.query(Role).filter(
                Role.role_name == request_data.role_name,
                Role.role_id != role_id
            ).first()
            if existing_role:
                raise HTTPException(
                    status_code=400,
                    detail=f"Role '{request_data.role_name}' already exists"
                )

            role.role_name = request_data.role_name

        # Update description if provided
        if request_data.description is not None:
            role.description = request_data.description

        db_session.commit()

        logger.info(f"Admin '{session['username']}' updated role '{old_name}' (ID: {role_id})")

        return {
            "success": True,
            "role_id": role.role_id,
            "role_name": role.role_name,
            "message": f"Role updated successfully"
        }

    except HTTPException:
        db_session.rollback()
        raise
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error updating role: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update role")
    finally:
        db_session.close()


@router.delete("/admin/api/roles/{role_id}", tags=["Admin"])
async def admin_delete_role(
    role_id: int,
    session: dict = Depends(RequireAdminSession)
):
    """
    Delete a role (only if no users are assigned to it)
    Per Task 8.5

    Args:
        role_id: Role ID to delete
        session: Admin session from dependency

    Returns:
        Success message
    """
    from database import db_manager
    db_session = db_manager.GetSession()

    try:
        # Find role
        role = db_session.query(Role).filter(Role.role_id == role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail=f"Role with ID {role_id} not found")

        # Prevent deleting system roles
        if role.is_system_role:
            raise HTTPException(
                status_code=403,
                detail="Cannot delete system roles"
            )

        # Check if any users are assigned to this role
        users_with_role = db_manager.GetUsersWithRole(db_session, role_id=role_id)
        if users_with_role:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete role: {len(users_with_role)} user(s) are assigned to this role"
            )

        role_name = role.role_name

        # Delete role permissions first (due to foreign key constraints)
        db_session.query(RolePermission).filter(RolePermission.role_id == role_id).delete()

        # Delete role
        db_session.delete(role)
        db_session.commit()

        logger.info(f"Admin '{session['username']}' deleted role '{role_name}' (ID: {role_id})")

        return {
            "success": True,
            "message": f"Role '{role_name}' deleted successfully"
        }

    except HTTPException:
        db_session.rollback()
        raise
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error deleting role: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete role")
    finally:
        db_session.close()




@router.put("/admin/api/roles/{role_id}/permissions", tags=["Admin"])
async def admin_set_role_permissions(
    role_id: int,
    request_data: SetRolePermissionsRequest,
    session: dict = Depends(RequireAdminSession)
):
    """
    Set permissions for a role (replaces all existing permissions)
    Per Task 8.5

    Args:
        role_id: Role ID to set permissions for
        request_data: Permissions list
        session: Admin session from dependency

    Returns:
        Success message with updated permissions
    """
    from database import db_manager
    db_session = db_manager.GetSession()

    try:
        # Find role
        role = db_session.query(Role).filter(Role.role_id == role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail=f"Role with ID {role_id} not found")

        # Validate permissions exist
        all_permissions = db_manager.GetAllPermissions(db_session)
        valid_permission_names = [p.permission_name for p in all_permissions]

        for perm_name in request_data.permissions:
            if perm_name not in valid_permission_names:
                raise HTTPException(
                    status_code=400,
                    detail=f"Permission '{perm_name}' does not exist"
                )

        # Remove all existing permissions for this role
        db_session.query(RolePermission).filter(RolePermission.role_id == role_id).delete()

        # Add new permissions
        for perm_name in request_data.permissions:
            permission = db_session.query(Permission).filter(Permission.permission_name == perm_name).first()
            if permission:
                role_permission = RolePermission(
                    role_id=role_id,
                    permission_id=permission.permission_id
                )
                db_session.add(role_permission)

        db_session.commit()

        logger.info(f"Admin '{session['username']}' set permissions for role '{role.role_name}' (ID: {role_id}): {request_data.permissions}")

        return {
            "success": True,
            "role_id": role.role_id,
            "role_name": role.role_name,
            "permissions": request_data.permissions,
            "message": f"Permissions updated for role '{role.role_name}'"
        }

    except HTTPException:
        db_session.rollback()
        raise
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error setting role permissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to set role permissions")
    finally:
        db_session.close()


