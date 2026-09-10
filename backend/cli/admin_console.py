import os
import sys
import getpass
import logging
from typing import Optional, List

# Ensure parent directory is in sys.path when running as script
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from services.metadata_service import metadata_service
from ai_modules.providers import get_llm_provider, OpenAIProvider, GeminiProvider, ClaudeProvider, SarvamProvider, QwenProvider, CustomProvider
from database.metadata_db import metadata_manager
from database.manager import db_manager

from services.policy_rag_service import policy_rag_service, EMBEDDING_MODEL_NAME, FAISS_INDEX_PATH

# Configure logging to suppress debug spam during CLI session
logging.basicConfig(level=logging.ERROR)

SUPPORTED_PROVIDERS = ["openai", "gemini", "claude", "sarvam", "qwen", "custom"]

def mask_api_key(key: Optional[str]) -> str:
    if not key:
        return "[NOT SET]"
    if len(key) <= 8:
        return "****" + key[-2:]
    return "*" * (len(key) - 4) + key[-4:]

class AdminConsole:
    def __init__(self, input_func=input, print_func=print, getpass_func=getpass.getpass):
        self.input = input_func
        self.print = print_func
        self.getpass = getpass_func
        self.last_test_result: Optional[dict] = None

    def display_header(self):
        self.print("\n╔══════════════════════════════════════════╗")
        self.print("║              HADIL BACKEND               ║")
        self.print("║         CONFIGURATION CONSOLE            ║")
        self.print("╚══════════════════════════════════════════╝\n")

    def main_menu(self, get_fastapi_status=None):
        while True:
            self.display_header()
            self.print("1. LLM Configuration")
            self.print("2. Database Configuration")
            self.print("3. RAG Configuration")
            self.print("4. System Status")
            self.print("5. Master Administrator Setup")
            self.print("6. Exit\n")
            
            choice = self.input("Select an option (1-6): ").strip()
            if choice == "1":
                self.llm_config_menu()
            elif choice == "2":
                self.database_config_menu()
            elif choice == "3":
                self.rag_config_menu()
            elif choice == "4":
                st = get_fastapi_status() if callable(get_fastapi_status) else "RUNNING"
                self.system_status_screen(fastapi_status=st)
            elif choice == "5":
                self.master_administrator_setup_menu()
            elif choice == "6":
                self.print("Exiting HADIL Configuration Console.")
                break
            else:
                self.print("\n[ERROR] Invalid selection. Please enter a number between 1 and 6.")

    # --- Master Administrator Setup Menu ---
    def master_administrator_setup_menu(self):
        self.print("\n------------------------------------------")
        self.print("Master Administrator Setup")
        self.print("------------------------------------------")

        master_info = metadata_service.get_master_admin()
        if master_info:
            self.print(f"Status: CONFIGURED")
            self.print(f"Master Administrator Username: {master_info['username']}")
            self.print("\nA Master Administrator already exists.")
            self.print("Bootstrap creation is disabled.\n")
            self.input("Press Enter to return to main menu...")
            return

        self.print("No Master Administrator exists.\n")

        username = self.input("Username: ").strip()
        if not username:
            self.print("\n[ERROR] Username cannot be empty.")
            return

        password = self.getpass("Password: ")
        confirm_password = self.getpass("Confirm Password: ")

        if not password:
            self.print("\n[ERROR] Password cannot be empty.")
            return

        if password != confirm_password:
            self.print("\n[ERROR] Passwords do not match.")
            return

        confirm = self.input("\nCreate Master Administrator? [y/N]: ").strip().lower()
        if confirm != 'y':
            self.print("\n[CANCELLED] Master Administrator setup cancelled.")
            return

        try:
            user = metadata_service.create_master_admin(username, password)
            self.print(f"\n[OK] Master Administrator '{user.username}' created successfully.")
        except Exception as e:
            self.print(f"\n[ERROR] Failed to create Master Administrator: {e}")

    # --- 1. LLM Configuration Menu ---
    def llm_config_menu(self):
        while True:
            # We target 'generator' as the default primary provider config
            cfg = metadata_service.get_llm_config_internal("generator")
            provider = cfg.get("provider_type", "openai")
            model = cfg.get("model") or "default"
            key_str = mask_api_key(cfg.get("api_key"))

            self.print("\n------------------------------------------")
            self.print("LLM CONFIGURATION")
            self.print("------------------------------------------")
            self.print(f"Provider : {provider.upper()}")
            self.print(f"Model    : {model}")
            self.print(f"API Key  : {key_str}")
            self.print("------------------------------------------")
            self.print("1. Change provider")
            self.print("2. Change model")
            self.print("3. Change API key")
            self.print("4. Test connection")
            self.print("5. Back\n")

            choice = self.input("Select an option (1-5): ").strip()
            if choice == "1":
                self._change_llm_provider(cfg)
            elif choice == "2":
                self._change_llm_model(cfg)
            elif choice == "3":
                self._change_llm_api_key(cfg)
            elif choice == "4":
                self._test_llm_connection(cfg)
            elif choice == "5":
                break
            else:
                self.print("\n[ERROR] Invalid selection. Please enter a number between 1 and 5.")

    def _change_llm_provider(self, current_cfg: dict):
        self.print(f"\nSupported Providers: {', '.join(SUPPORTED_PROVIDERS)}")
        new_provider = self.input("Enter new provider name: ").strip().lower()
        if new_provider not in SUPPORTED_PROVIDERS:
            self.print(f"\n[ERROR] Unsupported provider '{new_provider}'. Choose from {SUPPORTED_PROVIDERS}.")
            return

        endpoint = None
        if new_provider in ["custom", "qwen"]:
            endpoint = self.input(f"Enter endpoint URL for {new_provider} (leave empty for default): ").strip() or None

        try:
            metadata_service.set_llm_config(
                target="generator",
                provider_type=new_provider,
                endpoint=endpoint,
                model=current_cfg.get("model"),
                api_key="••••••••" # keep existing unless changed
            )
            # Synchronize verifier if target single config
            metadata_service.set_llm_config(
                target="verifier",
                provider_type=new_provider,
                endpoint=endpoint,
                model=current_cfg.get("model"),
                api_key="••••••••"
            )
            self.print(f"\n[OK] Provider changed to '{new_provider}'.")
        except Exception as e:
            self.print(f"\n[ERROR] Failed to update provider: {e}")

    def _change_llm_model(self, current_cfg: dict):
        new_model = self.input("\nEnter new model name (e.g. gemini-2.5-flash, gpt-4o, qwen2.5-coder:3b): ").strip()
        if not new_model:
            self.print("\n[ERROR] Model name cannot be empty.")
            return

        try:
            metadata_service.set_llm_config(
                target="generator",
                provider_type=current_cfg.get("provider_type", "openai"),
                endpoint=current_cfg.get("endpoint"),
                model=new_model,
                api_key="••••••••"
            )
            metadata_service.set_llm_config(
                target="verifier",
                provider_type=current_cfg.get("provider_type", "openai"),
                endpoint=current_cfg.get("endpoint"),
                model=new_model,
                api_key="••••••••"
            )
            self.print(f"\n[OK] Model updated to '{new_model}'.")
        except Exception as e:
            self.print(f"\n[ERROR] Failed to update model: {e}")

    def _change_llm_api_key(self, current_cfg: dict):
        self.print("\nEnter API Key (input will be hidden):")
        new_key = self.getpass("API Key: ").strip()
        if not new_key:
            self.print("\n[ERROR] API key cannot be empty.")
            return

        try:
            metadata_service.set_llm_config(
                target="generator",
                provider_type=current_cfg.get("provider_type", "openai"),
                endpoint=current_cfg.get("endpoint"),
                model=current_cfg.get("model"),
                api_key=new_key
            )
            metadata_service.set_llm_config(
                target="verifier",
                provider_type=current_cfg.get("provider_type", "openai"),
                endpoint=current_cfg.get("endpoint"),
                model=current_cfg.get("model"),
                api_key=new_key
            )
            self.print("\n[OK] API Key successfully updated and encrypted.")
        except Exception as e:
            self.print(f"\n[ERROR] Failed to update API key: {e}")

    def _test_llm_connection(self, current_cfg: dict):
        provider_name = current_cfg.get("provider_type", "openai")
        model_name = current_cfg.get("model") or "default"
        self.print(f"\nTesting {provider_name.title()}...")
        self.print(f"Provider : {provider_name.title()}")
        self.print(f"Model    : {model_name}\n")

        try:
            provider_instance = get_llm_provider("generator")
            check_res = provider_instance.health_check()
            self.last_test_result = check_res
            if check_res.get("success"):
                self.print("[OK] Connection successful.")
            else:
                msg = check_res.get("message", "Unknown error")
                self.print(f"[FAILED] {msg}")
        except Exception as e:
            err_msg = str(e)
            self.last_test_result = {"success": False, "message": err_msg}
            self.print(f"[FAILED] {err_msg}")

    # --- 2. Database Configuration Menu ---
    def database_config_menu(self):
        while True:
            dirs = metadata_service.list_db_directories()
            self.print("\n------------------------------------------")
            self.print("DATABASE CONFIGURATION")
            self.print("------------------------------------------")
            self.print("1. View configured directories")
            self.print("2. Add directory")
            self.print("3. Remove directory")
            self.print("4. Back\n")

            choice = self.input("Select an option (1-4): ").strip()
            if choice == "1":
                self.print("\nConfigured Directories:")
                if not dirs:
                    self.print("  (None configured)")
                else:
                    for idx, d in enumerate(dirs, 1):
                        self.print(f"  {idx}. {d}")
            elif choice == "2":
                new_dir = self.input("\nEnter absolute or relative directory path: ").strip()
                if not new_dir:
                    self.print("\n[ERROR] Directory path cannot be empty.")
                    continue
                try:
                    added = metadata_service.add_db_directory(new_dir)
                    self.print(f"\n[OK] Added directory: {added}")
                except Exception as e:
                    self.print(f"\n[ERROR] {e}")
            elif choice == "3":
                if not dirs:
                    self.print("\n[ERROR] No configured directories to remove.")
                    continue
                self.print("\nConfigured Directories:")
                for idx, d in enumerate(dirs, 1):
                    self.print(f"  {idx}. {d}")
                rem_input = self.input("Enter directory path or number to remove: ").strip()
                target_path = rem_input
                if rem_input.isdigit():
                    idx_val = int(rem_input)
                    if 1 <= idx_val <= len(dirs):
                        target_path = dirs[idx_val - 1]
                
                try:
                    removed = metadata_service.remove_db_directory(target_path)
                    if removed:
                        self.print(f"\n[OK] Removed directory configuration: {target_path}")
                    else:
                        self.print(f"\n[ERROR] Directory path '{target_path}' not found in configurations.")
                except Exception as e:
                    self.print(f"\n[ERROR] Failed to remove directory: {e}")
            elif choice == "4":
                break
            else:
                self.print("\n[ERROR] Invalid selection. Please enter a number between 1 and 4.")

    # --- 3. RAG Configuration Menu ---
    def rag_config_menu(self):
        while True:
            if not policy_rag_service.is_initialized:
                policy_rag_service.initialize()

            status_str = "Active" if policy_rag_service.is_initialized else "Uninitialized"
            faiss_ok = os.path.exists(FAISS_INDEX_PATH)
            policy_count = len(metadata_service.list_policy_documents())

            self.print("\n------------------------------------------")
            self.print("POLICY RAG CONFIGURATION")
            self.print("------------------------------------------")
            self.print(f"Status              : {status_str}")
            self.print(f"Embedding Model     : {EMBEDDING_MODEL_NAME}")
            self.print(f"Similarity Threshold: {policy_rag_service.threshold}")
            self.print(f"Indexed Policies    : {policy_count}")
            self.print("------------------------------------------")
            self.print("1. View current RAG status")
            self.print("2. View embedding model")
            self.print("3. View similarity threshold")
            self.print("4. Change similarity threshold")
            self.print("5. View indexed policy count")
            self.print("6. Back\n")

            choice = self.input("Select an option (1-6): ").strip()
            if choice == "1":
                self.print(f"\nPolicy RAG Status: {status_str} (FAISS Index: {'[OK]' if faiss_ok else '[MISSING]'})")
            elif choice == "2":
                self.print(f"\nEmbedding Model: {EMBEDDING_MODEL_NAME}")
            elif choice == "3":
                self.print(f"\nSimilarity Threshold: {policy_rag_service.threshold}")
            elif choice == "4":
                val_str = self.input("\nEnter new similarity threshold (0.0 - 1.0): ").strip()
                try:
                    val = float(val_str)
                    if not (0.0 <= val <= 1.0):
                        raise ValueError("Threshold must be between 0.0 and 1.0")
                    policy_rag_service.set_threshold(val)
                    self.print(f"\n[OK] Similarity threshold updated to {val}")
                except Exception as e:
                    self.print(f"\n[ERROR] Invalid threshold value: {e}")
            elif choice == "5":
                docs = metadata_service.list_policy_documents()
                self.print(f"\nIndexed Policy Count: {len(docs)}")
                for d in docs:
                    self.print(f"  - {d['filename']} (Scope: {d['scope']}, Chunks: {d['chunk_count']}, Status: {d['indexing_status']})")
            elif choice == "6":
                break
            else:
                self.print("\n[ERROR] Invalid selection. Please enter a number between 1 and 6.")

    # --- 4. System Status Screen ---
    def system_status_screen(self, fastapi_status: str = "RUNNING"):
        meta_db_ok = os.path.exists(metadata_manager.db_path)

        db_mgr_ok = db_manager is not None
        rag_ok = policy_rag_service.is_initialized
        faiss_ok = os.path.exists(FAISS_INDEX_PATH)

        cfg = metadata_service.get_llm_config_internal("generator")
        provider = cfg.get("provider_type", "openai").title()
        model = cfg.get("model") or "default"

        if self.last_test_result:
            conn_status = "[OK]" if self.last_test_result.get("success") else "[FAILED]"
        else:
            conn_status = "[NOT TESTED]"

        dirs = metadata_service.list_db_directories()
        policy_count = len(metadata_service.list_policy_documents())

        self.print("\n==========================================")
        self.print("         HADIL SYSTEM STATUS")
        self.print("==========================================")
        self.print(f"FastAPI           [{fastapi_status}]")
        self.print(f"CLI               [RUNNING]")
        self.print(f"Metadata DB       [{'OK' if meta_db_ok else 'FAILED'}]")
        self.print(f"Database Manager  [{'OK' if db_mgr_ok else 'FAILED'}]")
        self.print(f"Policy RAG        [{'OK' if rag_ok else 'FAILED'}]")
        self.print(f"FAISS Index       [{'OK' if faiss_ok else 'NOT FOUND'}]")
        self.print("")
        self.print(f"LLM Provider      {provider}")
        self.print(f"LLM Model         {model}")
        self.print(f"LLM Connection    {conn_status}")

        self.print("")
        self.print(f"Configured DB directories: {len(dirs)}")
        self.print(f"Indexed policies         : {policy_count}")
        self.print("==========================================\n")
        self.input("Press Enter to return to main menu...")

def main():
    console = AdminConsole()
    console.main_menu()

if __name__ == "__main__":
    main()
