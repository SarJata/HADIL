import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from sqlalchemy import text
from main import app
from database.manager import db_manager
from services.metadata_service import metadata_service

client = TestClient(app)

class TestSchemaMetadataRouting(unittest.TestCase):
    def test_schema_metadata_routing_and_isolation(self):
        # Setup test user and auth
        user = metadata_service.get_user_by_username("admin")
        if not user:
            user = metadata_service.create_user("admin", "admin123")
        
        from validators.security import create_access_token
        token = create_access_token(user.id, user.username)
        headers = {"Authorization": f"Bearer {token}"}

        # Database A: 2 tables (Orders, Users)
        import tempfile
        tmp_a = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp_a.close()
        db_manager.custom_connection_uri = f"sqlite:///{tmp_a.name}"
        db_manager.current_db_id = "test_db_a.db"
        db_manager._initialize_engine()
        
        metadata_service.assign_user_role(user.id, "test_db_a.db", "ADMIN")

        with db_manager.engine.connect() as conn:
            conn.execute(text("CREATE TABLE Orders (id INT PRIMARY KEY, val FLOAT)"))
            conn.execute(text("CREATE TABLE Users (id INT PRIMARY KEY, name VARCHAR(50))"))
            conn.commit()

        # 1. Test "How many tables does my database have?" on DB A
        gen_res = client.post("/api/generate-sql", json={"query": "How many tables does my database have?"}, headers=headers)
        self.assertEqual(gen_res.status_code, 200)
        gen_data = gen_res.json()
        self.assertIn("-- HADIL SCHEMA METADATA: TABLE_COUNT", gen_data["sql"])

        exec_res = client.post("/api/execute-query", json={"sql": gen_data["sql"], "natural_query": "How many tables does my database have?"}, headers=headers)
        self.assertEqual(exec_res.status_code, 200)
        exec_data = exec_res.json()
        self.assertTrue(exec_data["success"])
        self.assertEqual(exec_data["data"], [{"table_count": 2}])
        self.assertEqual(exec_data["interpreted_answer"], "Your database has 2 tables.")

        # 2. Test "What tables are in my database?" on DB A
        gen_res = client.post("/api/generate-sql", json={"query": "What tables are in my database?"}, headers=headers)
        self.assertEqual(gen_res.status_code, 200)
        gen_data = gen_res.json()
        exec_res = client.post("/api/execute-query", json={"sql": gen_data["sql"], "natural_query": "What tables are in my database?"}, headers=headers)
        self.assertEqual(exec_res.status_code, 200)
        exec_data = exec_res.json()
        self.assertTrue(exec_data["success"])
        table_names = [r["table_name"] for r in exec_data["data"]]
        self.assertEqual(sorted(table_names), ["Orders", "Users"])

        # 3. Test "What columns does Orders have?" on DB A
        exec_res = client.post("/api/execute-query", json={"sql": "-- HADIL SCHEMA METADATA: COLUMN_LIST for Orders", "natural_query": "What columns does Orders have?"}, headers=headers)
        self.assertEqual(exec_res.status_code, 200)
        exec_data = exec_res.json()
        self.assertTrue(exec_data["success"])
        col_names = [r["column_name"] for r in exec_data["data"]]
        self.assertEqual(sorted(col_names), ["id", "val"])

        # 4. Test DATA query path: "How many orders are in Orders?"
        from unittest.mock import patch
        with patch("routes.api.generate_sql_from_text", return_value=("SELECT COUNT(*) FROM Orders;", "Count orders", False, None)):
            gen_res = client.post("/api/generate-sql", json={"query": "How many orders are in Orders?"}, headers=headers)
            self.assertEqual(gen_res.status_code, 200)
            gen_data = gen_res.json()
            self.assertNotIn("-- HADIL SCHEMA METADATA", gen_data["sql"])
            self.assertIn("SELECT", gen_data["sql"].upper())


        # Database B: Switch to DB B with 1 table (Products)
        tmp_b = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp_b.close()
        db_manager.custom_connection_uri = f"sqlite:///{tmp_b.name}"
        db_manager.current_db_id = "test_db_b.db"
        db_manager._initialize_engine()

        metadata_service.assign_user_role(user.id, "test_db_b.db", "ADMIN")

        with db_manager.engine.connect() as conn:
            conn.execute(text("CREATE TABLE Products (id INT PRIMARY KEY, name VARCHAR(50))"))
            conn.commit()

        # 5. Isolation verification: Repeat table count on DB B -> MUST return 1 table
        exec_res = client.post("/api/execute-query", json={"sql": "-- HADIL SCHEMA METADATA: TABLE_COUNT", "natural_query": "How many tables does my database have?"}, headers=headers)
        self.assertEqual(exec_res.status_code, 200)
        exec_data = exec_res.json()
        self.assertTrue(exec_data["success"])
        self.assertEqual(exec_data["data"], [{"table_count": 1}])
        self.assertEqual(exec_data["interpreted_answer"], "Your database has 1 table.")

    def test_system_tables_exclusion_and_raw_sql(self):
        user = metadata_service.get_user_by_username("admin")
        if not user:
            user = metadata_service.create_user("admin", "admin123")
        from validators.security import create_access_token
        token = create_access_token(user.id, user.username)
        headers = {"Authorization": f"Bearer {token}"}

        import tempfile
        tmp_sys = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp_sys.close()
        db_manager.custom_connection_uri = f"sqlite:///{tmp_sys.name}"
        db_manager.current_db_id = "test_sys_db.db"
        db_manager._initialize_engine()

        metadata_service.assign_user_role(user.id, "test_sys_db.db", "ADMIN")

        with db_manager.engine.connect() as conn:
            conn.execute(text("CREATE TABLE Users (id INT PRIMARY KEY, name VARCHAR(50))"))
            conn.execute(text("CREATE TABLE Orders (id INT PRIMARY KEY, total FLOAT)"))
            conn.execute(text("CREATE TABLE hadil_query_history (id INT PRIMARY KEY, query TEXT)"))
            conn.execute(text("CREATE TABLE hadil_database_insights (id INT PRIMARY KEY, summary TEXT)"))
            conn.commit()

        from database.schema_extractor import get_filtered_tables, HADIL_SYSTEM_TABLES
        self.assertIn("hadil_query_history", HADIL_SYSTEM_TABLES)
        self.assertIn("hadil_database_insights", HADIL_SYSTEM_TABLES)

        tables = get_filtered_tables(db_manager.engine)
        self.assertEqual(len(tables), 2)
        self.assertEqual(sorted(tables), ["Orders", "Users"])

        # Discovered tables endpoint returns exactly 2 tables
        dt_res = client.get("/api/schema/tables", headers=headers)
        self.assertEqual(dt_res.status_code, 200)
        self.assertEqual(sorted(dt_res.json()["tables"]), ["Orders", "Users"])

        # Table details endpoint returns only 2 user tables
        td_res = client.get("/api/schema/table-details", headers=headers)
        self.assertEqual(td_res.status_code, 200)
        self.assertEqual(sorted(list(td_res.json()["tables"].keys())), ["Orders", "Users"])

        # "How many tables does my database have?" returns 2
        exec_res = client.post("/api/execute-query", json={"sql": "-- HADIL SCHEMA METADATA: TABLE_COUNT", "natural_query": "How many tables does my database have?"}, headers=headers)
        self.assertEqual(exec_res.json()["data"], [{"table_count": 2}])
        self.assertEqual(exec_res.json()["interpreted_answer"], "Your database has 2 tables.")

        # "List my tables" returns Users and Orders only
        list_res = client.post("/api/execute-query", json={"sql": "-- HADIL SCHEMA METADATA: TABLE_LIST", "natural_query": "List my tables"}, headers=headers)
        res_tables = [r["table_name"] for r in list_res.json()["data"]]
        self.assertEqual(sorted(res_tables), ["Orders", "Users"])

        # Raw SQL counting sqlite_master returns ALL 4 tables without modification
        raw_sql = "SELECT COUNT(*) as total FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        raw_res = client.post("/api/execute-query", json={"sql": raw_sql, "is_direct_sql": True, "is_verified": True}, headers=headers)
        self.assertEqual(raw_res.status_code, 200)
        self.assertTrue(raw_res.json().get("success"), f"Raw query failed: {raw_res.json()}")
        self.assertEqual(raw_res.json()["data"][0]["total"], 4)

    def test_empty_database_returns_zero(self):
        user = metadata_service.get_user_by_username("admin")
        if not user:
            user = metadata_service.create_user("admin", "admin123")
        from validators.security import create_access_token
        token = create_access_token(user.id, user.username)
        headers = {"Authorization": f"Bearer {token}"}

        import tempfile
        tmp_emp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp_emp.close()
        db_manager.custom_connection_uri = f"sqlite:///{tmp_emp.name}"
        db_manager.current_db_id = "test_empty_db.db"
        db_manager._initialize_engine()

        metadata_service.assign_user_role(user.id, "test_empty_db.db", "ADMIN")

        from database.schema_extractor import get_filtered_tables
        tables = get_filtered_tables(db_manager.engine)
        self.assertEqual(len(tables), 0)

        exec_res = client.post("/api/execute-query", json={"sql": "-- HADIL SCHEMA METADATA: TABLE_COUNT", "natural_query": "How many tables do I have?"}, headers=headers)
        self.assertEqual(exec_res.json()["data"], [{"table_count": 0}])
        self.assertEqual(exec_res.json()["interpreted_answer"], "Your database has 0 tables.")

if __name__ == "__main__":
    unittest.main()
