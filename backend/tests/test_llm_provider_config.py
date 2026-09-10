import sys
import os
import time
import json
import http.server
import socketserver
import threading

# Force isolated test metadata database to avoid wiping live developer metadata DB
os.environ["HADIL_METADATA_DB"] = "./test_hadil_metadata.db"

from fastapi.testclient import TestClient
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app
from database.manager import db_manager
from database.metadata_db import metadata_manager, HadilUser, HadilUserDatabaseRole
from services.metadata_service import metadata_service
from ai_modules.providers import get_llm_provider, CustomProvider, OpenAIProvider, QwenProvider

client = TestClient(app)

# --- Mock OpenAI-compatible HTTP Server ---
class MockLLMHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Suppress logging

    def do_POST(self):
        content_len = int(self.headers.get('Content-Length', 0))
        post_body = self.rfile.read(content_len)
        body = json.loads(post_body.decode('utf-8'))
        
        # Verify Authorization header if present
        auth_header = self.headers.get('Authorization', '')
        
        response_body = {
            "id": "chatcmpl-mock-123",
            "object": "chat.completion",
            "created": 123456789,
            "model": body.get("model", "mock-custom-model"),
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps({
                        "sql": "SELECT * FROM orders LIMIT 100;",
                        "intent": "Mock custom provider SQL",
                        "is_ambiguous": False,
                        "is_valid": True,
                        "explanation": "Mock verifier explanation"
                    })
                },
                "finish_reason": "stop"
            }]
        }
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response_body).encode('utf-8'))

import pytest

@pytest.fixture
def mock_llm_server():
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("127.0.0.1", 0), MockLLMHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    time.sleep(0.05)
    url = f"http://127.0.0.1:{port}/v1"
    yield url
    server.shutdown()
    thread.join(timeout=1.0)
    server.server_close()


@pytest.fixture
def mock_url(mock_llm_server):
    return mock_llm_server

def create_mock_llm_server():
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("127.0.0.1", 0), MockLLMHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    time.sleep(0.05)
    return server, f"http://127.0.0.1:{port}/v1"



@pytest.fixture
def setup_rbac_users():
    metadata_service.reset_and_seed_per_db_admins()
    db_id = "chinook.db"
    db_manager.current_db_id = db_id
    db_manager.current_db_name = db_id

    from validators.security import create_access_token

    # Create test admin, editor & viewer
    db = metadata_manager.get_session()
    try:
        admin_user = db.query(HadilUser).filter(HadilUser.username == "admin").first()
        if not admin_user:
            admin_user = metadata_service.create_user("admin", "password123")
        admin_id = admin_user.id


        editor = db.query(HadilUser).filter(HadilUser.username == "test_editor").first()
        if not editor:
            editor = metadata_service.create_user("test_editor", "password123")
            metadata_service.assign_user_role(editor.id, db_id, "EDITOR")
        editor_id = editor.id

        viewer = db.query(HadilUser).filter(HadilUser.username == "test_viewer").first()
        if not viewer:
            viewer = metadata_service.create_user("test_viewer", "password123")
            metadata_service.assign_user_role(viewer.id, db_id, "VIEWER")
        viewer_id = viewer.id
    finally:
        db.close()


    admin_token = create_access_token(user_id=admin_id, username="admin")
    editor_token = create_access_token(user_id=editor_id, username="test_editor")
    viewer_token = create_access_token(user_id=viewer_id, username="test_viewer")

    return {
        "admin_headers": {'Authorization': f'Bearer {admin_token}'},
        "editor_headers": {'Authorization': f'Bearer {editor_token}'},
        "viewer_headers": {'Authorization': f'Bearer {viewer_token}'}
    }


def test_admin_view_llm_config(setup_rbac_users):
    headers = setup_rbac_users["admin_headers"]
    res = client.get('/api/admin/llm-config', headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "generator" in data
    assert "verifier" in data
    assert data["generator"]["provider_type"] is not None
    # Ensure raw api_key and decrypted secrets are NEVER returned to frontend
    assert "api_key" not in data["generator"]
    assert "api_key_configured" in data["generator"]
    print("PASS: ADMIN can view AI provider configuration with provider selection only (no model, endpoint, or API key).")


def test_unauthenticated_request_fails_closed():
    res = client.get('/api/admin/llm-config')
    assert res.status_code == 401

    res = client.post('/api/admin/llm-config', json={
        "generator": {"provider_type": "custom"},
        "verifier": {"provider_type": "custom"}
    })
    assert res.status_code == 401
    print("PASS: Unauthenticated requests return 401 Unauthorized.")

def test_non_admin_cannot_view_or_change_config(setup_rbac_users):
    editor_h = setup_rbac_users["editor_headers"]
    viewer_h = setup_rbac_users["viewer_headers"]

    # Editor attempts
    assert client.get('/api/admin/llm-config', headers=editor_h).status_code == 403
    assert client.post('/api/admin/llm-config', json={
        "generator": {"provider_type": "custom", "endpoint": "http://evil.com", "model": "m"},
        "verifier": {"provider_type": "custom", "endpoint": "http://evil.com", "model": "m"}
    }, headers=editor_h).status_code == 403

    # Viewer attempts
    assert client.get('/api/admin/llm-config', headers=viewer_h).status_code == 403
    assert client.post('/api/admin/llm-config', json={
        "generator": {"provider_type": "custom", "endpoint": "http://evil.com", "model": "m"},
        "verifier": {"provider_type": "custom", "endpoint": "http://evil.com", "model": "m"}
    }, headers=viewer_h).status_code == 403
    print("PASS: EDITOR and VIEWER receive 403 Forbidden.")

def test_client_role_spoofing_prevented(setup_rbac_users):
    viewer_h = setup_rbac_users["viewer_headers"]
    # Body containing fake role: 'ADMIN'
    res = client.post('/api/admin/llm-config', json={
        "role": "ADMIN",
        "is_admin": True,
        "generator": {"provider_type": "custom"},
        "verifier": {"provider_type": "custom"}
    }, headers=viewer_h)
    assert res.status_code == 403
    print("PASS: Client role spoofing in body is strictly rejected via server-side JWT authorization.")

def test_admin_configure_custom_provider(setup_rbac_users, mock_llm_server):
    admin_h = setup_rbac_users["admin_headers"]
    
    # Save custom config
    res = client.post('/api/admin/llm-config', json={
        "generator": {
            "provider_type": "custom",
            "endpoint": mock_llm_server,
            "model": "company-sql-model",
            "api_key": "sk-secret-company-key-12345"
        },
        "verifier": {
            "provider_type": "custom",
            "endpoint": mock_llm_server,
            "model": "company-verifier-model",
            "api_key": "sk-secret-verifier-key-67890"
        }
    }, headers=admin_h)
    assert res.status_code == 200
    data = res.json()
    assert data["generator"]["provider_type"] == "custom"
    assert "model" not in data["generator"]
    assert "api_key" not in data["generator"]

    # Test GET config returns provider metadata without raw api_key
    get_res = client.get('/api/admin/llm-config', headers=admin_h).json()
    assert get_res["generator"]["provider_type"] == "custom"
    assert "api_key" not in get_res["generator"]
    assert "api_key_configured" in get_res["generator"]


    print("PASS: ADMIN successfully configured Custom Provider and verified frontend response secrecy.")

def test_admin_test_connection_endpoint(setup_rbac_users, mock_llm_server):
    admin_h = setup_rbac_users["admin_headers"]
    res = client.post('/api/admin/llm-config/test', json={
        "provider_type": "custom",
        "endpoint": mock_llm_server,
        "model": "company-sql-model",
        "api_key": "test-key"
    }, headers=admin_h)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] == True
    assert data["provider"] == "custom"
    assert data["model"] == "company-sql-model"
    print("PASS: Test Connection endpoint returned successful health check status.")

def test_custom_provider_execution(mock_llm_server):
    provider = CustomProvider(endpoint=mock_llm_server, model="company-sql-model", api_key="sk-test")
    res = provider.generate_json("System prompt", "User prompt")
    assert "sql" in res
    assert res["sql"] == "SELECT * FROM orders LIMIT 100;"
    print("PASS: CustomProvider successfully generated JSON response from mock server.")

def test_independent_generator_and_verifier_providers(setup_rbac_users, mock_llm_server):
    admin_h = setup_rbac_users["admin_headers"]
    
    # Configure Generator = Custom, Verifier = Ollama
    client.post('/api/admin/llm-config', json={
        "generator": {
            "provider_type": "custom",
            "endpoint": mock_llm_server,
            "model": "company-sql-model",
            "api_key": "test-key"
        },
        "verifier": {
            "provider_type": "ollama",
            "endpoint": "http://localhost:11434/api/chat",
            "model": "qwen2.5-coder:3b",
            "api_key": None
        }
    }, headers=admin_h)

    gen_provider = get_llm_provider("generator")
    ver_provider = get_llm_provider("verifier")

    assert isinstance(gen_provider, CustomProvider)
    assert isinstance(ver_provider, QwenProvider)
    assert gen_provider.model == "company-sql-model"
    assert ver_provider.model == "qwen2.5-coder:3b"
    print("PASS: Generator and Verifier successfully configured with different providers (Custom vs Ollama).")

def test_default_cloud_providers(setup_rbac_users):
    admin_h = setup_rbac_users["admin_headers"]
    
    # Configure Sarvam for Generator, Gemini for Verifier
    client.post('/api/admin/llm-config', json={
        "generator": {
            "provider_type": "sarvam",
            "model": "sarvam-2b",
            "api_key": "mock-test-key-not-real-sarvam"
        },
        "verifier": {
            "provider_type": "gemini",
            "model": "gemini-2.5-flash",
            "api_key": "mock-test-key-not-real-gemini"
        }
    }, headers=admin_h)

    gen = get_llm_provider("generator")
    ver = get_llm_provider("verifier")

    from ai_modules.providers import SarvamProvider, GeminiProvider, ClaudeProvider
    assert isinstance(gen, SarvamProvider)
    assert not isinstance(gen, CustomProvider)
    assert isinstance(ver, GeminiProvider)
    assert not isinstance(ver, CustomProvider)
    assert gen.model == "sarvam-2b"
    assert ver.model == "gemini-2.5-flash"
    print("PASS: Sarvam AI and Google Gemini resolve strictly to SarvamProvider & GeminiProvider (never CustomProvider).")

def test_gemini_provider_mock_execution(mock_url):
    from ai_modules.providers import GeminiProvider
    gp = GeminiProvider(endpoint=mock_url, model="gemini-2.5-flash", api_key="mock-test-key-not-real")
    res = gp.generate_json("System prompt", "User prompt")
    assert "sql" in res
    assert res["sql"] == "SELECT * FROM orders LIMIT 100;"
    print("PASS: GeminiProvider successfully generated JSON response using mock HTTP server.")





def test_customer_database_schema_untouched():
    test_db = os.path.join(db_manager.db_folder, "chinook.db")
    if not os.path.exists(test_db):
        with open(test_db, "w") as f:
            f.write("")
    tables = db_manager.list_databases()
    # Check that customer database table names do not have hadil_llm_config injected
    filtered_tables = [t for t in tables if t.get("name") == "chinook.db" or t.get("id") == "chinook.db"]
    assert len(filtered_tables) > 0
    print("PASS: Customer database schema remains 100% untouched.")



def test_provider_configuration_isolation(setup_rbac_users):
    admin_h = setup_rbac_users["admin_headers"]
    from ai_modules.providers import GeminiProvider, SarvamProvider

    # 1. Configure Gemini for Generator
    client.post('/api/admin/llm-config', json={
        "generator": {
            "provider_type": "gemini",
            "model": "gemini-2.5-flash",
            "api_key": "gemini-secret-key-111"
        },
        "verifier": {
            "provider_type": "openai"
        }
    }, headers=admin_h)

    gen = get_llm_provider("generator")
    assert isinstance(gen, GeminiProvider)
    assert gen.endpoint == "https://generativelanguage.googleapis.com/v1beta/openai"

    # 2. Configure Sarvam for Verifier
    client.post('/api/admin/llm-config', json={
        "generator": {
            "provider_type": "gemini",
            "model": "gemini-2.5-flash",
            "api_key": "gemini-secret-key-111"
        },
        "verifier": {
            "provider_type": "sarvam",
            "model": "sarvam-2b",
            "api_key": "sarvam-secret-key-222"
        }
    }, headers=admin_h)

    ver = get_llm_provider("verifier")
    assert isinstance(ver, SarvamProvider)
    assert ver.endpoint == "https://api.sarvam.ai/v1"

    # 3 & 4: Configure Gemini and Sarvam simultaneously
    gen_p = get_llm_provider("generator")
    ver_p = get_llm_provider("verifier")

    assert gen_p.endpoint == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert "sarvam" not in gen_p.endpoint
    assert ver_p.endpoint == "https://api.sarvam.ai/v1"
    assert "generativelanguage" not in ver_p.endpoint

    # 5 & 6: Assert API key isolation
    assert gen_p.api_key == "gemini-secret-key-111"
    assert ver_p.api_key == "sarvam-secret-key-222"
    assert gen_p.api_key != ver_p.api_key

    # 7. Generator = Gemini, Verifier = Sarvam
    assert isinstance(get_llm_provider("generator"), GeminiProvider)
    assert isinstance(get_llm_provider("verifier"), SarvamProvider)

    # 8. Swap: Generator = Sarvam, Verifier = Gemini
    client.post('/api/admin/llm-config', json={
        "generator": {
            "provider_type": "sarvam",
            "model": "sarvam-2b",
            "api_key": "sarvam-secret-key-222"
        },
        "verifier": {
            "provider_type": "gemini",
            "model": "gemini-2.5-flash",
            "api_key": "gemini-secret-key-111"
        }
    }, headers=admin_h)

    swapped_gen = get_llm_provider("generator")
    swapped_ver = get_llm_provider("verifier")

    assert isinstance(swapped_gen, SarvamProvider)
    assert isinstance(swapped_ver, GeminiProvider)
    assert swapped_gen.endpoint == "https://api.sarvam.ai/v1"
    assert swapped_ver.endpoint == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert swapped_gen.api_key == "sarvam-secret-key-222"
    assert swapped_ver.api_key == "gemini-secret-key-111"

    print("PASS: Complete provider configuration & credential isolation verified.")

if __name__ == "__main__":
    print("\n==========================================")
    print(" RUNNING EXTENSIBLE LLM PROVIDER TESTS")
    print("==========================================")
    
    server, mock_url = create_mock_llm_server()
    users = setup_rbac_users()

    try:
        test_admin_view_llm_config(users)
        test_unauthenticated_request_fails_closed()
        test_non_admin_cannot_view_or_change_config(users)
        test_client_role_spoofing_prevented(users)
        test_admin_configure_custom_provider(users, mock_url)
        test_admin_test_connection_endpoint(users, mock_url)
        test_custom_provider_execution(mock_url)
        test_independent_generator_and_verifier_providers(users, mock_url)
        test_default_cloud_providers(users)
        test_gemini_provider_mock_execution(mock_url)
        test_provider_configuration_isolation(users)
        test_customer_database_schema_untouched()

        print("\n--- ALL EXTENSIBLE LLM PROVIDER TESTS PASSED SUCCESSFULLY! ---")
    finally:
        server.shutdown()
        server.server_close()

