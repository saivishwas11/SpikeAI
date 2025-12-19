import logging
import asyncio
from typing import Dict, Any, Optional
from agents.analytics_agent import run_analytics_agent
from agents.seo_agent import run_seo_agent, seo_agent # Import the instance directly for fusion
from utils.llm_utils import LLMQueryPlanner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def handle_query(query: str, property_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Tier 3 Orchestrator: Handles intent detection, routing, and data fusion.
    """
    try:
        if not query or not query.strip():
            return {"answer": "Please provide a valid query.", "data": None}
            
        q = query.lower()
        
        # 1. Intent Detection
        is_ga4 = any(term in q for term in ["user", "session", "pageview", "traffic", "ga4", "analytics", "visit", "trend", "top pages"])
        is_seo = any(term in q for term in ["seo", "title", "meta", "description", "index", "https", "status code", "missing", "tag"])

        logger.info(f"Processing: '{query}' | GA4: {is_ga4}, SEO: {is_seo}")

        # ---------------------------------------------------------
        # TIER 3: CROSS-AGENT DATA FUSION
        # ---------------------------------------------------------
        if is_ga4 and is_seo and property_id:
            logger.info("⚡ Executing Multi-Agent Data Fusion ⚡")
            
            # Step A: Get Quantitative Data from GA4 (The "Top Pages")
            # We assume the user wants SEO details for the pages found in analytics
            ga4_result = await run_analytics_agent(query, property_id)
            ga4_data = ga4_result.get("data", [])

            if not ga4_data or not isinstance(ga4_data, list):
                return ga4_result # Return GA4 error or empty result if strictly empty
            
            # Step B: Extract Identifiers (Paths)
            # GA4 returns paths like "/pricing" or "/"
            target_paths = []
            for row in ga4_data:
                # Try common keys for path info
                path = row.get("pagePath") or row.get("pagePathPlusQueryString") or row.get("pageLocation")
                if path:
                    target_paths.append(path)
            
            # Step C: Get Qualitative Data from SEO Agent (The "Titles/Tags")
            # We call the fusion method we just added to seo_agent
            enrichment_map = await seo_agent.batch_lookup_seo_data(target_paths)
            
            # Step D: Fuse Data
            fused_data = []
            for row in ga4_data:
                path = row.get("pagePath") or row.get("pagePathPlusQueryString") or "unknown"
                
                # Get the matching SEO details
                seo_details = enrichment_map.get(path, {})
                
                # Create the unified record
                fused_record = {
                    "page_path": path,
                    "metrics": {k:v for k,v in row.items() if k not in ['pagePath', 'pagePathPlusQueryString']},
                    "seo_details": {
                        "title": seo_details.get("title", "N/A"),
                        "indexability": seo_details.get("indexability", "N/A")
                    }
                }
                fused_data.append(fused_record)
            
            # Step E: Generate Unified Natural Language Response
            summary = LLMQueryPlanner.generate_natural_language_response(
                f"Explain this fused Analytics and SEO data for: {query}", 
                fused_data
            )
            
            return {
                "answer": summary,
                "data": fused_data,
                "meta": {"agent": "Multi-Agent Fusion"}
            }

        # ---------------------------------------------------------
        # Standard Routing
        # ---------------------------------------------------------
        
        # Case B: Explicitly SEO or No Property ID (Fallback to SEO)
        if is_seo or not property_id:
            return await run_seo_agent(query)

        # Case C: Analytics Only
        return await run_analytics_agent(query, property_id)

    except Exception as e:
        logger.error(f"Orchestrator Error: {str(e)}")
        return {
            "answer": f"An error occurred: {str(e)}",
            "data": None
        }