import os
import unittest
from unittest.mock import MagicMock, patch

import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine

from database.manager import normalize_db_uri, DatabaseManager

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REQUIREMENTS_PATH = os.path.join(REPO_ROOT, "backend", "requirements.txt")
WINDOWS_REQUIREMENTS_PATH = os.path.join(REPO_ROOT, "backend", "requirements-windows.txt")
RENDER_YAML_PATH = os.path.join(REPO_ROOT, "deploy", "render.yaml")


def _requirement_names(path):
    names = []
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            names.append(line.split("==")[0].split(">")[0].split("<")[0].strip().lower())
    return names


class TestPostgreSQLDriverResolution(unittest.TestCase):
    def test_normalize_postgres_uris_to_psycopg2(self):
        encoded = "postgres://user:p%40ss%23word@db.example.com:5432/app?sslmode=require"
        self.assertEqual(
            normalize_db_uri(encoded),
            "postgresql+psycopg2://user:p%40ss%23word@db.example.com:5432/app?sslmode=require",
        )
        self.assertEqual(
            normalize_db_uri("postgresql://user:pass@localhost/db"),
            "postgresql+psycopg2://user:pass@localhost/db",
        )
        self.assertEqual(
            normalize_db_uri("postgresql+psycopg2://user:pass@localhost/db"),
            "postgresql+psycopg2://user:pass@localhost/db",
        )

    def test_mysql_normalization_is_preserved(self):
        self.assertEqual(
            normalize_db_uri("mysql://user:pass@localhost:3306/testdb"),
            "mysql+pymysql://user:pass@localhost:3306/testdb",
        )

    def test_sqlalchemy_engine_uses_psycopg2_dialect(self):
        uri = normalize_db_uri("postgresql://mockuser:mockpass@localhost:5432/mockdb")
        engine = create_engine(uri)
        self.assertEqual(engine.dialect.name, "postgresql")
        self.assertEqual(engine.driver, "psycopg2")
        engine.dispose()

    def test_render_requirements_install_psycopg2_binary_and_pymysql(self):
        cloud_reqs = _requirement_names(REQUIREMENTS_PATH)
        windows_reqs = _requirement_names(WINDOWS_REQUIREMENTS_PATH)
        self.assertIn("psycopg2-binary", cloud_reqs)
        self.assertIn("pymysql", cloud_reqs)
        self.assertNotIn("psycopg2", cloud_reqs)
        self.assertNotIn("psycopg2-binary", windows_reqs)
        with open(RENDER_YAML_PATH, encoding="utf-8") as handle:
            render_src = handle.read()
        self.assertIn("pip install -r backend/requirements.txt", render_src)
        self.assertNotIn("requirements-windows.txt", render_src)

    def test_psycopg2_is_importable(self):
        import psycopg2  # noqa: F401

    def test_test_connection_uses_psycopg2_url_without_live_connect(self):
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        with patch.object(DatabaseManager, "list_databases", return_value=[]), \
             patch("database.manager.create_engine", return_value=mock_engine) as mock_create:
            mgr = DatabaseManager()
            result = mgr.test_connection(
                "postgres://u:p%40ss@aws-0.pooler.supabase.com:6543/postgres?sslmode=require"
            )
        self.assertTrue(result["success"])
        used_url = mock_create.call_args.args[0]
        self.assertTrue(used_url.startswith("postgresql+psycopg2://"))
        self.assertIn("p%40ss", used_url)
        self.assertIn("sslmode=require", used_url)


if __name__ == "__main__":
    unittest.main()
