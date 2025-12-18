from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.oauth2 import service_account


def get_ga4_client():
    credentials = service_account.Credentials.from_service_account_file(
        "credentials.json",
        scopes=["https://www.googleapis.com/auth/analytics.readonly"]
    )
    return BetaAnalyticsDataClient(credentials=credentials)
