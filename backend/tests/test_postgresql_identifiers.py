import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.dialects import postgresql, mysql, sqlite
from sqlalchemy import Table, Column, MetaData, Integer, String, select

from ai_modules.generator import generate_sql_from_text
from validators.intent_classifier import extract_mutation_details

class TestPostgresqlIdentifierHandling(unittest.TestCase):

    def test_postgresql_compiler_identifier_quoting(self):
        """
        Verify that SQLAlchemy's PostgreSQL dialect compiler quotes mixed-case identifiers ("Orders")
        and leaves lowercase identifiers (orders) unquoted.
        """
        metadata = MetaData()
        table_orders_mixed = Table("Orders", metadata, Column("id", Integer, primary_key=True), Column("Amount", Integer))
        table_orders_lower = Table("orders", metadata, Column("id", Integer, primary_key=True), Column("amount", Integer))

        pg_dialect = postgresql.dialect()

        # Mixed-case "Orders" and "Amount" MUST be double-quoted in PostgreSQL
        stmt_mixed = select(table_orders_mixed)
        compiled_mixed = str(stmt_mixed.compile(dialect=pg_dialect))
        self.assertIn('"Orders"', compiled_mixed)
        self.assertIn('"Orders"."Amount"', compiled_mixed)

        # Lowercase "orders" and "amount" should remain unquoted in PostgreSQL
        stmt_lower = select(table_orders_lower)
        compiled_lower = str(stmt_lower.compile(dialect=pg_dialect))
        self.assertIn('FROM orders', compiled_lower)

    def test_cross_dialect_quoting_compatibility(self):
        """
        Verify that identifier quoting behavior is correct across PostgreSQL, MySQL, and SQLite.
        """
        metadata = MetaData()
        t = Table("Orders", metadata, Column("Id", Integer, primary_key=True))

        pg_sql = str(select(t).compile(dialect=postgresql.dialect()))
        mysql_sql = str(select(t).compile(dialect=mysql.dialect()))
        sqlite_sql = str(select(t).compile(dialect=sqlite.dialect()))

        # PostgreSQL quotes with double quotes: "Orders"
        self.assertIn('"Orders"', pg_sql)

        # MySQL quotes with backticks: `Orders`
        self.assertIn('`Orders`', mysql_sql)

        # SQLite quotes with double quotes when compiled with dialect: "Orders"
        self.assertIn('"Orders"', sqlite_sql)

    def test_extract_mutation_details_case_preservation(self):
        """
        Verify that target table extraction preserves exact casing of reflected table identifiers.
        """
        mock_tables = ["Orders", "users", "CustomerDetails"]

        from unittest.mock import patch
        with patch("database.schema_extractor.get_filtered_tables", return_value=mock_tables), \
             patch("database.schema_extractor.get_table_schema", return_value=[{"name": "id", "type": "INTEGER"}]):

            # Query with mixed case matching
            res_orders = extract_mutation_details("Add an item to Orders", "CREATE")
            self.assertEqual(res_orders["table"], "Orders")

            # Query with lower case matching should still resolve to reflected mixed-case "Orders"
            res_orders_lower = extract_mutation_details("Add an item to orders", "CREATE")
            self.assertEqual(res_orders_lower["table"], "Orders")

            # Lowercase table
            res_users = extract_mutation_details("Add a user", "CREATE")
            self.assertEqual(res_users["table"], "users")

            # Mixed-case CustomerDetails
            res_cust = extract_mutation_details("Add customer details", "CREATE")
            self.assertEqual(res_cust["table"], "CustomerDetails")

    def test_quote_sql_identifiers_execution_boundary(self):
        """
        Verify that quote_sql_identifiers automatically quotes unquoted raw SQL queries
        at the execution boundary based on the active engine dialect.
        """
        from validators.sql_sanitizer import quote_sql_identifiers
        from sqlalchemy import create_engine

        # Mock engine for PostgreSQL
        pg_engine = create_engine("postgresql+psycopg2://user:pass@localhost/db")

        from unittest.mock import patch
        mock_tables = ["Orders", "orders_lower", "CustomerDetails", "ORDERS_UPPER"]

        with patch("validators.sql_sanitizer.inspect") as mock_inspect:
            mock_inspector = MagicMock()
            mock_inspector.get_table_names.return_value = mock_tables
            mock_inspector.get_columns.return_value = []
            mock_inspect.return_value = mock_inspector

            # 1. Mixed case "Orders" -> "Orders"
            sql1 = "SELECT * FROM Orders LIMIT 50"
            out1 = quote_sql_identifiers(sql1, engine=pg_engine)
            self.assertEqual(out1, 'SELECT * FROM "Orders" LIMIT 50')

            # 2. Lowercase "orders_lower" -> remains unquoted orders_lower (no uppercase chars)
            sql2 = "SELECT * FROM orders_lower LIMIT 50"
            out2 = quote_sql_identifiers(sql2, engine=pg_engine)
            self.assertEqual(out2, 'SELECT * FROM orders_lower LIMIT 50')

            # 3. Mixed case "CustomerDetails" -> "CustomerDetails"
            sql3 = "SELECT * FROM CustomerDetails LIMIT 50"
            out3 = quote_sql_identifiers(sql3, engine=pg_engine)
            self.assertEqual(out3, 'SELECT * FROM "CustomerDetails" LIMIT 50')

            # 4. Uppercase "ORDERS_UPPER" -> "ORDERS_UPPER"
            sql4 = "SELECT * FROM ORDERS_UPPER LIMIT 50"
            out4 = quote_sql_identifiers(sql4, engine=pg_engine)
            self.assertEqual(out4, 'SELECT * FROM "ORDERS_UPPER" LIMIT 50')

            # 5. MySQL dialect engine -> `Orders`
            mysql_engine = MagicMock()
            mysql_engine.dialect.identifier_preparer = mysql.dialect().identifier_preparer
            out5 = quote_sql_identifiers(sql1, engine=mysql_engine)
            self.assertEqual(out5, 'SELECT * FROM `Orders` LIMIT 50')

            # 7. Unquoted lowercase query "orders" matching reflected mixed-case "Orders" table
            sql7 = "SELECT * FROM orders LIMIT 50"
            out7 = quote_sql_identifiers(sql7, engine=pg_engine)
            self.assertEqual(out7, 'SELECT * FROM "Orders" LIMIT 50')

    def test_full_pipeline_execute_query_boundary(self):
        """
        End-to-end regression test for /api/execute-query execution boundary.
        Verifies that even if incoming request.sql is unquoted ('SELECT * FROM orders LIMIT 50'),
        db.execute receives dialect-quoted ('SELECT * FROM "Orders" LIMIT 50').
        """
        from routes.api import execute_query, ExecuteRequest

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        pg_engine = MagicMock()
        pg_engine.name = "postgresql"
        pg_engine.dialect.identifier_preparer = postgresql.dialect().identifier_preparer

        from unittest.mock import patch
        with patch("routes.api.db_manager") as mock_db_mgr, \
             patch("validators.sql_sanitizer.inspect") as mock_inspect, \
             patch("routes.api.verify_sql_intent", return_value={"is_valid": True, "explanation": "Valid"}):

            mock_db_mgr.engine = pg_engine
            mock_inspector = MagicMock()
            mock_inspector.get_table_names.return_value = ["Orders"]
            mock_inspector.get_columns.return_value = []
            mock_inspect.return_value = mock_inspector

            req = ExecuteRequest(sql="SELECT * FROM orders LIMIT 50", natural_query="show me orders", is_direct_sql=False)
            
            # Execute async endpoint synchronously in test using asyncio.run
            import asyncio
            res = asyncio.run(execute_query(req, db=mock_db))

            # Verify that db.execute was called with text('SELECT * FROM "Orders" LIMIT 50')
            self.assertTrue(mock_db.execute.called)
            executed_text_obj = mock_db.execute.call_args[0][0]
            self.assertEqual(str(executed_text_obj), 'SELECT * FROM "Orders" LIMIT 50')

if __name__ == "__main__":
    unittest.main()
