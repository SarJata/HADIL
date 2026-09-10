"""
Targeted Tests for SuAdmin SQLite Database Registration (Existing File Path vs Upload File).
"""

import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import os
import sys
import tempfile
import sqlite3

# Ensure backend directory is in path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from main import app
from validators.security import create_access_token
from services.metadata_service import metadata_service
from utils.path_resolver import get_default_database_folder

class TestSQLiteDatabaseImport(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

        # Create a valid temporary SQLite file
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        conn = sqlite3.connect(self.temp_db_path)
        conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT);")
        conn.execute("INSERT INTO test_table VALUES (1, 'Test Item');")
        conn.commit()
        conn.close()

        # Create an invalid file
        self.temp_invalid_fd, self.temp_invalid_path = tempfile.mkstemp(suffix=".txt")
        with open(self.temp_invalid_path, "wb") as f:
            f.write(b"NOT A SQLITE FILE HEADER")

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

        os.close(self.temp_invalid_fd)
        if os.path.exists(self.temp_invalid_path):
            os.remove(self.temp_invalid_path)

    # --- Authorization Tests ---
    def test_unauthenticated_requests_rejected(self):
        res1 = self.client.post("/api/admin/databases/register-path", json={"file_path": self.temp_db_path})
        self.assertEqual(res1.status_code, 401)

        res2 = self.client.post("/api/admin/databases/upload", files={"file": ("test.db", b"data")})
        self.assertEqual(res2.status_code, 401)

    def test_non_suadmin_roles_forbidden(self):
        for role in ["ADMIN", "EDITOR", "VIEWER"]:
            token = create_access_token(user_id=10, username="regular_user")
            with patch.object(metadata_service, "get_user_role_for_database", return_value=role):
                res1 = self.client.post(
                    "/api/admin/databases/register-path",
                    json={"file_path": self.temp_db_path},
                    headers={"Authorization": f"Bearer {token}"}
                )
                self.assertEqual(res1.status_code, 403)

                res2 = self.client.post(
                    "/api/admin/databases/upload",
                    files={"file": ("test.db", b"data")},
                    headers={"Authorization": f"Bearer {token}"}
                )
                self.assertEqual(res2.status_code, 403)

    # --- Method 1: Existing File Path Tests ---
    def test_register_existing_sqlite_path_success(self):
        token = create_access_token(user_id=1, username="admin")
        with patch.object(metadata_service, "get_user_role_for_database", return_value="MASTER_ADMIN"):
            res = self.client.post(
                "/api/admin/databases/register-path",
                json={"file_path": self.temp_db_path, "display_name": "My Custom Test DB"},
                headers={"Authorization": f"Bearer {token}"}
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertTrue(data["success"])
            self.assertEqual(data["database"]["name"], "My Custom Test DB")
            self.assertEqual(data["database"]["database_type"], "sqlite")

    def test_register_nonexistent_or_invalid_file_rejected(self):
        token = create_access_token(user_id=1, username="admin")
        with patch.object(metadata_service, "get_user_role_for_database", return_value="MASTER_ADMIN"):
            # Non-existent file
            res1 = self.client.post(
                "/api/admin/databases/register-path",
                json={"file_path": "C:\\non_existent_folder\\fake.db"},
                headers={"Authorization": f"Bearer {token}"}
            )
            self.assertEqual(res1.status_code, 400)
            self.assertIn("does not exist", res1.json()["detail"])

            # Non-SQLite header
            res2 = self.client.post(
                "/api/admin/databases/register-path",
                json={"file_path": self.temp_invalid_path},
                headers={"Authorization": f"Bearer {token}"}
            )
            self.assertEqual(res2.status_code, 400)
            self.assertIn("not a valid SQLite", res2.json()["detail"])

    # --- Method 2: Upload Database File Tests ---
    def test_upload_sqlite_database_success(self):
        token = create_access_token(user_id=1, username="admin")
        with open(self.temp_db_path, "rb") as f:
            file_bytes = f.read()

        with patch.object(metadata_service, "get_user_role_for_database", return_value="MASTER_ADMIN"):
            res = self.client.post(
                "/api/admin/databases/upload",
                files={"file": ("uploaded_sales.db", file_bytes, "application/octet-stream")},
                data={"display_name": "Uploaded Sales Database"},
                headers={"Authorization": f"Bearer {token}"}
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertTrue(data["success"])
            self.assertEqual(data["database"]["name"], "Uploaded Sales Database")
            self.assertEqual(data["database"]["storage_mode"], "MANAGED_UPLOAD")

            # Verify file exists under HADIL runtime databases folder
            storage_folder = get_default_database_folder()
            uploaded_id = data["database"]["id"]
            expected_dest = os.path.join(storage_folder, uploaded_id)
            self.assertTrue(os.path.exists(expected_dest))

            # Clean up uploaded file
            if os.path.exists(expected_dest):
                os.remove(expected_dest)

    def test_upload_invalid_file_cleaned_up(self):
        token = create_access_token(user_id=1, username="admin")
        invalid_bytes = b"CORRUPTED FILE CONTENTS"

        with patch.object(metadata_service, "get_user_role_for_database", return_value="MASTER_ADMIN"):
            res = self.client.post(
                "/api/admin/databases/upload",
                files={"file": ("bad_file.db", invalid_bytes, "application/octet-stream")},
                headers={"Authorization": f"Bearer {token}"}
            )
            self.assertEqual(res.status_code, 400)
            self.assertIn("not a valid SQLite", res.json()["detail"])

if __name__ == "__main__":
    unittest.main()
