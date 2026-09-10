import sys
import os
import time
import json

os.environ["HADIL_METADATA_DB"] = "./test_hadil_metadata.db"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from main import app
from database.manager import db_manager
from database.metadata_db import metadata_manager, HadilUser
from services.metadata_service import metadata_service
from ai_modules.providers import GeminiProvider

client = TestClient(app)

# Counter for tracking actual LLM API calls during test
llm_call_count = 0

def mock_gemini_generate_json(self, system_prompt: str, user_prompt: str):
    global llm_call_count
    llm_call_count += 1
    if "verifier" in system_prompt.lower() or "verify" in system_prompt.lower() or "intent" in system_prompt.lower():
        return {"is_safe": True, "reason": "Query matches intent"}
    return {"sql": "SELECT * FROM Album LIMIT 5;"}

def test_e2e_2_llm_calls_and_mutation_security():
    global llm_call_count
    print("\n==========================================")
    print(" RUNNING END-TO-END PIPELINE & CALL COUNT TEST")
    print("==========================================")

    orig_generate_json = GeminiProvider.generate_json
    try:
        # Monkeypatch GeminiProvider.generate_json to count calls offline
        GeminiProvider.generate_json = mock_gemini_generate_json

        # Setup database & users
        metadata_service.reset_and_seed_per_db_admins()
        db_id = "chinook.db"
        db_manager.current_db_id = db_id
        db_manager.current_db_name = db_id

        # Configure Gemini for generator and verifier
        admin_token = client.post('/api/auth/login', json={'username': 'admin', 'password': 'password123'}).json()['access_token']
        admin_headers = {'Authorization': f'Bearer {admin_token}'}

        # Create test viewer user
        db = metadata_manager.get_session()
        try:
            viewer = db.query(HadilUser).filter(HadilUser.username == "test_viewer_e2e").first()
            if not viewer:
                viewer = metadata_service.create_user("test_viewer_e2e", "password123")
                metadata_service.assign_user_role(viewer.id, db_id, "VIEWER")
        finally:
            db.close()

        viewer_token = client.post('/api/auth/login', json={'username': 'test_viewer_e2e', 'password': 'password123'}).json()['access_token']
        viewer_headers = {'Authorization': f'Bearer {viewer_token}'}

        metadata_service.set_llm_config("generator", "gemini", model="gemini-2.5-flash")
        metadata_service.set_llm_config("verifier", "gemini", model="gemini-2.5-flash")

        # 1. Measure LLM Call Count for ONE Normal Query: "What are the top 5 selling albums by revenue?"
        llm_call_count = 0
        query_str = "What are the top 5 selling albums by revenue?"
        start_time = time.time()

        # Step 1: Mode Detection (Local)
        res_mode = client.post("/api/detect-mode", json={"query": query_str}, headers=admin_headers)
        assert res_mode.json()["mode"] == "NL"

        # Step 2: Form/Intent Detection (Deterministic - 0 LLM Calls!)
        res_form = client.post("/api/generate-form", json={"query": query_str}, headers=admin_headers)
        assert res_form.json()["operation"] == "READ"

        # Step 3: SQL Generation (LLM Call #1)
        res_gen = client.post("/api/generate-sql", json={"query": query_str}, headers=admin_headers)
        assert res_gen.status_code == 200
        sql = res_gen.json()["sql"]

        # Step 4: SQL Verification (LLM Call #2)
        res_ver = client.post("/api/verify-sql", json={"query": query_str, "sql": sql}, headers=admin_headers)
        assert res_ver.status_code == 200

        # Step 5: SQL Validation (Deterministic AST - 0 LLM Calls)
        res_val = client.post("/api/validate-sql", json={"sql": sql}, headers=admin_headers)
        assert res_val.status_code == 200

        # Step 6: Query Execution (SQLAlchemy - 0 LLM Calls)
        res_exec = client.post("/api/execute-query", json={"sql": sql, "natural_query": query_str, "is_verified": True}, headers=admin_headers)
        assert res_exec.status_code == 200

        total_latency = round(time.time() - start_time, 3)

        print(f"Total LLM Call Count for Query: {llm_call_count} (EXPECTED: 2)")
        print(f"Total Pipeline Execution Latency: {total_latency}s")
        assert llm_call_count == 2, f"Expected exactly 2 LLM calls, but recorded {llm_call_count}!"

        # 2. Test Mutation Security & RBAC Enforcement
        print("\n--- Testing Mutation Security & RBAC ---")
        del_query = "Delete order 42."
        
        # Deterministic intent classification flags it as DELETE
        res_del_form = client.post("/api/generate-form", json={"query": del_query}, headers=admin_headers)
        assert res_del_form.json()["operation"] == "DELETE"

        # VIEWER attempting DELETE on /api/execute-form receives 403 Forbidden
        res_viewer_del = client.post("/api/execute-form", json={
            "operation": "DELETE",
            "table": "orders",
            "fields": {},
            "where": {"id": 42}
        }, headers=viewer_headers)

        assert res_viewer_del.status_code == 403, f"Expected 403 Forbidden for VIEWER DELETE, got {res_viewer_del.status_code}"
        print("PASS: VIEWER attempting DELETE is strictly rejected with 403 Forbidden.")

        print("\n--- ALL E2E PIPELINE & LATENCY TESTS PASSED SUCCESSFULLY! ---")
    finally:
        GeminiProvider.generate_json = orig_generate_json

if __name__ == "__main__":
    test_e2e_2_llm_calls_and_mutation_security()
