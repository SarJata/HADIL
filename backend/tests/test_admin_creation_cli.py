import os
import sys
import unittest

# Force isolated test metadata database
os.environ["HADIL_METADATA_DB"] = "./test_master_admin_creation_isolation.db"

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from main import app
from database.metadata_db import metadata_manager, MetadataBase, HadilUser, HadilSystemRole, verify_password
from services.metadata_service import metadata_service
from cli.admin_console import AdminConsole
from validators.security import decode_access_token, create_access_token
from database.manager import db_manager

client = TestClient(app)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class TestMasterAdminCreationCLI(unittest.TestCase):

    def setUp(self):
        # Reset metadata tables before each test
        db_path = os.environ.get("HADIL_METADATA_DB", "./test_master_admin_creation_isolation.db")
        metadata_manager.db_path = db_path
        metadata_manager.engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        metadata_manager._SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=metadata_manager.engine)
        metadata_manager.init_db()
        MetadataBase.metadata.drop_all(bind=metadata_manager.engine)
        MetadataBase.metadata.create_all(bind=metadata_manager.engine)
        metadata_service.register_or_update_database("sales.db", "Sales Database", "sqlite")

    def tearDown(self):
        pass

    def test_01_fresh_installation_has_zero_master_admins(self):
        """1. Fresh installation has zero Master Administrators."""
        master_info = metadata_service.get_master_admin()
        self.assertIsNone(master_info)

    def test_02_cli_can_create_first_master_admin(self):
        """2. CLI can create the first Master Administrator."""
        user = metadata_service.create_master_admin("root_master", "SuperSecretPass123!")
        self.assertIsNotNone(user)
        self.assertEqual(user.username, "root_master")

    def test_03_master_admin_is_persisted(self):
        """3. Master Administrator is persisted in HadilSystemRole table."""
        metadata_service.create_master_admin("root_master", "SuperSecretPass123!")
        master_info = metadata_service.get_master_admin()
        self.assertIsNotNone(master_info)
        self.assertEqual(master_info["username"], "root_master")

    def test_04_master_admin_survives_restart(self):
        """4. Master Administrator survives application restart (re-querying DB)."""
        metadata_service.create_master_admin("root_master", "SuperSecretPass123!")
        # Simulate restart by acquiring a new session
        db_session = metadata_manager.get_session()
        try:
            sys_role = db_session.query(HadilSystemRole).filter(HadilSystemRole.role == "MASTER_ADMIN").first()
            self.assertIsNotNone(sys_role)
            user = db_session.query(HadilUser).filter(HadilUser.id == sys_role.user_id).first()
            self.assertEqual(user.username, "root_master")
        finally:
            db_session.close()

    def test_05_cli_refuses_second_master_admin(self):
        """5. CLI refuses to create a second Master Administrator."""
        metadata_service.create_master_admin("first_master", "Pass123!")
        with self.assertRaises(ValueError) as ctx:
            metadata_service.create_master_admin("second_master", "Pass456!")
        self.assertIn("A Master Administrator already exists", str(ctx.exception))

    def test_06_second_attempt_does_not_modify_existing(self):
        """6. Attempting to create a second Master Administrator does not modify the existing Master Administrator."""
        metadata_service.create_master_admin("first_master", "Pass123!")
        try:
            metadata_service.create_master_admin("second_master", "NewPass456!")
        except ValueError:
            pass

        master_info = metadata_service.get_master_admin()
        self.assertEqual(master_info["username"], "first_master")

        # Confirm password of first_master is unchanged
        user = metadata_service.get_user_by_username("first_master")
        self.assertTrue(verify_password("Pass123!", user.password_hash))

    def test_07_different_usernames_cannot_circumvent_restriction(self):
        """7. Different usernames (master, root, administrator, sarat) cannot circumvent restriction."""
        metadata_service.create_master_admin("initial_master", "Pass123!")

        bad_usernames = ["master", "root", "administrator", "sarat"]
        for un in bad_usernames:
            with self.assertRaises(ValueError) as ctx:
                metadata_service.create_master_admin(un, "Pass123!")
            self.assertIn("A Master Administrator already exists", str(ctx.exception))

    def test_08_master_admin_password_is_hashed(self):
        """8. Master Administrator password is hashed, never stored as plaintext."""
        user = metadata_service.create_master_admin("root_master", "SuperSecretPass123!")
        self.assertNotEqual(user.password_hash, "SuperSecretPass123!")
        self.assertTrue(user.password_hash.startswith("pbkdf2:sha256:"))

    def test_09_master_admin_authenticates_through_existing_login(self):
        """9. Master Administrator can authenticate through the existing login path."""
        metadata_service.create_master_admin("root_master", "SuperSecretPass123!")

        response = client.post("/api/auth/login", json={
            "username": "root_master",
            "password": "SuperSecretPass123!"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("access_token", data)
        token = data["access_token"]
        payload = decode_access_token(token)
        self.assertEqual(payload["username"], "root_master")

    def test_10_master_admin_receives_root_authority(self):
        """10. Master Administrator receives the intended root administrative authority."""
        user = metadata_service.create_master_admin("root_master", "SuperSecretPass123!")

        # Verify role for database returns MASTER_ADMIN
        role = metadata_service.get_user_role_for_database(user.id, "sales.db")
        self.assertEqual(role, "MASTER_ADMIN")

        # Verify permissions
        self.assertTrue(metadata_service.check_permission(user.id, "sales.db", "READ"))
        self.assertTrue(metadata_service.check_permission(user.id, "sales.db", "DELETE"))
        self.assertTrue(metadata_service.check_permission(user.id, "sales.db", "MANAGE_USERS"))

    def test_11_existing_admin_users_continue_to_work(self):
        """11. Existing ADMIN users continue to work."""
        admin_user = metadata_service.create_user("normal_admin", "Pass123!")
        metadata_service.assign_user_role(admin_user.id, "sales.db", "ADMIN")

        role = metadata_service.get_user_role_for_database(admin_user.id, "sales.db")
        self.assertEqual(role, "ADMIN")
        self.assertTrue(metadata_service.check_permission(admin_user.id, "sales.db", "MANAGE_USERS"))

    def test_12_existing_editor_users_continue_to_work(self):
        """12. Existing EDITOR users continue to work."""
        editor_user = metadata_service.create_user("normal_editor", "Pass123!")
        metadata_service.assign_user_role(editor_user.id, "sales.db", "EDITOR")

        role = metadata_service.get_user_role_for_database(editor_user.id, "sales.db")
        self.assertEqual(role, "EDITOR")
        self.assertTrue(metadata_service.check_permission(editor_user.id, "sales.db", "ADD"))
        self.assertFalse(metadata_service.check_permission(editor_user.id, "sales.db", "DELETE"))

    def test_13_existing_viewer_users_continue_to_work(self):
        """13. Existing VIEWER users continue to work."""
        viewer_user = metadata_service.create_user("normal_viewer", "Pass123!")
        metadata_service.assign_user_role(viewer_user.id, "sales.db", "VIEWER")

        role = metadata_service.get_user_role_for_database(viewer_user.id, "sales.db")
        self.assertEqual(role, "VIEWER")
        self.assertTrue(metadata_service.check_permission(viewer_user.id, "sales.db", "READ"))
        self.assertFalse(metadata_service.check_permission(viewer_user.id, "sales.db", "ADD"))

    def test_14_cli_interaction_flow(self):
        """14. Test CLI interaction flow via mock inputs."""
        inputs = ["master_cli", "y"]
        passwords = ["Secret123!", "Secret123!"]
        printed = []

        def mock_input(prompt):
            return inputs.pop(0)

        def mock_getpass(prompt):
            return passwords.pop(0)

        def mock_print(msg=""):
            printed.append(msg)

        console = AdminConsole(input_func=mock_input, print_func=mock_print, getpass_func=mock_getpass)
        console.master_administrator_setup_menu()

        self.assertTrue(any("created successfully" in p for p in printed))

        # Subsequent menu call on existing master admin
        printed.clear()
        inputs2 = [""]
        console2 = AdminConsole(input_func=lambda p: inputs2.pop(0), print_func=mock_print, getpass_func=mock_getpass)
        console2.master_administrator_setup_menu()
        self.assertTrue(any("Status: CONFIGURED" in p for p in printed))
        self.assertTrue(any("Bootstrap creation is disabled" in p for p in printed))

    def test_15_master_admin_permissions_and_endpoints(self):
        """15. Test MASTER_ADMIN permission inheritance and API endpoints."""
        master = metadata_service.create_master_admin("master_nav", "Pass123!")
        
        # Test auth token login
        login_res = client.post("/api/auth/login", json={"username": "master_nav", "password": "Pass123!"})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Test /api/auth/me returns MASTER_ADMIN role and MANAGE_USERS permission
        me_res = client.get("/api/auth/me", headers=headers)
        self.assertEqual(me_res.status_code, 200)
        me_data = me_res.json()
        self.assertEqual(me_data["role"], "MASTER_ADMIN")
        self.assertIn("MANAGE_USERS", me_data["permissions"])

        # Test /api/users endpoint access for MASTER_ADMIN
        users_res = client.get("/api/users", headers=headers)
        self.assertEqual(users_res.status_code, 200)

        # Test EDITOR user cannot access /api/users
        editor = metadata_service.create_user("editor_user", "Pass123!")
        metadata_service.assign_user_role(editor.id, "sales.db", "EDITOR")
        editor_login = client.post("/api/auth/login", json={"username": "editor_user", "password": "Pass123!"})
        editor_headers = {"Authorization": f"Bearer {editor_login.json()['access_token']}"}
        editor_users_res = client.get("/api/users", headers=editor_headers)
        self.assertEqual(editor_users_res.status_code, 403)

    def test_16_suadmin_not_named_admin_can_assign_admin_on_selected_database(self):
        """MASTER_ADMIN named SuAdmin can grant database-scoped ADMIN on the selected DB."""
        su = metadata_service.create_master_admin("SuAdmin", "SuAdminPass123!")
        metadata_service.register_or_update_database("OtherDb", "Other Database", "sqlite")
        db_manager.current_db_id = "sales.db"

        headers = {"Authorization": f"Bearer {create_access_token(su.id, su.username)}"}
        create_admin = client.post(
            "/api/users",
            json={"username": "db_admin_b", "password": "UserBPass123!", "role": "ADMIN"},
            headers=headers,
        )
        self.assertEqual(create_admin.status_code, 200, create_admin.text)
        user_b_id = create_admin.json()["user_id"]
        self.assertEqual(metadata_service.get_user_role_for_database(user_b_id, "sales.db"), "ADMIN")
        self.assertIsNone(metadata_service.get_user_role_for_database(user_b_id, "OtherDb"))
        self.assertTrue(metadata_service.check_permission(user_b_id, "sales.db", "DELETE"))
        self.assertTrue(metadata_service.check_permission(user_b_id, "sales.db", "MANAGE_USERS"))
        self.assertFalse(metadata_service.check_permission(user_b_id, "OtherDb", "DELETE"))
        self.assertEqual(metadata_service.get_user_role_for_database(su.id, "sales.db"), "MASTER_ADMIN")

        create_editor = client.post(
            "/api/users",
            json={"username": "editor_c", "password": "EditorPass123!", "role": "EDITOR"},
            headers=headers,
        )
        self.assertEqual(create_editor.status_code, 200, create_editor.text)
        editor_id = create_editor.json()["user_id"]
        create_viewer = client.post(
            "/api/users",
            json={"username": "viewer_d", "password": "ViewerPass123!", "role": "VIEWER"},
            headers=headers,
        )
        self.assertEqual(create_viewer.status_code, 200, create_viewer.text)
        viewer_id = create_viewer.json()["user_id"]

        db_admin_headers = {"Authorization": f"Bearer {create_access_token(user_b_id, 'db_admin_b')}"}
        blocked_admin = client.post(
            "/api/users",
            json={"username": "should_fail_admin", "password": "Nope123!", "role": "ADMIN"},
            headers=db_admin_headers,
        )
        self.assertEqual(blocked_admin.status_code, 403, blocked_admin.text)

        editor_headers = {"Authorization": f"Bearer {create_access_token(editor_id, 'editor_c')}"}
        blocked_editor = client.post(
            "/api/users",
            json={"username": "should_fail_editor", "password": "Nope123!", "role": "ADMIN"},
            headers=editor_headers,
        )
        self.assertEqual(blocked_editor.status_code, 403, blocked_editor.text)

        viewer_headers = {"Authorization": f"Bearer {create_access_token(viewer_id, 'viewer_d')}"}
        blocked_viewer = client.post(
            "/api/users",
            json={"username": "should_fail_viewer", "password": "Nope123!", "role": "ADMIN"},
            headers=viewer_headers,
        )
        self.assertEqual(blocked_viewer.status_code, 403, blocked_viewer.text)

        assign_ok = client.post(
            f"/api/users/{editor_id}/roles",
            json={"user_id": editor_id, "role": "VIEWER"},
            headers=headers,
        )
        self.assertEqual(assign_ok.status_code, 200, assign_ok.text)

    def test_17_user_management_ui_uses_master_admin_role_not_username(self):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        path = os.path.join(repo_root, "frontend", "src", "components", "UserManagementView.jsx")
        with open(path, encoding="utf-8") as handle:
            src = handle.read()
        self.assertNotIn("username === 'admin'", src)
        self.assertIn("MASTER_ADMIN", src)
        self.assertIn("Only a Master Admin can assign the ADMIN role to new users.", src)


if __name__ == "__main__":
    unittest.main()
