import asyncio
import inspect
import json
import os
import sys
import unittest
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, text
from starlette.responses import JSONResponse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.result_serializer import serialize_query_rows


class _Row:
    def __init__(self, mapping):
        self._mapping = mapping


class TestQueryResultSerialization(unittest.TestCase):
    def test_uuid_becomes_json_string(self):
        value = uuid.UUID("12345678-1234-5678-1234-567812345678")
        rows = serialize_query_rows([_Row({"id": value})])
        self.assertEqual(rows, [{"id": "12345678-1234-5678-1234-567812345678"}])
        json.dumps(rows)

    def test_uuid_alongside_string_and_integer(self):
        value = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        rows = serialize_query_rows([
            {"id": value, "name": "ada", "qty": 3, "active": True, "note": None}
        ])
        self.assertEqual(rows, [{
            "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "name": "ada",
            "qty": 3,
            "active": True,
            "note": None,
        }])
        self.assertIsInstance(rows[0]["qty"], int)
        self.assertIsInstance(rows[0]["active"], bool)
        json.dumps(rows)

    def test_nested_uuid_datetime_date_time_and_decimal(self):
        value = uuid.UUID("11111111-2222-3333-4444-555555555555")
        created = datetime(2024, 5, 6, 7, 8, 9)
        when = time(7, 8, 9)
        rows = serialize_query_rows([{
            "id": value,
            "created_at": created,
            "on_day": date(2024, 5, 6),
            "at_time": when,
            "amount": Decimal("19.99"),
            "whole": Decimal("4"),
            "tags": [value, {"ref": value}],
            "blob": memoryview(b"hello"),
        }])
        row = rows[0]
        self.assertEqual(row["id"], str(value))
        self.assertEqual(row["created_at"], created.isoformat())
        self.assertEqual(row["on_day"], "2024-05-06")
        self.assertEqual(row["at_time"], when.isoformat())
        self.assertEqual(row["amount"], float(Decimal("19.99")))
        self.assertEqual(row["whole"], 4)
        self.assertIsInstance(row["whole"], int)
        self.assertEqual(row["tags"], [str(value), {"ref": str(value)}])
        self.assertEqual(row["blob"], "hello")
        json.dumps(rows)

    def test_sqlite_result_values_stay_unchanged(self):
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE items (id INTEGER, name TEXT, price REAL, active INTEGER, note TEXT)"
            ))
            conn.execute(text(
                "INSERT INTO items (id, name, price, active, note) VALUES (1, 'ada', 2.5, 1, NULL)"
            ))
            fetched = conn.execute(text("SELECT id, name, price, active, note FROM items")).fetchall()
        original = [dict(row._mapping) for row in fetched]
        serialized = serialize_query_rows(fetched)
        self.assertEqual(serialized, original)
        self.assertEqual(serialized, [{
            "id": 1,
            "name": "ada",
            "price": 2.5,
            "active": 1,
            "note": None,
        }])
        engine.dispose()

    def test_mysql_json_native_values_stay_unchanged(self):
        """PyMySQL already returns JSON-native scalars for these column types."""
        original = [{
            "id": 7,
            "name": "widget",
            "ratio": 1.25,
            "active": True,
            "note": None,
        }]
        self.assertEqual(serialize_query_rows(original), original)

    def test_mysql_decimal_and_datetime_match_response_encoder(self):
        """
        MySQL DECIMAL/DATETIME reach the API as Decimal and datetime.
        FastAPI's response encoder already turns those into int/float and ISO strings.
        """
        created = datetime(2024, 1, 2, 3, 4, 5)
        original = [{
            "id": 7,
            "name": "widget",
            "price": Decimal("10.50"),
            "qty": Decimal("3"),
            "created_at": created,
            "active": False,
        }]
        serialized = serialize_query_rows(original)
        self.assertEqual(serialized, [{
            "id": 7,
            "name": "widget",
            "price": float(Decimal("10.50")),
            "qty": 3,
            "created_at": created.isoformat(),
            "active": False,
        }])
        self.assertIsInstance(serialized[0]["qty"], int)
        self.assertIs(serialized[0]["active"], False)


class TestInterpretQueryResultWithNormalizedData(unittest.TestCase):
    def test_interpret_json_dumps_succeeds_on_normalized_postgresql_row(self):
        """
        Confirmed failure path: PostgreSQL uuid.UUID must be normalized before
        interpret_query_result() calls stdlib json.dumps(data).
        """
        from ai_modules.interpreter import interpret_query_result

        raw = [{
            "id": uuid.UUID("20000000-0000-0000-0000-000000000001"),
            "full_name": "Siddharth Rao",
            "email": "si***@ex***",
            "course_count": 2,
        }]
        with self.assertRaises(TypeError) as ctx:
            json.dumps(raw)
        self.assertIn("UUID", str(ctx.exception))

        normalized = serialize_query_rows(raw)
        self.assertEqual(normalized[0]["id"], "20000000-0000-0000-0000-000000000001")
        json.dumps(normalized)

        provider = MagicMock()
        provider.generate_json.return_value = {
            "interpretation": "One student is enrolled in more than one course."
        }
        with patch("ai_modules.interpreter.get_llm_provider", return_value=provider):
            answer = interpret_query_result(
                "Are there students enrolled in more than one course",
                normalized,
            )
        self.assertEqual(answer, "One student is enrolled in more than one course.")
        self.assertTrue(provider.generate_json.called)
        prompt = provider.generate_json.call_args[0][1]
        self.assertIn("20000000-0000-0000-0000-000000000001", prompt)
        self.assertIn("course_count", prompt)

    def test_interpret_json_dumps_failure_is_contained(self):
        """Secondary hardening: raw UUID data must not abort the caller."""
        from ai_modules.interpreter import interpret_query_result

        provider = MagicMock()
        with patch("ai_modules.interpreter.get_llm_provider", return_value=provider):
            answer = interpret_query_result(
                "Are there students enrolled in more than one course",
                [{"id": uuid.UUID("20000000-0000-0000-0000-000000000001")}],
            )
        self.assertIsNone(answer)
        provider.generate_json.assert_not_called()


class TestExecuteQueryJsonBoundary(unittest.TestCase):
    def _run_execute(self, rows, natural_query="Show the customer id", sql=None):
        from routes.api import ExecuteRequest, execute_query

        mock_db = MagicMock()
        mock_db.execute.return_value.fetchall.return_value = rows
        provider = MagicMock()
        provider.generate_json.return_value = {"interpretation": "One customer row."}

        with patch("routes.api.db_manager") as mgr, \
             patch("ai_modules.interpreter.get_llm_provider", return_value=provider), \
             patch("routes.api.extract_query_context", return_value=None):
            mgr.engine = None
            mgr.current_db_id = None
            request = ExecuteRequest(
                sql=sql or "SELECT id, name, qty FROM customers LIMIT 5",
                natural_query=natural_query,
                is_verified=True,
            )
            result = asyncio.run(execute_query(request, db=mock_db))
        return result

    def test_execute_query_response_shape_and_json_encoding(self):
        customer_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
        created = datetime(2024, 5, 6, 7, 8, 9)
        result = self._run_execute([
            _Row({
                "id": customer_id,
                "name": "ada",
                "qty": 3,
                "amount": Decimal("19.99"),
                "created_at": created,
            })
        ])

        self.assertTrue(result["success"], result)
        self.assertEqual(
            set(result.keys()),
            {
                "success",
                "data",
                "interpreted_answer",
                "columns",
                "suggested_visualization",
                "metadata",
                "followup_suggestions",
            },
        )
        self.assertEqual(result["columns"], ["id", "name", "qty", "amount", "created_at"])
        self.assertEqual(result["data"], [{
            "id": str(customer_id),
            "name": "ada",
            "qty": 3,
            "amount": float(Decimal("19.99")),
            "created_at": created.isoformat(),
        }])
        self.assertIsInstance(result["interpreted_answer"], str)

        encoded = json.dumps(result)
        payload = json.loads(JSONResponse(result).body)
        self.assertIn(str(customer_id), encoded)
        self.assertEqual(payload["success"], True)
        self.assertEqual(payload["data"][0]["id"], str(customer_id))
        self.assertEqual(payload["data"][0]["name"], "ada")
        self.assertEqual(payload["data"][0]["qty"], 3)
        self.assertEqual(payload["columns"], result["columns"])

    def test_original_supabase_students_uuid_failure_now_succeeds(self):
        """
        Reproduce the production failure:

            PostgreSQL result with students.id uuid.UUID
            -> /api/execute-query
            -> interpret_query_result
            -> json.dumps
        """
        from routes.api import ExecuteRequest, execute_query

        student_id = uuid.UUID("20000000-0000-0000-0000-000000000001")
        rows = [_Row({
            "id": student_id,
            "full_name": "Siddharth Rao",
            "email": "si***@ex***",
            "course_count": 2,
        })]
        sql = (
            "SELECT s.id, s.full_name, s.email, COUNT(e.course_id) AS course_count "
            "FROM students s JOIN enrollments e ON s.id = e.student_id "
            "GROUP BY s.id, s.full_name, s.email HAVING COUNT(e.course_id) > 1"
        )
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchall.return_value = rows
        provider = MagicMock()
        provider.generate_json.return_value = {
            "interpretation": "Siddharth Rao is enrolled in more than one course."
        }

        with patch("routes.api.db_manager") as mgr, \
             patch("ai_modules.interpreter.get_llm_provider", return_value=provider), \
             patch("routes.api.extract_query_context", return_value=None):
            mgr.engine = MagicMock()
            mgr.engine.name = "postgresql"
            mgr.current_db_id = "Test"
            request = ExecuteRequest(
                sql=sql,
                natural_query="Are there students enrolled in more than one course",
                is_verified=True,
            )
            result = asyncio.run(execute_query(request, db=mock_db))

        self.assertTrue(result["success"], result)
        self.assertNotIn("error", result)
        self.assertEqual(result["data"], [{
            "id": "20000000-0000-0000-0000-000000000001",
            "full_name": "Siddharth Rao",
            "email": "si***@ex***",
            "course_count": 2,
        }])
        self.assertEqual(
            result["interpreted_answer"],
            "Siddharth Rao is enrolled in more than one course.",
        )
        self.assertTrue(provider.generate_json.called)
        dumped_prompt = provider.generate_json.call_args[0][1]
        self.assertIn("20000000-0000-0000-0000-000000000001", dumped_prompt)
        json.dumps(result)

    def test_mysql_datetime_visualization_uses_native_types(self):
        created = datetime(2024, 5, 1, 0, 0, 0)
        result = self._run_execute(
            [_Row({"stamp": created, "total": 10, "amount": Decimal("2.5")})],
            natural_query=None,
        )
        self.assertTrue(result["success"], result)
        self.assertIn("stamp", result["metadata"]["time_columns"])
        self.assertIn("total", result["metadata"]["numeric_columns"])
        self.assertNotIn("amount", result["metadata"]["numeric_columns"])
        self.assertEqual(result["data"][0]["stamp"], created.isoformat())
        self.assertEqual(result["data"][0]["total"], 10)
        self.assertEqual(result["suggested_visualization"], "line")

    def test_http_execute_query_encodes_uuid_result(self):
        from fastapi.testclient import TestClient
        from main import app
        from database.session import get_db
        from routes.api import execute_query

        customer_id = uuid.UUID("abcdefab-cdef-abcd-efab-cdefabcdefab")
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchall.return_value = [
            _Row({"id": customer_id, "name": "ada", "qty": 4})
        ]

        def override_db():
            yield mock_db

        user_dep = inspect.signature(execute_query).parameters["current_user"].default.dependency
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[user_dep] = lambda: {"sub": "1", "username": "tester"}
        provider = MagicMock()
        provider.generate_json.return_value = {"interpretation": "Ada."}

        try:
            with patch("routes.api.db_manager") as mgr, \
                 patch("ai_modules.interpreter.get_llm_provider", return_value=provider), \
                 patch("routes.api.extract_query_context", return_value=None):
                mgr.engine = None
                mgr.current_db_id = None
                client = TestClient(app)
                response = client.post("/api/execute-query", json={
                    "sql": "SELECT id, name, qty FROM customers LIMIT 5",
                    "natural_query": "Who is the customer?",
                    "is_verified": True,
                })
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(user_dep, None)

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["success"], payload)
        self.assertEqual(payload["data"], [{
            "id": str(customer_id),
            "name": "ada",
            "qty": 4,
        }])
        self.assertEqual(payload["columns"], ["id", "name", "qty"])
        self.assertIn("suggested_visualization", payload)
        self.assertIn("metadata", payload)
        self.assertIn("followup_suggestions", payload)
        json.dumps(payload)


if __name__ == "__main__":
    unittest.main()
