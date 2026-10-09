"""
Policy RAG authorization: SUADMIN vs database ADMIN, tenant isolation, MASTER_ADMIN bounds.

Covers cloud and desktop deployment modes without packaging an executable.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, ".."))


def _run_script(script: str, env_extra: dict) -> None:
    fd, meta_path = tempfile.mkstemp(suffix="_hadil_policy_auth.db")
    os.close(fd)
    empty_folder = tempfile.mkdtemp(prefix="hadil_policy_dbs_")
    policy_dir = tempfile.mkdtemp(prefix="hadil_policy_files_")
    env = os.environ.copy()
    env.update(env_extra)
    env["HADIL_METADATA_DB"] = meta_path
    env["DATABASE_FOLDER"] = empty_folder
    env["HADIL_POLICY_STORAGE_DIR"] = policy_dir
    env["HADIL_JWT_SECRET"] = "policy-auth-test-secret-not-default"
    env.pop("HADIL_METADATA_DATABASE_URL", None)
    env.pop("RENDER", None)
    try:
        filled = (
            script.replace("__BACKEND__", repr(BACKEND_DIR))
            .replace("__META__", repr(meta_path))
            .replace("__FOLDER__", repr(empty_folder))
            .replace("__POLICY__", repr(policy_dir))
        )
        proc = subprocess.run(
            [sys.executable, "-c", filled],
            cwd=BACKEND_DIR,
            env=env,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise AssertionError(
                f"Script failed ({proc.returncode}):\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
            )
    finally:
        for path in (meta_path, empty_folder, policy_dir):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                elif os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass


CLOUD_SCRIPT = r'''
import os, sys, io
os.environ["HADIL_DEPLOYMENT_MODE"] = "cloud"
os.environ["HADIL_JWT_SECRET"] = "policy-auth-test-secret-not-default"
os.environ["HADIL_METADATA_DB"] = __META__
os.environ["DATABASE_FOLDER"] = __FOLDER__
os.environ["HADIL_POLICY_STORAGE_DIR"] = __POLICY__
os.environ.pop("HADIL_METADATA_DATABASE_URL", None)
sys.path.insert(0, __BACKEND__)

from fastapi.testclient import TestClient
from database.metadata_db import MetadataBase, metadata_manager, HadilUserDatabaseRole
from services.metadata_service import MetadataService
from database.manager import db_manager
from validators.security import create_access_token
from main import app
from unittest.mock import patch

MetadataBase.metadata.drop_all(bind=metadata_manager.engine)
MetadataBase.metadata.create_all(bind=metadata_manager.engine)

master = MetadataService.create_first_admin("platform_master", "MasterPass123!")
client = TestClient(app)
master_headers = {"Authorization": f"Bearer {create_access_token(master.id, master.username)}"}

# Org A
signup_a = client.post("/api/auth/signup", json={
    "username": "admin1", "organization": "orgA", "password": "OrgPass123!", "confirm_password": "OrgPass123!"
})
assert signup_a.status_code == 200, signup_a.text
org_a = signup_a.json()["organization_id"]
assert client.post(f"/api/platform/organizations/{org_a}/approve", headers=master_headers).status_code == 200
login_a = client.post("/api/auth/login", json={"username": "admin1@orga", "password": "OrgPass123!"})
assert login_a.status_code == 200, login_a.text
su_a_id = login_a.json()["user_id"]
su_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

# Org B
signup_b = client.post("/api/auth/signup", json={
    "username": "admin2", "organization": "orgB", "password": "Org2Pass123!", "confirm_password": "Org2Pass123!"
})
assert signup_b.status_code == 200, signup_b.text
org_b = signup_b.json()["organization_id"]
assert client.post(f"/api/platform/organizations/{org_b}/approve", headers=master_headers).status_code == 200
login_b = client.post("/api/auth/login", json={"username": "admin2@orgb", "password": "Org2Pass123!"})
assert login_b.status_code == 200, login_b.text
su_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

MetadataService.register_or_update_database(
    "DB_A1", "DB_A1", "postgresql", connection_uri="postgresql://u:p@h/a1", organization_id=org_a
)
MetadataService.register_or_update_database(
    "DB_B1", "DB_B1", "postgresql", connection_uri="postgresql://u:p@h/b1", organization_id=org_b
)

# Create database-scoped ADMIN / EDITOR / VIEWER in org A
db_manager.current_db_id = "DB_A1"
john = client.post("/api/users", json={"username": "john", "password": "JohnPass123!", "role": "ADMIN"}, headers=su_a)
assert john.status_code == 200, john.text
john_id = john.json().get("user_id") or john.json().get("id")
assert client.post(f"/api/users/{john_id}/roles", json={"user_id": john_id, "role": "ADMIN"}, headers=su_a).status_code == 200

editor = client.post("/api/users", json={"username": "ed", "password": "EdPass123!", "role": "EDITOR"}, headers=su_a)
assert editor.status_code == 200, editor.text
editor_id = editor.json().get("user_id") or editor.json().get("id")
assert client.post(f"/api/users/{editor_id}/roles", json={"user_id": editor_id, "role": "EDITOR"}, headers=su_a).status_code == 200

viewer = client.post("/api/users", json={"username": "vi", "password": "ViPass123!", "role": "VIEWER"}, headers=su_a)
assert viewer.status_code == 200, viewer.text
viewer_id = viewer.json().get("user_id") or viewer.json().get("id")
assert client.post(f"/api/users/{viewer_id}/roles", json={"user_id": viewer_id, "role": "VIEWER"}, headers=su_a).status_code == 200

john_login = client.post("/api/auth/login", json={"username": "john@orga", "password": "JohnPass123!"})
assert john_login.status_code == 200, john_login.text
john_h = {"Authorization": f"Bearer {john_login.json()['access_token']}"}
editor_h = {"Authorization": f"Bearer {client.post('/api/auth/login', json={'username': 'ed@orga', 'password': 'EdPass123!'}).json()['access_token']}"}
viewer_h = {"Authorization": f"Bearer {client.post('/api/auth/login', json={'username': 'vi@orga', 'password': 'ViPass123!'}).json()['access_token']}"}

def _txt(name, body="Company retention policy: keep records 5 years.\n"):
    return (name, body.encode("utf-8"), "text/plain")

# Patch indexing so tests do not require sentence-transformers/FAISS models
with patch("services.policy_rag_service.policy_rag_service.add_document", return_value={"success": True, "status": "INDEXED", "chunk_count": 1}), \
     patch("services.policy_rag_service.policy_rag_service.delete_document", return_value=True):

    # 1) SUADMIN can upload + delete organization (GLOBAL -> ORGANIZATION) policies without active DB
    db_manager.current_db_id = None
    up = client.post(
        "/api/policies/upload",
        headers=su_a,
        files={"file": _txt("org_policy.txt")},
        data={"scope": "GLOBAL"},
    )
    assert up.status_code == 200, up.text
    doc = up.json()["document"]
    assert doc["scope"] == f"ORGANIZATION:{org_a}", doc
    org_doc_id = doc["id"]

    # 2) Database ADMIN cannot obtain organization-level policy management
    db_manager.current_db_id = "DB_A1"
    denied_global = client.post(
        "/api/policies/upload",
        headers=john_h,
        files={"file": _txt("admin_global.txt")},
        data={"scope": "GLOBAL"},
    )
    assert denied_global.status_code == 403, denied_global.text

    denied_delete_org = client.delete(f"/api/policies/{org_doc_id}", headers=john_h)
    assert denied_delete_org.status_code == 403, denied_delete_org.text

    # Database ADMIN can upload/delete DATABASE-scoped policy for their DB
    up_db = client.post(
        "/api/policies/upload",
        headers=john_h,
        files={"file": _txt("db_policy.txt")},
        data={"scope": f"DATABASE:DB_A1"},
    )
    assert up_db.status_code == 200, up_db.text
    db_doc_id = up_db.json()["document"]["id"]
    assert up_db.json()["document"]["scope"] == "DATABASE:DB_A1"
    assert client.delete(f"/api/policies/{db_doc_id}", headers=john_h).status_code == 200

    # 3) Org A cannot access/modify Org B policies
    db_manager.current_db_id = None
    up_b = client.post(
        "/api/policies/upload",
        headers=su_b,
        files={"file": _txt("org_b_policy.txt")},
        data={"scope": "GLOBAL"},
    )
    assert up_b.status_code == 200, up_b.text
    org_b_doc = up_b.json()["document"]["id"]
    assert up_b.json()["document"]["scope"] == f"ORGANIZATION:{org_b}"

    listed_a = client.get("/api/policies", headers=su_a)
    assert listed_a.status_code == 200
    ids_a = {p["id"] for p in listed_a.json()}
    assert org_doc_id in ids_a
    assert org_b_doc not in ids_a

    listed_b = client.get("/api/policies", headers=su_b)
    ids_b = {p["id"] for p in listed_b.json()}
    assert org_b_doc in ids_b
    assert org_doc_id not in ids_b

    cross_delete = client.delete(f"/api/policies/{org_b_doc}", headers=su_a)
    assert cross_delete.status_code == 403, cross_delete.text

    # 4) EDITOR / VIEWER unchanged — cannot manage policies
    for headers in (editor_h, viewer_h):
        db_manager.current_db_id = "DB_A1"
        r = client.post(
            "/api/policies/upload",
            headers=headers,
            files={"file": _txt("nope.txt")},
            data={"scope": "DATABASE:DB_A1"},
        )
        assert r.status_code == 403, r.text
        r2 = client.delete(f"/api/policies/{org_doc_id}", headers=headers)
        assert r2.status_code == 403, r2.text
        # Listing remains allowed for org members (read visibility), but empty of other orgs
        listed = client.get("/api/policies", headers=headers)
        assert listed.status_code == 200
        assert org_b_doc not in {p["id"] for p in listed.json()}

    # 5) MASTER_ADMIN restrictions intact
    master_up = client.post(
        "/api/policies/upload",
        headers=master_headers,
        files={"file": _txt("master.txt")},
        data={"scope": "GLOBAL"},
    )
    assert master_up.status_code == 403, master_up.text
    master_list = client.get("/api/policies", headers=master_headers)
    assert master_list.status_code == 200
    assert master_list.json() == []

    # 6) Direct unauthorized API requests rejected (unauthenticated)
    assert client.post(
        "/api/policies/upload",
        files={"file": _txt("anon.txt")},
        data={"scope": "GLOBAL"},
    ).status_code == 401
    assert client.delete(f"/api/policies/{org_doc_id}").status_code == 401

    # SUADMIN can delete own org policy
    db_manager.current_db_id = None
    assert client.delete(f"/api/policies/{org_doc_id}", headers=su_a).status_code == 200

    # Config: SUADMIN yes, DB ADMIN no
    assert client.get("/api/policies/config", headers=su_a).status_code == 200
    db_manager.current_db_id = "DB_A1"
    assert client.get("/api/policies/config", headers=john_h).status_code == 403

print("CLOUD_POLICY_AUTH_OK")
'''


DESKTOP_SCRIPT = r'''
import os, sys
os.environ["HADIL_DEPLOYMENT_MODE"] = "desktop"
os.environ["HADIL_JWT_SECRET"] = "policy-auth-test-secret-not-default"
os.environ["HADIL_METADATA_DB"] = __META__
os.environ["DATABASE_FOLDER"] = __FOLDER__
os.environ["HADIL_POLICY_STORAGE_DIR"] = __POLICY__
os.environ.pop("HADIL_METADATA_DATABASE_URL", None)
sys.path.insert(0, __BACKEND__)

from fastapi.testclient import TestClient
from database.metadata_db import MetadataBase, metadata_manager
from services.metadata_service import MetadataService
from database.manager import db_manager
from validators.security import create_access_token
from main import app
from unittest.mock import patch

MetadataBase.metadata.drop_all(bind=metadata_manager.engine)
MetadataBase.metadata.create_all(bind=metadata_manager.engine)

master = MetadataService.create_first_admin("desk_master", "MasterPass123!")
MetadataService.register_or_update_database("sales.db", "Sales", "sqlite")
admin = MetadataService.create_user("db_admin", "AdminPass123!")
MetadataService.assign_user_role(admin.id, "sales.db", "ADMIN")
editor = MetadataService.create_user("db_editor", "EditorPass123!")
MetadataService.assign_user_role(editor.id, "sales.db", "EDITOR")
viewer = MetadataService.create_user("db_viewer", "ViewerPass123!")
MetadataService.assign_user_role(viewer.id, "sales.db", "VIEWER")

client = TestClient(app)
db_manager.current_db_id = "sales.db"
master_h = {"Authorization": f"Bearer {create_access_token(master.id, master.username)}"}
admin_h = {"Authorization": f"Bearer {create_access_token(admin.id, admin.username)}"}
editor_h = {"Authorization": f"Bearer {create_access_token(editor.id, editor.username)}"}
viewer_h = {"Authorization": f"Bearer {create_access_token(viewer.id, viewer.username)}"}

def _txt(name, body="Desktop policy body.\n"):
    return (name, body.encode("utf-8"), "text/plain")

with patch("services.policy_rag_service.policy_rag_service.add_document", return_value={"success": True, "status": "INDEXED", "chunk_count": 1}), \
     patch("services.policy_rag_service.policy_rag_service.delete_document", return_value=True):

    # MASTER_ADMIN and ADMIN can manage GLOBAL policies on desktop
    up_m = client.post("/api/policies/upload", headers=master_h, files={"file": _txt("m.txt")}, data={"scope": "GLOBAL"})
    assert up_m.status_code == 200, up_m.text
    assert up_m.json()["document"]["scope"] == "GLOBAL"
    mid = up_m.json()["document"]["id"]

    up_a = client.post("/api/policies/upload", headers=admin_h, files={"file": _txt("a.txt")}, data={"scope": "GLOBAL"})
    assert up_a.status_code == 200, up_a.text
    aid = up_a.json()["document"]["id"]

    # EDITOR / VIEWER rejected
    for headers in (editor_h, viewer_h):
        assert client.post(
            "/api/policies/upload", headers=headers, files={"file": _txt("x.txt")}, data={"scope": "GLOBAL"}
        ).status_code == 403

    assert client.delete(f"/api/policies/{mid}", headers=master_h).status_code == 200
    assert client.delete(f"/api/policies/{aid}", headers=admin_h).status_code == 200
    assert client.get("/api/policies/config", headers=master_h).status_code == 200

print("DESKTOP_POLICY_AUTH_OK")
'''


class TestPolicyRAGAuthorization(unittest.TestCase):
    def test_cloud_suadmin_admin_isolation_and_master_bounds(self):
        _run_script(CLOUD_SCRIPT, {"HADIL_DEPLOYMENT_MODE": "cloud"})

    def test_desktop_admin_and_editor_bounds(self):
        _run_script(DESKTOP_SCRIPT, {"HADIL_DEPLOYMENT_MODE": "desktop"})

    def test_frontend_recognizes_suadmin_for_policy_management(self):
        path = os.path.join(REPO_ROOT, "frontend", "src", "components", "PolicyManagementView.jsx")
        with open(path, encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("const isAdmin = userRole === 'ADMIN';", src)
        self.assertIn("canManagePolicies", src)
        self.assertIn("SUADMIN", src)
        self.assertIn("isOrgSuAdmin", src)


class TestPolicyScopeHelpers(unittest.TestCase):
    def test_normalize_and_retrieval_scopes_unit(self):
        # Lightweight unit checks that do not require FastAPI app boot when importable.
        sys.path.insert(0, BACKEND_DIR)
        os.environ.setdefault("HADIL_DEPLOYMENT_MODE", "desktop")
        from services.metadata_service import MetadataService

        self.assertEqual(MetadataService.clean_policy_scope("GLOBAL"), "GLOBAL")
        self.assertEqual(MetadataService.clean_policy_scope("sales.db"), "DATABASE:sales.db")
        self.assertEqual(MetadataService.clean_policy_scope("DATABASE:x"), "DATABASE:x")
        scopes = MetadataService.policy_retrieval_scopes("sales.db")
        self.assertIn("GLOBAL", scopes)
        self.assertIn("DATABASE:sales.db", scopes)


if __name__ == "__main__":
    unittest.main()
