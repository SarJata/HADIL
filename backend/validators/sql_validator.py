import re
import logging

logger = logging.getLogger(__name__)

def check_unsafe_subquery_limit(sql: str) -> tuple[bool, str]:
    """
    Analyzes SQL to distinguish between:
    - Final outer LIMIT (valid on top-N grouped/aggregated results)
    - Unsafe intermediate LIMIT inside subqueries or derived tables prior to aggregation (invalid/unsafe)
    
    Returns (is_unsafe, reason).
    """
    sql_clean = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    sql_clean = re.sub(r"--.*$", "", sql_clean, flags=re.MULTILINE)
    
    # Match subqueries containing LIMIT inside parentheses e.g. (SELECT ... LIMIT ...)
    subquery_limit_pattern = r"\(\s*select\b.*?\blimit\s+\d+.*?\)"
    if re.search(subquery_limit_pattern, sql_clean, re.IGNORECASE | re.DOTALL):
        if re.search(r"\bgroup\s+by\b|\bcount\s*\(|\bsum\s*\(|\bavg\s*\(|\bmin\s*\(|\bmax\s*\(", sql_clean, re.IGNORECASE):
            return True, "Subquery contains a LIMIT clause prior to outer aggregation/GROUP BY, which unsafely truncates data before grouping."
            
    return False, ""

def validate_sql(sql: str, is_direct_sql: bool = False):
    """
    Rule-Based SQL Validator.
    Enforces safety rules before execution.
    """
    sql_lower = sql.lower().strip()
    
    is_safe = True
    warnings = []
    errors = []

    # 0. Basic Sanity Checks
    # Prevent multiple statements (SQL injection attempt or just unsafe)
    if sql_lower.count(";") > 1 or (sql_lower.count(";") == 1 and not sql_lower.endswith(";")):
        is_safe = False
        errors.append("Multiple SQL statements are not permitted.")

    # Prevent comment-based injection
    if "--" in sql_lower or "/*" in sql_lower:
        is_safe = False
        errors.append("SQL comments are not allowed in queries for safety reasons.")
    
    # Prevent unsafe intermediate subquery LIMIT
    is_unsafe_subquery, subquery_reason = check_unsafe_subquery_limit(sql)
    if is_unsafe_subquery:
        is_safe = False
        errors.append(subquery_reason)
    
    # 1. Block CRITICAL Dangerous Keywords
    critical_blocked = ["drop", "alter", "truncate", "exec", "grant", "revoke", "vacuum"]
    for kw in critical_blocked:
        if re.search(rf"\b{kw}\b", sql_lower):
            is_safe = False
            errors.append(f"Command '{kw.upper()}' is strictly blocked for security.")

    # 2. Handle Operation Types
    if sql_lower.startswith("select") or sql_lower.startswith("with"):
        # SELECT/CTE Rules
        # Enforce LIMIT conditionally for raw row retrieval
        bypass_limit_patterns = [r"count\s*\(", r"sum\s*\(", r"avg\s*\(", r"min\s*\(", r"max\s*\(", r"group\s+by", r"\bexists\b"]
        needs_limit = True
        for pattern in bypass_limit_patterns:
            if re.search(pattern, sql_lower):
                needs_limit = False
                break
                
        if needs_limit and "limit" not in sql_lower:
            # We enforce LIMIT even for direct SQL if it's a raw SELECT
            is_safe = False
            errors.append("Raw row retrieval queries must include a LIMIT clause for safety.")

    elif sql_lower.startswith("update"):
        if not is_direct_sql:
            is_safe = False
            errors.append("AI-generated UPDATE queries are not allowed. Please use standard CRUD forms.")
        elif "where" not in sql_lower:
            is_safe = False
            errors.append("UPDATE without a WHERE clause is blocked to prevent massive data loss.")

    elif sql_lower.startswith("delete"):
        if not is_direct_sql:
            is_safe = False
            errors.append("AI-generated DELETE queries are not allowed. Please use standard CRUD forms.")
        elif "where" not in sql_lower:
            is_safe = False
            errors.append("DELETE without a WHERE clause is blocked to prevent massive data loss.")

    elif sql_lower.startswith("insert"):
        if not is_direct_sql:
            is_safe = False
            errors.append("AI-generated INSERT queries are not allowed. Please use standard CRUD forms.")
        # INSERT is allowed if direct, but we rely on parameterized execution in the engine
        pass

    elif not is_direct_sql:
        # For AI-generated, we only allow SELECT/WITH
        is_safe = False
        errors.append("Only SELECT queries are allowed for AI-generated SQL.")
    
    # 3. Risky Tables Check
    risky_tables = ["users", "orders", "products"]
    has_where = "where" in sql_lower
    for table in risky_tables:
        if re.search(rf"\b{table}\b", sql_lower) and not has_where:
            if sql_lower.startswith("select"):
                warnings.append(f"Query on '{table}' table without WHERE clause. Ensure this is intentional.")
            else:
                # For non-SELECT, we already enforced WHERE above, but being double safe
                is_safe = False
                errors.append(f"Mutations on '{table}' table MUST include a WHERE clause.")
                break
            
    # 4. Join Complexity
    join_count = sql_lower.count("join")
    if join_count > 3:
        warnings.append(f"High JOIN complexity ({join_count}). This might impact performance.")
        
    logger.info(f"Validation result for SQL (Direct: {is_direct_sql}): {sql} -> Safe: {is_safe}, Errors: {errors}")
    
    return is_safe, warnings, errors

