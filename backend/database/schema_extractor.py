from sqlalchemy import inspect
from database.session import get_engine

HADIL_SYSTEM_TABLES = {
    "hadil_query_history",
    "hadil_database_insights",
}

HADIL_SYSTEM_TABLE_PREFIXES = ("hadil_", "meta_")

def is_system_table(table_name: str) -> bool:
    """
    Centralized check to determine if a table is a HADIL internal/system table.
    System tables are excluded from all user-facing schema metadata discovery.
    """
    if not table_name:
        return False
    t_lower = table_name.lower()
    if t_lower in HADIL_SYSTEM_TABLES:
        return True
    return t_lower.startswith(HADIL_SYSTEM_TABLE_PREFIXES)

def get_filtered_tables(engine=None):
    target_engine = engine if engine is not None else get_engine()
    if not target_engine:
        return []
    inspector = inspect(target_engine)
    all_tables = inspector.get_table_names()
    return [
        t for t in all_tables 
        if not is_system_table(t)
    ]

def get_filtered_schema():
    """
    Returns a compact, token-efficient text representation of the filtered database schema.
    """
    inspector = inspect(get_engine())
    tables = get_filtered_tables()
    lines = ["Schema:"]
    for table_name in tables:
        columns = inspector.get_columns(table_name)
        col_str = ", ".join([f"{c['name']} {str(c['type']).split('(')[0]}" for c in columns])
        lines.append(f"{table_name}({col_str})")
    return "\n".join(lines)

def get_schema_context():
    """
    Deprecated: Use get_filtered_schema instead. 
    Kept for compatibility but now returns filtered schema.
    """
    return get_filtered_schema()

def get_table_schema(table_name: str):
    """
    Returns detailed metadata for a specific table.
    """
    if is_system_table(table_name):
        return None
        
    inspector = inspect(get_engine())
    if table_name not in inspector.get_table_names():
        return None
    
    columns = inspector.get_columns(table_name)
    schema = []
    for col in columns:
        schema.append({
            "name": col["name"],
            "type": str(col["type"]),
            "nullable": col["nullable"],
            "default": str(col["default"]) if col["default"] is not None else None,
            "primary_key": col.get("primary_key", False)
        })
    return schema

def extract_schema_snapshot() -> dict:
    """
    Extracts complete schema metadata (tables, columns, types, primary keys, foreign keys, constraints).
    MUST NOT contain database rows.
    """
    inspector = inspect(get_engine())
    tables = get_filtered_tables()
    snapshot = {
        "tables": []
    }
    
    for table_name in tables:
        columns = inspector.get_columns(table_name)
        pk_constraint = inspector.get_pk_constraint(table_name)
        foreign_keys = inspector.get_foreign_keys(table_name)
        
        col_meta = []
        for col in columns:
            col_meta.append({
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": col.get("nullable", True),
                "default": str(col["default"]) if col.get("default") is not None else None
            })
            
        fk_meta = []
        for fk in foreign_keys:
            fk_meta.append({
                "constrained_columns": fk.get("constrained_columns", []),
                "referred_table": fk.get("referred_table"),
                "referred_columns": fk.get("referred_columns", [])
            })

        snapshot["tables"].append({
            "table_name": table_name,
            "columns": col_meta,
            "primary_keys": pk_constraint.get("constrained_columns", []),
            "foreign_keys": fk_meta
        })
        
    return snapshot

