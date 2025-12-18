import pandas as pd
from io import StringIO
import requests

# Link with gid=1438203274 to ensure we get the correct sheet tab
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1zzf4ax_H2WiTBVrJigGjF2Q3Yz-qy2qMCbAMKvl6VEE/export?format=csv&gid=1438203274"

def load_seo_data() -> pd.DataFrame:
    try:
        response = requests.get(SHEET_CSV_URL)
        response.raise_for_status()
        csv_data = StringIO(response.text)
        return pd.read_csv(csv_data)
    except Exception as e:
        print(f"Error loading sheets: {e}")
        return pd.DataFrame() # Return empty DF on failure