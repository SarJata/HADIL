"""Cloud / desktop deployment-mode tests. Existing Windows V1 tests remain in sibling modules."""

import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from validators.security import create_access_token
from services.metadata_service import metadata_service


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FRONTEND_API_JS = os.path.join(REPO_ROOT, "frontend", "src", "api.js")
CONNECT_MODAL = os.path.join(REPO_ROOT, "frontend", "src", "components", "ConnectDatabaseModal.jsx")


class TestDeploymentModeConfig(unittest.TestCase):
    def test_desktop_mode_enables_sqlite_and_windows_runtime(self):
        from config.deployment import get_deployment_config
        saved_host = os.environ.pop("HOST", None)
        saved_port = os.environ.pop("PORT", None)
        try:
            with patch.dict(os.environ, {"HADIL_DEPLOYMENT_MODE": "desktop"}, clear=False):
                os.environ.pop("RENDER", None)
                cfg = get_deployment_config()
                self.assertTrue(cfg.is_desktop)
                self.assertTrue(cfg.sqlite_local)
                self.assertTrue(cfg.sqlite_upload)
                self.assertTrue(cfg.sqlite_file_location)
                self.assertTrue(cfg.sqlite_directory_scan)
                self.assertTrue(cfg.windows_runtime)
                self.assertTrue(cfg.server_shutdown)
                self.assertTrue(cfg.remote_mysql)
                self.assertTrue(cfg.remote_postgresql)
                self.assertEqual(cfg.bind_host, "127.0.0.1")
        finally:
            if saved_host is not None:
                os.environ["HOST"] = saved_host
            if saved_port is not None:
                os.environ["PORT"] = saved_port

    def test_cloud_mode_disables_sqlite_and_windows_runtime(self):
        from config.deployment import get_deployment_config
        with patch.dict(os.environ, {"HADIL_DEPLOYMENT_MODE": "cloud", "PORT": "24680", "HOST": "0.0.0.0"}, clear=False):
            cfg = get_deployment_config()
            self.assertTrue(cfg.is_cloud)
            self.assertFalse(cfg.sqlite_local)
            self.assertFalse(cfg.sqlite_upload)
            self.assertFalse(cfg.sqlite_file_location)
            self.assertFalse(cfg.sqlite_directory_scan)
            self.assertFalse(cfg.windows_runtime)
            self.assertFalse(cfg.native_splash)
            self.assertFalse(cfg.system_tray)
            self.assertFalse(cfg.browser_auto_launch)
            self.assertFalse(cfg.server_shutdown)
            self.assertTrue(cfg.remote_mysql)
            self.assertTrue(cfg.remote_postgresql)
            self.assertEqual(cfg.bind_host, "0.0.0.0")
            self.assertEqual(cfg.bind_port, 24680)

    def test_render_env_implies_cloud_when_mode_unset(self):
        from config.deployment import resolve_deployment_mode
        with patch.dict(os.environ, {"RENDER": "true", "HADIL_DEPLOYMENT_MODE": ""}, clear=False):
            self.assertEqual(resolve_deployment_mode(), "cloud")

    def test_cloud_rejects_default_jwt_secret(self):
        from config.deployment import get_deployment_config, DEFAULT_JWT_SECRET
        with patch.dict(
            os.environ,
            {
                "HADIL_DEPLOYMENT_MODE": "cloud",
                "HADIL_JWT_SECRET": DEFAULT_JWT_SECRET,
            },
            clear=False,
        ):
            os.environ.pop("HADIL_METADATA_DATABASE_URL", None)
            os.environ.pop("HADIL_METADATA_DB", None)
            with self.assertRaises(RuntimeError):
                get_deployment_config().validate_cloud_runtime()

    def test_cloud_cors_never_allows_wildcard(self):
        from config.deployment import get_deployment_config
        with patch.dict(
            os.environ,
            {
                "HADIL_DEPLOYMENT_MODE": "cloud",
                "HADIL_ALLOWED_ORIGINS": "*,https://hadil.example.com",
            },
            clear=False,
        ):
            origins = get_deployment_config().cors_origins()
            self.assertNotIn("*", origins)
            self.assertIn("https://hadil.example.com", origins)
            self.assertNotIn("http://localhost:5173", origins)


class TestCloudSqliteAndAuthEndpoints(unittest.TestCase):
    def setUp(self):
        self._prev = {
            "HADIL_DEPLOYMENT_MODE": os.environ.get("HADIL_DEPLOYMENT_MODE"),
            "HADIL_JWT_SECRET": os.environ.get("HADIL_JWT_SECRET"),
            "HADIL_METADATA_DB": os.environ.get("HADIL_METADATA_DB"),
        }
        os.environ["HADIL_DEPLOYMENT_MODE"] = "cloud"
        os.environ["HADIL_JWT_SECRET"] = "cloud-test-secret-not-default-value"
        os.environ["HADIL_METADATA_DB"] = "./test_hadil_metadata.db"
        from main import app
        self.client = TestClient(app)
        self.token = create_access_token(user_id=1, username="admin")
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def tearDown(self):
        for key, value in self._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_sqlite_filesystem_endpoints_forbidden_in_cloud(self):
        with patch.object(metadata_service, "get_user_role_for_database", return_value="MASTER_ADMIN"):
            res_path = self.client.post(
                "/api/admin/databases/register-path",
                json={"file_path": "C:/data/sales.db"},
                headers=self.headers,
            )
            res_upload = self.client.post(
                "/api/admin/databases/upload",
                files={"file": ("sales.db", b"SQLite format 3\x00", "application/octet-stream")},
                headers=self.headers,
            )
            res_dirs = self.client.get("/api/admin/db-directories", headers=self.headers)
            res_shutdown = self.client.post("/api/admin/server/shutdown", headers=self.headers)
        self.assertEqual(res_path.status_code, 403)
        self.assertEqual(res_upload.status_code, 403)
        self.assertEqual(res_dirs.status_code, 403)
        self.assertEqual(res_shutdown.status_code, 403)

    def test_capabilities_endpoint_cloud(self):
        res = self.client.get("/api/capabilities")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["deployment_mode"], "cloud")
        self.assertFalse(data["sqlite_upload"])
        self.assertFalse(data["sqlite_file_location"])
        self.assertTrue(data["remote_mysql"])
        self.assertTrue(data["remote_postgresql"])

    def test_sqlite_uri_rejected_in_cloud_test_connection(self):
        res = self.client.post("/api/test-connection", json={"connection_uri": "sqlite:///./sales.db"})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["success"])


class TestDesktopCapabilitiesEndpoint(unittest.TestCase):
    def setUp(self):
        self._prev_mode = os.environ.get("HADIL_DEPLOYMENT_MODE")
        os.environ["HADIL_DEPLOYMENT_MODE"] = "desktop"
        from main import app
        self.client = TestClient(app)

    def tearDown(self):
        if self._prev_mode is None:
            os.environ.pop("HADIL_DEPLOYMENT_MODE", None)
        else:
            os.environ["HADIL_DEPLOYMENT_MODE"] = self._prev_mode

    def test_capabilities_endpoint_desktop(self):
        res = self.client.get("/api/capabilities")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["deployment_mode"], "desktop")
        self.assertTrue(data["sqlite_local"])
        self.assertTrue(data["sqlite_upload"])
        self.assertTrue(data["sqlite_file_location"])
        self.assertTrue(data["server_shutdown"])


class TestMetadataPostgresUrl(unittest.TestCase):
    def test_normalize_supabase_style_urls(self):
        from database.metadata_db import normalize_metadata_database_url
        self.assertTrue(
            normalize_metadata_database_url("postgres://u:p@host/db").startswith("postgresql+psycopg2://")
        )
        self.assertTrue(
            normalize_metadata_database_url("postgresql://u:p@host/db").startswith("postgresql+psycopg2://")
        )
        self.assertEqual(
            normalize_metadata_database_url("postgresql+psycopg2://u:p@host/db"),
            "postgresql+psycopg2://u:p@host/db",
        )

    def test_manager_uses_postgres_url_without_sqlite_path_engine(self):
        from database.metadata_db import MetadataDatabaseManager, MetadataBase
        mock_engine = MagicMock()
        mock_engine.dialect.name = "postgresql"
        with patch("database.metadata_db.create_engine", return_value=mock_engine) as mock_create, \
             patch.object(MetadataBase.metadata, "create_all"):
            mgr = MetadataDatabaseManager(database_url="postgres://u:p@localhost/hadil")
        self.assertEqual(mgr.database_url, "postgresql+psycopg2://u:p@localhost/hadil")
        kwargs = mock_create.call_args.kwargs
        self.assertTrue(kwargs.get("pool_pre_ping"))
        self.assertEqual(mgr.dialect_name, "postgresql")

    def test_sqlite_metadata_still_works(self):
        from database.metadata_db import MetadataDatabaseManager
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            mgr = MetadataDatabaseManager(db_path=path)
            self.assertEqual(mgr.dialect_name, "sqlite")
            self.assertTrue(mgr.is_healthy())
        finally:
            mgr.engine.dispose()
            if os.path.exists(path):
                os.remove(path)


class TestRagModelStrategy(unittest.TestCase):
    def test_bundled_or_hub_resolution_does_not_disable_rag(self):
        from services.policy_rag_service import resolve_embedding_model_source, EMBEDDING_MODEL_NAME
        resolved = resolve_embedding_model_source()
        self.assertIn(resolved["source"], ("explicit_path", "bundled", "local_cache", "huggingface_hub"))
        self.assertTrue(resolved["location"])
        if resolved["source"] == "huggingface_hub":
            self.assertEqual(resolved["location"], EMBEDDING_MODEL_NAME)
            self.assertTrue(resolved["hub_download"])


class TestFrontendApiUrlAndSqliteUx(unittest.TestCase):
    def test_api_js_prefers_same_origin_over_localhost(self):
        with open(FRONTEND_API_JS, encoding="utf-8") as handle:
            src = handle.read()
        self.assertIn("window.location.origin", src)
        self.assertIn("VITE_API_URL", src)
        self.assertLess(src.index("VITE_API_URL"), src.index("http://localhost:8000"))
        self.assertIn("fetchDeploymentCapabilities", src)

    def test_connect_modal_hides_sqlite_import_behind_capabilities(self):
        with open(CONNECT_MODAL, encoding="utf-8") as handle:
            src = handle.read()
        self.assertIn("allowSqliteImport", src)
        self.assertIn("capabilities.sqlite_upload", src)
        self.assertIn("capabilities.sqlite_file_location", src)


class TestRenderAsgiImportPath(unittest.TestCase):
    """Render cwd is the repo root. backend/main.py is not importable as `main` unless backend is on sys.path."""

    def test_render_yaml_start_command_uses_app_dir_not_backend_main(self):
        yaml_path = os.path.join(REPO_ROOT, "render.yaml")
        with open(yaml_path, encoding="utf-8") as handle:
            start_lines = [
                line.strip()
                for line in handle
                if line.strip().startswith("startCommand:")
            ]
        self.assertEqual(len(start_lines), 1)
        start = start_lines[0]
        self.assertIn("uvicorn main:app --app-dir backend", start)
        self.assertNotIn("backend.main:app", start)

    def test_repo_root_cannot_import_main_without_backend_on_path(self):
        script = (
            "import os, sys\n"
            "os.environ.pop('PYTHONPATH', None)\n"
            "from uvicorn.importer import import_from_string, ImportFromStringError\n"
            "try:\n"
            "    import_from_string('main:app')\n"
            "except ImportFromStringError as exc:\n"
            "    assert 'Could not import module' in str(exc) and 'main' in str(exc)\n"
            "    print('MAIN_MISSING_OK')\n"
            "else:\n"
            "    raise SystemExit('expected main import to fail from repo root')\n"
            "try:\n"
            "    import_from_string('backend.main:app')\n"
            "except ModuleNotFoundError as exc:\n"
            "    assert exc.name == 'config'\n"
            "    print('BACKEND_MAIN_CONFIG_FAIL_OK')\n"
            "else:\n"
            "    raise SystemExit('expected backend.main:app to fail on config')\n"
        )
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("MAIN_MISSING_OK", result.stdout)
        self.assertIn("BACKEND_MAIN_CONFIG_FAIL_OK", result.stdout)

    def test_app_dir_backend_imports_and_exposes_app(self):
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        script = (
            "import os, sys\n"
            "os.environ['HADIL_DEPLOYMENT_MODE'] = 'cloud'\n"
            "os.environ['HADIL_JWT_SECRET'] = 'cloud-test-secret-not-default-value'\n"
            "os.environ['HADIL_METADATA_DB'] = './test_cloud_startup_metadata.db'\n"
            "os.environ.pop('PYTHONPATH', None)\n"
            f"sys.path.insert(0, {backend_dir!r})\n"
            "from uvicorn.importer import import_from_string\n"
            "app = import_from_string('main:app')\n"
            "assert app.__class__.__name__ == 'FastAPI'\n"
            "print('APP_DIR_IMPORT_OK')\n"
        )
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env["HADIL_DEPLOYMENT_MODE"] = "cloud"
        env["HADIL_JWT_SECRET"] = "cloud-test-secret-not-default-value"
        env["HADIL_METADATA_DB"] = "./test_cloud_startup_metadata.db"
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("APP_DIR_IMPORT_OK", result.stdout)


class TestCloudStartupIsolation(unittest.TestCase):
    def test_import_main_in_cloud_does_not_load_windows_gui(self):
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        script = (
            "import os, sys\n"
            "os.environ['HADIL_DEPLOYMENT_MODE'] = 'cloud'\n"
            "os.environ['HADIL_JWT_SECRET'] = 'cloud-test-secret-not-default-value'\n"
            "os.environ['HADIL_METADATA_DB'] = './test_cloud_startup_metadata.db'\n"
            f"sys.path.insert(0, {backend_dir!r})\n"
            "import main\n"
            "assert 'pystray' not in sys.modules\n"
            "assert 'tkinter' not in sys.modules\n"
            "from config.deployment import get_deployment_config\n"
            "cfg = get_deployment_config()\n"
            "assert cfg.is_cloud\n"
            "assert cfg.bind_host == '0.0.0.0'\n"
            "print('CLOUD_STARTUP_OK')\n"
        )
        env = os.environ.copy()
        env["HADIL_DEPLOYMENT_MODE"] = "cloud"
        env["HADIL_JWT_SECRET"] = "cloud-test-secret-not-default-value"
        env["HADIL_METADATA_DB"] = "./test_cloud_startup_metadata.db"
        env.pop("RENDER", None)
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CLOUD_STARTUP_OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
