import re
import logging
from typing import Optional
from sqlalchemy import inspect
from database.session import get_engine

logger = logging.getLogger(__name__)

def quote_sql_identifiers(sql: str, engine=None) -> str:
    """
    Enforces dialect-correct identifier quoting on raw SQL strings immediately before execution/validation.
    Ensures reflected schema table and column identifiers with uppercase or mixed-case characters
    (e.g., 'Orders', 'CustomerDetails') are quoted appropriately for the target database dialect
    (PostgreSQL: "Orders", MySQL: `Orders`, SQLite: "Orders").
    """
    if not sql or not sql.strip():
        return sql

    print("[HADIL SQL SANITIZER] ACTIVE")
    logger.info("[HADIL SQL SANITIZER] ACTIVE")

    if engine is None:
        engine = get_engine()

    if not engine:
        return sql

    target_tables = []
    columns_map = {}
    try:
        from database.schema_extractor import is_system_table
        inspector = inspect(engine)
        reflected = inspector.get_table_names()
        target_tables = [t for t in reflected if not is_system_table(t)]
        for t in target_tables:
            try:
                columns_map[t] = inspector.get_columns(t)
            except Exception:
                columns_map[t] = []
    except Exception as e:
        logger.warning(f"Could not inspect engine for identifier quoting: {e}")
        try:
            from database.schema_extractor import get_filtered_tables, get_table_schema
            target_tables = get_filtered_tables()
            for t in target_tables:
                columns_map[t] = get_table_schema(t) or []
        except Exception:
            return sql

    if not target_tables:
        return sql

    dialect_preparer = engine.dialect.identifier_preparer

    # 1. Process Table Identifiers
    modified_sql = sql
    for table_name in target_tables:
        has_uppercase = any(c.isupper() for c in table_name)
        quoted_name = dialect_preparer.quote(table_name)

        if has_uppercase:
            # Match unquoted table_name case-insensitively (e.g. Orders, orders, ORDERS) if the reflected schema table has uppercase letters
            pattern = r'(?<!["`\[])\b' + re.escape(table_name) + r'\b(?!["`\]])'
            modified_sql = re.sub(pattern, quoted_name, modified_sql, flags=re.IGNORECASE)

        # 2. Process Column Identifiers for this table
        try:
            columns = columns_map.get(table_name, [])
            for col in columns:
                col_name = col["name"] if isinstance(col, dict) else (col.get("name") if hasattr(col, "get") else getattr(col, "name", str(col)))
                if any(c.isupper() for c in col_name):
                    quoted_col = dialect_preparer.quote(col_name)
                    col_pattern = r'(?<!["`\[])\b' + re.escape(col_name) + r'\b(?!["`\]])'
                    modified_sql = re.sub(col_pattern, quoted_col, modified_sql)
        except Exception as col_err:
            logger.debug(f"Could not inspect columns for table {table_name}: {col_err}")

    if modified_sql != sql:
        logger.info(f"Identifier Quoting Transformer: Transformed SQL from '{sql}' to '{modified_sql}'")

    return modified_sql
