import os
import json
import logging
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)

logger = logging.getLogger(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def interpret_query_result(query: str, data: list):
    """
    Converts raw query results into a human-readable sentence based on the original intent.
    """
    if not data:
        return "No data found for your request."
    
    # Heuristic: only interpret if data is small (like a single value or few values)
    # or if the query looks like a specific question.
    if len(data) > 5:
        return None # Too much data, let the UI handle it as a table/chart
    
    prompt = f"""
You are a helpful data assistant. Convert the following database query result into a concise, natural language sentence that answers the user's question.

User Question: "{query}"
Raw Data: {json.dumps(data)}

Rules:
1. Be direct and concise.
2. Maintain accuracy based on the data.
3. If the data is a single number or date, make it the focus of the sentence.
4. If there are multiple values, list them clearly.

Example:
Question: "What is the latest year of sales data available?"
Data: [{{"latest_year": 2018}}]
Output: "The latest year of sales data available is 2018."

Output:
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a specialized interpreter that converts data results into human-friendly answers."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        
        interpretation = response.choices[0].message.content.strip()
        logger.info(f"Result Interpretation: {interpretation}")
        return interpretation
    except Exception as e:
        logger.error(f"Error in result interpretation: {e}")
        return None
