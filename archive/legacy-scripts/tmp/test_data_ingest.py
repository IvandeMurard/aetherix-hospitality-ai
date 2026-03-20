import sys
import unittest
from datetime import date
import pandas as pd
import os

# Ensure app is in path
sys.path.append(os.path.join(os.getcwd(), "fastapi-backend"))

from app.services.pms_sync import PIIStripper
from app.services.data_transformer import DataTransformer

class TestDataIngest(unittest.TestCase):
    
    def test_pii_stripping(self):
        """Verify guest data is anonymized."""
        raw_res = {
            "guest_id": 12345,
            "guest_name": "Ivan de Murard",
            "guest_email": "ivan@example.com",
            "arrival": "2026-03-12"
        }
        
        stripped = PIIStripper.strip_guest_data(raw_res)
        
        self.assertNotIn("guest_name", stripped)
        self.assertNotIn("guest_email", stripped)
        self.assertNotIn("guest_id", stripped)
        self.assertIn("guest_hashed_id", stripped)
        self.assertEqual(len(stripped["guest_hashed_id"]), 64) # SHA-256 length

    def test_stay_records_transformation(self):
        """Verify Prophet-ready DataFrame generation."""
        records = [
            {"arrival": "2026-06-01T14:00:00Z", "adults": 2, "children": 1},
            {"arrival": "2026-06-01T15:00:00Z", "adults": 1, "children": 0},
            {"arrival": "2026-06-02T10:00:00Z", "adults": 2, "children": 2},
        ]
        
        df = DataTransformer.stay_records_to_prophet(records)
        
        self.assertEqual(len(df), 2) # Two distinct dates
        self.assertEqual(df[df['ds'] == '2026-06-01']['y'].iloc[0], 4) # 3 + 1
        self.assertEqual(df[df['ds'] == '2026-06-02']['y'].iloc[0], 4) # 4

if __name__ == '__main__':
    unittest.main()
