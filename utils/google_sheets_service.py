import os
import logging
import re
from typing import List, Dict, Any, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

class GoogleSheetsService:
    def __init__(self, credentials_path: str = "credentials.json"):
        self.credentials_path = credentials_path
        self.service = None
        self._authenticate()

    def _authenticate(self):
        try:
            # Fallback to env var if file missing
            if not os.path.exists(self.credentials_path):
                self.credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', self.credentials_path)

            if os.path.exists(self.credentials_path):
                creds = service_account.Credentials.from_service_account_file(
                    self.credentials_path, 
                    scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
                )
                self.service = build('sheets', 'v4', credentials=creds, cache_discovery=False)
            else:
                logger.warning("⚠️ No credentials found. Sheets API will fail.")
        except Exception as e:
            logger.error(f"❌ Auth Error: {e}")

    def extract_id_from_url(self, url: str) -> Optional[str]:
        match = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
        return match.group(1) if match else None

    def get_all_sheets_data(self, spreadsheet_url: str) -> Dict[str, List[List[Any]]]:
        """Returns { 'SheetName': [[row1], [row2]] }"""
        if not self.service: return {}
        
        spreadsheet_id = self.extract_id_from_url(spreadsheet_url)
        if not spreadsheet_id: return {}

        try:
            # 1. Get Sheet Names
            meta = self.service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            sheet_names = [s['properties']['title'] for s in meta.get('sheets', [])]
            
            # 2. Batch Get Data
            result = self.service.spreadsheets().values().batchGet(
                spreadsheetId=spreadsheet_id,
                ranges=sheet_names
            ).execute()
            
            all_data = {}
            value_ranges = result.get('valueRanges', [])
            
            for i, vr in enumerate(value_ranges):
                name = sheet_names[i]
                values = vr.get('values', [])
                all_data[name] = values
                
            return all_data

        except Exception as e:
            logger.error(f"❌ API Error: {e}")
            return {}