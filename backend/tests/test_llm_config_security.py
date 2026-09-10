"""
Targeted Tests for SuAdmin LLM API Key Management & Masking Security Requirements.
"""

import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import os
import sys

# Ensure backend directory is in path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from main import app
from validators.security import create_access_token
from services.metadata_service import metadata_service

class TestLLMConfigSecurity(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_get_llm_config_never_exposes_raw_api_key(self):
        """GET /admin/llm-config must return boolean status flags and never return raw API keys."""
        token = create_access_token(user_id=1, username="admin")
        with patch.object(metadata_service, "get_user_role_for_database", return_value="MASTER_ADMIN"):
            res = self.client.get("/api/admin/llm-config", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(res.status_code, 200)
            data = res.json()
            
            for key in ["generator", "verifier"]:
                self.assertIn(key, data)
                self.assertIn("api_key_configured", data[key])
                self.assertNotIn("api_key", data[key])
                self.assertNotIn("api_key_encrypted", data[key])

    def test_post_llm_config_updates_key_and_returns_only_boolean_status(self):
        """POST /admin/llm-config updates provider and API key over HTTPS/auth header and returns only metadata."""
        token = create_access_token(user_id=1, username="admin")
        payload = {
            "generator": {
                "provider_type": "openai",
                "api_key": "sk-test-secret-key-12345"
            },
            "verifier": {
                "provider_type": "openai",
                "api_key": "sk-test-verifier-key-67890"
            }
        }
        with patch.object(metadata_service, "get_user_role_for_database", return_value="MASTER_ADMIN"):
            res = self.client.post(
                "/api/admin/llm-config",
                json=payload,
                headers={"Authorization": f"Bearer {token}"}
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertTrue(data["generator"]["api_key_configured"])
            self.assertTrue(data["verifier"]["api_key_configured"])
            self.assertNotIn("sk-test-secret-key-12345", str(data))

    def test_non_suadmin_cannot_access_llm_config(self):
        """Non-SuAdmin (ADMIN, EDITOR, VIEWER) cannot view or post LLM configs."""
        for role in ["ADMIN", "EDITOR", "VIEWER"]:
            token = create_access_token(user_id=99, username="testuser")
            with patch.object(metadata_service, "get_user_role_for_database", return_value=role):
                get_res = self.client.get("/api/admin/llm-config", headers={"Authorization": f"Bearer {token}"})
                self.assertEqual(get_res.status_code, 403)
                
                post_res = self.client.post(
                    "/api/admin/llm-config",
                    json={"generator": {"provider_type": "openai"}, "verifier": {"provider_type": "openai"}},
                    headers={"Authorization": f"Bearer {token}"}
                )
                self.assertEqual(post_res.status_code, 403)

if __name__ == "__main__":
    unittest.main()
