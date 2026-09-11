"""Cloud V1 AI provider policy, organization selection, env credentials, and RBAC."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class TestCloudAIProviderConfig(unittest.TestCase):
    def test_platform_policy_org_selection_credentials_and_rbac(self):
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        fd, meta_path = tempfile.mkstemp(suffix="_hadil_ai.db")
        os.close(fd)
        empty_folder = tempfile.mkdtemp(prefix="hadil_ai_dbs_")
        try:
            script = r'''
import json
import os
import sys
os.environ["HADIL_DEPLOYMENT_MODE"] = "cloud"
os.environ["HADIL_JWT_SECRET"] = "cloud-test-secret-not-default-value"
os.environ["HADIL_METADATA_DB"] = __META__
os.environ["DATABASE_FOLDER"] = __FOLDER__
os.environ.pop("HADIL_METADATA_DATABASE_URL", None)
os.environ["HADIL_GEMINI_API_KEY"] = "test-env-gemini-key-not-real"
os.environ["HADIL_OPENAI_API_KEY"] = "test-env-openai-key-not-real"
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("HADIL_ANTHROPIC_API_KEY", None)
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("CLAUDE_API_KEY", None)
sys.path.insert(0, __BACKEND__)
from fastapi.testclient import TestClient
from database.metadata_db import MetadataBase, metadata_manager
from services.metadata_service import MetadataService, metadata_service
from database.manager import db_manager
from validators.security import create_access_token
from ai_modules.providers import get_llm_provider, GeminiProvider
from services.ai_provider_service import AIProviderConfigError, resolve_cloud_llm_runtime
from main import app

SECRET_MARKERS = (
    "test-env-gemini-key-not-real",
    "test-env-openai-key-not-real",
    "attacker-submitted-key",
    "db-stored-evil-key",
    "HADIL_GEMINI_API_KEY",
    "HADIL_OPENAI_API_KEY",
)

def assert_no_secrets(payload):
    blob = payload if isinstance(payload, str) else json.dumps(payload)
    assert "api_key_encrypted" not in blob.lower()
    for marker in SECRET_MARKERS:
        assert marker not in blob, blob

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
client.post(f"/api/platform/organizations/{org1}/approve", headers=master_headers)
login = client.post("/api/auth/login", json={"username": "admin1@org1", "password": "OrgPass123!"})
su1_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
su1_id = login.json()["user_id"]

signup2 = client.post("/api/auth/signup", json={
    "username": "admin2", "organization": "org2", "password": "Org2Pass123!", "confirm_password": "Org2Pass123!"
})
org2 = signup2.json()["organization_id"]
client.post(f"/api/platform/organizations/{org2}/approve", headers=master_headers)
login2 = client.post("/api/auth/login", json={"username": "admin2@org2", "password": "Org2Pass123!"})
su2_id = login2.json()["user_id"]
su2_headers = {"Authorization": f"Bearer {create_access_token(su2_id, 'admin2@org2')}"}

MetadataService.register_or_update_database(
    "DB1", "DB1", "postgresql", connection_uri="postgresql://u:p@h/db1", organization_id=org1
)
MetadataService.register_or_update_database(
    "ORG2DB", "ORG2DB", "postgresql", connection_uri="postgresql://u:p@h/org2", organization_id=org2
)
assert MetadataService.get_user_role_for_database(master.id, "DB1") is None

# A. Platform SuAdmin can enable/disable a provider
plat_get = client.get("/api/platform/ai-providers", headers=master_headers)
assert plat_get.status_code == 200, plat_get.text
assert_no_secrets(plat_get.json())
names = [p["provider"] for p in plat_get.json()["providers"]]
assert "gemini" in names and "openai" in names and "claude" in names
disable = client.put("/api/platform/ai-providers", json={
    "providers": [
        {"provider": "gemini", "enabled": True, "model": "gemini-2.5-flash"},
        {"provider": "openai", "enabled": False, "model": "gpt-4o"},
        {"provider": "claude", "enabled": False},
        {"provider": "sarvam", "enabled": False},
    ]
}, headers=master_headers)
assert disable.status_code == 200, disable.text
assert_no_secrets(disable.json())
by_name = {p["provider"]: p for p in disable.json()["providers"]}
assert by_name["gemini"]["enabled"] is True
assert by_name["openai"]["enabled"] is False

# Desktop LLM admin endpoints are closed in cloud
assert client.get("/api/admin/llm-config", headers=master_headers).status_code == 403

# J. DB ADMIN / org SUADMIN cannot modify platform policy
assert client.get("/api/platform/ai-providers", headers=su1_headers).status_code == 403
assert client.put("/api/platform/ai-providers", json={"providers": [{"provider": "openai", "enabled": True}]}, headers=su1_headers).status_code == 403

db_manager.current_db_id = "DB1"
john = client.post("/api/users", json={"username": "john", "password": "JohnPass123!", "role": "ADMIN"}, headers=su1_headers)
assert john.status_code == 200, john.text
john_id = john.json()["user_id"]
jane = client.post("/api/users", json={"username": "jane", "password": "JanePass123!", "role": "EDITOR"}, headers=su1_headers)
jane_id = jane.json()["user_id"]
bob = client.post("/api/users", json={"username": "bob", "password": "BobPass123!", "role": "VIEWER"}, headers=su1_headers)
bob_id = bob.json()["user_id"]
john_headers = {"Authorization": f"Bearer {create_access_token(john_id, 'john@org1')}"}
jane_headers = {"Authorization": f"Bearer {create_access_token(jane_id, 'jane@org1')}"}
bob_headers = {"Authorization": f"Bearer {create_access_token(bob_id, 'bob@org1')}"}

# C. Organization DB Admin can select an enabled provider
db_manager.current_db_id = "DB1"
sel = client.put("/api/organization/ai-provider", json={"provider": "gemini"}, headers=john_headers)
assert sel.status_code == 200, sel.text
assert sel.json()["provider"] == "gemini"
assert "model" not in sel.json()
assert_no_secrets(sel.json())
avail = [p["provider"] for p in sel.json()["available_providers"]]
assert "gemini" in avail
assert "openai" not in avail

view = client.get("/api/organization/ai-provider", headers=john_headers)
assert view.status_code == 200
assert view.json()["provider"] == "gemini"
assert "model" not in view.json()
assert_no_secrets(view.json())

# B. Disabled provider cannot be selected
blocked = client.put("/api/organization/ai-provider", json={"provider": "openai"}, headers=john_headers)
assert blocked.status_code == 400, blocked.text
assert "gemini" in json.dumps(client.get("/api/organization/ai-provider", headers=john_headers).json())

unknown = client.put("/api/organization/ai-provider", json={"provider": "not-a-real-vendor"}, headers=john_headers)
assert unknown.status_code == 400

# D / E. Organization DB Admin cannot select a model or cause a submitted API key to be used
ignored = client.put("/api/organization/ai-provider", json={
    "provider": "gemini",
    "model": "attacker-model",
    "api_key": "attacker-submitted-key",
    "temperature": 1.5,
}, headers=john_headers)
assert ignored.status_code == 200, ignored.text
assert ignored.json()["provider"] == "gemini"
assert "model" not in ignored.json()
assert_no_secrets(ignored.json())

# Competing DB-stored key must not be used in cloud
metadata_service.set_llm_config(
    "generator", provider_type="openai", model="gpt-attacker", api_key="db-stored-evil-key"
)

# F. Backend resolves credential from server environment
db_manager.current_db_id = "DB1"
runtime = resolve_cloud_llm_runtime(database_id="DB1")
assert runtime.provider_type == "gemini"
assert runtime.model == "gemini-2.5-flash"
assert runtime.api_key == "test-env-gemini-key-not-real"
assert runtime.api_key != "attacker-submitted-key"
assert runtime.api_key != "db-stored-evil-key"
provider = get_llm_provider("generator")
assert isinstance(provider, GeminiProvider)
assert provider.api_key == "test-env-gemini-key-not-real"
assert provider.model == "gemini-2.5-flash"
verifier = get_llm_provider("verifier")
assert isinstance(verifier, GeminiProvider)
assert verifier.api_key == "test-env-gemini-key-not-real"

# G. Missing provider environment variable produces a safe error
os.environ.pop("HADIL_GEMINI_API_KEY", None)
try:
    resolve_cloud_llm_runtime(database_id="DB1")
    raise AssertionError("expected missing credential to fail")
except AIProviderConfigError as err:
    msg = str(err)
    assert "unavailable" in msg.lower()
    for marker in SECRET_MARKERS:
        assert marker not in msg
try:
    get_llm_provider("generator")
    raise AssertionError("expected missing credential to fail")
except RuntimeError as err:
    msg = str(err)
    assert "unavailable" in msg.lower()
    for marker in SECRET_MARKERS:
        assert marker not in msg
os.environ["HADIL_GEMINI_API_KEY"] = "test-env-gemini-key-not-real"

# I. Organization A cannot modify Organization B
db_manager.current_db_id = "ORG2DB"
cross = client.put("/api/organization/ai-provider", json={"provider": "gemini"}, headers=john_headers)
assert cross.status_code == 403, cross.text
db_manager.current_db_id = "DB1"
org2_sel = client.put("/api/organization/ai-provider", json={"provider": "gemini"}, headers=su2_headers)
assert org2_sel.status_code == 200
org1_still = client.get("/api/organization/ai-provider", headers=john_headers)
assert org1_still.json()["provider"] == "gemini"

# Re-enable openai for org2 isolation check, then confirm org1 unchanged after org2 switch
client.put("/api/platform/ai-providers", json={"providers": [{"provider": "openai", "enabled": True}]}, headers=master_headers)
org2_openai = client.put("/api/organization/ai-provider", json={"provider": "openai"}, headers=su2_headers)
assert org2_openai.status_code == 200, org2_openai.text
assert client.get("/api/organization/ai-provider", headers=john_headers).json()["provider"] == "gemini"

# K. VIEWER/EDITOR cannot perform privileged AI configuration changes
assert client.get("/api/organization/ai-provider", headers=jane_headers).status_code == 403
assert client.put("/api/organization/ai-provider", json={"provider": "gemini"}, headers=jane_headers).status_code == 403
assert client.get("/api/organization/ai-provider", headers=bob_headers).status_code == 403
assert client.put("/api/organization/ai-provider", json={"provider": "gemini"}, headers=bob_headers).status_code == 403
assert client.put("/api/platform/ai-providers", json={"providers": [{"provider": "gemini", "enabled": False}]}, headers=jane_headers).status_code == 403
assert client.put("/api/platform/ai-providers", json={"providers": [{"provider": "gemini", "enabled": False}]}, headers=bob_headers).status_code == 403

# L. Platform MASTER_ADMIN remains platform-level
assert MetadataService.get_user_role_for_database(master.id, "DB1") is None
master_org = client.put("/api/organization/ai-provider", json={"provider": "openai"}, headers=master_headers)
assert master_org.status_code == 403
assert client.get("/api/organization/ai-provider", headers=master_headers).status_code == 403
assert client.get("/api/users", headers=master_headers).status_code == 403
assert client.get("/api/organization/ai-provider", headers=john_headers).json()["provider"] == "gemini"

# H. Responses never contain the API key (also platform GET after keys set)
plat = client.get("/api/platform/ai-providers", headers=master_headers)
assert_no_secrets(plat.json())
assert plat.json()["providers"][0].get("credential_configured") in (True, False)

print("CLOUD_AI_PROVIDER_OK")
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
            self.assertIn("CLOUD_AI_PROVIDER_OK", result.stdout)
        finally:
            try:
                os.remove(meta_path)
            except OSError:
                pass
            shutil.rmtree(empty_folder, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
