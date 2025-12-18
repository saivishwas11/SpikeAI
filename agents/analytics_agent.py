"""
Analytics Agent for GA4 Data API interactions.

This module provides functionality to query Google Analytics 4 (GA4) data
using natural language queries. It handles query planning, execution,
and response formatting.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.oauth2 import service_account
import os
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    Metric,
    Dimension,
    DateRange,
    FilterExpression,
    Filter,
    FilterExpressionList,
    OrderBy,
)

from utils.ga4_planner import plan_ga4_query
from utils.llm_utils import LLMQueryPlanner

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize LLM utilities
llm_utils = LLMQueryPlanner()

class AnalyticsAgent:
    """Handles GA4 data retrieval and processing."""
    
    def __init__(self):
        """Initialize the AnalyticsAgent with a GA4 client."""
        try:
            # Get the path to the credentials file from environment variables
            credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            
            if not credentials_path:
                error_msg = "GOOGLE_APPLICATION_CREDENTIALS environment variable not set"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            if not os.path.exists(credentials_path):
                error_msg = f"Credentials file not found at: {credentials_path}"
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)
            
            logger.info(f"Loading GA4 credentials from: {credentials_path}")
            
            # Load the service account credentials
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/analytics.readonly']
            )
            
            # Initialize the client with explicit credentials
            self.client = BetaAnalyticsDataClient(credentials=credentials)
            logger.info("Successfully initialized GA4 client with service account")
            
            # Test the connection with a simple request
            try:
                property_id = os.getenv("GA4_PROPERTY_ID")
                if not property_id:
                    logger.warning("GA4_PROPERTY_ID not set. Skipping connection test.")
                else:
                    request = RunReportRequest(
                        property=f"properties/{property_id}",
                        date_ranges=[{"start_date": "7daysAgo", "end_date": "today"}],
                        dimensions=[{"name": "date"}],
                        metrics=[{"name": "activeUsers"}]
                    )
                    self.client.run_report(request)
                    logger.info("Successfully verified GA4 API connection")
                    
            except Exception as e:
                logger.error(f"Failed to verify GA4 API connection: {str(e)}")
                raise ValueError(f"Failed to connect to GA4 API: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error initializing GA4 client: {str(e)}")
            raise
    
    async def run_analytics_query(self, query: str, property_id: str = None) -> Dict[str, Any]:
        """
        Execute a GA4 query based on natural language input.
        
        Args:
            query: Natural language query string
            property_id: Optional GA4 property ID (falls back to GA4_PROPERTY_ID env var)
            
        Returns:
            Dict containing the query results and a natural language response
        """
        try:
            # Get property ID from args or environment
            property_id = property_id or os.getenv("GA4_PROPERTY_ID")
            if not property_id:
                error_msg = "No GA4 property ID provided and GA4_PROPERTY_ID environment variable not set"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            logger.info(f"Processing analytics query: {query}")
            
            # Plan the query using the LLM with the property ID
            plan = plan_ga4_query(f"{query} for GA4 property {property_id}")
            
            # Log the generated query plan
            logger.debug(f"Generated query plan: {plan}")
            
            # Ensure we have valid metrics
            if not plan.get('metrics'):
                plan['metrics'] = ["activeUsers", "screenPageViews"]
                logger.warning(f"No metrics specified in plan, using defaults: {plan['metrics']}")
                
            # Ensure we have a date range
            if not plan.get('start_date') or not plan.get('end_date'):
                plan['start_date'] = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
                plan['end_date'] = datetime.now().strftime('%Y-%m-%d')
                logger.info(f"Using default date range: {plan['start_date']} to {plan['end_date']}")
            
            # Build the GA4 request
            request = self._build_ga4_request(plan, property_id)
            
            # Execute the request
            response = self.client.run_report(request)
            
            # Process the response
            result = self._process_ga4_response(response, plan)
            
            # Generate a natural language response
            answer = llm_utils.generate_natural_language_response(query, result)
            
            return {
                "answer": answer,
                "data": result,
                "query_plan": plan
            }
            
        except Exception as e:
            error_msg = f"Error executing GA4 query: {str(e)}"
            logger.exception(error_msg)
            return {
                "answer": f"Sorry, I couldn't process your request. {error_msg}",
                "data": None,
                "error": str(e)
            }
    
    def _build_ga4_request(self, plan: Dict[str, Any], property_id: str) -> RunReportRequest:
        """Build a GA4 RunReportRequest from a query plan."""
        # Convert metrics and dimensions to GA4 types
        metrics = [Metric(name=m) for m in plan["metrics"]]
        dimensions = [Dimension(name=d) for d in plan["dimensions"]]
        
        # Create date range
        date_range = DateRange(
            start_date=plan["start_date"],
            end_date=plan["end_date"]
        )
        
        # Create filter expression if filters exist
        filter_expression = self._build_filter_expression(plan.get("filters", {}))
        
        # Create order by expressions
        order_bys = self._build_order_bys(plan.get("order_by", []))
        
        # Build the request
        request = RunReportRequest(
            property=f"properties/{property_id}",
            metrics=metrics,
            dimensions=dimensions,
            date_ranges=[date_range],
            limit=plan.get("limit", 1000),
        )
        
        if filter_expression:
            request.dimension_filter = filter_expression
        
        if order_bys:
            request.order_bys = order_bys
        
        return request
    
    def _build_filter_expression(self, filters: Dict[str, Any]) -> Optional[FilterExpression]:
        """Build a GA4 filter expression from filter criteria."""
        if not filters:
            return None
            
        filter_expressions = []
        
        for field, criteria in filters.items():
            if isinstance(criteria, dict) and "value" in criteria:
                filter_exp = Filter(
                    field_name=field,
                    string_filter=Filter.StringFilter(
                        value=criteria["value"],
                        match_type=self._get_match_type(criteria.get("match_type", "EXACT"))
                    )
                )
                filter_expressions.append(FilterExpression(filter=filter_exp))
        
        if not filter_expressions:
            return None
            
        return FilterExpression(
            and_group=FilterExpressionList(expressions=filter_expressions)
        )
    
    def _get_match_type(self, match_type: str) -> int:
        """Convert match type string to GA4 enum value."""
        match_type = match_type.upper()
        if match_type == "BEGINS_WITH":
            return Filter.StringFilter.MatchType.BEGINS_WITH
        elif match_type == "ENDS_WITH":
            return Filter.StringFilter.MatchType.ENDS_WITH
        elif match_type == "CONTAINS":
            return Filter.StringFilter.MatchType.CONTAINS
        elif match_type == "FULL_REGEXP":
            return Filter.StringFilter.MatchType.FULL_REGEXP
        else:  # EXACT or default
            return Filter.StringFilter.MatchType.EXACT
    
    def _build_order_bys(self, order_specs: List[Dict[str, str]]) -> List[OrderBy]:
        """Build GA4 order by expressions."""
        order_bys = []
        
        for spec in order_specs:
            field_name = spec.get("field_name")
            if not field_name:
                continue
                
            # Determine if it's a metric or dimension
            if any(m in field_name.lower() for m in ["metric", "count", "total"]):
                order_by = OrderBy(
                    metric=OrderBy.MetricOrderBy(metric_name=field_name)
                )
            else:
                order_by = OrderBy(
                    dimension=OrderBy.DimensionOrderBy(dimension_name=field_name)
                )
            
            # Set sort order
            if spec.get("sort_order", "").upper() == "ASCENDING":
                order_by.desc = False
            else:  # Default to descending
                order_by.desc = True
                
            order_bys.append(order_by)
        
        return order_bys
    
    def _process_ga4_response(
        self, 
        response: Any, 
        plan: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Process GA4 API response into a more usable format."""
        results = []
        
        # Get dimension and metric headers
        dimension_headers = [h.name for h in response.dimension_headers]
        metric_headers = [h.name for h in response.metric_headers]
        
        # Process each row
        for row in response.rows:
            result = {}
            
            # Add dimensions
            for i, value in enumerate(row.dimension_values):
                if i < len(dimension_headers):
                    result[dimension_headers[i]] = value.value
            
            # Add metrics
            for i, value in enumerate(row.metric_values):
                if i < len(metric_headers):
                    # Try to convert to appropriate numeric type
                    try:
                        # Check if it's a float with no decimal part
                        float_val = float(value.value)
                        if float_val.is_integer():
                            result[metric_headers[i]] = int(float_val)
                        else:
                            result[metric_headers[i]] = float_val
                    except (ValueError, TypeError):
                        result[metric_headers[i]] = value.value
            
            results.append(result)
        
        return results


# Create a singleton instance
analytics_agent = AnalyticsAgent()


def run_analytics_agent(query: str, property_id: str) -> Dict[str, Any]:
    """
    Run the analytics agent with the given query and property ID.
    This is a convenience function that uses the singleton instance.
    """
    return analytics_agent.run_analytics_query(query, property_id)
