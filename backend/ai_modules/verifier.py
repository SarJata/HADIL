import os
import json
import logging
from dotenv import load_dotenv
from ai_modules.providers import get_llm_provider
from database.schema_extractor import get_filtered_schema

load_dotenv(override=True)

logger = logging.getLogger(__name__)

def verify_sql_intent(user_query: str, generated_sql: str, policy_context: str = ""):
    """
    Verifier Module with dynamic schema awareness supporting multiple LLM providers.
    Verifies that the executable SQL statement is well-formed, targets existing schema tables/columns,
    aligns with the request context, and respects active policy constraints.
    """
    logger.info(f"Verifying SQL intent for: {user_query}")
    
    schema_context = get_filtered_schema()
    
    policy_prompt_block = ""
    if policy_context and policy_context.strip():
        policy_prompt_block = f"""\n{policy_context.strip()}\n\nNote on Policy Context:
Evaluate if the executable SQL violates any explicit organizational policy rules contained above (e.g. attempting to delete protected data or bypassing retention rules). If a policy violation exists, set "is_valid": false and detail the policy conflict in "errors".\n"""

    system_prompt = "SQL security auditor, schema verifier, and policy compliance evaluator."
    user_prompt = f"""Verify executable SQL against database schema, request context, and organizational policy rules.

{schema_context}
{policy_prompt_block}
User Query / Request: "{user_query}"
Executable SQL: "{generated_sql}"

Rules:
- Mark is_valid: false if query targets non-existent tables or columns, or is structurally malformed.
- Mark is_valid: false if query omits critical WHERE clauses or conditions required by the request or active policy rules.
- Mark is_valid: false if executable SQL directly violates an active policy rule specified in [POLICY CONTEXT].
- Safety LIMIT on raw row retrieval queries is VALID. Final outer LIMIT on top-N aggregate/GROUP BY queries (e.g. GROUP BY ... ORDER BY ... LIMIT N) is VALID and normal. Unsafe intermediate LIMIT inside subqueries or derived tables prior to outer aggregation is INVALID (mark is_valid: false).

- Return JSON:
{{
    "is_valid": true,
    "missing_conditions": [],
    "errors": [],
    "explanation": "concise explanation"
}}
"""


    try:
        provider = get_llm_provider("verifier")
        result = provider.generate_json(system_prompt, user_prompt)
        
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
