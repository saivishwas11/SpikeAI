import pandas as pd
import os
import time
import logging
from utils.google_sheets_service import GoogleSheetsService

logger = logging.getLogger(__name__)

_cache = {"df": None, "timestamp": 0}

def load_seo_data() -> pd.DataFrame:
    global _cache
    if _cache["df"] is not None and (time.time() - _cache["timestamp"] < 300):
        return _cache["df"]

    try:
        sheet_url = os.getenv("SEO_SHEET_URL", "https://docs.google.com/spreadsheets/d/1zzf4ax_H2WiTBVrJigGjF2Q3Yz-qy2qMCbAMKvl6VEE/edit")
        service = GoogleSheetsService()
        
        # Returns { "Sheet1": [[...]], "Sheet2": [[...]] }
        all_tabs_data = service.get_all_sheets_data(sheet_url)
        
        if not all_tabs_data:
            logger.warning("⚠️ No data returned from Sheets Service.")
            return pd.DataFrame()
        
        combined_dfs = []
        
        # --- FIX IS HERE: Ensure .items() is used ---
        for sheet_name, rows in all_tabs_data.items():
            if not rows or len(rows) < 2: 
                continue 
            
            # Headers (Row 1)
            headers = [str(h).strip() for h in rows[0]]
            # Data (Row 2+)
            data = rows[1:]
            
            # Align columns
            max_cols = len(headers)
            aligned_data = [r + [""] * (max_cols - len(r)) for r in data]
            
            # Create DF
            df = pd.DataFrame([r[:max_cols] for r in aligned_data], columns=headers)
            df['Sheet_Source'] = sheet_name
            combined_dfs.append(df)

        if not combined_dfs:
            return pd.DataFrame()

        master_df = pd.concat(combined_dfs, axis=0, ignore_index=True, sort=False)
        
        # Clean empty cols
        master_df.dropna(axis=1, how='all', inplace=True)
        master_df.fillna("", inplace=True)

        _cache["df"] = master_df
        _cache["timestamp"] = time.time()
        
        logger.info(f"✅ Loaded {len(master_df)} rows from {len(combined_dfs)} tabs.")
        return master_df

    except Exception as e:
        logger.error(f"❌ Error in load_seo_data: {e}")
        return pd.DataFrame()