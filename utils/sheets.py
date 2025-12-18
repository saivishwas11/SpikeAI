import pandas as pd

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1zzf4ax_H2WiTBVrJigGjF2Q3Yz-qy2qMCbAMKvl6VEE/export?format=csv"


def load_seo_data():
    return pd.read_csv(SHEET_CSV_URL)
