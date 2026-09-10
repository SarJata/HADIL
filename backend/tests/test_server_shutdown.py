"""
Unit & Integration Tests for Server Shutdown Endpoint & Dual-Mode Runtime Lifecycle.
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

class TestServerShutdownEndpoint(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_unauthenticated_shutdown_rejected(self):
        """Unauthenticated request to /admin/server/shutdown must return 401."""
        res = self.client.post("/api/admin/server/shutdown")
        self.assertEqual(res.status_code, 401)

    def test_get_method_shutdown_rejected(self):
        """GET request to /admin/server/shutdown must return 404 or 405 (Method Not Allowed)."""
        res = self.client.get("/api/admin/server/shutdown")
        self.assertIn(res.status_code, [404, 405])

    def test_non_suadmin_roles_shutdown_forbidden(self):
        """Non-SuAdmin accounts (VIEWER, EDITOR, ADMIN) must receive 403 Forbidden."""
        for role in ["VIEWER", "EDITOR", "ADMIN"]:
            token = create_access_token(user_id=99, username="testuser")
            
            with patch.object(metadata_service, "get_user_role_for_database", return_value=role):
                res = self.client.post(
                    "/api/admin/server/shutdown",
                    headers={"Authorization": f"Bearer {token}"}
                )
                self.assertEqual(
                    res.status_code, 403,
                    f"Role '{role}' should have been rejected with 403, got {res.status_code}"
                )

    def test_suadmin_shutdown_success(self):
        """Authenticated MASTER_ADMIN (SuAdmin) must successfully trigger shutdown."""
        token = create_access_token(user_id=1, username="admin")
        
        with patch.object(metadata_service, "get_user_role_for_database", return_value="MASTER_ADMIN"):
            with patch("hadil_runtime.shutdown_active_runtime") as mock_shutdown:
                res = self.client.post(
                    "/api/admin/server/shutdown",
                    headers={"Authorization": f"Bearer {token}"}
                )
                self.assertEqual(res.status_code, 200)
                self.assertTrue(res.json().get("success"))
                self.assertIn("shutdown initiated", res.json().get("message", "").lower())

if __name__ == "__main__":
    unittest.main()
