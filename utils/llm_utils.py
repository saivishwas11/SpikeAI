import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import litellm
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure LiteLLM
litellm.api_key = os.getenv("LITELLM_API_KEY")
litellm.api_base = "http://3.110.18.218"

class LLMQueryPlanner:
    """Class to handle natural language to GA4 query conversion using LiteLLM."""
    
    @staticmethod
    def plan_ga4_query(natural_language_query: str) -> Dict[str, Any]:
        """Convert natural language query to GA4 query parameters."""
        system_prompt = """You are an expert at converting natural language questions into Google Analytics 4 (GA4) API queries. 
        Your task is to analyze the user's question and extract the following information:
        - Metrics: The quantitative measurements (e.g., users, sessions, pageViews)
        - Dimensions: The categories for analysis (e.g., date, pagePath, country)
        - Date range: The time period for the data
        - Filters: Any specific conditions to filter the data
        - Sort order: How to sort the results
        
        Return the response as a JSON object with the following structure:
        {
            "metrics": ["metric1", "metric2", ...],
            "dimensions": ["dimension1", "dimension2", ...],
            "start_date": "YYYY-MM-DD",
            "end_date": "YYYY-MM-DD",
            "filters": {
                "dimension_name": {
                    "value": "value_to_match",
                    "match_type": "EXACT" | "BEGINS_WITH" | "ENDS_WITH" | "CONTAINS" | "FULL_REGEXP"
                }
            },
            "order_by": [
                {
                    "field_name": "metric_or_dimension_name",
                    "sort_order": "ASCENDING" | "DESCENDING"
                }
            ],
            "limit": 1000
        }
        """
        
        try:
            response = litellm.completion(
                model="gemini-1.5-pro",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": natural_language_query}
                ],
                temperature=0.2,
                max_tokens=1000
            )
            
            # Parse the response
            import json
            query_plan = json.loads(response.choices[0].message.content)
            
            # Set default date range if not provided (last 30 days)
            if not query_plan.get("start_date") or not query_plan.get("end_date"):
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=30)
                query_plan["start_date"] = start_date.isoformat()
                query_plan["end_date"] = end_date.isoformat()
            
            # Ensure required fields exist
            query_plan.setdefault("metrics", ["screenPageViews", "users", "sessions"])
            query_plan.setdefault("dimensions", ["date"])
            query_plan.setdefault("filters", {})
            query_plan.setdefault("order_by", [{"field_name": "date", "sort_order": "DESCENDING"}])
            query_plan.setdefault("limit", 1000)
            
            return query_plan
            
        except Exception as e:
            # Fallback to a simple query plan if LLM fails
            return {
                "metrics": ["screenPageViews", "users", "sessions"],
                "dimensions": ["date"],
                "start_date": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
                "end_date": datetime.now().strftime("%Y-%m-%d"),
                "filters": {},
                "order_by": [{"field_name": "date", "sort_order": "DESCENDING"}],
                "limit": 1000
            }

    @staticmethod
    def generate_natural_language_response(query: str, data: Dict[str, Any]) -> str:
        """Generate a natural language response based on the query and data."""
        system_prompt = """You are an analytics assistant that helps users understand their GA4 data. 
        You will be given a user's question and the corresponding data from GA4. 
        Your task is to provide a clear, concise, and insightful response that answers the user's question.
        
        Guidelines:
        1. Start with a direct answer to the question
        2. Provide key insights from the data
        3. Highlight any interesting patterns or anomalies
        4. Keep it concise but informative
        5. Use bullet points for key metrics
        6. If the data is empty or not available, explain why that might be the case
        """
        
        try:
            response = litellm.completion(
                model="gemini-1.5-pro",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Question: {query}\n\nData: {str(data)[:3000]}"}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            # Fallback response if LLM fails
            return f"Here's the data for your query:\n{str(data)[:1000]}..."


# Example usage
if __name__ == "__main__":
    planner = LLMQueryPlanner()
    
    # Test query planning
    query = "Show me the top 10 pages by page views in the last 7 days"
    plan = planner.plan_ga4_query(query)
    print("Query Plan:", plan)
    
    # Test response generation
    data = {
        "rows": [
            {"pagePath": "/home", "screenPageViews": 1500},
            {"pagePath": "/pricing", "screenPageViews": 1200},
            {"pagePath": "/contact", "screenPageViews": 800}
        ]
    }
    response = planner.generate_natural_language_response(query, data)
    print("\nResponse:", response)
