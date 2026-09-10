import os
import json
import logging
from dotenv import load_dotenv
from database.schema_extractor import get_filtered_schema
from ai_modules.providers import get_llm_provider

load_dotenv(override=True)

logger = logging.getLogger(__name__)

def generate_followup_questions(user_query: str, sql: str, context: dict, columns: list):
    """
    Generates 3-5 intelligent follow-up questions based on the current query context,
    the schema, and the results (columns).
    """
    logger.info(f"Generating follow-up questions for: {user_query}")
    
    schema_context = get_filtered_schema()
    
    system_prompt = "You are a specialized analytical assistant that suggests context-aware follow-up questions."
    user_prompt = f"""
Based on the user's last query and the current database schema, suggest 3-5 intelligent, analytical follow-up questions that help the user explore the data further.

Database Schema (Filtered):
{schema_context}

Last User Query: "{user_query}"
SQL Executed: "{sql}"
Extracted Context: {json.dumps(context)}
Result Columns: {", ".join(columns)}

Follow-up Types to consider:
1. Trend analysis (if time columns exist)
2. Comparative analysis (comparing across regions, categories, or groups)
3. Drill-down analysis (looking at contributors like customers or products)
4. Ranking expansion (showing more results)
5. Correlation/Relationship exploration (e.g., "Which factors correlate with higher sales?")

Rules:
- Questions must be grounded in the PROVIDED SCHEMA. Do NOT suggest questions about tables or columns that don't exist.
- Suggestions should feel like a natural continuation of the user's analytical journey.
- Be concise and business-aware.
- Return the response as a JSON object with a "suggestions" key containing a list of strings.

Example Output:
{{
    "suggestions": [
        "How has this metric changed over the last 6 months?",
        "Which product categories contribute most to this total?",
        "Compare this result across different regions."
    ]
}}
"""

    try:
        provider = get_llm_provider("generator")
        result = provider.generate_json(system_prompt, user_prompt)
        suggestions = result.get("suggestions", [])
        
        # Limit to 5 suggestions
        suggestions = suggestions[:5]
        
        logger.info(f"Generated Suggestions: {suggestions}")
        return suggestions
    except Exception as e:
        logger.error(f"Error generating follow-up questions: {e}")
        return []

