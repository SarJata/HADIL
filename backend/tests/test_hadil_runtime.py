import os
import sys
import time
import tempfile
import unittest
import urllib.request
import urllib.error
import json
from unittest.mock import patch, MagicMock

# Force test metadata database
os.environ["HADIL_METADATA_DB"] = "./test_hadil_metadata.db"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from hadil_runtime import HadilRuntime
from services.metadata_service import metadata_service
from ai_modules.providers import get_llm_provider, CustomProvider
from services.policy_rag_service import policy_rag_service

class TestHadilRuntimePhase2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from hadil_runtime import find_free_port
        cls.port = find_free_port(8089)
        cls.runtime = HadilRuntime(host="127.0.0.1", port=cls.port)
        cls.runtime.server_thread = MagicMock() # stub thread for manual control or run actual background thread
        
        # Start server thread
        import threading
        cls.thread = threading.Thread(target=cls.runtime.start_fastapi, daemon=True)
        cls.thread.start()
        
        # Wait up to 5 seconds for server to be responsive
        start_time = time.time()
        cls.server_up = False
        while time.time() - start_time < 5:
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{cls.port}/api/setup/status")
                with urllib.request.urlopen(req, timeout=1) as resp:
                    if resp.status == 200:
                        cls.server_up = True
                        break
            except Exception:
                time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        cls.runtime.shutdown()

    # --- Test 1: FastAPI Startup ---
    def test_fastapi_startup(self):
        self.assertTrue(self.server_up, "FastAPI server failed to start within timeout.")
        self.assertEqual(self.runtime.get_fastapi_status(), "RUNNING")

    # --- Test 2: API Responsiveness ---
    def test_api_responsiveness(self):
        url = f"http://127.0.0.1:{self.port}/api/setup/status"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode('utf-8'))
            self.assertIn("setup_required", data)

    # --- Test 3: CLI Non-Blocking / Responsiveness ---
    def test_cli_remains_responsive(self):
        # Verify AdminConsole can be instantiated and controlled without blocking FastAPI
        from cli.admin_console import AdminConsole
        # Provide enough '5' menu choices to safely handle any setup prompt or main menu
        inputs = ["6"]
        outputs = []
        console = AdminConsole(
            input_func=lambda p: inputs.pop(0) if inputs else "6", 
            print_func=lambda *a: outputs.append(" ".join(str(x) for x in a)),
            getpass_func=lambda p: "adminpass123"
        )
        console.main_menu(get_fastapi_status=self.runtime.get_fastapi_status)
        self.assertTrue(len(outputs) > 0)

    # --- Test 4: Shared Configuration ---
    def test_shared_configuration(self):
        # Update LLM provider in metadata DB via service
        metadata_service.set_llm_config("generator", provider_type="openai", model="gpt-4o-test-shared")
        
        # Verify read from metadata DB matches
        cfg = metadata_service.get_llm_config_internal("generator")
        self.assertEqual(cfg["model"], "gpt-4o-test-shared")

    # --- Test 5: LLM Configuration Propagation ---
    def test_llm_config_propagation(self):
        metadata_service.set_llm_config(
            target="generator",
            provider_type="custom",
            endpoint="http://127.0.0.1:9999/v1",
            model="custom-propagation-model"
        )

        provider = get_llm_provider("generator")
        self.assertIsInstance(provider, CustomProvider)
        self.assertEqual(provider.model, "custom-propagation-model")
        self.assertEqual(provider.endpoint, "http://127.0.0.1:9999/v1")

    # --- Test 6: Database Directory Persistence ---
    def test_database_directory_persistence(self):
        temp_dir = tempfile.mkdtemp()
        try:
            added = metadata_service.add_db_directory(temp_dir)
            dirs = metadata_service.list_db_directories()
            self.assertIn(added, dirs)

            # Re-read through fresh metadata service list
            dirs_fresh = metadata_service.list_db_directories()
            self.assertIn(added, dirs_fresh)

            metadata_service.remove_db_directory(temp_dir)
        finally:
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)

    # --- Test 7: RAG Startup Regression ---
    def test_rag_startup_regression(self):
        self.assertTrue(hasattr(policy_rag_service, "threshold"))
        self.assertGreaterEqual(policy_rag_service.threshold, 0.0)

    # --- Test 8: Graceful Shutdown ---
    def test_graceful_shutdown(self):
        from hadil_runtime import find_free_port
        test_port = find_free_port(8095)
        test_runtime = HadilRuntime(host="127.0.0.1", port=test_port)
        import threading
        t = threading.Thread(target=test_runtime.start_fastapi, daemon=True)
        t.start()
        time.sleep(0.5)
        self.assertEqual(test_runtime.get_fastapi_status(), "RUNNING")
        
        test_runtime.shutdown()
        self.assertEqual(test_runtime.get_fastapi_status(), "STOPPED")

    # --- Test 10: Uvicorn GUI Logging Redirection Regression ---
    def test_uvicorn_gui_logging_redirection(self):
        """
        Verifies that uvicorn.Config(..., log_config=None) starts cleanly even when sys.stdout
        and sys.stderr are redirected to HadilLogStream in windowless GUI runtime mode.
        """
        import logging
        from hadil_runtime import configure_logging, find_free_port, HadilLogStream
        
        orig_stdout, orig_stderr = sys.stdout, sys.stderr
        try:
            # Simulate GUI mode logging setup
            configure_logging(cli_mode=False)
            self.assertIsInstance(sys.stdout, HadilLogStream)
            self.assertTrue(hasattr(sys.stdout, 'write'))
            self.assertFalse(sys.stdout.isatty())

            # Verify print() and write() execute cleanly without throwing AttributeError
            sys.stdout.write("[TEST TRACE] Testing HadilLogStream write\n")
            sys.stdout.flush()

            test_port = find_free_port(8098)
            gui_runtime = HadilRuntime(host="127.0.0.1", port=test_port)
            import threading
            t = threading.Thread(target=gui_runtime.start_fastapi, daemon=True)
            t.start()

            # Wait up to 3 seconds for server startup
            started = False
            for _ in range(30):
                if gui_runtime.get_fastapi_status() == "RUNNING":
                    started = True
                    break
                time.sleep(0.1)

            self.assertTrue(started, "FastAPI server failed to start under GUI FileHandler redirection.")
            gui_runtime.shutdown()
        finally:
            sys.stdout = orig_stdout
            sys.stderr = orig_stderr


if __name__ == "__main__":
    unittest.main()
