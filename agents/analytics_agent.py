import logging
from typing import Dict, Any, List
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.oauth2 import service_account
from google.analytics.data_v1beta.types import RunReportRequest, Metric, Dimension, DateRange, FilterExpression
import os
from utils.ga4_planner import plan_ga4_query
from utils.llm_utils import LLMQueryPlanner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AnalyticsAgent:
    def __init__(self):
        try:
            # 1. Prioritize credentials.json at root (for Evaluators)
            creds_file = "credentials.json"
            
            if os.path.exists(creds_file):
                logger.info(f"Loading credentials from local {creds_file}")
                credentials = service_account.Credentials.from_service_account_file(
                    creds_file,
                    scopes=['https://www.googleapis.com/auth/analytics.readonly']
                )
            else:
                # 2. Fallback to Env Var
                credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
                if not credentials_path:
                    # Don't crash here, just log. Connection will fail later if used.
                    logger.warning("No credentials found. Analytics will fail.")
                    self.client = None
                    return

                credentials = service_account.Credentials.from_service_account_file(
                    credentials_path,
                    scopes=['https://www.googleapis.com/auth/analytics.readonly']
                )

            self.client = BetaAnalyticsDataClient(credentials=credentials)
            logger.info("Successfully initialized GA4 client")
            
        except Exception as e:
            logger.error(f"Error initializing GA4 client: {str(e)}")
            self.client = None
    
    async def run_analytics_query(self, query: str, property_id: str) -> Dict[str, Any]:
        if not self.client:
            return {"answer": "Server credentials missing. Cannot connect to GA4.", "data": None}

        try:
            logger.info(f"Running GA4 Query: {query} on Property: {property_id}")
            
            # 1. Plan
            plan = plan_ga4_query(f"{query} for GA4 property {property_id}")
            
            # 2. Execute
            request = RunReportRequest(
                property=f"properties/{property_id}",
                metrics=[Metric(name=m) for m in plan.get("metrics", ["activeUsers"])],
                dimensions=[Dimension(name=d) for d in plan.get("dimensions", ["date"])],
                date_ranges=[DateRange(
                    start_date=plan.get("start_date", "30daysAgo"), 
                    end_date=plan.get("end_date", "today")
                )]
            )
            
            response = self.client.run_report(request)
            
            # 3. Process
            data = []
            for row in response.rows:
                item = {}
                # Dimensions
                for i, dim_val in enumerate(row.dimension_values):
                    item[plan["dimensions"][i]] = dim_val.value
                # Metrics
                for i, met_val in enumerate(row.metric_values):
                    item[plan["metrics"][i]] = met_val.value
                data.append(item)
            
            # 4. Summarize
            answer = LLMQueryPlanner.generate_natural_language_response(query, data)
            
            return {"answer": answer, "data": data, "query_plan": plan}
            
        except Exception as e:
            logger.error(f"GA4 Execution Error: {e}")
            return {"answer": f"Error querying GA4: {e}", "data": None}

# Singleton
analytics_agent = AnalyticsAgent()

async def run_analytics_agent(query: str, property_id: str) -> Dict[str, Any]:
    return await analytics_agent.run_analytics_query(query, property_id)