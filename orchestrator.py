from agents.analytics_agent import run_analytics_agent
from agents.seo_agent import run_seo_agent


def handle_query(query: str, property_id: str | None):
    q = query.lower()

    is_ga4 = any(k in q for k in ["user", "session", "page", "traffic", "ga4"])
    is_seo = any(k in q for k in ["seo", "title", "meta", "index", "https"])

    if is_ga4 and not property_id:
        raise ValueError("propertyId is required for GA4 queries")

    if is_ga4 and is_seo:
        ga4 = run_analytics_agent(query, property_id)
        seo = run_seo_agent(query)

        return {
            "answer": ga4["answer"] + "\n\nSEO Info:\n" + seo["answer"],
            "data": {
                "analytics": ga4["data"],
                "seo": seo["data"]
            }
        }

    if is_ga4:
        return run_analytics_agent(query, property_id)

    if is_seo:
        return run_seo_agent(query)

    return {
        "answer": "Could not determine intent of query.",
        "data": None
    }
