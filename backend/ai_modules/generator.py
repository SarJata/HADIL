import os
import logging
import re
import json
from openai import OpenAI
from dotenv import load_dotenv
from database.schema_extractor import get_filtered_schema

load_dotenv(override=True)

logger = logging.getLogger(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def should_apply_limit(sql: str) -> bool:
    """
    Detection logic to determine if a LIMIT clause should be applied.
    Returns True for raw row retrieval, False for aggregates, GROUP BY, or EXISTS.
    """
    sql_lower = sql.lower()
    bypass_limit_patterns = [r"count\s*\(", r"sum\s*\(", r"avg\s*\(", r"min\s*\(", r"max\s*\(", r"group\s+by", r"\bexists\b"]
    for pattern in bypass_limit_patterns:
        if re.search(pattern, sql_lower):
            return False
    return True

def generate_sql_from_text(query: str, dialect: str = "sqlite"):
    """
    OpenAI-powered SQL Generator with dynamic schema awareness and dialect sensitivity.
    Input: user query, database dialect
    Output: SQL query, intent, ambiguity status, options
    """
    logger.info(f"Generating SQL for query: {query} (Dialect: {dialect})")
    
    schema_context = get_filtered_schema()
    
    prompt = f"""
You are an expert SQL generator for a secure database layer (HADIL). 
Convert the following natural language query into a valid SQL SELECT query using the provided schema.

Target Database Dialect: {dialect}

{schema_context}

Constraints & Rules:
1. ONLY generate SELECT queries compatible with the {dialect} dialect.
2. DO NOT generate destructive operations (DELETE, UPDATE, DROP, etc.).
3. Apply LIMIT 100 ONLY for raw row retrieval queries.
4. Do NOT apply LIMIT for aggregates, GROUP BY, or EXISTS queries.
5. **Dialect Specifics**:
   - If dialect is 'sqlite': Use strftime('%Y', column) for years, strftime('%m', column) for months. SQLite DOES NOT support YEAR() or MONTH().
   - If dialect is 'postgresql': Use EXTRACT(YEAR FROM column) or TO_CHAR(column, 'YYYY').
   - If dialect is 'mysql': Use YEAR(column) or DATE_FORMAT(column, '%Y').
6. For analytical queries like "latest year", use appropriate aggregates (e.g., MAX(year_column)).
7. **Confidence-Based Resolution**:
   - If there is ONLY one strong candidate table/column, proceed.
   - If MULTIPLE plausible candidates exist, set "is_ambiguous" to true.
8. Return your response as a valid JSON object.

JSON Structure:
{{
    "sql": "SELECT ...",
    "intent": "Brief description of intent",
    "is_ambiguous": false,
    "options": []
}}

User Query: {query}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a secure SQL generator that handles both direct and analytical queries with ambiguity detection."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )
        
        result_json = json.loads(response.choices[0].message.content.strip())
        sql = result_json.get("sql", "").strip()
        intent = result_json.get("intent", "Generated SQL")
        is_ambiguous = result_json.get("is_ambiguous", False)
        options = result_json.get("options", [])

        if is_ambiguous:
            return None, intent, True, options
        
        # Basic cleanup
        sql = sql.replace("```sql", "").replace("```", "").strip()
        
        # Enforce conditional LIMIT logic
        if should_apply_limit(sql):
            if "limit" not in sql.lower():
                # Append LIMIT if it's a raw query and AI forgot it
                sql = f"{sql.rstrip(';')} LIMIT 100"
        else:
            # Remove LIMIT if AI incorrectly added it to an aggregate query
            if "limit" in sql.lower():
                # Basic removal: find the last occurrence of LIMIT and remove it
                sql = re.sub(r"\s+LIMIT\s+\d+\s*$", "", sql, flags=re.IGNORECASE).strip()
        
        logger.info(f"Final SQL (after conditional LIMIT): {sql}")
        return sql, intent, False, [] 
    except Exception as e:
        logger.error(f"Error generating SQL: {e}")
        raise Exception(f"AI Generation Error: {e}")
