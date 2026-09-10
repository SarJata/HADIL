import unittest
from unittest.mock import patch, MagicMock
from database.manager import DatabaseManager
from services.metadata_service import MetadataService
from database.metadata_db import metadata_manager, MetadataBase, HadilDatabase

class TestRemoteDBRegistrationAndReactivity(unittest.TestCase):
    def setUp(self):
        # Create metadata tables in memory / metadata manager
        MetadataBase.metadata.create_all(bind=metadata_manager.engine)
        self.db_manager = DatabaseManager()

    def test_remote_db_registration_and_list(self):
        # 1. Register remote database via MetadataService
        remote_id = "remote_mysql_test"
        remote_name = "Production Remote MySQL"
        remote_type = "mysql"
        remote_uri = "mysql+pymysql://testuser:testpass@remotehost:3306/remotedb"

        MetadataService.register_or_update_database(
            db_id=remote_id,
            name=remote_name,
            database_type=remote_type,
            connection_uri=remote_uri
        )

        # 2. Verify registered remote DB appears in list_databases()
        dbs = self.db_manager.list_databases()
        registered_ids = [d["id"] for d in dbs]
        self.assertIn(remote_id, registered_ids)

        remote_item = next(d for d in dbs if d["id"] == remote_id)
        self.assertEqual(remote_item["name"], remote_name)
        self.assertEqual(remote_item["type"], remote_type)

    def test_remote_db_config_retrieval_and_decryption(self):
        remote_id = "remote_pg_test"
        remote_name = "Analytics Postgres"
        remote_type = "postgresql"
        remote_uri = "postgresql://pguser:secretpass@pghost:5432/analytics"

        MetadataService.register_or_update_database(
            db_id=remote_id,
            name=remote_name,
            database_type=remote_type,
            connection_uri=remote_uri
        )

        # 3. Check get_database_config returns decrypted URI for connection engine
        config = self.db_manager.get_database_config(remote_id)
        self.assertIsNotNone(config)
        self.assertEqual(config["id"], remote_id)
        self.assertEqual(config["name"], remote_name)
        self.assertEqual(config["connection"], remote_uri)

        # 4. Verify password is NOT exposed in list_databases or list_registered_databases
        registered_list = MetadataService.list_registered_databases()
        target = next(r for r in registered_list if r["id"] == remote_id)
        self.assertNotIn("secretpass", str(target))
        self.assertNotIn("connection_uri", target)

    @patch("database.manager.create_engine")
    def test_switch_between_local_and_remote_databases(self, mock_create_engine):
        mock_engine = MagicMock()
        mock_engine.name = "mysql"
        mock_create_engine.return_value = mock_engine


        # Register remote database
        remote_id = "remote_switch_db"
        remote_uri = "mysql+pymysql://usr:pwd@host:3306/db"
        MetadataService.register_or_update_database(
            db_id=remote_id,
            name="Remote Switch Test",
            database_type="mysql",
            connection_uri=remote_uri
        )

        # Set database to remote
        config = self.db_manager.set_database(remote_id)
        self.assertEqual(self.db_manager.current_db_id, remote_id)
        self.assertEqual(self.db_manager.current_db_name, "Remote Switch Test")
        self.assertEqual(self.db_manager.custom_connection_uri, remote_uri)

        # Switch back to local sqlite DB
        local_dbs = [d for d in self.db_manager.list_databases() if d["type"] == "sqlite"]
        if local_dbs:
            local_id = local_dbs[0]["id"]
            with patch("os.path.exists", return_value=True):
                self.db_manager.set_database(local_id)
            self.assertEqual(self.db_manager.current_db_id, local_id)
            self.assertIsNone(self.db_manager.custom_connection_uri)


    def test_registered_remote_db_not_treated_as_local_file(self):
        remote_id = "remote_pg_test"
        remote_name = "Analytics Postgres"
        remote_type = "postgresql"
        remote_uri = "postgresql://pguser:secretpass@pghost:5432/analytics"

        MetadataService.register_or_update_database(
            db_id=remote_id,
            name=remote_name,
            database_type=remote_type,
            connection_uri=remote_uri
        )

        with patch("database.manager.create_engine") as mock_create:
            mock_engine = MagicMock()
            mock_engine.name = "postgresql"
            mock_create.return_value = mock_engine
            self.db_manager.set_database(remote_id)


        self.assertEqual(self.db_manager.current_db_id, remote_id)
        self.assertEqual(self.db_manager.custom_connection_uri, remote_uri)

    def test_startup_does_not_call_ddl_with_none_engine(self):
        from routes.api import startup
        with patch("routes.api.get_engine", return_value=None), \
             patch("routes.api.models.Base.metadata.create_all") as mock_create_all:
            startup()
            mock_create_all.assert_not_called()


    def test_registered_remote_db_not_auto_selected_on_startup(self):
        remote_id = "aaa_remote_postgres"
        remote_name = "AAA Postgres DB"
        remote_type = "postgresql"
        remote_uri = "postgresql://user:pass@host:5432/db"

        MetadataService.register_or_update_database(
            db_id=remote_id,
            name=remote_name,
            database_type=remote_type,
            connection_uri=remote_uri
        )

        # Fresh DatabaseManager instance startup
        fresh_manager = DatabaseManager()
        self.assertNotEqual(fresh_manager.current_db_id, remote_id)
        if fresh_manager.current_db_id:
            self.assertTrue(fresh_manager.current_db_id.endswith(".db") or fresh_manager.current_db_id == "default_db")


if __name__ == "__main__":
    unittest.main()


