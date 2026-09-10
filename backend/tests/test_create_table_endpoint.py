import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from main import app
from database.manager import db_manager
from validators.security import create_access_token
from services.metadata_service import MetadataService
from database.metadata_db import metadata_manager, MetadataBase, HadilUser, HadilUserDatabaseRole
from sqlalchemy import inspect

class TestCreateTableEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        MetadataBase.metadata.create_all(bind=metadata_manager.engine)
        cls.client = TestClient(app)

    def setUp(self):
        # Create test database connection (temp SQLite file)
        import tempfile
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp_db.close()
        db_manager.custom_connection_uri = f"sqlite:///{self.tmp_db.name}"
        db_manager.current_db_id = "test_create_table_db.db"
        db_manager.current_db_name = "Test Table DB"
        db_manager._initialize_engine()



        # Set up test users & roles in Hadil Metadata DB
        db = metadata_manager.get_session()
        try:
            db.query(HadilUserDatabaseRole).delete()
            db.query(HadilUser).delete()
            db.commit()

            admin_user = HadilUser(id=1, username="test_admin", password_hash="hash")
            viewer_user = HadilUser(id=2, username="test_viewer", password_hash="hash")
            db.add_all([admin_user, viewer_user])
            db.commit()

            MetadataService.assign_user_role(1, "test_create_table_db.db", "ADMIN")
            MetadataService.assign_user_role(2, "test_create_table_db.db", "VIEWER")
        finally:
            db.close()

        self.admin_token = create_access_token(1, "test_admin")
        self.viewer_token = create_access_token(2, "test_viewer")

    def tearDown(self):
        # Clean up metadata record & temp file
        db = metadata_manager.get_session()
        try:
            db.query(HadilDatabase).filter(HadilDatabase.id == "test_create_table_db.db").delete()
            db.commit()
        except Exception:
            pass
        finally:
            db.close()

        if hasattr(self, "tmp_db") and os.path.exists(self.tmp_db.name):
            try:
                os.remove(self.tmp_db.name)
            except Exception:
                pass


    def test_valid_table_creation(self):
        payload = {
            "table_name": "employees_test",
            "columns": [
                {"name": "id", "type": "INTEGER", "primary_key": True},
                {"name": "name", "type": "VARCHAR", "length": 150, "primary_key": False},
                {"name": "salary", "type": "FLOAT", "primary_key": False}
            ]
        }
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        res = self.client.post("/api/create-table", json=payload, headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get("success"))

        # Verify table exists in engine
        inspector = inspect(db_manager.engine)
        tables = inspector.get_table_names()
        self.assertIn("employees_test", tables)

        columns = {c["name"]: c for c in inspector.get_columns("employees_test")}
        self.assertIn("id", columns)
        self.assertIn("name", columns)
        self.assertIn("salary", columns)

    def test_varchar_with_explicit_length(self):
        payload = {
            "table_name": "departments_test",
            "columns": [
                {"name": "dept_id", "type": "INTEGER", "primary_key": True},
                {"name": "dept_name", "type": "VARCHAR", "length": 100, "primary_key": False}
            ]
        }
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        res = self.client.post("/api/create-table", json=payload, headers=headers)
        self.assertEqual(res.status_code, 200)

        inspector = inspect(db_manager.engine)
        columns = {c["name"]: c for c in inspector.get_columns("departments_test")}
        self.assertIn("dept_name", columns)

    def test_duplicate_column_names_rejected(self):
        payload = {
            "table_name": "bad_table_dup",
            "columns": [
                {"name": "id", "type": "INTEGER", "primary_key": True},
                {"name": "id", "type": "VARCHAR", "length": 50, "primary_key": False}
            ]
        }
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        res = self.client.post("/api/create-table", json=payload, headers=headers)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Duplicate column name", res.json().get("detail", ""))

    def test_invalid_table_name_rejected(self):
        payload = {
            "table_name": "invalid-table-name!",
            "columns": [
                {"name": "id", "type": "INTEGER", "primary_key": True}
            ]
        }
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        res = self.client.post("/api/create-table", json=payload, headers=headers)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid table name", res.json().get("detail", ""))

    def test_invalid_column_name_rejected(self):
        payload = {
            "table_name": "valid_table",
            "columns": [
                {"name": "bad column space", "type": "INTEGER", "primary_key": True}
            ]
        }
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        res = self.client.post("/api/create-table", json=payload, headers=headers)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid column name", res.json().get("detail", ""))

    def test_missing_table_name_rejected(self):
        payload = {
            "table_name": "   ",
            "columns": [
                {"name": "id", "type": "INTEGER", "primary_key": True}
            ]
        }
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        res = self.client.post("/api/create-table", json=payload, headers=headers)
        self.assertEqual(res.status_code, 400)

    def test_missing_columns_rejected(self):
        payload = {
            "table_name": "no_cols_table",
            "columns": []
        }
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        res = self.client.post("/api/create-table", json=payload, headers=headers)
        self.assertEqual(res.status_code, 400)
        self.assertIn("At least one column is required", res.json().get("detail", ""))

    def test_multiple_primary_keys_rejected(self):
        payload = {
            "table_name": "multi_pk_table",
            "columns": [
                {"name": "id1", "type": "INTEGER", "primary_key": True},
                {"name": "id2", "type": "INTEGER", "primary_key": True}
            ]
        }
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        res = self.client.post("/api/create-table", json=payload, headers=headers)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Multiple primary keys selected", res.json().get("detail", ""))

    def test_generate_form_create_table_user(self):
        res = self.client.post("/api/generate-form", json={"query": "Create a table user"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("operation"), "CREATE_TABLE")
        self.assertEqual(data.get("target_table_name"), "user")
        self.assertNotIn("error", data)

    def test_foreign_key_table_creation_success(self):
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        # 1. Create parent table 'users'
        res_user = self.client.post("/api/create-table", json={
            "table_name": "users",
            "columns": [
                {"name": "id", "type": "INTEGER", "primary_key": True},
                {"name": "name", "type": "VARCHAR", "length": 100, "primary_key": False}
            ]
        }, headers=headers)
        self.assertEqual(res_user.status_code, 200)

        # 2. Create parent table 'products'
        res_prod = self.client.post("/api/create-table", json={
            "table_name": "products",
            "columns": [
                {"name": "id", "type": "INTEGER", "primary_key": True},
                {"name": "title", "type": "VARCHAR", "length": 100, "primary_key": False}
            ]
        }, headers=headers)
        self.assertEqual(res_prod.status_code, 200)

        # 3. Create child table 'orders' referencing 'users.id' and 'products.id'
        res_orders = self.client.post("/api/create-table", json={
            "table_name": "orders",
            "columns": [
                {"name": "id", "type": "INTEGER", "primary_key": True},
                {"name": "user_id", "type": "INTEGER", "primary_key": False},
                {"name": "product_id", "type": "INTEGER", "primary_key": False},
                {"name": "amount", "type": "FLOAT", "primary_key": False}
            ],
            "foreign_keys": [
                {
                    "column": "user_id",
                    "ref_table": "users",
                    "ref_column": "id",
                    "on_delete": "CASCADE"
                },
                {
                    "column": "product_id",
                    "ref_table": "products",
                    "ref_column": "id",
                    "on_delete": "NO ACTION"
                }
            ]
        }, headers=headers)
        self.assertEqual(res_orders.status_code, 200)
        self.assertTrue(res_orders.json().get("success"))

        # 4. Verify actual foreign key constraints in database via inspector
        inspector = inspect(db_manager.engine)
        fks = inspector.get_foreign_keys("orders")
        self.assertEqual(len(fks), 2)
        ref_tables = [fk["referred_table"] for fk in fks]
        self.assertIn("users", ref_tables)
        self.assertIn("products", ref_tables)

    def test_foreign_key_invalid_local_column_rejected(self):
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.client.post("/api/create-table", json={
            "table_name": "parents",
            "columns": [{"name": "id", "type": "INTEGER", "primary_key": True}]
        }, headers=headers)

        res = self.client.post("/api/create-table", json={
            "table_name": "children_invalid_local",
            "columns": [{"name": "id", "type": "INTEGER", "primary_key": True}],
            "foreign_keys": [{
                "column": "non_existent_local_col",
                "ref_table": "parents",
                "ref_column": "id"
            }]
        }, headers=headers)
        self.assertEqual(res.status_code, 400)
        self.assertIn("does not exist in new table", res.json().get("detail", ""))

    def test_foreign_key_invalid_ref_table_rejected(self):
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        res = self.client.post("/api/create-table", json={
            "table_name": "children_invalid_table",
            "columns": [
                {"name": "id", "type": "INTEGER", "primary_key": True},
                {"name": "parent_id", "type": "INTEGER", "primary_key": False}
            ],
            "foreign_keys": [{
                "column": "parent_id",
                "ref_table": "non_existent_table",
                "ref_column": "id"
            }]
        }, headers=headers)
        self.assertEqual(res.status_code, 400)
        self.assertIn("does not exist in active database", res.json().get("detail", ""))

    def test_foreign_key_invalid_ref_column_rejected(self):
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.client.post("/api/create-table", json={
            "table_name": "existing_parent",
            "columns": [{"name": "id", "type": "INTEGER", "primary_key": True}]
        }, headers=headers)

    def test_schema_table_details_endpoint(self):
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        # 1. Create table 'Orders' with columns
        res_orders = self.client.post("/api/create-table", json={
            "table_name": "Orders",
            "columns": [
                {"name": "id", "type": "INTEGER", "primary_key": True},
                {"name": "user_id", "type": "INTEGER", "primary_key": False},
                {"name": "amount", "type": "FLOAT", "primary_key": False}
            ]
        }, headers=headers)
        self.assertEqual(res_orders.status_code, 200)

        # 2. Fetch table details schema endpoint
        res_details = self.client.get("/api/schema/table-details", headers=headers)
        self.assertEqual(res_details.status_code, 200)
        tables_data = res_details.json().get("tables", {})
        self.assertIn("Orders", tables_data)
        self.assertEqual(tables_data["Orders"], ["id", "user_id", "amount"])

        # 3. Create 'Users' table referencing existing 'Orders.id'
        res_users = self.client.post("/api/create-table", json={
            "table_name": "Users",
            "columns": [
                {"name": "id", "type": "INTEGER", "primary_key": True},
                {"name": "order_id", "type": "INTEGER", "primary_key": False}
            ],
            "foreign_keys": [
                {
                    "column": "order_id",
                    "ref_table": "Orders",
                    "ref_column": "id"
                }
            ]
        }, headers=headers)
        self.assertEqual(res_users.status_code, 200)

if __name__ == "__main__":
    unittest.main()
