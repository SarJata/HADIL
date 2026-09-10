import re
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

def detect_table_creation_intent(query: str) -> Optional[Dict[str, Any]]:
    """
    Deterministically detects explicit requests to create a new database table/schema.
    Returns dict with extracted table_name if matched, or None if not table creation.

    Examples matching:
    - "Create table user" -> table_name: "user"
    - "Create a table user" -> table_name: "user"
    - "Create a table called user" -> table_name: "user"
    - "Create a table named user" -> table_name: "user"
    - "Add table user" -> table_name: "user"
    - "Add a table user" -> table_name: "user"
    - "Add a table called user" -> table_name: "user"
    - "Make a new table user" -> table_name: "user"
    - "Make a new table called user" -> table_name: "user"
    - "Create a new table named user" -> table_name: "user"

    Does NOT match record creation:
    - "Create a user" -> record CREATE
    - "Create a user record" -> record CREATE
    - "Add a user" -> record CREATE
    - "Add an inventory item" -> record CREATE
    """
    if not query or not query.strip():
        return None

    q_clean = query.strip().lower()

    # Reject record-specific phrases like "create a table record" or "add a table row"
    if re.search(r'\btable\s+(?:record|records|row|rows|entry|entries|item|items)\b', q_clean):
        return None

    # Explicit schema / table creation patterns
    table_create_patterns = [
        r'\b(?:create|add|make|build)\s+(?:a\s+|an\s+)?(?:new\s+)?table\s+(?:called|named)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b',
        r'\b(?:create|add|make|build)\s+(?:a\s+|an\s+)?(?:new\s+)?table\s+([a-zA-Z_][a-zA-Z0-9_]*)\b',
    ]

    record_descriptors = {
        "record", "records", "row", "rows", "item", "items",
        "entry", "entries", "data", "field", "fields", "column", "columns"
    }

    for pat in table_create_patterns:
        match = re.search(pat, q_clean)
        if match:
            table_name = match.group(1).strip()
            if table_name not in record_descriptors:
                return {"is_table_creation": True, "table_name": table_name}

    # Catch-all for "create a table" or "make a new table" where table name is omitted or separated
    if re.search(r'\b(?:create|add|make|build)\s+(?:a\s+|an\s+)?(?:new\s+)?table\b', q_clean):
        return {"is_table_creation": True, "table_name": ""}

    return None


def detect_schema_metadata_intent(query: str) -> Optional[Dict[str, Any]]:
    """
    Deterministically detects schema / metadata queries such as:
    - "How many tables does my database have?" -> {"type": "TABLE_COUNT"}
    - "What tables are in the database?" -> {"type": "TABLE_LIST"}
    - "How many relationships exist?" -> {"type": "RELATIONSHIP_COUNT"}
    - "What columns does Orders have?" -> {"type": "COLUMN_LIST", "table": "Orders"}
    """
    if not query or not query.strip():
        return None

    q_clean = query.strip().lower()

    # Rule A: Table count queries
    if re.search(r'\bhow\s+many\s+tables\b', q_clean) or re.search(r'\bcount\s+of\s+tables\b', q_clean) or re.search(r'\bnumber\s+of\s+tables\b', q_clean):
        return {"type": "TABLE_COUNT"}

    # Rule B: Relationship count queries
    if re.search(r'\bhow\s+many\s+(?:relationships|foreign\s+keys|fk\s+constraints|relations)\b', q_clean) or re.search(r'\bnumber\s+of\s+(?:relationships|foreign\s+keys|relations)\b', q_clean):
        return {"type": "RELATIONSHIP_COUNT"}

    # Rule C: Table list queries (e.g. "what tables are in my database?", "list all tables", "show tables")
    if re.search(r'\b(?:what|which|list|show)\s+(?:all\s+)?tables\b', q_clean) or re.search(r'\btables\s+in\s+(?:the|my|this)\s+database\b', q_clean):
        return {"type": "TABLE_LIST"}

    # Rule D: Column list for a specific table (e.g. "what columns does Orders have?", "columns in Users table")
    col_match = re.search(r'\b(?:what|which|show|list)\s+columns?\s+(?:does|in|of|for|belong\s+to)?\s+([a-zA-Z_][a-zA-Z0-9_]*)\b', q_clean)
    if col_match:
        target_t = col_match.group(1).strip()
        if target_t not in {"have", "exist", "the", "my", "this", "database"}:
            return {"type": "COLUMN_LIST", "target": target_t}

    return None


def classify_intent(query: str) -> str:
    """
    Deterministically classifies a natural language user query into one of:
    - "READ"
    - "CREATE"
    - "UPDATE"
    - "DELETE"
    - "CREATE_TABLE"
    """
    if not query or not query.strip():
        return "READ"

    # Rule 0: Table Creation Intent (highest priority schema mutation)
    if detect_table_creation_intent(query):
        return "CREATE_TABLE"

    # Rule 0.5: Schema / Metadata Query Intent
    if detect_schema_metadata_intent(query):
        return "SCHEMA_METADATA"

    q_clean = query.strip().lower()

    # Rule 1: Questions / Inquiries / Contextual queries -> ALWAYS READ
    inquiry_patterns = [
        r'\bhow\s+(do|can|to|i|should|would|did|does)\b',
        r'\bcan\s+you\b',
        r'\btell\s+me\s+about\b',
        r'\bshow\s+me\s+how\b',
        r'\bwhat\s+(is|are|were|about)\b',
        r'\bwho\s+(deleted|updated|created|added)\b',
        r'\bcustomers\s+who\b',
        r'\borders\s+that\s+were\b',
        r'\bhistory\s+of\b',
        r'\blist\s+of\b',
        r'\binfo\b',
        r'\binformation\b',
        r'\bexplain\b'
    ]
    for pat in inquiry_patterns:
        if re.search(pat, q_clean):
            return "READ"

    # If query ends with '?' and doesn't start with a strong imperative verb -> READ
    if q_clean.endswith("?") and not re.match(r'^\s*(please\s+|kindly\s+)?(add|create|insert|update|change|modify|delete|remove|drop|purge|erase)\b', q_clean):
        return "READ"

    # Rule 2: Strong Direct Imperative Mutation Commands at the beginning of query
    trimmed_cmd = re.sub(r'^\s*(please|kindly)\s+', '', q_clean)

    # Imperative DELETE
    if re.match(r'^\s*(delete|remove|drop|purge|erase)\b', trimmed_cmd):
        return "DELETE"

    # Imperative CREATE
    if re.match(r'^\s*(add|create|insert|new)\b', trimmed_cmd):
        return "CREATE"

    # Imperative UPDATE
    if re.match(r'^\s*(update|change|modify|edit|set)\b', trimmed_cmd):
        return "UPDATE"

    # Rule 3: Explicit Action Intent ("I want to delete order 42", "Please remove customer 10")
    if re.search(r'\b(want|need|wish)\s+to\s+(delete|remove|drop|purge|erase)\b', trimmed_cmd):
        return "DELETE"
    if re.search(r'\b(want|need|wish)\s+to\s+(add|create|insert)\b', trimmed_cmd):
        return "CREATE"
    if re.search(r'\b(want|need|wish)\s+to\s+(update|change|modify|edit)\b', trimmed_cmd):
        return "UPDATE"

    # Rule 4: Conservative Safe Fallback -> READ
    return "READ"


def extract_mutation_details(query: str, operation: str) -> Dict[str, Any]:
    """
    Extracts target table, prefill fields, and where clause details deterministically
    using the active database schema metadata for CRUD form modals.
    Does NOT invoke any LLM API call.
    """
    from database.schema_extractor import get_filtered_tables, get_table_schema
    
    tables = get_filtered_tables()
    q_raw = query.strip()
    q_lower = q_raw.lower()
    
    # 1. Target Table Extraction
    target_table = None
    
    # Check exact case match first
    for t in tables:
        t_singular = t[:-1] if t.endswith('s') or t.endswith('S') else t
        pattern = r'\b' + r'\s*'.join([re.escape(w) for w in re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)', t)]) + r'\b'
        if re.search(r'\b' + re.escape(t) + r'\b', q_raw) or (pattern and re.search(pattern, q_raw, re.IGNORECASE)):
            target_table = t
            break

    if not target_table:
        for t in tables:
            t_lower = t.lower()
            t_singular = t_lower[:-1] if t_lower.endswith('s') else t_lower
            if re.search(r'\b' + re.escape(t_lower) + r'\b', q_lower) or re.search(r'\b' + re.escape(t_singular) + r'\b', q_lower):
                target_table = t
                break

    if not target_table:
        table_aliases = {
            "user": ["users", "customers", "employees", "accounts"],
            "client": ["customers"],
            "buyer": ["customers"],
            "item": ["products", "tracks", "items", "invoice_items"],
            "song": ["tracks"],
            "purchase": ["invoices", "orders"],
            "sale": ["invoices", "orders"]
        }
        for alias, candidates in table_aliases.items():
            if re.search(r'\b' + alias + r'\b', q_lower):
                for candidate in candidates:
                    if any(t.lower() == candidate for t in tables):
                        target_table = next(t for t in tables if t.lower() == candidate)
                        break
                if target_table:
                    break

    if not target_table and tables:
        target_table = tables[0]

    schema_cols = get_table_schema(target_table) if target_table else []
    col_names = [c["name"] for c in schema_cols] if schema_cols else []

    fields = {}
    where_clause = {}

    # 2. Extract ID / Primary Key for Where Clause
    id_match = re.search(r'\b(?:id|order|customer|product|track|album|artist|invoice|user)\s*#?\s*(\d+)\b', q_lower)
    if not id_match:
        id_match = re.search(r'\b(?:where|for|id)\s+(?:id\s+)?=?\s*(\d+)\b', q_lower)
        
    if id_match and target_table:
        val_id = int(id_match.group(1))
        pk_col = "id"
        if schema_cols:
            pk_candidates = [c["name"] for c in schema_cols if c.get("primary_key")]
            if pk_candidates:
                pk_col = pk_candidates[0]
            else:
                for c in col_names:
                    if c.lower() in ("id", f"{target_table.lower()}id", f"{target_table.lower()[:-1]}id"):
                        pk_col = c
                        break
        if operation == "CREATE":
            fields[pk_col] = val_id
        else:
            where_clause[pk_col] = val_id

    # 3. Extract Name / String Values
    name_val = None
    named_match = re.search(r'\bnamed\s+([A-Z][a-zA-Z0-9_-]*|[a-zA-Z0-9_-]+)\b', q_raw, re.IGNORECASE)
    if named_match:
        name_val = named_match.group(1)
    else:
        user_match = re.search(r'\b(?:user|customer|artist|employee|client|person)\s+([A-Z][a-zA-Z0-9_-]*)\b', q_raw)
        if user_match and user_match.group(1).lower() not in ("named", "with", "worth", "for", "from"):
            name_val = user_match.group(1)
        else:
            for_match = re.search(r'\bfor\s+([A-Z][a-zA-Z0-9_-]*)\b', q_raw)
            if for_match and for_match.group(1).lower() not in ("customer", "user", "order", "product", "a", "an", "the"):
                name_val = for_match.group(1)

    if name_val and col_names:
        target_col = None
        priority_names = ["username", "firstname", "first_name", "name", "customername", "title"]
        for p in priority_names:
            for c in col_names:
                if c.lower() == p:
                    target_col = c
                    break
            if target_col:
                break
        if not target_col:
            for c in schema_cols:
                col_type = str(c.get("type", "")).upper()
                if ("VARCHAR" in col_type or "TEXT" in col_type or "STRING" in col_type) and not c.get("primary_key"):
                    target_col = c["name"]
                    break
        if target_col:
            fields[target_col] = name_val

    # 4. Extract Amount / Numeric Values
    amt_val = None
    amt_match = re.search(r'\b(?:worth|amount|price|total|val|cost|sum)(?:\s+to|\s+of|\s+is)?\s+\$?(\d+(?:\.\d+)?)\b', q_lower)
    if amt_match:
        amt_val = float(amt_match.group(1)) if '.' in amt_match.group(1) else int(amt_match.group(1))
    else:
        to_amt_match = re.search(r'\bto\s+\$?(\d+(?:\.\d+)?)\b', q_lower)
        if to_amt_match:
            amt_val = float(to_amt_match.group(1)) if '.' in to_amt_match.group(1) else int(to_amt_match.group(1))

    if amt_val is not None and col_names:
        amt_col = None
        priority_amt_names = ["total", "amount", "price", "unitprice", "unit_price", "val", "cost", "sum"]
        for p in priority_amt_names:
            for c in col_names:
                if c.lower() == p:
                    amt_col = c
                    break
            if amt_col:
                break
        if not amt_col:
            for c in schema_cols:
                col_type = str(c.get("type", "")).upper()
                if ("INT" in col_type or "NUMERIC" in col_type or "DECIMAL" in col_type or "FLOAT" in col_type or "REAL" in col_type) and not c.get("primary_key"):
                    amt_col = c["name"]
                    break
        if amt_col:
            fields[amt_col] = amt_val

    # 5. Extract Email if present
    email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', q_raw)
    if email_match and col_names:
        email_col = next((c for c in col_names if "email" in c.lower()), None)
        if email_col:
            fields[email_col] = email_match.group(1)

    return {
        "operation": operation,
        "table": target_table,
        "fields": fields,
        "where": where_clause
    }
