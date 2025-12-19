import logging
import re
import json
import pandas as pd
from urllib.parse import urlparse
import litellm 
from typing import Dict, Any, List
from utils.sheets import load_seo_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SEOAgent:
    def __init__(self, df: pd.DataFrame = None):
        """Initialize SEOAgent with optional DataFrame.
        
        Args:
            df: Optional DataFrame containing SEO data. If not provided,
                it will be loaded on demand in batch_lookup_seo_data.
        """
        self.df = df

    async def batch_lookup_seo_data(self, paths: List[str]) -> Dict[str, Any]:
        """Fusion Lookup."""
        # Use stored DataFrame if available, otherwise load fresh
        if self.df is None:
            df, error = load_seo_data()
            if error or df.empty:
                logger.error(f"Failed to load SEO data: {error}")
                return {}
        else:
            df = self.df
            
        if df.empty: 
            return {}

        lookup_map = {}
        
        # Determine URL column (Address or URL)
        url_col = next((c for c in df.columns if c.lower() in ['address', 'url']), None)
        if not url_col: 
            return {}

        # Pre-compute paths for matching
        # Use a copy to avoid SettingWithCopy warnings on cached DF
        match_df = df[[url_col]].copy()
        match_df['path'] = match_df[url_col].astype(str).apply(lambda x: urlparse(x).path.rstrip('/'))
        
        # Create dictionary for O(1) lookup
        # Map path -> index in original DF
        path_to_idx = dict(zip(match_df['path'], match_df.index))

        for path in paths:
            clean_path = path.strip().rstrip('/')
            if not clean_path: clean_path = "/"
            
            if clean_path in path_to_idx:
                row = df.iloc[path_to_idx[clean_path]].to_dict()
                lookup_map[path] = {
                    "title": row.get("Title 1", "N/A"),
                    "status": row.get("Status Code", "Unknown"),
                    "indexability": row.get("Indexability", "Unknown")
                }
            else:
                lookup_map[path] = {"error": "Not found in crawl"}
        
        return lookup_map

    async def execute_query(self, query: str) -> Dict[str, Any]:
        if self.df is None:
            df, error = load_seo_data()
            if error or df.empty:
                logger.error(f"Failed to load SEO data: {error}")
                return {"answer": f"Error loading SEO data: {error}", "data": None}
        else:
            df = self.df
            
        if df.empty:
             return {"answer": "No SEO data available.", "data": None}

        try:
            # 1. LLM Planning
            system_prompt = f"""Analyze SEO question. Columns: {list(df.columns)[:15]}. 
            Return JSON: {{ "limit": 10 }}"""
            
            response = litellm.completion(
                model="openai/gemini-2.5-flash",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": query}],
                temperature=0.0
            )
            
            # 2. Hybrid Filtering
            result_df = df.copy()
            q = query.lower()

            if "https" in q and "not" in q:
                url_col = next((c for c in result_df.columns if c.lower() in ['address', 'url']), None)
                if url_col:
                    result_df = result_df[result_df[url_col].astype(str).str.startswith('http://', na=False)]

            # 3. Output
            result_data = result_df.head(20).fillna("").to_dict(orient='records')
            
            # Clean data for LLM Context
            clean_data = [{k:v for k,v in r.items() if str(v).strip()} for r in result_data]

            summ_resp = litellm.completion(
                model="openai/gemini-2.5-flash", 
                messages=[{"role": "user", "content": f"Summarize for '{query}': {str(clean_data)[:3000]}"}]
            )
            
            return {
                "answer": summ_resp.choices[0].message.content,
                "data": result_data
            }

        except Exception as e:
            logger.error(f"SEO Agent Error: {e}")
            return {"answer": f"Error: {e}", "data": None}

# Initialize with None, will be populated in initialize_seo_agent
seo_agent = SEOAgent()

async def run_seo_agent(query: str, df: pd.DataFrame = None) -> Dict[str, Any]:
    """Run SEO analysis on the given query.
    
    Args:
        query: The search query or URL to analyze
        df: Optional DataFrame with SEO data. If not provided, uses the agent's data.
            
    Returns:
        Dict with SEO analysis results
    """
    # If df is provided, use it. Otherwise, rely on the agent's data.
    agent = SEOAgent(df) if df is not None else seo_agent
    return await agent.execute_query(query)