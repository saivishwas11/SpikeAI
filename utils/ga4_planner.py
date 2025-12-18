from datetime import date, timedelta
from typing import Dict, Any, List, Optional
from .llm_utils import LLMQueryPlanner


class GA4QueryPlanner:
    """Class to handle GA4 query planning with LLM assistance."""
    
    def __init__(self):
        self.llm_planner = LLMQueryPlanner()
        self.safe_metrics = {
            # User metrics
            "activeUsers", "newUsers", "totalUsers", "sessionsPerUser", "userEngagementDuration",
            # Session metrics
            "sessions", "sessionsPerUser", "averageSessionDuration", "engagedSessions",
            # Engagement metrics
            "screenPageViews", "screenPageViewsPerSession", "screenPageViewsPerUser",
            "bounceRate", "engagementRate", "averageEngagementTime",
            # Ecommerce metrics
            "purchaseRevenue", "transactions", "totalRevenue", "ecommercePurchases",
            "itemsViewed", "itemsAddedToCart", "itemsPurchased",
            # Event metrics
            "eventCount", "eventsPerSession", "eventCountPerUser",
        }
        
        self.safe_dimensions = {
            # Time dimensions
            "date", "dayOfWeek", "hour", "month", "year", "dateHour", "dateHourMinute",
            # Traffic source dimensions
            "source", "medium", "campaign", "sourceMedium", "campaignId", "defaultChannelGrouping",
            # Page/screen dimensions
            "pageTitle", "pagePath", "pageLocation", "pageReferrer", "pagePathPlusQueryString",
            # User dimensions
            "country", "city", "region", "language", "deviceCategory", "browser", "os", "platform",
            # Event dimensions
            "eventName", "eventCount", "eventValue", "eventCountPerUser",
        }

    def plan_ga4_query(self, query: str) -> Dict[str, Any]:
        """
        Plan a GA4 query based on natural language input.
        
        Args:
            query: Natural language query string
            
        Returns:
            Dict containing the GA4 query parameters
        """
        # Get LLM-generated query plan
        plan = self.llm_planner.plan_ga4_query(query)
        
        # Validate and sanitize the plan
        return self._sanitize_plan(plan)
    
    def _sanitize_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize the query plan to ensure it's safe to execute."""
        # Ensure required fields exist
        plan.setdefault("metrics", ["screenPageViews", "users", "sessions"])
        plan.setdefault("dimensions", ["date"])
        plan.setdefault("filters", {})
        plan.setdefault("order_by", [{"field_name": "date", "sort_order": "DESCENDING"}])
        plan.setdefault("limit", 1000)
        
        # Set default date range if not provided (last 30 days)
        today = date.today()
        plan.setdefault("start_date", (today - timedelta(days=30)).isoformat())
        plan.setdefault("end_date", today.isoformat())
        
        # Sanitize metrics and dimensions
        plan["metrics"] = [m for m in plan["metrics"] if m in self.safe_metrics]
        plan["dimensions"] = [d for d in plan["dimensions"] if d in self.safe_dimensions]
        
        # Ensure we have at least one metric and dimension
        if not plan["metrics"]:
            plan["metrics"] = ["screenPageViews", "users", "sessions"]
        if not plan["dimensions"]:
            plan["dimensions"] = ["date"]
        
        # Sanitize limit
        plan["limit"] = min(int(plan.get("limit", 1000)), 10000)  # Max 10,000 rows
        
        return plan


# Create a singleton instance
query_planner = GA4QueryPlanner()


def plan_ga4_query(query: str) -> Dict[str, Any]:
    """
    Plan a GA4 query based on natural language input.
    This is a convenience function that uses the singleton instance.
    """
    return query_planner.plan_ga4_query(query)
