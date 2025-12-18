import os
import re
import json
from typing import Dict, Any
import litellm
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure LiteLLM
litellm.api_key = os.getenv("LITELLM_API_KEY")
litellm.api_base = "http://3.110.18.218"

class LLMQueryPlanner:
    
    @staticmethod
    def _clean_json_response(response_text: str) -> str:
        """Removes Markdown formatting (```json ... ```) from LLM response."""
        cleaned = re.sub(r'```json\s*', '', response_text)
        cleaned = re.sub(r'```\s*', '', cleaned)
        return cleaned.strip()

    @staticmethod
    def plan_ga4_query(natural_language_query: str) -> Dict[str, Any]:
        """Convert natural language query to GA4 query parameters."""
        system_prompt = """You are a Google Analytics 4 expert. Convert the question into a valid API query JSON.
        Required JSON Structure:
        {
            "metrics": ["activeUsers", "sessions"], 
            "dimensions": ["date"], 
            "start_date": "YYYY-MM-DD",
            "end_date": "YYYY-MM-DD",
            "filters": {},
            "limit": 1000
        }
        Use 'activeUsers' instead of 'users'. Use 'screenPageViews' for page views.
        Default to last 28 days if no date specified.
        """
        
        try:
            # FIX: Changed model to 'gemini-2.5-flash' as per Hackathon PDF requirements
            response = litellm.completion(
                model="openai/gemini-2.5-flash",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": natural_language_query}
                ],
                temperature=0.0
            )
            
            content = response.choices[0].message.content
            cleaned_json = LLMQueryPlanner._clean_json_response(content)
            query_plan = json.loads(cleaned_json)
            
            # Basic Defaults
            if "metrics" not in query_plan: query_plan["metrics"] = ["activeUsers"]
            if "dimensions" not in query_plan: query_plan["dimensions"] = ["date"]
            
            return query_plan
            
        except Exception as e:
            print(f"LLM Planning Error: {e}")
            # Fallback
            return {
                "metrics": ["activeUsers"],
                "dimensions": ["date"],
                "start_date": "30daysAgo",
                "end_date": "today"
            }

    @staticmethod
    def generate_natural_language_response(query: str, data: Any) -> str:
        """Summarize data."""
        system_prompt = "Summarize this analytics/SEO data in 2-3 concise sentences. If data is empty, politely say no data was found."
        try:
            # FIX: Changed model to 'gemini-2.5-flash'
            response = litellm.completion(
                model="openai/gemini-2.5-flash",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Query: {query}\nData: {str(data)[:2000]}"}
                ],
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception:
            return "Here is the data requested."