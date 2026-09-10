import unittest
from unittest.mock import MagicMock, patch
from database.models import User, HadilQueryHistory, HadilDatabaseInsight
from sqlalchemy.types import String, VARCHAR
from sqlalchemy.dialects import mysql, sqlite, postgresql

class TestSchemaTypeHandling(unittest.TestCase):
    def test_sqlalchemy_model_string_lengths_defined(self):
        """
        Ensures all String/VARCHAR columns defined in database/models.py include explicit lengths,
        preventing 'VARCHAR requires a length on dialect mysql' DDL errors.
        """
        for model in [User, HadilQueryHistory, HadilDatabaseInsight]:
            for col in model.__table__.columns:
                if isinstance(col.type, (String, VARCHAR)):
                    self.assertIsNotNone(
                        col.type.length, 
                        f"Column '{col.name}' in table '{model.__tablename__}' lacks explicit length requirement for MySQL DDL compatibility."
                    )

    def test_mysql_varchar_length_preservation(self):
        """
        Verifies that MySQL VARCHAR columns preserve their exact source length when compiled for MySQL dialect.
        """
        v100 = VARCHAR(100)
        v255 = VARCHAR(255)
        
        self.assertEqual(v100.length, 100)
        self.assertEqual(v255.length, 255)
        
        # Verify dialect compilation does not drop length
        compiled_100 = str(v100.compile(dialect=mysql.dialect()))
        compiled_255 = str(v255.compile(dialect=mysql.dialect()))
        
        self.assertIn("VARCHAR(100)", compiled_100)
        self.assertIn("VARCHAR(255)", compiled_255)

    def test_sqlite_string_length_flexibility(self):
        """
        Verifies that SQLite dialect continues to accept both explicit and un-lengthed String columns smoothly.
        """
        s_bare = String()
        s_len = String(100)
        
        compiled_bare = str(s_bare.compile(dialect=sqlite.dialect()))
        compiled_len = str(s_len.compile(dialect=sqlite.dialect()))
        
        self.assertIn("VARCHAR", compiled_bare)
        self.assertIn("VARCHAR(100)", compiled_len)

if __name__ == "__main__":
    unittest.main()
