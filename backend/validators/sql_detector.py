import re

def is_sql_query(text: str) -> bool:
    """
    Detects if the input string is likely a raw SQL query.
    """
    text_clean = text.strip().lower()
    
    # Common SQL keywords that usually start a query
    sql_start_keywords = [
        r"^select\b",
        r"^with\b",
        r"^insert\s+into\b",
        r"^update\b",
        r"^delete\s+from\b",
        r"^create\b",
        r"^drop\b",
        r"^alter\b",
        r"^truncate\b"
    ]
    
    for pattern in sql_start_keywords:
        if re.match(pattern, text_clean):
            return True
            
    # Check for other SQL patterns if it doesn't start with a keyword (less common but possible)
    # e.g. "/* comment */ SELECT ..."
    if "select" in text_clean and "from" in text_clean:
        return True
        
    return False
