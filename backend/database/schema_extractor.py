from sqlalchemy import inspect
from database.session import get_engine

def get_filtered_tables():
    inspector = inspect(get_engine())
    all_tables = inspector.get_table_names()
    return [
        t for t in all_tables 
        if not (t == "hadil_query_history" or t.startswith("hadil_") or t.startswith("meta_"))
    ]

def get_filtered_schema():
    """
    Returns a text representation of the filtered database schema (business tables only).
    """
    inspector = inspect(get_engine())
    tables = get_filtered_tables()
    schema_text = "Database Schema (Filtered):\n"
    
    for table_name in tables:
        schema_text += f"\nTable: {table_name}\n"
        columns = inspector.get_columns(table_name)
        for col in columns:
            schema_text += f"- {col['name']} ({col['type']})\n"
            
    return schema_text

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
    if table_name == "hadil_query_history" or table_name.startswith("hadil_") or table_name.startswith("meta_"):
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

