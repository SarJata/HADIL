import os
import datetime
import jwt
from typing import Optional, Dict, Any
from fastapi import Header, HTTPException, Depends
from database.metadata_db import HadilUser
from services.metadata_service import metadata_service
from database.manager import db_manager

JWT_SECRET = os.getenv("HADIL_JWT_SECRET", "hadil-dev-secret-key-change-in-production-12345")
JWT_ALGORITHM = "HS256"

def create_access_token(user_id: int, username: str, expires_in_hours: int = 24) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": datetime.datetime.utcnow(),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=expires_in_hours)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token.")

def get_current_user_optional(authorization: Optional[str] = Header(None)) -> Optional[Dict[str, Any]]:
    """
    Retrieves user payload if authorization header is provided. Returns None if missing.
    """
    if not authorization:
        return None
    
    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header format. Expected 'Bearer <token>'.")
    
    token = parts[1]
    return decode_access_token(token)

def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    Requires an authenticated user header. Fails closed with 401 if missing or invalid.
    Cloud PENDING/SUSPENDED accounts cannot use protected APIs.
    """
    user_payload = get_current_user_optional(authorization)
    if not user_payload:
        raise HTTPException(status_code=401, detail="Authentication required. Missing Bearer token header.")
    try:
        user_id = int(user_payload["sub"])
    except (TypeError, ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid authentication token.")
    user = metadata_service.get_user_by_id(user_id)
    if user:
        try:
            metadata_service.assert_account_usable(user.id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        user_payload["organization_id"] = user.organization_id
        user_payload["organization_role"] = user.organization_role
        user_payload["account_status"] = user.account_status
    return user_payload

def enforce_permission(action: str):
    """
    FastAPI Dependency that checks database-scoped RBAC permissions.
    Fetches authenticated user identity and active database ID from server state.
    """
    def check_user_permission(current_user: Dict[str, Any] = Depends(get_current_user)):
        user_id = int(current_user["sub"])
        from config.deployment import get_deployment_config
        cfg = get_deployment_config()

        # Cloud organization user management is not a database-scoped permission.
        if cfg.is_cloud and action.upper() == "MANAGE_USERS":
            return enforce_manage_users(current_user)

        active_db_id = db_manager.current_db_id or "sales.db"

        if cfg.is_cloud and db_manager.current_db_id:
            try:
                metadata_service.assert_customer_database_access(user_id, db_manager.current_db_id)
            except PermissionError as exc:
                raise HTTPException(status_code=403, detail=str(exc))

        has_permission = metadata_service.check_permission(
            user_id=user_id,
            database_id=active_db_id,
            action=action
        )

        if not has_permission:
            raise HTTPException(
                status_code=403, 
                detail=f"Access Denied: User '{current_user['username']}' lacks '{action}' permission on active database '{active_db_id}'."
            )
        return current_user

    return check_user_permission


def enforce_manage_users(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Organization-level user administration on cloud (SUADMIN, no active DB required).
    Database-scoped ADMIN still uses MANAGE_USERS on the selected customer database.
    Platform MASTER_ADMIN is not a customer user-manager.
    """
    user_id = int(current_user["sub"])
    from config.deployment import get_deployment_config
    if get_deployment_config().is_cloud:
        user = metadata_service.get_user_by_id(user_id)
        if user and (user.organization_role or "").upper() == "SUADMIN":
            return current_user
        if metadata_service.is_platform_master_admin(user_id):
            raise HTTPException(
                status_code=403,
                detail="Access Denied: Platform Master Admin manages organizations, not customer database users.",
            )
        active_db_id = db_manager.current_db_id
        if not active_db_id:
            raise HTTPException(
                status_code=403,
                detail="Access Denied: Organization user management requires SUADMIN, or MANAGE_USERS on a selected organization database.",
            )
        if not metadata_service.check_permission(user_id, active_db_id, "MANAGE_USERS"):
            raise HTTPException(
                status_code=403,
                detail=f"Access Denied: User '{current_user.get('username')}' lacks 'MANAGE_USERS' permission on database '{active_db_id}'.",
            )
        return current_user

    active_db_id = db_manager.current_db_id or "sales.db"
    if not metadata_service.check_permission(user_id, active_db_id, "MANAGE_USERS"):
        raise HTTPException(
            status_code=403,
            detail=f"Access Denied: User '{current_user.get('username')}' lacks 'MANAGE_USERS' permission on active database '{active_db_id}'.",
        )
    return current_user


def enforce_suadmin(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Desktop: MASTER_ADMIN via database-role lookup (existing tests patch this).
    Cloud: platform MASTER_ADMIN via HadilSystemRole only.
    """
    user_id = int(current_user["sub"])
    from config.deployment import get_deployment_config
    if get_deployment_config().is_cloud:
        if not metadata_service.is_platform_master_admin(user_id):
            raise HTTPException(
                status_code=403,
                detail=f"Access Denied: Administrative feature requires platform Master Admin privileges. User '{current_user.get('username')}' is not authorized."
            )
        return current_user
    role = metadata_service.get_user_role_for_database(user_id, db_manager.current_db_id or "default")
    if role != "MASTER_ADMIN":
        raise HTTPException(
            status_code=403,
            detail=f"Access Denied: Administrative feature requires SuAdmin privileges. User '{current_user.get('username')}' is not authorized."
        )
    return current_user


def enforce_platform_master(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    user_id = int(current_user["sub"])
    if not metadata_service.is_platform_master_admin(user_id):
        raise HTTPException(
            status_code=403,
            detail="Access Denied: Platform Master Admin privileges are required.",
        )
    return current_user


def enforce_org_suadmin(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    user_id = int(current_user["sub"])
    user = metadata_service.get_user_by_id(user_id)
    if not user or (user.organization_role or "").upper() != "SUADMIN":
        raise HTTPException(
            status_code=403,
            detail="Access Denied: Organization SUADMIN privileges are required.",
        )
    return current_user

