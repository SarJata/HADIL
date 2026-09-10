import os
import sys
import json

# Force isolated test metadata database to avoid wiping live developer metadata DB
os.environ["HADIL_METADATA_DB"] = "./test_hadil_metadata.db"

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from main import app
from database.metadata_db import metadata_manager, MetadataBase, HadilUser
from services.metadata_service import metadata_service
from database.manager import db_manager

client = TestClient(app)

def setup_test_environment():
    """
    Sets up isolated databases (Metadata DB and 2 customer databases) for testing.
    """
    # 1. Reset metadata tables
    MetadataBase.metadata.drop_all(bind=metadata_manager.engine)
    MetadataBase.metadata.create_all(bind=metadata_manager.engine)

    # 2. Register Database A and Database B
    metadata_service.register_or_update_database("db_a.db", "Database A", "sqlite")
    metadata_service.register_or_update_database("db_b.db", "Database B", "sqlite")

    # 3. Create Users
    admin_user = metadata_service.create_user("admin_user", "password123")
    editor_user = metadata_service.create_user("editor_user", "password123")
    viewer_user = metadata_service.create_user("viewer_user", "password123")
    scoped_user = metadata_service.create_user("sarat", "password123")

    # 4. Assign Database A Roles
    metadata_service.assign_user_role(admin_user.id, "db_a.db", "ADMIN")
    metadata_service.assign_user_role(editor_user.id, "db_a.db", "EDITOR")
    metadata_service.assign_user_role(viewer_user.id, "db_a.db", "VIEWER")

    # 5. Assign Database-Scoped Roles for Sarat
    # Sarat -> db_a.db: ADMIN
    # Sarat -> db_b.db: VIEWER
    metadata_service.assign_user_role(scoped_user.id, "db_a.db", "ADMIN")
    metadata_service.assign_user_role(scoped_user.id, "db_b.db", "VIEWER")

    # Ensure active db is db_a.db by default and engine is initialized
    db_manager.current_db_id = "db_a.db"
    db_manager.current_db_name = "Database A"
    db_manager.custom_connection_uri = "sqlite:///:memory:"
    db_manager._initialize_engine()

def setup_module(module):
    setup_test_environment()

def get_auth_header(username: str, password: str = "password123"):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, f"Login failed for {username}: {response.text}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

# ==================================================
# TEST SUITE 1: AUTHENTICATION & FAIL-CLOSED CHECKS
# ==================================================
def test_unauthenticated_request_fails_closed():
    """Unauthenticated requests to protected endpoints MUST fail with HTTP 401."""
    resp = client.post("/api/execute-query", json={"sql": "SELECT 1"})
    assert resp.status_code == 401
    assert "Authentication required" in resp.json()["detail"]

    resp = client.post("/api/execute-form", json={"operation": "CREATE", "table": "products", "fields": {"name": "Test"}})
    assert resp.status_code == 401

    resp = client.post("/api/users", json={"username": "hacker", "password": "123"})
    assert resp.status_code == 401

def test_invalid_token_fails_closed():
    """Invalid or tampered token headers MUST fail with HTTP 401."""
    headers = {"Authorization": "Bearer invalid_jwt_token_string"}
    resp = client.post("/api/execute-query", json={"sql": "SELECT 1"}, headers=headers)
    assert resp.status_code == 401
    assert "Invalid authentication token" in resp.json()["detail"]

def test_unknown_user_fails_closed():
    """Valid JWT format with non-existent user MUST fail authorization."""
    from validators.security import create_access_token
    token = create_access_token(user_id=99999, username="ghost_user")
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = client.post("/api/execute-query", json={"sql": "SELECT 1"}, headers=headers)
    assert resp.status_code == 403

# ==================================================
# TEST SUITE 2: RBAC MATRIX (ADMIN, EDITOR, VIEWER)
# ==================================================
def test_rbac_admin_permissions():
    """ADMIN must be allowed to READ, ADD, UPDATE, DELETE, and MANAGE_USERS."""
    headers = get_auth_header("admin_user")

    # READ
    resp = client.post("/api/execute-query", json={"sql": "SELECT 1"}, headers=headers)
    assert resp.status_code == 200

    # ADD
    resp = client.post("/api/execute-form", json={"operation": "CREATE", "table": "products", "fields": {"name": "Test", "price": 10.0}}, headers=headers)
    assert resp.status_code in [200, 400] # Pass RBAC check (not 403)

    # UPDATE
    resp = client.post("/api/execute-form", json={"operation": "UPDATE", "table": "products", "fields": {"price": 12.0}, "where": {"id": 1}}, headers=headers)
    assert resp.status_code in [200, 400]

    # DELETE
    resp = client.post("/api/execute-form", json={"operation": "DELETE", "table": "products", "fields": {}, "where": {"id": 1}}, headers=headers)
    assert resp.status_code in [200, 400]

    # MANAGE USERS
    resp = client.post("/api/users", json={"username": "new_user", "password": "pw"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "new_user"

def test_rbac_editor_permissions():
    """EDITOR must be allowed READ, ADD, UPDATE; DENIED DELETE and MANAGE_USERS."""
    headers = get_auth_header("editor_user")

    # READ -> ALLOWED
    resp = client.post("/api/execute-query", json={"sql": "SELECT 1"}, headers=headers)
    assert resp.status_code == 200

    # ADD -> ALLOWED
    resp = client.post("/api/execute-form", json={"operation": "CREATE", "table": "products", "fields": {"name": "Test"}}, headers=headers)
    assert resp.status_code != 403

    # UPDATE -> ALLOWED
    resp = client.post("/api/execute-form", json={"operation": "UPDATE", "table": "products", "fields": {"name": "Test"}, "where": {"id": 1}}, headers=headers)
    assert resp.status_code != 403

    # DELETE -> DENIED (403)
    resp = client.post("/api/execute-form", json={"operation": "DELETE", "table": "products", "fields": {}, "where": {"id": 1}}, headers=headers)
    assert resp.status_code == 403
    assert "lacks 'DELETE' permission" in resp.json()["detail"]

    # MANAGE USERS -> DENIED (403)
    resp = client.post("/api/users", json={"username": "hacker", "password": "pw"}, headers=headers)
    assert resp.status_code == 403
    assert "lacks 'MANAGE_USERS' permission" in resp.json()["detail"]

def test_rbac_viewer_permissions():
    """VIEWER must be allowed READ; DENIED ADD, UPDATE, DELETE, and MANAGE_USERS."""
    headers = get_auth_header("viewer_user")

    # READ -> ALLOWED
    resp = client.post("/api/execute-query", json={"sql": "SELECT 1"}, headers=headers)
    assert resp.status_code == 200

    # ADD -> DENIED
    resp = client.post("/api/execute-form", json={"operation": "CREATE", "table": "products", "fields": {"name": "Test"}}, headers=headers)
    assert resp.status_code == 403

    # UPDATE -> DENIED
    resp = client.post("/api/execute-form", json={"operation": "UPDATE", "table": "products", "fields": {"name": "Test"}, "where": {"id": 1}}, headers=headers)
    assert resp.status_code == 403

    # DELETE -> DENIED
    resp = client.post("/api/execute-form", json={"operation": "DELETE", "table": "products", "fields": {}, "where": {"id": 1}}, headers=headers)
    assert resp.status_code == 403

    # MANAGE USERS -> DENIED
    resp = client.post("/api/users", json={"username": "hacker", "password": "pw"}, headers=headers)
    assert resp.status_code == 403

# ==================================================
# TEST SUITE 3: DATABASE-SCOPED ROLES & CONTEXT SWITCH
# ==================================================
def test_database_scoped_role_switch():
    """
    Verifies that roles are strictly scoped per database.
    User 'sarat' is ADMIN on db_a.db, but VIEWER on db_b.db.
    """
    headers = get_auth_header("sarat")

    # 1. Active DB is db_a.db -> DELETE allowed
    db_manager.current_db_id = "db_a.db"
    resp = client.post("/api/execute-form", json={"operation": "DELETE", "table": "products", "fields": {}, "where": {"id": 1}}, headers=headers)
    assert resp.status_code != 403

    # 2. Switch Active DB to db_b.db -> DELETE MUST BE DENIED
    db_manager.current_db_id = "db_b.db"
    resp = client.post("/api/execute-form", json={"operation": "DELETE", "table": "products", "fields": {}, "where": {"id": 1}}, headers=headers)
    assert resp.status_code == 403
    assert "lacks 'DELETE' permission" in resp.json()["detail"]

# ==================================================
# TEST SUITE 4: BOLA / IDOR MITIGATION FOUNDATION
# ==================================================
def test_client_cannot_inject_user_id_or_role():
    """
    Ensures authorization relies strictly on server-side JWT claims and metadata tables,
    ignoring any client payload attempting role elevation or user identity spoofing.
    """
    headers = get_auth_header("viewer_user")
    
    # Client attempts to pass spoofed role/user_id in request body
    body = {
        "operation": "DELETE",
        "table": "products",
        "fields": {},
        "where": {"id": 1},
        "role": "ADMIN",
        "user_id": 1
    }
    resp = client.post("/api/execute-form", json=body, headers=headers)
    assert resp.status_code == 403

def run_all_security_tests():
    setup_test_environment()
    test_unauthenticated_request_fails_closed()
    print("[PASS] test_unauthenticated_request_fails_closed")

    test_invalid_token_fails_closed()
    print("[PASS] test_invalid_token_fails_closed")

    test_unknown_user_fails_closed()
    print("[PASS] test_unknown_user_fails_closed")

    test_rbac_admin_permissions()
    print("[PASS] test_rbac_admin_permissions")

    test_rbac_editor_permissions()
    print("[PASS] test_rbac_editor_permissions")

    test_rbac_viewer_permissions()
    print("[PASS] test_rbac_viewer_permissions")

    test_database_scoped_role_switch()
    print("[PASS] test_database_scoped_role_switch")

    test_client_cannot_inject_user_id_or_role()
    print("[PASS] test_client_cannot_inject_user_id_or_role")

    print("\n--- ALL SECURITY & RBAC END-TO-END TESTS PASSED SUCCESSFULLY! ---")

if __name__ == "__main__":
    run_all_security_tests()
