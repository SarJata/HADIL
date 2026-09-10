import os
import sys
import pytest

# Force isolated test metadata database
os.environ["HADIL_METADATA_DB"] = "./test_suadmin_regression_metadata.db"

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from main import app
from database.metadata_db import metadata_manager, MetadataBase, HadilUser, HadilSystemRole
from services.metadata_service import metadata_service
from database.manager import db_manager

client = TestClient(app)

def setup_module(module):
    """
    Reset and seed test metadata database for SuAdmin and UX authorization tests.
    """
    MetadataBase.metadata.drop_all(bind=metadata_manager.engine)
    MetadataBase.metadata.create_all(bind=metadata_manager.engine)

    # Register default test DB
    metadata_service.register_or_update_database("sales.db", "Sales Database", "sqlite")

    db_manager.current_db_id = "sales.db"
    db_manager.current_db_name = "Sales Database"
    db_manager.custom_connection_uri = "sqlite:///:memory:"
    db_manager._initialize_engine()

    # Seed initial setup admin (MASTER_ADMIN)
    metadata_service.create_first_admin("suadmin_user", "SuAdminPassword123!")

    # Seed regular users
    reg_admin = metadata_service.create_user("regular_admin", "Password123!")
    metadata_service.assign_user_role(reg_admin.id, "sales.db", "ADMIN")

    reg_viewer = metadata_service.create_user("regular_viewer", "Password123!")
    metadata_service.assign_user_role(reg_viewer.id, "sales.db", "VIEWER")


def test_initial_admin_setup_creates_and_recognizes_master_admin():
    """
    Requirement 2: Initial setup-created administrator MUST be assigned and recognized as MASTER_ADMIN.
    """
    # 1. Login as the setup admin
    login_res = client.post("/api/auth/login", json={"username": "suadmin_user", "password": "SuAdminPassword123!"})
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Query /api/auth/me -> Must return role "MASTER_ADMIN" and all management permissions
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    data = me_res.json()
    assert data["role"] == "MASTER_ADMIN"
    assert "MANAGE_USERS" in data["permissions"]
    assert "DELETE" in data["permissions"]


def test_privileged_endpoints_enforce_suadmin_and_block_non_master():
    """
    Requirement 2: Backend enforcement must block non-MASTER_ADMIN users from privileged SuAdmin endpoints with 403.
    """
    # Login regular admin
    login_admin = client.post("/api/auth/login", json={"username": "regular_admin", "password": "Password123!"})
    token_admin = login_admin.json()["access_token"]
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    # Login regular viewer
    login_viewer = client.post("/api/auth/login", json={"username": "regular_viewer", "password": "Password123!"})
    token_viewer = login_viewer.json()["access_token"]
    headers_viewer = {"Authorization": f"Bearer {token_viewer}"}

    # Privileged SuAdmin Endpoints to test
    privileged_endpoints = [
        ("/api/admin/system-status", "GET"),
        ("/api/admin/db-directories", "GET"),
        ("/api/admin/llm-config", "GET"),
    ]

    # Non-MASTER_ADMIN users MUST be denied access (HTTP 403)
    for endpoint, method in privileged_endpoints:
        if method == "GET":
            res_admin = client.get(endpoint, headers=headers_admin)
            res_viewer = client.get(endpoint, headers=headers_viewer)

            assert res_admin.status_code == 403, f"Expected 403 for regular admin on {endpoint}, got {res_admin.status_code}"
            assert res_viewer.status_code == 403, f"Expected 403 for viewer on {endpoint}, got {res_viewer.status_code}"

    # MASTER_ADMIN user MUST be granted access (HTTP 200)
    login_master = client.post("/api/auth/login", json={"username": "suadmin_user", "password": "SuAdminPassword123!"})
    token_master = login_master.json()["access_token"]
    headers_master = {"Authorization": f"Bearer {token_master}"}

    res_sys_status = client.get("/api/admin/system-status", headers=headers_master)
    assert res_sys_status.status_code == 200
    assert "fastapi_status" in res_sys_status.json()

    res_directories = client.get("/api/admin/db-directories", headers=headers_master)
    assert res_directories.status_code == 200
    assert "directories" in res_directories.json()


def test_ui_permissions_mapping_for_all_roles():
    """
    Requirement 2: Ensure UI-visible roles map cleanly from backend /auth/me payloads without leaking internal identifiers.
    """
    # Test SuAdmin (MASTER_ADMIN)
    token_master = client.post("/api/auth/login", json={"username": "suadmin_user", "password": "SuAdminPassword123!"}).json()["access_token"]
    me_master = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_master}"}).json()
    assert me_master["role"] == "MASTER_ADMIN"

    # Test Regular Admin
    token_admin = client.post("/api/auth/login", json={"username": "regular_admin", "password": "Password123!"}).json()["access_token"]
    me_admin = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_admin}"}).json()
    assert me_admin["role"] == "ADMIN"

    # Test Viewer
    token_viewer = client.post("/api/auth/login", json={"username": "regular_viewer", "password": "Password123!"}).json()["access_token"]
    me_viewer = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_viewer}"}).json()
    assert me_viewer["role"] == "VIEWER"
    assert me_viewer["permissions"] == ["READ"]
