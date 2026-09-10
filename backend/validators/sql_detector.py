import re

def is_sql_query(text: str) -> bool:
    """
    Detects if the input string is likely a raw SQL query.
    Strictly matches valid raw SQL statements, not natural language sentences starting with imperative words.
    """
    if not text or not text.strip():
        return False

    text_clean = text.strip().lower()
    
    # Precise raw SQL syntax patterns
    sql_start_keywords = [
        r"^select\b",
        r"^with\b",
        r"^insert\s+into\b",
        r"^update\s+[a-zA-Z0-9_`\"\.]+\s+set\b",
        r"^delete\s+from\b",
        r"^create\s+(table|view|index|database|schema|trigger|procedure|function|user|role)\b",
        r"^drop\s+(table|view|index|database|schema|trigger|procedure|function|user|role)\b",
        r"^alter\s+(table|view|index|database|schema|trigger|procedure|function|user|role)\b",
        r"^truncate\s+(table\s+)?[a-zA-Z0-9_`\"\.]+\b"
    ]
    
    for pattern in sql_start_keywords:
        if re.match(pattern, text_clean):
            return True
            
    # Check for SQL comments preceding SELECT ... FROM ...
    if "select" in text_clean and "from" in text_clean:
        return True
        
    return False
