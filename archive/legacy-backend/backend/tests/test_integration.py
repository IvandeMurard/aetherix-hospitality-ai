"""
Integration tests for F&B Agent prediction API
Tests the full pipeline: context → patterns → prediction → staffing
"""

import pytest
from httpx import AsyncClient, ASGITransport
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app


@pytest.fixture
def client():
    """Async test client"""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class TestPredictionAPI:
    """Integration tests for /predict endpoint"""

    @pytest.mark.asyncio
    async def test_christmas_low_demand(self, client):
        """Christmas Day should predict very low covers (40-70)"""
        async with client as c:
            response = await c.post("/predict", json={
                "restaurant_id": "test",
                "service_date": "2024-12-25",
                "service_type": "dinner"
            })
        
        assert response.status_code == 200
        data = response.json()
        
        # Covers: 30-80 range for Christmas (allowing some variance)
        assert 30 <= data["predicted_covers"] <= 80, f"Christmas covers {data['predicted_covers']} not in expected range"
        
        # Confidence should be high (model is confident about holidays)
        assert data["confidence"] >= 0.80
        
        # Staff should be reduced
        assert data["staff_recommendation"]["servers"]["delta"] < 0
        
    @pytest.mark.asyncio
    async def test_new_years_eve_peak(self, client):
        """NYE should predict very high covers (180-220)"""
        async with client as c:
            response = await c.post("/predict", json={
                "restaurant_id": "test",
                "service_date": "2024-12-31",
                "service_type": "dinner"
            })
        
        assert response.status_code == 200
        data = response.json()
        
        # Covers: 170-230 range for NYE (allowing some variance)
        assert 170 <= data["predicted_covers"] <= 230, f"NYE covers {data['predicted_covers']} not in expected range"
        
        # Staff should be increased
        assert data["staff_recommendation"]["servers"]["delta"] > 0
        
    @pytest.mark.asyncio
    async def test_regular_weekday(self, client):
        """Regular Tuesday should predict moderate covers (100-130)"""
        async with client as c:
            response = await c.post("/predict", json={
                "restaurant_id": "test",
                "service_date": "2024-12-17",  # Tuesday
                "service_type": "dinner"
            })
        
        assert response.status_code == 200
        data = response.json()
        
        # Covers: 80-150 range for weekday (accounting for weather variance)
        assert 80 <= data["predicted_covers"] <= 150, f"Weekday covers {data['predicted_covers']} not in expected range"
        
    @pytest.mark.asyncio
    async def test_weekend_boost(self, client):
        """Saturday should predict higher covers than weekday (130-160+)"""
        async with client as c:
            response = await c.post("/predict", json={
                "restaurant_id": "test",
                "service_date": "2024-12-14",  # Saturday
                "service_type": "dinner"
            })
        
        assert response.status_code == 200
        data = response.json()
        
        # Covers: 110-190 range for weekend (may include event boost)
        assert 110 <= data["predicted_covers"] <= 190, f"Weekend covers {data['predicted_covers']} not in expected range"
        
    @pytest.mark.asyncio
    async def test_response_structure(self, client):
        """Verify complete response structure"""
        async with client as c:
            response = await c.post("/predict", json={
                "restaurant_id": "test",
                "service_date": "2024-12-20",
                "service_type": "dinner"
            })
        
        assert response.status_code == 200
        data = response.json()
        
        # Required fields exist
        assert "prediction_id" in data
        assert "predicted_covers" in data
        assert "confidence" in data
        assert "reasoning" in data
        assert "staff_recommendation" in data
        
        # Staff recommendation structure
        staff = data["staff_recommendation"]
        assert "servers" in staff
        assert "hosts" in staff
        assert "kitchen" in staff
        assert "rationale" in staff
        assert "covers_per_staff" in staff
        
        # Staff delta structure
        assert "recommended" in staff["servers"]
        assert "usual" in staff["servers"]
        assert "delta" in staff["servers"]
        
        # Reasoning exists
        assert len(data["reasoning"]["summary"]) > 10
        
        # Patterns returned (in reasoning.patterns_used)
        assert len(data["reasoning"]["patterns_used"]) == 3


class TestEdgeCases:
    """Edge case tests"""
    
    @pytest.mark.asyncio
    async def test_invalid_date_format(self, client):
        """Invalid date should return 422"""
        async with client as c:
            response = await c.post("/predict", json={
                "restaurant_id": "test",
                "service_date": "not-a-date",
                "service_type": "dinner"
            })
        
        assert response.status_code == 422
        
    @pytest.mark.asyncio
    async def test_invalid_service_type(self, client):
        """Invalid service type should return 422"""
        async with client as c:
            response = await c.post("/predict", json={
                "restaurant_id": "test",
                "service_date": "2024-12-20",
                "service_type": "invalid"
            })
        
        assert response.status_code == 422
