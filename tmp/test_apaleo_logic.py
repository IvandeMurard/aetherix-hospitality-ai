import asyncio
import unittest
from unittest.mock import MagicMock, patch
from datetime import date
import sys
import os

# Ensure app is in path
sys.path.append(os.path.join(os.getcwd(), "fastapi-backend"))

from app.services.apaleo_adapter import ApaleoPMSAdapter

class TestApaleoLogic(unittest.IsolatedAsyncioTestCase):
    
    async def asyncSetUp(self):
        # We pass dummy credentials to avoid env errors during mock tests
        self.adapter = ApaleoPMSAdapter(client_id="test_id", client_secret="test_secret")

    @patch('httpx.AsyncClient.post')
    async def test_authentication_caching(self, mock_post):
        """Verify token is cached and not re-fetched within expiry."""
        mock_post.return_value = MagicMock(
            status_code=200, 
            json=lambda: {"access_token": "fake_token", "expires_in": 3600}
        )
        
        # 1st call triggers auth
        await self.adapter._authenticate()
        self.assertEqual(mock_post.call_count, 1)
        self.assertEqual(self.adapter.access_token, "fake_token")
        
        # 2nd call uses cache
        await self.adapter._authenticate()
        self.assertEqual(mock_post.call_count, 1)

    @patch('httpx.AsyncClient.get')
    async def test_get_occupancy_parsing(self, mock_get):
        """Verify occupancy is correctly parsed from Apaleo payload."""
        self.adapter.access_token = "valid_token"
        self.adapter.token_expiry = sys.maxsize # Far in future
        
        mock_get.return_value = MagicMock(
            status_code=200, 
            json=lambda: {"occupancy": 92}
        )
        
        occ = await self.adapter.get_occupancy("pilot_hotel", date.today())
        self.assertEqual(occ, 92)
        
        # Test fallback
        mock_get.return_value = MagicMock(status_code=500)
        occ_fallback = await self.adapter.get_occupancy("pilot_hotel", date.today())
        self.assertEqual(occ_fallback, 85)

    @patch('httpx.AsyncClient.get')
    async def test_get_fb_revenue_sum(self, mock_get):
        """Verify F&B revenue is correctly filtered and summed."""
        self.adapter.access_token = "valid_token"
        self.adapter.token_expiry = sys.maxsize
        
        payload = {
            "revenue": [
                {"category": "Room", "amount": 1000.0},
                {"category": "F&B Breakfast", "amount": 250.0},
                {"category": "F&B Dinner", "amount": 500.0},
            ]
        }
        mock_get.return_value = MagicMock(status_code=200, json=lambda: payload)
        
        rev = await self.adapter.get_revenue("pilot_hotel", date.today(), category="F&B")
        self.assertEqual(rev, 750.0) # 250 + 500

if __name__ == '__main__':
    # Fix for PYTHONPATH issues in some envs
    unittest.main()
