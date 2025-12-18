from typing import Dict, Any
from .llm_utils import LLMQueryPlanner

# Simple wrapper to maintain your existing import structure
def plan_ga4_query(query: str) -> Dict[str, Any]:
    return LLMQueryPlanner.plan_ga4_query(query)