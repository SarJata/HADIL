import re
import logging

logger = logging.getLogger(__name__)

# Mapping of dialects to unsupported functions and their regex patterns
DIALECT_RESTRICTIONS = {
    "sqlite": {
        "unsupported_patterns": [
            (r"\byear\s*\(", "YEAR() is not supported in SQLite. Use strftime('%Y', ...) instead."),
            (r"\bmonth\s*\(", "MONTH() is not supported in SQLite. Use strftime('%m', ...) instead."),
            (r"\bday\s*\(", "DAY() is not supported in SQLite. Use strftime('%d', ...) instead."),
            (r"\bextract\s*\(", "EXTRACT() is not supported in SQLite. Use strftime() instead."),
            (r"\bconcat\s*\(", "CONCAT() is not supported in SQLite. Use the || operator instead.")
        ]
    },
    "postgresql": {
        "unsupported_patterns": [
            (r"\bstrftime\s*\(", "strftime() is not supported in PostgreSQL. Use TO_CHAR() or EXTRACT() instead."),
            (r"\byear\s*\(", "YEAR() is not supported in PostgreSQL. Use EXTRACT(YEAR FROM ...) instead.")
        ]
    },
    "mysql": {
        "unsupported_patterns": [
            (r"\bstrftime\s*\(", "strftime() is not supported in MySQL. Use DATE_FORMAT() instead."),
            (r"\bextract\s*\(\s*year\s+from", "EXTRACT(YEAR FROM ...) syntax is supported but YEAR() is preferred in MySQL.")
        ]
    }
}

def validate_dialect_compatibility(sql: str, dialect: str):
    """
    Checks if the SQL query uses functions or syntax unsupported by the target dialect.
    """
    sql_lower = sql.lower()
    dialect = dialect.lower()
    
    errors = []
    
    if dialect not in DIALECT_RESTRICTIONS:
        logger.warning(f"No specific restrictions defined for dialect: {dialect}. Skipping check.")
        return True, []
        
    restrictions = DIALECT_RESTRICTIONS[dialect]
    
    for pattern, message in restrictions["unsupported_patterns"]:
        if re.search(pattern, sql_lower):
            errors.append(message)
            
    is_compatible = len(errors) == 0
    
    if not is_compatible:
        logger.warning(f"Dialect compatibility check failed for {dialect}: {errors}")
        
    return is_compatible, errors
