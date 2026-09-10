import unittest
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.manager import DatabaseManager, normalize_db_uri

from sqlalchemy.engine import Engine
from sqlalchemy import create_engine

class TestMySQLDriverResolution(unittest.TestCase):
    def test_normalize_db_uri_mysql(self):
        # 1. Standard mysql:// bare URI -> mysql+pymysql://
        uri1 = "mysql://user:pass@localhost:3306/testdb"
        self.assertEqual(normalize_db_uri(uri1), "mysql+pymysql://user:pass@localhost:3306/testdb")

        # 2. mysql+mysqldb:// -> mysql+pymysql://
        uri2 = "mysql+mysqldb://user:pass@localhost:3306/testdb"
        self.assertEqual(normalize_db_uri(uri2), "mysql+pymysql://user:pass@localhost:3306/testdb")

        # 3. mysql+pymysql:// explicit -> untouched
        uri3 = "mysql+pymysql://user:pass@sql.freedb.tech:3306/testdb"
        self.assertEqual(normalize_db_uri(uri3), "mysql+pymysql://user:pass@sql.freedb.tech:3306/testdb")

        # 4. Other drivers (sqlite, postgresql) -> untouched
        self.assertEqual(normalize_db_uri("sqlite:///test.db"), "sqlite:///test.db")
        self.assertEqual(normalize_db_uri("postgresql://user:pass@localhost/db"), "postgresql://user:pass@localhost/db")

    def test_sqlalchemy_engine_uses_pymysql_dialect(self):
        uri = "mysql+pymysql://mockuser:mockpass@localhost:3306/mockdb"
        normalized = normalize_db_uri(uri)
        engine = create_engine(normalized)
        
        # Verify engine dialect driver is pymysql (NOT mysqldb)
        self.assertEqual(engine.dialect.name, "mysql")
        self.assertEqual(engine.driver, "pymysql")
        self.assertNotEqual(engine.driver, "mysqldb")
        engine.dispose()

if __name__ == "__main__":
    unittest.main()
