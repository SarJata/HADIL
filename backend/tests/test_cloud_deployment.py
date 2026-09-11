"""Cloud / desktop deployment-mode tests. Existing Windows V1 tests remain in sibling modules."""

import os
import shutil
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
        self.assertTrue(data["organization_signup"])

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

    def test_render_yaml_build_copies_frontend_dist_next_to_backend(self):
        yaml_path = os.path.join(REPO_ROOT, "render.yaml")
        with open(yaml_path, encoding="utf-8") as handle:
            body = handle.read()
        self.assertIn("npm --prefix frontend run build", body)
        self.assertIn("backend/static_frontend", body)
        self.assertIn("cp -a frontend/dist/.", body)

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
            "assert 'sentence_transformers' not in sys.modules\n"
            "assert 'torch' not in sys.modules\n"
            "from services.policy_rag_service import policy_rag_service\n"
            "assert policy_rag_service.model is None\n"
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

    def test_import_main_does_not_eagerly_import_sentence_transformers(self):
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        script = (
            "import os, sys, time\n"
            "os.environ['HADIL_DEPLOYMENT_MODE'] = 'cloud'\n"
            "os.environ['HADIL_JWT_SECRET'] = 'cloud-test-secret-not-default-value'\n"
            "os.environ['HADIL_METADATA_DB'] = './test_cloud_startup_metadata.db'\n"
            "os.environ.pop('PYTHONPATH', None)\n"
            f"sys.path.insert(0, {backend_dir!r})\n"
            "t0 = time.perf_counter()\n"
            "from uvicorn.importer import import_from_string\n"
            "app = import_from_string('main:app')\n"
            "elapsed = time.perf_counter() - t0\n"
            "assert app.__class__.__name__ == 'FastAPI'\n"
            "assert 'sentence_transformers' not in sys.modules\n"
            "assert 'torch' not in sys.modules\n"
            "from services.policy_rag_service import policy_rag_service\n"
            "assert policy_rag_service.model is None\n"
            "print('LAZY_ST_IMPORT_OK', round(elapsed, 3))\n"
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
        self.assertIn("LAZY_ST_IMPORT_OK", result.stdout)

    def test_get_model_lazily_imports_sentence_transformer(self):
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        script = (
            "import os, sys, types\n"
            "from unittest.mock import MagicMock\n"
            "os.environ['HADIL_DEPLOYMENT_MODE'] = 'cloud'\n"
            f"sys.path.insert(0, {backend_dir!r})\n"
            "fake_model = object()\n"
            "fake_cls = MagicMock(return_value=fake_model)\n"
            "fake_mod = types.ModuleType('sentence_transformers')\n"
            "fake_mod.SentenceTransformer = fake_cls\n"
            "sys.modules['sentence_transformers'] = fake_mod\n"
            "from services.policy_rag_service import PolicyRAGService\n"
            "svc = PolicyRAGService()\n"
            "assert svc.model is None\n"
            "got = svc._get_model()\n"
            "assert got is fake_model\n"
            "assert svc.model is fake_model\n"
            "assert fake_cls.call_count == 1\n"
            "assert svc._get_model() is fake_model\n"
            "assert fake_cls.call_count == 1\n"
            "print('GET_MODEL_LAZY_OK')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("GET_MODEL_LAZY_OK", result.stdout)


class TestFrontendDistResolution(unittest.TestCase):
    def test_backend_static_frontend_is_accepted(self):
        from utils import path_resolver
        tmp = tempfile.mkdtemp(prefix="hadil_backend_spa_")
        previous_cwd = os.getcwd()
        try:
            utils_dir = os.path.join(tmp, "backend", "utils")
            dist = os.path.join(tmp, "backend", "static_frontend")
            os.makedirs(utils_dir)
            os.makedirs(dist)
            with open(os.path.join(dist, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<!doctype html><title>HADIL-SPA-COPY</title>")
            os.chdir(tmp)
            fake_file = os.path.join(utils_dir, "path_resolver.py")
            with patch.object(path_resolver, "is_frozen", return_value=False), patch.object(
                path_resolver, "__file__", fake_file
            ):
                resolved = path_resolver.resolve_frontend_dist()
            self.assertEqual(os.path.normpath(resolved), os.path.normpath(dist))
        finally:
            os.chdir(previous_cwd)
            shutil.rmtree(tmp, ignore_errors=True)

    def test_frozen_frontend_dist_stays_under_bundle_dir(self):
        from utils import path_resolver
        meipass = os.path.join(tempfile.gettempdir(), "hadil_fake_meipass")
        with patch.object(path_resolver, "is_frozen", return_value=True), patch.object(
            path_resolver, "get_bundle_dir", return_value=meipass
        ):
            resolved = path_resolver.resolve_frontend_dist()
        self.assertEqual(
            os.path.normpath(resolved),
            os.path.normpath(os.path.join(meipass, "frontend", "dist")),
        )

    def test_cwd_frontend_dist_found_when_file_relative_path_missing(self):
        from utils import path_resolver
        tmp = tempfile.mkdtemp(prefix="hadil_spa_")
        previous_cwd = os.getcwd()
        try:
            dist = os.path.join(tmp, "frontend", "dist")
            os.makedirs(dist)
            index_path = os.path.join(dist, "index.html")
            with open(index_path, "w", encoding="utf-8") as handle:
                handle.write("<!doctype html><title>HADIL-SPA</title>")
            os.chdir(tmp)
            fake_file = os.path.join(os.path.abspath(os.sep), "nonexistent_hadil", "backend", "utils", "path_resolver.py")
            with patch.object(path_resolver, "is_frozen", return_value=False), patch.object(
                path_resolver, "__file__", fake_file
            ):
                resolved = path_resolver.resolve_frontend_dist()
            self.assertTrue(os.path.isfile(os.path.join(resolved, "index.html")))
            self.assertEqual(os.path.normpath(resolved), os.path.normpath(dist))
        finally:
            os.chdir(previous_cwd)
            shutil.rmtree(tmp, ignore_errors=True)

    def test_import_main_serves_index_and_docs_when_dist_present(self):
        dist_index = os.path.join(REPO_ROOT, "frontend", "dist", "index.html")
        if not os.path.isfile(dist_index):
            self.skipTest("frontend/dist/index.html is not built")
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        script = (
            "import os, sys\n"
            "os.environ['HADIL_DEPLOYMENT_MODE'] = 'cloud'\n"
            "os.environ['HADIL_JWT_SECRET'] = 'cloud-test-secret-not-default-value'\n"
            "os.environ['HADIL_METADATA_DB'] = './test_cloud_spa_metadata.db'\n"
            "os.environ.pop('PYTHONPATH', None)\n"
            f"sys.path.insert(0, {backend_dir!r})\n"
            "from fastapi.testclient import TestClient\n"
            "from uvicorn.importer import import_from_string\n"
            "app = import_from_string('main:app')\n"
            "client = TestClient(app)\n"
            "root = client.get('/')\n"
            "assert root.status_code == 200, root.text\n"
            "assert 'text/html' in root.headers.get('content-type', '')\n"
            "assert b'<html' in root.content.lower() or b'<!doctype html' in root.content.lower()\n"
            "docs = client.get('/docs')\n"
            "assert docs.status_code == 200, docs.status_code\n"
            "assert 'swagger' in docs.text.lower() or 'openapi' in docs.text.lower()\n"
            "health = client.get('/health')\n"
            "assert health.status_code == 200\n"
            "assert health.json()['deployment_mode'] == 'cloud'\n"
            "print('SPA_MOUNT_OK')\n"
        )
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env["HADIL_DEPLOYMENT_MODE"] = "cloud"
        env["HADIL_JWT_SECRET"] = "cloud-test-secret-not-default-value"
        env["HADIL_METADATA_DB"] = "./test_cloud_spa_metadata.db"
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SPA_MOUNT_OK", result.stdout)


class TestInitialAdminWithoutDefaultDatabase(unittest.TestCase):
    """Initial MASTER_ADMIN must provision when hadil_databases is empty (cloud / FK-safe)."""

    def test_first_admin_then_customer_database_role(self):
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        fd, meta_path = tempfile.mkstemp(suffix="_hadil_admin.db")
        os.close(fd)
        empty_folder = tempfile.mkdtemp(prefix="hadil_empty_dbs_")
        try:
            script = (
                "import os, sys\n"
                "os.environ['HADIL_DEPLOYMENT_MODE'] = 'cloud'\n"
                "os.environ['HADIL_JWT_SECRET'] = 'cloud-test-secret-not-default-value'\n"
                f"os.environ['HADIL_METADATA_DB'] = {meta_path!r}\n"
                f"os.environ['DATABASE_FOLDER'] = {empty_folder!r}\n"
                "os.environ.pop('HADIL_METADATA_DATABASE_URL', None)\n"
                f"sys.path.insert(0, {backend_dir!r})\n"
                "from database.metadata_db import HadilUser, HadilUserDatabaseRole, HadilDatabase, HadilSystemRole, MetadataBase, metadata_manager\n"
                "from services.metadata_service import MetadataService\n"
                "MetadataBase.metadata.drop_all(bind=metadata_manager.engine)\n"
                "MetadataBase.metadata.create_all(bind=metadata_manager.engine)\n"
                "user = MetadataService.create_first_admin('cloud_setup_admin', 'CloudAdminPass123!')\n"
                "db = metadata_manager.get_session()\n"
                "try:\n"
                "    assert db.query(HadilDatabase).count() == 0\n"
                "    roles = db.query(HadilUserDatabaseRole).filter(HadilUserDatabaseRole.user_id == user.id).all()\n"
                "    assert roles == []\n"
                "    assert db.query(HadilUserDatabaseRole).filter(HadilUserDatabaseRole.database_id == 'default_db').count() == 0\n"
                "    sys_role = db.query(HadilSystemRole).filter(HadilSystemRole.user_id == user.id).one()\n"
                "    assert sys_role.role == 'MASTER_ADMIN'\n"
                "    assert MetadataService.get_user_role_for_database(user.id, 'default_db') is None\n"
                "finally:\n"
                "    db.close()\n"
                "record = MetadataService.register_or_update_database(\n"
                "    'customer_analytics_pg', 'Customer Analytics', 'postgresql',\n"
                "    connection_uri='postgresql://u:p@db.example:5432/analytics',\n"
                ")\n"
                "assert record.id == 'customer_analytics_pg'\n"
                "db = metadata_manager.get_session()\n"
                "try:\n"
                "    assert db.query(HadilDatabase).filter(HadilDatabase.id == 'default_db').count() == 0\n"
                "    role_rows = db.query(HadilUserDatabaseRole).filter(\n"
                "        HadilUserDatabaseRole.user_id == user.id,\n"
                "        HadilUserDatabaseRole.database_id == 'customer_analytics_pg',\n"
                "    ).all()\n"
                "    assert role_rows == []\n"
                "finally:\n"
                "    db.close()\n"
                "assert not MetadataService.check_permission(user.id, 'customer_analytics_pg', 'MANAGE_USERS')\n"
                "assert not MetadataService.check_permission(user.id, 'customer_analytics_pg', 'READ')\n"
                "print('INITIAL_ADMIN_NO_DEFAULT_DB_OK')\n"
            )
            env = os.environ.copy()
            env["HADIL_DEPLOYMENT_MODE"] = "cloud"
            env["HADIL_JWT_SECRET"] = "cloud-test-secret-not-default-value"
            env["HADIL_METADATA_DB"] = meta_path
            env["DATABASE_FOLDER"] = empty_folder
            env.pop("HADIL_METADATA_DATABASE_URL", None)
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("INITIAL_ADMIN_NO_DEFAULT_DB_OK", result.stdout)
        finally:
            try:
                os.remove(meta_path)
            except OSError:
                pass
            shutil.rmtree(empty_folder, ignore_errors=True)


class TestMasterAdminAssignsDatabaseAdmin(unittest.TestCase):
    """MASTER_ADMIN/SuAdmin may grant database-scoped ADMIN regardless of username."""

    def test_user_management_ui_uses_master_admin_role_not_username(self):
        path = os.path.join(REPO_ROOT, "frontend", "src", "components", "UserManagementView.jsx")
        with open(path, encoding="utf-8") as handle:
            src = handle.read()
        self.assertNotIn("username === 'admin'", src)
        self.assertIn("SUADMIN", src)
        self.assertIn("organization SUADMIN", src)
        app_path = os.path.join(REPO_ROOT, "frontend", "src", "App.jsx")
        with open(app_path, encoding="utf-8") as handle:
            app_src = handle.read()
        self.assertIn("currentRole={role}", app_src)

    def test_suadmin_not_named_admin_can_assign_admin_on_selected_database(self):
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        fd, meta_path = tempfile.mkstemp(suffix="_hadil_rbac.db")
        os.close(fd)
        empty_folder = tempfile.mkdtemp(prefix="hadil_empty_dbs_")
        try:
            script = (
                "import os, sys\n"
                "os.environ['HADIL_DEPLOYMENT_MODE'] = 'cloud'\n"
                "os.environ['HADIL_JWT_SECRET'] = 'cloud-test-secret-not-default-value'\n"
                f"os.environ['HADIL_METADATA_DB'] = {meta_path!r}\n"
                f"os.environ['DATABASE_FOLDER'] = {empty_folder!r}\n"
                "os.environ.pop('HADIL_METADATA_DATABASE_URL', None)\n"
                f"sys.path.insert(0, {backend_dir!r})\n"
                "from fastapi.testclient import TestClient\n"
                "from database.metadata_db import HadilUserDatabaseRole, HadilDatabase, MetadataBase, metadata_manager\n"
                "from services.metadata_service import MetadataService\n"
                "from database.manager import db_manager\n"
                "from validators.security import create_access_token\n"
                "from main import app\n"
                "MetadataBase.metadata.drop_all(bind=metadata_manager.engine)\n"
                "MetadataBase.metadata.create_all(bind=metadata_manager.engine)\n"
                "su = MetadataService.create_first_admin('platform_master', 'MasterPass123!')\n"
                "client = TestClient(app)\n"
                "master_headers = {'Authorization': f'Bearer {create_access_token(su.id, su.username)}'}\n"
                "signup = client.post('/api/auth/signup', json={'username': 'admin1', 'organization': 'org1', 'password': 'OrgPass123!', 'confirm_password': 'OrgPass123!'})\n"
                "assert signup.status_code == 200, signup.text\n"
                "org_id = signup.json()['organization_id']\n"
                "pending_login = client.post('/api/auth/login', json={'username': 'admin1@org1', 'password': 'OrgPass123!'})\n"
                "assert pending_login.status_code == 403, pending_login.text\n"
                "pending = client.get('/api/platform/organizations?status=PENDING', headers=master_headers)\n"
                "assert pending.status_code == 200, pending.text\n"
                "assert pending.json()['organizations'][0]['slug'] == 'org1'\n"
                "approve = client.post(f'/api/platform/organizations/{org_id}/approve', headers=master_headers)\n"
                "assert approve.status_code == 200, approve.text\n"
                "assert approve.json()['suadmin_role'] == 'SUADMIN'\n"
                "login_ok = client.post('/api/auth/login', json={'username': 'admin1@org1', 'password': 'OrgPass123!'})\n"
                "assert login_ok.status_code == 200, login_ok.text\n"
                "suadmin_id = login_ok.json()['user_id']\n"
                "su_headers = {'Authorization': f'Bearer {create_access_token(suadmin_id, \"admin1@org1\")}'}\n"
                "me = client.get('/api/auth/me', headers=su_headers)\n"
                "assert me.status_code == 200, me.text\n"
                "assert me.json()['role'] == 'SUADMIN'\n"
                "assert me.json()['permissions'] == ['READ', 'ADD', 'UPDATE', 'DELETE', 'MANAGE_USERS']\n"
                "MetadataService.register_or_update_database(\n"
                "    'Test', 'Test', 'postgresql',\n"
                "    connection_uri='postgresql://u:p@db.example:5432/test',\n"
                "    organization_id=org_id,\n"
                ")\n"
                "MetadataService.register_or_update_database(\n"
                "    'OtherDb', 'Other', 'postgresql',\n"
                "    connection_uri='postgresql://u:p@db.example:5432/other',\n"
                "    organization_id=org_id,\n"
                ")\n"
                "db_manager.current_db_id = 'Test'\n"
                "create_admin = client.post('/api/users', json={'username': 'db_admin_b', 'password': 'UserBPass123!', 'role': 'ADMIN'}, headers=su_headers)\n"
                "assert create_admin.status_code == 200, create_admin.text\n"
                "user_b_id = create_admin.json()['user_id']\n"
                "assert create_admin.json()['username'] == 'db_admin_b@org1'\n"
                "db = metadata_manager.get_session()\n"
                "try:\n"
                "    roles = db.query(HadilUserDatabaseRole).filter(HadilUserDatabaseRole.user_id == user_b_id).all()\n"
                "    assert [(r.database_id, r.role) for r in roles] == [('Test', 'ADMIN')]\n"
                "    assert db.query(HadilDatabase).filter(HadilDatabase.id == 'default_db').count() == 0\n"
                "    master_roles = db.query(HadilUserDatabaseRole).filter(HadilUserDatabaseRole.user_id == su.id).all()\n"
                "    assert master_roles == []\n"
                "finally:\n"
                "    db.close()\n"
                "assert MetadataService.get_user_role_for_database(user_b_id, 'Test') == 'ADMIN'\n"
                "assert MetadataService.get_user_role_for_database(user_b_id, 'OtherDb') is None\n"
                "assert MetadataService.get_user_role_for_database(su.id, 'Test') is None\n"
                "assert MetadataService.get_user_role_for_database(suadmin_id, 'Test') == 'SUADMIN'\n"
                "create_editor = client.post('/api/users', json={'username': 'editor_c', 'password': 'EditorPass123!', 'role': 'EDITOR'}, headers=su_headers)\n"
                "assert create_editor.status_code == 200, create_editor.text\n"
                "editor_id = create_editor.json()['user_id']\n"
                "create_viewer = client.post('/api/users', json={'username': 'viewer_d', 'password': 'ViewerPass123!', 'role': 'VIEWER'}, headers=su_headers)\n"
                "assert create_viewer.status_code == 200, create_viewer.text\n"
                "viewer_id = create_viewer.json()['user_id']\n"
                "db_admin_headers = {'Authorization': f'Bearer {create_access_token(user_b_id, \"db_admin_b@org1\")}'}\n"
                "blocked_admin = client.post('/api/users', json={'username': 'should_fail_admin', 'password': 'Nope123!', 'role': 'ADMIN'}, headers=db_admin_headers)\n"
                "assert blocked_admin.status_code == 403, blocked_admin.text\n"
                "editor_headers = {'Authorization': f'Bearer {create_access_token(editor_id, \"editor_c@org1\")}'}\n"
                "blocked_editor = client.post('/api/users', json={'username': 'should_fail_editor', 'password': 'Nope123!', 'role': 'ADMIN'}, headers=editor_headers)\n"
                "assert blocked_editor.status_code == 403, blocked_editor.text\n"
                "viewer_headers = {'Authorization': f'Bearer {create_access_token(viewer_id, \"viewer_d@org1\")}'}\n"
                "blocked_viewer = client.post('/api/users', json={'username': 'should_fail_viewer', 'password': 'Nope123!', 'role': 'ADMIN'}, headers=viewer_headers)\n"
                "assert blocked_viewer.status_code == 403, blocked_viewer.text\n"
                "assign_editor_ok = client.post(f'/api/users/{editor_id}/roles', json={'user_id': editor_id, 'role': 'VIEWER'}, headers=su_headers)\n"
                "assert assign_editor_ok.status_code == 200, assign_editor_ok.text\n"
                "print('MASTER_ADMIN_ASSIGN_ADMIN_OK')\n"
            )
            env = os.environ.copy()
            env["HADIL_DEPLOYMENT_MODE"] = "cloud"
            env["HADIL_JWT_SECRET"] = "cloud-test-secret-not-default-value"
            env["HADIL_METADATA_DB"] = meta_path
            env["DATABASE_FOLDER"] = empty_folder
            env.pop("HADIL_METADATA_DATABASE_URL", None)
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("MASTER_ADMIN_ASSIGN_ADMIN_OK", result.stdout)
        finally:
            try:
                os.remove(meta_path)
            except OSError:
                pass
            shutil.rmtree(empty_folder, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
