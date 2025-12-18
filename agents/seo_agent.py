import logging
import re
import json
import pandas as pd
import litellm 
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from utils.sheets import load_seo_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SEOQueryPlan(BaseModel):
    filters: List[Dict[str, Any]] = Field(default_factory=list)
    limit: int = 100

class SEOAgent:
    def __init__(self):
        self.df = None

    def load_data(self, df: pd.DataFrame):
        self.df = df
        # Normalize columns
        self.df.columns = [c.strip() for c in self.df.columns]

    async def execute_query(self, query: str) -> Dict[str, Any]:
        if self.df is None or self.df.empty:
             return {"answer": "No SEO data loaded.", "data": None}

        try:
            # 1. LLM Planning
            system_prompt = f"""Analyze this SEO question. 
            Available columns: {list(self.df.columns)[:10]}...
            Return JSON: {{ "filters": [{{"column": "Name", "operator": "==", "value": "x"}}], "limit": 10 }}"""
            
            # FIX: Changed model to 'gemini-2.5-flash'
            response = litellm.completion(
                model="openai/gemini-2.5-flash",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": query}],
                temperature=0.0
            )
            
            # Clean JSON
            content = response.choices[0].message.content
            content = re.sub(r'```json\s*|```\s*', '', content).strip()
            
            try:
                plan_dict = json.loads(content)
            except:
                plan_dict = {}

            # 2. Apply Logic
            result_df = self.df.copy()
            
            if "missing meta descriptions" in query.lower():
                cols = [c for c in result_df.columns if "meta description" in c.lower()]
                if cols:
                    result_df = result_df[result_df[cols[0]].isna() | (result_df[cols[0]] == "")]
            
            result_data = result_df.head(plan_dict.get("limit", 10)).fillna("").to_dict(orient='records')
            
            # 3. Generate Answer
            answer_prompt = f"Summarize these SEO results for query '{query}': {str(result_data)[:1000]}"
            
            # FIX: Changed model to 'gemini-2.5-flash'
            summ_resp = litellm.completion(
                model="openai/gemini-2.5-flash", 
                messages=[{"role": "user", "content": answer_prompt}]
            )
            
            return {
                "answer": summ_resp.choices[0].message.content,
                "data": result_data
            }

        except Exception as e:
            logger.error(f"SEO Agent Error: {e}")
            return {"answer": f"Error analyzing SEO data: {e}", "data": None}

seo_agent = SEOAgent()

async def run_seo_agent(query: str, df: pd.DataFrame = None) -> Dict[str, Any]:
    global seo_agent
    
    # Lazy Load
    if seo_agent.df is None:
        try:
            logger.info("Loading SEO Data from Sheets...")
            loaded_df = load_seo_data()
            seo_agent.load_data(loaded_df)
        except Exception as e:
            return {"answer": f"Failed to load SEO Sheet: {e}", "data": None}
            
    return await seo_agent.execute_query(query)