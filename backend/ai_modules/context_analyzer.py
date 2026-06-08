import os
import json
import logging
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)

logger = logging.getLogger(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_query_context(query: str, sql: str):
    """
    Uses AI to extract the semantic context of a database query.
    Returns structured info about metrics, entities, and dimensions.
    """
    if not query or not sql:
        return None

    prompt = f"""
Analyze the following natural language query and its corresponding SQL to extract business context for machine learning forecasting.

User Query: "{query}"
SQL: "{sql}"

Extract:
1. target_metric: What is being measured? (e.g., sales, quantity, price, count)
2. entity_type: What is the primary subject? (e.g., genre, user, product, country)
3. filters: Any specific conditions? (e.g., "Rock music", "USA")
4. time_dimension: Is there a time aspect? (e.g., yearly, monthly, daily, or null)
5. aggregation: How is the data summarized? (e.g., SUM, AVG, COUNT, or raw)

Return ONLY a JSON object.

Example:
{{
  "target_metric": "sales",
  "entity_type": "genre",
  "filters": "Rock music in USA",
  "time_dimension": "yearly",
  "aggregation": "SUM"
}}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a specialized business context analyzer for data science."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )
        
        context = json.loads(response.choices[0].message.content.strip())
        logger.info(f"Extracted Context: {context}")
        return context
    except Exception as e:
        logger.error(f"Error extracting context: {e}")
        return None
