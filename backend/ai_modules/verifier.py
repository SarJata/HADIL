import os
import json
import logging
from openai import OpenAI
from dotenv import load_dotenv
from database.schema_extractor import get_filtered_schema

load_dotenv(override=True)

logger = logging.getLogger(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def verify_sql_intent(user_query: str, generated_sql: str):
    """
    OpenAI-powered Verifier Module with dynamic schema awareness.
    Completely separate call from the generator.
    """
    logger.info(f"Verifying SQL intent for: {user_query}")
    
    schema_context = get_filtered_schema()
    
    prompt = f"""
You are a security auditor for a database query layer. Your task is to verify if the generated SQL matches the user's natural language intent, using the provided database schema for context.

{schema_context}

User Query: "{user_query}"
Generated SQL: "{generated_sql}"

Tasks:
1. Extract the core intent from the user query.
2. Extract the intent implemented by the SQL.
3. Check if the SQL uses correct tables and columns as defined in the schema.
4. Compare the intents for any discrepancies (missing conditions, wrong filters, unintended data modification).

Return your response as a valid JSON object with the following structure:
{{
    "is_valid": true/false,
    "missing_conditions": ["list of strings or empty"],
    "errors": ["list of strings or empty"],
    "explanation": "concise explanation of why it is valid or not"
}}

Rules:
- If the SQL is missing a WHERE condition mentioned in the query, mark as invalid.
- If the SQL targets the wrong table or uses non-existent columns, mark as invalid.
- If the SQL tries to do something other than SELECT (e.g. DELETE), mark as invalid.
- Infer meaning from column names when comparing intent (e.g., a query for "revenue" might correctly use a column named "price" or "amount").
- **LIMIT Clause Rules**: 
    - A `LIMIT 100` clause is automatically added for raw row retrieval queries for safety; do NOT mark it as a discrepancy unless the user requested a specific different limit.
    - Aggregate queries (COUNT, SUM, AVG, MIN, MAX), GROUP BY queries, and EXISTS queries should NOT have a LIMIT clause.
- Do NOT reject valid queries if they correctly implement the user's intent using the available schema.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a specialized SQL auditor focused on intent verification."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )
        
        result_content = response.choices[0].message.content
        result = json.loads(result_content)
        
        logger.info(f"Verification result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in AI verification: {e}")
        return {
            "is_valid": False,
            "missing_conditions": [],
            "errors": [str(e)],
            "explanation": "An error occurred during AI verification."
        }
