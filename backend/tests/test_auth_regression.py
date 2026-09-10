import os
import sys
import unittest

# Force isolated test metadata database
os.environ["HADIL_METADATA_DB"] = "./test_hadil_auth_regression.db"

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from main import app
from database.metadata_db import metadata_manager, MetadataBase, HadilUser, verify_password
from services.metadata_service import metadata_service
from validators.security import decode_access_token

client = TestClient(app)

class TestAuthenticationSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # 1. Reset metadata tables on isolated DB
        db_path = os.environ.get("HADIL_METADATA_DB", "./test_hadil_auth_regression.db")
        metadata_manager.db_path = db_path
        metadata_manager.engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        metadata_manager._SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=metadata_manager.engine)
        metadata_manager.init_db()
        MetadataBase.metadata.drop_all(bind=metadata_manager.engine)
        MetadataBase.metadata.create_all(bind=metadata_manager.engine)

        # 2. Register a default database
        metadata_service.register_or_update_database("sales.db", "Sales Database", "sqlite")

        # 3. Create test users
        cls.valid_user = metadata_service.create_user("valid_user", "ValidPassword123!")
        metadata_service.assign_user_role(cls.valid_user.id, "sales.db", "ADMIN")

    def test_01_valid_username_and_password_succeeds(self):
        """1. Valid username + valid password -> login succeeds."""
        response = client.post("/api/auth/login", json={
            "username": "valid_user",
            "password": "ValidPassword123!"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["username"], "valid_user")
        self.assertEqual(data["token_type"], "bearer")

    def test_02_valid_username_incorrect_password_fails(self):
        """2. Valid username + incorrect password -> login fails."""
        response = client.post("/api/auth/login", json={
            "username": "valid_user",
            "password": "WrongPassword123!"
        })
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid username or password.")

    def test_03_unknown_username_fails(self):
        """3. Unknown username + password -> login fails."""
        response = client.post("/api/auth/login", json={
            "username": "non_existent_user",
            "password": "ValidPassword123!"
        })
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid username or password.")

    def test_04_empty_username_validation_failure(self):
        """4. Empty username -> validation failure."""
        response = client.post("/api/auth/login", json={
            "username": "",
            "password": "ValidPassword123!"
        })
        self.assertEqual(response.status_code, 422)

    def test_05_empty_password_validation_failure(self):
        """5. Empty password -> validation failure."""
        response = client.post("/api/auth/login", json={
            "username": "valid_user",
            "password": ""
        })
        self.assertEqual(response.status_code, 422)

    def test_06_successful_login_returns_jwt(self):
        """6. Successful login returns a JWT containing user identity."""
        response = client.post("/api/auth/login", json={
            "username": "valid_user",
            "password": "ValidPassword123!"
        })
        self.assertEqual(response.status_code, 200)
        token = response.json()["access_token"]
        payload = decode_access_token(token)
        self.assertEqual(payload["username"], "valid_user")
        self.assertEqual(payload["sub"], str(self.valid_user.id))

    def test_07_jwt_can_authenticate_protected_endpoint(self):
        """7. JWT can authenticate a protected endpoint (/api/auth/me)."""
        login_res = client.post("/api/auth/login", json={
            "username": "valid_user",
            "password": "ValidPassword123!"
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        me_res = client.get("/api/auth/me", headers=headers)
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()["username"], "valid_user")

    def test_08_user_lookup_uses_hadil_metadata_db(self):
        """8. User lookup uses HADIL metadata DB."""
        user = metadata_service.get_user_by_username("valid_user")
        self.assertIsNotNone(user)
        self.assertEqual(user.username, "valid_user")
        self.assertTrue(verify_password("ValidPassword123!", user.password_hash))

if __name__ == "__main__":
    unittest.main()
