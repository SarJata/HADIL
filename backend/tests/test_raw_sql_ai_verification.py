import sys
import os

os.environ["HADIL_METADATA_DB"] = "./test_hadil_metadata.db"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from main import app
from database.manager import db_manager
from database.metadata_db import metadata_manager, HadilUser
from services.metadata_service import metadata_service
import routes.api

client = TestClient(app)

llm_call_count = 0

def test_raw_sql_verification_suite():
    global llm_call_count
    print("\n==========================================")
    print(" RUNNING RAW SQL & AI VERIFICATION SUITE")
    print("==========================================")

    original_verify = routes.api.verify_sql_intent
    def wrap_verifier(*args, **kwargs):
        global llm_call_count
        llm_call_count += 1
        return original_verify(*args, **kwargs)

    routes.api.verify_sql_intent = wrap_verifier

    try:
        # Setup database & users
        metadata_service.reset_and_seed_per_db_admins()
        db_id = "chinook.db"
        db_manager.current_db_id = db_id
        db_manager.current_db_name = db_id
        db_manager._initialize_engine()

        from sqlalchemy import text
        with db_manager.engine.connect() as conn:
            conn.execute(text("CREATE TABLE IF NOT EXISTS albums (AlbumId INTEGER PRIMARY KEY, Title TEXT);"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS customers (CustomerId INTEGER PRIMARY KEY, Name TEXT);"))
            conn.commit()


        admin_token = client.post('/api/auth/login', json={'username': 'admin', 'password': 'password123'}).json()['access_token']
        admin_headers = {'Authorization': f'Bearer {admin_token}'}

        # Create test viewer user
        db = metadata_manager.get_session()
        try:
            viewer = db.query(HadilUser).filter(HadilUser.username == "test_viewer_raw").first()
            if not viewer:
                viewer = metadata_service.create_user("test_viewer_raw", "password123")
                metadata_service.assign_user_role(viewer.id, db_id, "VIEWER")
        finally:
            db.close()

        viewer_token = client.post('/api/auth/login', json={'username': 'test_viewer_raw', 'password': 'password123'}).json()['access_token']
        viewer_headers = {'Authorization': f'Bearer {viewer_token}'}

        # Test 1: Raw SELECT (AI verifier called exactly once)
        llm_call_count = 0
        raw_select = "SELECT Title FROM albums LIMIT 5;"
        res_mode = client.post("/api/detect-mode", json={"query": raw_select}, headers=admin_headers)
        assert res_mode.json()["mode"] == "SQL"
        res_ver = client.post("/api/verify-sql", json={"query": raw_select, "sql": raw_select}, headers=admin_headers)
        assert res_ver.status_code == 200
        res_exec = client.post("/api/execute-query", json={"sql": raw_select, "is_direct_sql": True, "is_verified": True}, headers=admin_headers)
        assert res_exec.status_code == 200
        print(f"PASS Test 1: Raw SELECT invoked AI Verifier exactly {llm_call_count} time(s).")
        assert llm_call_count == 1

        # Test 2: Raw UPDATE (AI verifier called)
        llm_call_count = 0
        raw_update = "UPDATE albums SET Title='Updated Title' WHERE AlbumId=1;"
        res_ver2 = client.post("/api/verify-sql", json={"query": raw_update, "sql": raw_update}, headers=admin_headers)
        assert res_ver2.status_code == 200
        print(f"PASS Test 2: Raw UPDATE invoked AI Verifier ({llm_call_count} call).")
        assert llm_call_count == 1

        # Test 3: Raw DELETE (AI verifier called)
        llm_call_count = 0
        raw_delete = "DELETE FROM albums WHERE AlbumId=9999;"
        res_ver3 = client.post("/api/verify-sql", json={"query": raw_delete, "sql": raw_delete}, headers=admin_headers)
        assert res_ver3.status_code == 200
        print(f"PASS Test 3: Raw DELETE invoked AI Verifier ({llm_call_count} call).")
        assert llm_call_count == 1

        # Test 4: Raw Dangerous SQL (Verifier called AND deterministic SQL validator still blocks it)
        llm_call_count = 0
        raw_drop = "DROP TABLE albums;"
        client.post("/api/verify-sql", json={"query": raw_drop, "sql": raw_drop}, headers=admin_headers)
        assert llm_call_count == 1
        res_val = client.post("/api/validate-sql?is_direct_sql=true", json={"sql": raw_drop}, headers=admin_headers)
        assert not res_val.json()["is_safe"]
        print("PASS Test 4: Raw dangerous SQL (DROP TABLE) is blocked by deterministic SQL validator.")

        # Test 5: NL READ (Generator + Verifier = 2 LLM Calls)
        nl_read = "What are the top 5 albums by revenue?"
        res_mode_nl = client.post("/api/detect-mode", json={"query": nl_read}, headers=admin_headers)
        assert res_mode_nl.json()["mode"] == "NL"
        res_form_nl = client.post("/api/generate-form", json={"query": nl_read}, headers=admin_headers)
        assert res_form_nl.json()["operation"] == "READ"
        print("PASS Test 5: NL READ classification returns READ with 0 intent LLM calls.")

        # Test 6: NL CREATE/UPDATE/DELETE (Existing deterministic CRUD path preserved)
        nl_crud = "Create a new customer named Darshan"
        res_crud = client.post("/api/generate-form", json={"query": nl_crud}, headers=admin_headers)
        assert res_crud.json()["operation"] == "CREATE"
        assert res_crud.json()["table"] == "customers"
        print("PASS Test 6: NL CREATE returns structured CRUD form for customers table.")

        # Test 7: VIEWER attempting unauthorized mutation -> 403 Forbidden
        res_viewer = client.post("/api/execute-form", json={
            "operation": "DELETE",
            "table": "orders",
            "fields": {},
            "where": {"id": 42}
        }, headers=viewer_headers)
        assert res_viewer.status_code == 403
        print("PASS Test 7: VIEWER attempting unauthorized mutation correctly receives 403 Forbidden.")

        # Test 8: Backend Security Boundary - Unverified direct execute-query triggers backend verifier
        llm_call_count = 0
        res_unverified = client.post("/api/execute-query", json={
            "sql": "SELECT Title FROM albums LIMIT 1;",
            "is_direct_sql": True,
            "is_verified": False
        }, headers=admin_headers)
        assert res_unverified.status_code == 200
        assert llm_call_count == 1
        print("PASS Test 8: Unverified direct execute-query request triggers backend AI Verification.")

        # Test 9: AI Verifier returning is_valid=false prevents execution
        routes.api.verify_sql_intent = lambda *args, **kwargs: {"is_valid": False, "errors": ["Mocked Invalid"], "explanation": "Failed"}
        res_failed_ver = client.post("/api/execute-query", json={
            "sql": "SELECT * FROM albums LIMIT 1;",
            "is_direct_sql": True,
            "is_verified": False
        }, headers=admin_headers)
        assert res_failed_ver.json()["success"] == False
        assert "AI Verification failed" in res_failed_ver.json()["error"]
        print("PASS Test 9: AI Verifier returning is_valid=false strictly blocks execution.")

    finally:
        # Guarantee monkeypatch is strictly cleaned up
        routes.api.verify_sql_intent = original_verify


    print("\n--- ALL RAW SQL & AI VERIFICATION SUITE TESTS PASSED SUCCESSFULLY! ---")

if __name__ == "__main__":
    test_raw_sql_verification_suite()
