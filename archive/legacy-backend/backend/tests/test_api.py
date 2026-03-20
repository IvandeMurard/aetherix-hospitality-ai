"""
Basic API endpoint tests
"""

import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_root_endpoint():
    """Test root endpoint returns correct response"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["message"] == "F&B Operations Agent API"
    assert data["status"] == "Phase 1 - Backend Development"


def test_health_endpoint():
    """Test health endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_qdrant_test_endpoint():
    """Test Qdrant connection endpoint"""
    response = client.get("/test/qdrant")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    # Should work with in-memory mode
    assert data["status"] in ["success", "error"]


@pytest.mark.skipif(
    True, reason="Requires ANTHROPIC_API_KEY in .env"
)
def test_claude_test_endpoint():
    """Test Claude API connection endpoint (requires API key)"""
    response = client.get("/test/claude")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
