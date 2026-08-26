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
    """
    user_payload = get_current_user_optional(authorization)
    if not user_payload:
        raise HTTPException(status_code=401, detail="Authentication required. Missing Bearer token header.")
    return user_payload

def enforce_permission(action: str):
    """
    FastAPI Dependency that checks database-scoped RBAC permissions.
    Fetches authenticated user identity and active database ID from server state.
    """
    def check_user_permission(current_user: Dict[str, Any] = Depends(get_current_user)):
        user_id = int(current_user["sub"])
        active_db_id = db_manager.current_db_id

        if not active_db_id:
            raise HTTPException(status_code=400, detail="No database currently selected.")

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
