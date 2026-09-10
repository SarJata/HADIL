import os
import json
import logging
from dotenv import load_dotenv
from ai_modules.providers import get_llm_provider
from database.schema_extractor import get_schema_context

load_dotenv(override=True)

logger = logging.getLogger(__name__)

def detect_intent_and_extract_fields(query: str):
    """
    Detects if the query is a READ or MUTATION (CREATE, UPDATE, DELETE).
    If mutation, extracts table and fields. Supports OpenAI or local Qwen provider.
    """
    logger.info(f"Detecting intent for: {query}")
    
    schema_context = get_schema_context()
    
    system_prompt = "Database intent detector."
    user_prompt = f"""Classify query operation and extract table/fields.

{schema_context}

Rules:
- Operations: READ, CREATE, UPDATE, DELETE.
- For READ: Identify table. Set is_analytical: true for count/sum/avg/max/latest.
- For CREATE/UPDATE/DELETE: Extract target table, fields, where conditions.
- If table/field is unknown, set error message.
- Return JSON:
{{
    "operation": "READ|CREATE|UPDATE|DELETE",
    "table": "table_name",
    "fields": {{}},
    "where": {{}},
    "is_analytical": false,
    "error": null
}}

User Query: "{query}"
"""

    try:
        provider = get_llm_provider("generator")
        result = provider.generate_json(system_prompt, user_prompt)
        
        logger.info(f"Intent Detection Result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in intent detection: {e}")
        return {
            "operation": "READ",
            "error": str(e)
        }
