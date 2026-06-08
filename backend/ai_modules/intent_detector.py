import os
import json
import logging
from openai import OpenAI
from dotenv import load_dotenv
from database.schema_extractor import get_schema_context

load_dotenv(override=True)

logger = logging.getLogger(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def detect_intent_and_extract_fields(query: str):
    """
    Detects if the query is a READ or MUTATION (CREATE, UPDATE, DELETE).
    If mutation, extracts table and fields.
    """
    logger.info(f"Detecting intent for: {query}")
    
    schema_context = get_schema_context()
    
    prompt = f"""
You are an intent detection and field extraction engine for a database system.
Analyze the user query and the database schema provided below.

{schema_context}

Tasks:
1. Classify the operation: READ, CREATE, UPDATE, or DELETE.
2. Identify the target table name.
3. Extract field-value pairs for the operation.

Rules:
- For READ: Identify if it is a standard row retrieval or an analytical query (latest, average, total, count, etc.). Return operation: READ.
- For CREATE: Identify table and values to insert.
- For UPDATE: Identify table, values to update, and WHERE criteria.
- For DELETE: Identify table and WHERE criteria.
- Use only tables and columns from the schema.
- If the intent is a READ operation but the table is implicit (e.g., "latest sales year"), return operation: READ and try to identify the most likely table based on context.
- If the intent is unclear or not a database operation, return error.

Return your response as a valid JSON object with the following structure:
{{
    "operation": "READ | CREATE | UPDATE | DELETE",
    "table": "table_name or null for READ if ambiguous",
    "fields": {{ "column_name": "value", ... }},
    "where": {{ "column_name": "value", ... }},  # For UPDATE/DELETE
    "is_analytical": true/false, # New field for READ queries
    "error": "Error message if any"
}}

Example for "Add a new order for user 1 with amount 500":
{{
    "operation": "CREATE",
    "table": "orders",
    "fields": {{ "user_id": 1, "amount": 500 }},
    "where": {{}},
    "error": null
}}

User Query: "{query}"
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a specialized intent detector for database CRUD operations."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )
        
        result_content = response.choices[0].message.content
        result = json.loads(result_content)
        
        logger.info(f"Intent Detection Result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in intent detection: {e}")
        return {
            "operation": "READ",
            "error": str(e)
        }
