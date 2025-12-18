import logging
import asyncio
from typing import Dict, Any, Optional
from agents.analytics_agent import run_analytics_agent
from agents.seo_agent import run_seo_agent

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def handle_query(query: str, property_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Route the query to the appropriate agent based on its content and context.
    """
    try:
        if not query or not query.strip():
            return {"answer": "Please provide a valid query.", "data": None}
            
        q = query.lower()
        
        # 1. Keyword Detection
        is_ga4 = any(term in q for term in ["user", "session", "pageview", "traffic", "ga4", "analytics", "visit", "trend"])
        is_seo = any(term in q for term in ["seo", "title", "meta", "description", "index", "https", "status code", "h1", "missing", "url"])

        logger.info(f"Processing: '{query}' | GA4: {is_ga4}, SEO: {is_seo}, PropertyID: {property_id}")

        # 2. Routing Logic
        
        # Case A: Combined or Ambiguous but Property ID is present
        if (is_ga4 and is_seo) or (is_ga4 and property_id):
            if not property_id:
                return {"answer": "A Google Analytics 4 property ID is required for analytics queries.", "data": None}
            
            # If strictly both, we could run parallel (Tier 3), but here we prioritize GA4 for safety
            # unless it's explicitly an SEO specific question asking about titles/meta.
            if is_seo:
                # Run both tasks in parallel
                ga4_task = asyncio.create_task(run_analytics_agent(query, property_id))
                seo_task = asyncio.create_task(run_seo_agent(query))
                
                ga4_res, seo_res = await asyncio.gather(ga4_task, seo_task)
                
                return {
                    "answer": f"**Analytics:** {ga4_res.get('answer')}\n\n**SEO:** {seo_res.get('answer')}",
                    "data": {"analytics": ga4_res.get("data"), "seo": seo_res.get("data")}
                }
            
            return await run_analytics_agent(query, property_id)

        # Case B: Explicitly SEO or No Property ID (Fallback to SEO)
        if is_seo or not property_id:
            return await run_seo_agent(query)

        return {"answer": "I couldn't determine the intent. Please provide a Property ID for analytics or ask about SEO.", "data": None}

    except Exception as e:
        logger.error(f"Orchestrator Error: {str(e)}")
        return {
            "answer": f"An error occurred while processing your request: {str(e)}",
            "data": None
        }