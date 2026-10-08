"""JSON-safe normalization for SQL query result rows.

PostgreSQL/psycopg2 returns native uuid.UUID (and often Decimal/datetime) values.
/api/execute-query previously passed those objects into interpret_query_result(),
which calls stdlib json.dumps and raises:
"Object of type UUID is not JSON serializable".

Normalize at the shared fetch boundary so SQLite, MySQL, and PostgreSQL rows are
JSON-safe before interpretation or the HTTP response. Uses FastAPI's
jsonable_encoder: JSON-native values stay as-is; UUID/datetime become strings;
Decimal becomes int or float. Nested lists and dicts are encoded recursively.
"""

from typing import Any, Dict, Iterable, List, Mapping

from fastapi.encoders import jsonable_encoder


def _encode_memoryview(value: memoryview) -> str:
    # Same outcome as FastAPI's bytes encoder: a JSON string.
    return bytes(value).decode()


_QUERY_ENCODERS = {memoryview: _encode_memoryview}


def serialize_query_value(value: Any) -> Any:
    """Normalize one result cell, including values nested in lists or dicts."""
    return jsonable_encoder(value, custom_encoder=_QUERY_ENCODERS)


def serialize_query_rows(rows: Iterable[Any]) -> List[Dict[str, Any]]:
    """Normalize SQLAlchemy rows or plain mappings into JSON-safe dicts."""
    serialized: List[Dict[str, Any]] = []
    for row in rows:
        if isinstance(row, Mapping):
            mapping = dict(row)
        elif hasattr(row, "_mapping"):
            mapping = dict(row._mapping)
        else:
            mapping = dict(row)
        serialized.append(serialize_query_value(mapping))
    return serialized
