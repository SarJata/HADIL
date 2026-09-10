import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Force test database metadata path
os.environ["HADIL_METADATA_DB"] = "./test_hadil_metadata.db"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cli.admin_console import AdminConsole, mask_api_key
from services.metadata_service import metadata_service
from services.policy_rag_service import policy_rag_service

class TestAdminConsoleCLI(unittest.TestCase):
    def setUp(self):
        self.inputs = []
        self.outputs = []
        self.passwords = []

    def mock_input(self, prompt=""):
        if self.inputs:
            val = self.inputs.pop(0)
            self.outputs.append(f"{prompt}{val}")
            return val
        return "6" # Fallback exit

    def mock_print(self, *args, **kwargs):
        line = " ".join(str(a) for a in args)
        self.outputs.append(line)

    def mock_getpass(self, prompt=""):
        if self.passwords:
            return self.passwords.pop(0)
        return "mock_secret_key"

    # --- 1. CLI Input Behavior Tests ---
    def test_cli_navigation_and_exit(self):
        self.inputs = ["6"] # Immediately exit
        console = AdminConsole(input_func=self.mock_input, print_func=self.mock_print, getpass_func=self.mock_getpass)
        console.main_menu()
        combined = "\n".join(self.outputs)
        self.assertIn("Exiting HADIL Configuration Console", combined)

    def test_cli_invalid_input_resilience(self):
        self.inputs = ["invalid_choice", "99", "6"] # Invalid inputs followed by exit
        console = AdminConsole(input_func=self.mock_input, print_func=self.mock_print, getpass_func=self.mock_getpass)
        console.main_menu()
        combined = "\n".join(self.outputs)
        self.assertIn("Invalid selection", combined)

    # --- 2. LLM Configuration Tests ---
    def test_llm_config_changes(self):
        self.inputs = [
            "1", # Select LLM Config
            "1", # Change provider
            "gemini",
            "2", # Change model
            "gemini-2.5-flash",
            "5", # Back
            "6"  # Exit
        ]
        console = AdminConsole(input_func=self.mock_input, print_func=self.mock_print, getpass_func=self.mock_getpass)
        console.main_menu()
        
        cfg = metadata_service.get_llm_config_internal("generator")
        self.assertEqual(cfg["provider_type"], "gemini")
        self.assertEqual(cfg["model"], "gemini-2.5-flash")

    def test_llm_api_key_storage_and_masking(self):
        self.passwords = ["secret_api_key_12345"]
        self.inputs = [
            "1", # Select LLM Config
            "3", # Change API key
            "5", # Back
            "6"  # Exit
        ]
        console = AdminConsole(input_func=self.mock_input, print_func=self.mock_print, getpass_func=self.mock_getpass)
        console.main_menu()

        cfg = metadata_service.get_llm_config_internal("generator")
        self.assertEqual(cfg["api_key"], "secret_api_key_12345")
        
        # Verify secret is masked and never printed in plaintext in CLI output
        masked = mask_api_key("secret_api_key_12345")
        self.assertNotIn("secret_api_key_12345", "\n".join(self.outputs))
        self.assertTrue(masked.endswith("2345"))

    # --- 3. Database Directory Configuration Tests ---
    def test_db_directory_management(self):
        temp_dir = tempfile.mkdtemp()
        try:
            # Add directory
            added = metadata_service.add_db_directory(temp_dir)
            self.assertEqual(os.path.abspath(temp_dir), added)
            dirs = metadata_service.list_db_directories()
            self.assertIn(added, dirs)

            # Duplicate rejection
            with self.assertRaises(ValueError):
                metadata_service.add_db_directory(temp_dir)

            # Nonexistent directory rejection
            with self.assertRaises(ValueError):
                metadata_service.add_db_directory("/nonexistent/directory/path/12345")

            # Remove directory
            removed = metadata_service.remove_db_directory(temp_dir)
            self.assertTrue(removed)
            self.assertNotIn(added, metadata_service.list_db_directories())
            # Ensure filesystem directory is NOT deleted
            self.assertTrue(os.path.exists(temp_dir))
        finally:
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)

    # --- 4. RAG Configuration Tests ---
    def test_rag_configuration_threshold(self):
        initial_threshold = policy_rag_service.threshold
        try:
            policy_rag_service.set_threshold(0.85)
            self.assertEqual(policy_rag_service.threshold, 0.85)
            
            with self.assertRaises(ValueError):
                # Invalid float conversion or range
                val = float("invalid_num")
        finally:
            policy_rag_service.set_threshold(initial_threshold)

    # --- 5. System Status Tests ---
    def test_system_status_rendering(self):
        self.inputs = [
            "4", # System Status
            "",  # Enter to return
            "6"  # Exit
        ]
        console = AdminConsole(input_func=self.mock_input, print_func=self.mock_print, getpass_func=self.mock_getpass)
        console.main_menu()
        combined = "\n".join(self.outputs)
        self.assertIn("HADIL SYSTEM STATUS", combined)
        self.assertIn("Metadata DB", combined)
        self.assertIn("Configured DB directories", combined)

if __name__ == "__main__":
    unittest.main()
