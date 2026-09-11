"""Cloud V1 login resolution and MASTER_ADMIN vs SUADMIN identity contract."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class TestCloudAuthIdentity(unittest.TestCase):
    def test_username_at_organization_and_authority_contract(self):
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        fd, meta_path = tempfile.mkstemp(suffix="_hadil_auth_id.db")
        os.close(fd)
        empty_folder = tempfile.mkdtemp(prefix="hadil_auth_id_")
        try:
            script = r'''
import os, sys
os.environ["HADIL_DEPLOYMENT_MODE"] = "cloud"
os.environ["HADIL_JWT_SECRET"] = "cloud-test-secret-not-default-value"
os.environ["HADIL_METADATA_DB"] = __META__
os.environ["DATABASE_FOLDER"] = __FOLDER__
os.environ.pop("HADIL_METADATA_DATABASE_URL", None)
sys.path.insert(0, __BACKEND__)
from fastapi.testclient import TestClient
from database.metadata_db import HadilUser, HadilUserDatabaseRole, HadilDatabase, MetadataBase, metadata_manager
from services.metadata_service import MetadataService
from database.manager import db_manager
from main import app

MetadataBase.metadata.drop_all(bind=metadata_manager.engine)
MetadataBase.metadata.create_all(bind=metadata_manager.engine)
master = MetadataService.create_first_admin("masteradmin", "MasterPass123!")
client = TestClient(app)

# 1. Platform MASTER_ADMIN username-only login
master_login = client.post("/api/auth/login", json={"username": "masteradmin", "password": "MasterPass123!"})
assert master_login.status_code == 200, master_login.text
master_headers = {"Authorization": f"Bearer {master_login.json()['access_token']}"}
master_me = client.get("/api/auth/me", headers=master_headers).json()
assert master_me["role"] == "MASTER_ADMIN"
assert master_me["authority_type"] == "PLATFORM"
assert master_me["platform_role"] == "MASTER_ADMIN"
assert master_me["organization_role"] is None
assert master_me["database_role"] is None

# 2. MASTER_ADMIN with @organization does not resolve as MASTER_ADMIN
spoof = client.post("/api/auth/login", json={"username": "masteradmin@hadil", "password": "MasterPass123!"})
assert spoof.status_code == 401, spoof.text

signup_h = client.post("/api/auth/signup", json={
    "username": "suadmin", "organization": "HADIL", "password": "SuPass123!", "confirm_password": "SuPass123!"
})
assert signup_h.status_code == 200, signup_h.text
org_hadil = signup_h.json()["organization_id"]
assert signup_h.json()["username"] == "suadmin@hadil"

# 4. pending organization cannot authenticate
pending = client.post("/api/auth/login", json={"username": "suadmin@hadil", "password": "SuPass123!"})
assert pending.status_code == 403, pending.text

approve = client.post(f"/api/platform/organizations/{org_hadil}/approve", headers=master_headers)
assert approve.status_code == 200, approve.text

# 3/7/9/10/11/12. SUADMIN username@organization, casing, zero DBs, identity
for payload in (
    {"username": "suadmin@hadil", "password": "SuPass123!"},
    {"username": "suadmin@HADIL", "password": "SuPass123!"},
    {"username": "SuAdmin@hadil", "password": "SuPass123!"},
    {"username": "suadmin", "organization": "HADIL", "password": "SuPass123!"},
    {"username": "suadmin", "organization": "hadil", "password": "SuPass123!"},
):
    res = client.post("/api/auth/login", json=payload)
    assert res.status_code == 200, (payload, res.text)

su_login = client.post("/api/auth/login", json={"username": "suadmin@hadil", "password": "SuPass123!"})
su_headers = {"Authorization": f"Bearer {su_login.json()['access_token']}"}
su_id = su_login.json()["user_id"]
su_me = client.get("/api/auth/me", headers=su_headers).json()
assert su_me["role"] == "SUADMIN"
assert su_me["authority_type"] == "ORGANIZATION"
assert su_me["organization_role"] == "SUADMIN"
assert su_me["platform_role"] is None
assert su_me["database_role"] is None
assert su_me["organization"]["slug"] == "hadil"
assert su_me["username"] == "suadmin@hadil"
session = metadata_manager.get_session()
try:
    assert session.query(HadilUserDatabaseRole).filter(HadilUserDatabaseRole.user_id == su_id).count() == 0
    assert session.query(HadilDatabase).filter(HadilDatabase.organization_id == org_hadil).count() == 0
finally:
    session.close()
users_zero_db = client.get("/api/users", headers=su_headers)
assert users_zero_db.status_code == 200, users_zero_db.text
assert "sales.db" not in (users_zero_db.text or "")

# 6. Wrong username fails
assert client.post("/api/auth/login", json={"username": "nobody@hadil", "password": "SuPass123!"}).status_code == 401

# 5. Wrong organization suffix fails
assert client.post("/api/auth/login", json={"username": "suadmin@otherorg", "password": "SuPass123!"}).status_code == 401
assert client.post("/api/auth/login", json={"username": "suadmin", "organization": "otherorg", "password": "SuPass123!"}).status_code == 401

# Same local username in two organizations
signup_o = client.post("/api/auth/signup", json={
    "username": "suadmin", "organization": "otherorg", "password": "OtherPass123!", "confirm_password": "OtherPass123!"
})
assert signup_o.status_code == 200, signup_o.text
org_other = signup_o.json()["organization_id"]
client.post(f"/api/platform/organizations/{org_other}/approve", headers=master_headers)
login_other = client.post("/api/auth/login", json={"username": "suadmin@otherorg", "password": "OtherPass123!"})
assert login_other.status_code == 200, login_other.text
assert login_other.json()["user_id"] != su_id
other_headers = {"Authorization": f"Bearer {login_other.json()['access_token']}"}
other_me = client.get("/api/auth/me", headers=other_headers).json()
assert other_me["organization"]["id"] == org_other
assert other_me["role"] == "SUADMIN"

# 8. rejected / suspended cannot authenticate
client.post(f"/api/platform/organizations/{org_other}/reject", headers=master_headers)
# already ACTIVE org reject may not flip user; suspend instead
client.post(f"/api/platform/organizations/{org_other}/suspend", headers=master_headers)
suspended = client.post("/api/auth/login", json={"username": "suadmin@otherorg", "password": "OtherPass123!"})
assert suspended.status_code == 403, suspended.text

signup_r = client.post("/api/auth/signup", json={
    "username": "pendinguser", "organization": "rejectme", "password": "RejectPass123!", "confirm_password": "RejectPass123!"
})
org_rej = signup_r.json()["organization_id"]
client.post(f"/api/platform/organizations/{org_rej}/reject", headers=master_headers)
rejected = client.post("/api/auth/login", json={"username": "pendinguser@rejectme", "password": "RejectPass123!"})
assert rejected.status_code == 403, rejected.text

# 13-17 authorization after registering DBs
MetadataService.register_or_update_database(
    "HADIL_DB", "HADIL_DB", "postgresql", connection_uri="postgresql://u:p@h/hadil", organization_id=org_hadil
)
db_manager.current_db_id = "HADIL_DB"
created = client.post("/api/users", json={"username": "john", "password": "JohnPass123!", "role": "ADMIN"}, headers=su_headers)
assert created.status_code == 200, created.text
assert created.json()["username"] == "john@hadil"
john_id = created.json()["user_id"]
viewer = client.post("/api/users", json={"username": "jane", "password": "JanePass123!", "role": "VIEWER"}, headers=su_headers)
assert viewer.status_code == 200, viewer.text
jane_id = viewer.json()["user_id"]
assign = client.post(f"/api/users/{jane_id}/roles", json={"user_id": jane_id, "role": "EDITOR"}, headers=su_headers)
assert assign.status_code == 200, assign.text
assert MetadataService.get_user_role_for_database(jane_id, "HADIL_DB") == "EDITOR"
assert MetadataService.get_user_role_for_database(john_id, "HADIL_DB") == "ADMIN"
assert MetadataService.get_user_role_for_database(su_id, "HADIL_DB") == "SUADMIN"

reactivate = client.post(f"/api/platform/organizations/{org_other}/reactivate", headers=master_headers)
assert reactivate.status_code == 200, reactivate.text
MetadataService.register_or_update_database(
    "OTHER_DB", "OTHER_DB", "postgresql", connection_uri="postgresql://u:p@h/other", organization_id=org_other
)
other_login = client.post("/api/auth/login", json={"username": "suadmin@otherorg", "password": "OtherPass123!"})
other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}
db_manager.current_db_id = "OTHER_DB"
cross_users = client.get("/api/users", headers=other_headers)
assert cross_users.status_code == 200
assert su_id not in [u["id"] for u in cross_users.json()]
db_manager.current_db_id = "HADIL_DB"
cross_create = client.post("/api/users", json={"username": "intruder", "password": "Intruder123!", "role": "VIEWER"}, headers=other_headers)
assert cross_create.status_code == 403, cross_create.text
cross_db = client.post("/api/select-database", json={"db_id": "HADIL_DB"}, headers=other_headers)
assert cross_db.status_code == 403, cross_db.text

# 18. DB ADMIN cannot gain SUADMIN powers
john_login = client.post("/api/auth/login", json={"username": "john@hadil", "password": "JohnPass123!"})
assert john_login.status_code == 200, john_login.text
john_headers = {"Authorization": f"Bearer {john_login.json()['access_token']}"}
db_manager.current_db_id = "HADIL_DB"
john_me = client.get("/api/auth/me", headers=john_headers).json()
assert john_me["role"] == "ADMIN"
assert john_me["organization_role"] is None
assert john_me["authority_type"] == "DATABASE"
assert john_me["platform_role"] is None
john_assign_admin = client.post(f"/api/users/{jane_id}/roles", json={"user_id": jane_id, "role": "ADMIN"}, headers=john_headers)
assert john_assign_admin.status_code == 403, john_assign_admin.text

# 19. MASTER_ADMIN has no customer DB roles
session = metadata_manager.get_session()
try:
    assert session.query(HadilUserDatabaseRole).filter(HadilUserDatabaseRole.user_id == master.id).count() == 0
finally:
    session.close()
master_me2 = client.get("/api/auth/me", headers=master_headers).json()
assert master_me2["role"] == "MASTER_ADMIN"
assert master_me2["authority_type"] == "PLATFORM"

print("CLOUD_AUTH_IDENTITY_OK")
'''
            script = (
                script.replace("__META__", repr(meta_path))
                .replace("__FOLDER__", repr(empty_folder))
                .replace("__BACKEND__", repr(backend_dir))
            )
            env = os.environ.copy()
            env["HADIL_DEPLOYMENT_MODE"] = "cloud"
            env["HADIL_JWT_SECRET"] = "cloud-test-secret-not-default-value"
            env["HADIL_METADATA_DB"] = meta_path
            env["DATABASE_FOLDER"] = empty_folder
            env.pop("HADIL_METADATA_DATABASE_URL", None)
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("CLOUD_AUTH_IDENTITY_OK", result.stdout)
        finally:
            try:
                os.remove(meta_path)
            except OSError:
                pass
            shutil.rmtree(empty_folder, ignore_errors=True)


class TestCloudFrontendAuthorityContract(unittest.TestCase):
    def test_login_and_identity_ui_do_not_conflate_master_and_suadmin(self):
        login_path = os.path.join(REPO_ROOT, "frontend", "src", "components", "LoginScreen.jsx")
        with open(login_path, encoding="utf-8") as handle:
            login_src = handle.read()
        self.assertIn("organization", login_src)
        self.assertIn("onLogin(username.trim(), password, isCloud ? organization.trim() : undefined)", login_src)

        app_path = os.path.join(REPO_ROOT, "frontend", "src", "App.jsx")
        with open(app_path, encoding="utf-8") as handle:
            app_src = handle.read()
        self.assertIn("payload.organization", app_src)
        self.assertIn("authority_type", app_src)
        self.assertIn("canManageOrgUsers", app_src)
        self.assertNotIn("username === 'admin'", app_src)

        users_path = os.path.join(REPO_ROOT, "frontend", "src", "components", "UserManagementView.jsx")
        with open(users_path, encoding="utf-8") as handle:
            users_src = handle.read()
        self.assertIn("isOrgSuAdmin", users_src)
        self.assertNotIn("ADMIN ONLY", users_src)

        sidebar_path = os.path.join(REPO_ROOT, "frontend", "src", "components", "SidebarNav.jsx")
        with open(sidebar_path, encoding="utf-8") as handle:
            sidebar_src = handle.read()
        self.assertIn("isOrgSuAdmin", sidebar_src)
        self.assertIn("isPlatformMaster", sidebar_src)


if __name__ == "__main__":
    unittest.main()
