"""Cloud V1 organization signup, approval, tenant isolation, and database-scoped RBAC."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class TestCloudOrganizationLifecycle(unittest.TestCase):
    def test_signup_approval_tenant_isolation_and_db_roles(self):
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        fd, meta_path = tempfile.mkstemp(suffix="_hadil_org.db")
        os.close(fd)
        empty_folder = tempfile.mkdtemp(prefix="hadil_org_dbs_")
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
from database.metadata_db import (
    HadilUser, HadilUserDatabaseRole, HadilDatabase, HadilOrganization, MetadataBase, metadata_manager,
)
from services.metadata_service import MetadataService
from database.manager import db_manager
from validators.security import create_access_token
from main import app

MetadataBase.metadata.drop_all(bind=metadata_manager.engine)
MetadataBase.metadata.create_all(bind=metadata_manager.engine)
master = MetadataService.create_first_admin("platform_master", "MasterPass123!")
client = TestClient(app)
master_headers = {"Authorization": f"Bearer {create_access_token(master.id, master.username)}"}

signup = client.post("/api/auth/signup", json={
    "username": "admin1", "organization": "org1", "password": "OrgPass123!", "confirm_password": "OrgPass123!"
})
assert signup.status_code == 200, signup.text
org1 = signup.json()["organization_id"]
assert signup.json()["account_status"] == "PENDING"
assert signup.json()["organization_role"] == "SUADMIN"
assert MetadataService.get_setup_status()["setup_required"] is False

blocked = client.post("/api/auth/login", json={"username": "admin1@org1", "password": "OrgPass123!"})
assert blocked.status_code == 403

pending = client.get("/api/platform/organizations?status=PENDING", headers=master_headers)
assert pending.status_code == 200
assert any(o["id"] == org1 for o in pending.json()["organizations"])

approve = client.post(f"/api/platform/organizations/{org1}/approve", headers=master_headers)
assert approve.status_code == 200, approve.text
assert approve.json()["suadmin_role"] == "SUADMIN"

login = client.post("/api/auth/login", json={"username": "admin1@org1", "password": "OrgPass123!"})
assert login.status_code == 200, login.text
su1_id = login.json()["user_id"]
su1_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
me = client.get("/api/auth/me", headers=su1_headers)
assert me.json()["role"] == "SUADMIN"
assert me.json()["authority_type"] == "ORGANIZATION"
assert me.json()["organization_role"] == "SUADMIN"
assert me.json()["platform_role"] is None
assert me.json()["database_role"] is None
assert me.json()["organization"]["id"] == org1

# Zero databases is valid; SUADMIN can still list org users
dbs = metadata_manager.get_session()
try:
    assert dbs.query(HadilDatabase).filter(HadilDatabase.organization_id == org1).count() == 0
    assert dbs.query(HadilDatabase).filter(HadilDatabase.id == "default_db").count() == 0
    assert dbs.query(HadilUserDatabaseRole).filter(HadilUserDatabaseRole.user_id == master.id).count() == 0
    assert dbs.query(HadilUserDatabaseRole).filter(HadilUserDatabaseRole.user_id == su1_id).count() == 0
finally:
    dbs.close()
listed = client.get("/api/users", headers=su1_headers)
assert listed.status_code == 200, listed.text
assert any(u["id"] == su1_id for u in listed.json())
master_users = client.get("/api/users", headers=master_headers)
assert master_users.status_code == 403, master_users.text

MetadataService.register_or_update_database(
    "DB1", "DB1", "postgresql", connection_uri="postgresql://u:p@h/db1", organization_id=org1
)
MetadataService.register_or_update_database(
    "DB2", "DB2", "postgresql", connection_uri="postgresql://u:p@h/db2", organization_id=org1
)
assert MetadataService.get_user_role_for_database(su1_id, "DB1") == "SUADMIN"
assert MetadataService.get_user_role_for_database(master.id, "DB1") is None

signup2 = client.post("/api/auth/signup", json={
    "username": "admin2", "organization": "org2", "password": "Org2Pass123!", "confirm_password": "Org2Pass123!"
})
assert signup2.status_code == 200, signup2.text
org2 = signup2.json()["organization_id"]
client.post(f"/api/platform/organizations/{org2}/approve", headers=master_headers)
login2 = client.post("/api/auth/login", json={"username": "admin2@org2", "password": "Org2Pass123!"})
su2_id = login2.json()["user_id"]
su2_headers = {"Authorization": f"Bearer {create_access_token(su2_id, 'admin2@org2')}"}
MetadataService.register_or_update_database(
    "ORG2DB", "ORG2DB", "postgresql", connection_uri="postgresql://u:p@h/org2", organization_id=org2
)

db_manager.current_db_id = "DB1"
john = client.post("/api/users", json={"username": "john", "password": "JohnPass123!", "role": "ADMIN"}, headers=su1_headers)
assert john.status_code == 200, john.text
assert john.json()["username"] == "john@org1"
john_id = john.json()["user_id"]
jane = client.post("/api/users", json={"username": "jane", "password": "JanePass123!", "role": "EDITOR"}, headers=su1_headers)
assert jane.status_code == 200, jane.text
jane_id = jane.json()["user_id"]
bob = client.post("/api/users", json={"username": "bob", "password": "BobPass123!", "role": "VIEWER"}, headers=su1_headers)
assert bob.status_code == 200, bob.text

db_manager.current_db_id = "DB2"
assign_john_viewer = client.post(f"/api/users/{john_id}/roles", json={"user_id": john_id, "role": "VIEWER"}, headers=su1_headers)
assert assign_john_viewer.status_code == 200, assign_john_viewer.text
sarah = client.post("/api/users", json={"username": "sarah", "password": "SarahPass123!", "role": "ADMIN"}, headers=su1_headers)
assert sarah.status_code == 200, sarah.text
sarah_id = sarah.json()["user_id"]

assert MetadataService.get_user_role_for_database(john_id, "DB1") == "ADMIN"
assert MetadataService.get_user_role_for_database(john_id, "DB2") == "VIEWER"
assert MetadataService.get_user_role_for_database(sarah_id, "DB2") == "ADMIN"
assert MetadataService.get_user_role_for_database(jane_id, "DB1") == "EDITOR"

# Cross-org: org1 cannot use org2 database id
db_manager.current_db_id = "ORG2DB"
cross_switch = client.post("/api/select-database", json={"db_id": "ORG2DB"}, headers=su1_headers)
assert cross_switch.status_code == 403, cross_switch.text
cross_role = client.post(f"/api/users/{john_id}/roles", json={"user_id": john_id, "role": "ADMIN"}, headers=su1_headers)
assert cross_role.status_code == 403, cross_role.text
cross_create = client.post("/api/users", json={"username": "alice", "password": "AlicePass123!", "role": "VIEWER"}, headers=su1_headers)
assert cross_create.status_code == 403, cross_create.text

# Org1 cannot create users for org2 login
db_manager.current_db_id = "DB1"
spoof = client.post("/api/users", json={"username": "alice@org2", "password": "AlicePass123!", "role": "VIEWER"}, headers=su1_headers)
assert spoof.status_code == 400, spoof.text

master_create = client.post("/api/users", json={"username": "evil", "password": "Nope123!", "role": "MASTER_ADMIN"}, headers=su1_headers)
assert master_create.status_code == 403, master_create.text

# Suspended user cannot use APIs
MetadataService.set_user_account_status(john_id, "SUSPENDED", actor_org_id=org1)
john_headers = {"Authorization": f"Bearer {create_access_token(john_id, 'john@org1')}"}
suspended_me = client.get("/api/auth/me", headers=john_headers)
assert suspended_me.status_code == 403, suspended_me.text
suspended_login = client.post("/api/auth/login", json={"username": "john@org1", "password": "JohnPass123!"})
assert suspended_login.status_code == 403

print("CLOUD_ORG_RBAC_OK")
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
            self.assertIn("CLOUD_ORG_RBAC_OK", result.stdout)
        finally:
            try:
                os.remove(meta_path)
            except OSError:
                pass
            shutil.rmtree(empty_folder, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
