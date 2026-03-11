"""Tests for RFC 7807 Problem Details error handler.

Verifies that all HTTP exceptions from the FastAPI backend return
the RFC 7807 format: type, title, status, detail.

Story 1.1 AC #4: Given a route throws an exception, Then it returns
an RFC 7807 Problem Details JSON response.
"""
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

# Import the error handler from our core module
# NOTE: After template bootstrap, import path may be:
# from app.core.error_handlers import problem_details_handler
from app.core.error_handlers import problem_details_handler


def create_test_app() -> FastAPI:
    """Create a minimal FastAPI app with the RFC 7807 handler registered."""
    app = FastAPI()
    app.add_exception_handler(HTTPException, problem_details_handler)

    @app.get("/test-404")
    async def trigger_404():
        raise HTTPException(status_code=404, detail="Item not found")

    @app.get("/test-422")
    async def trigger_422():
        raise HTTPException(status_code=422, detail="Unprocessable entity")

    @app.get("/test-500")
    async def trigger_500():
        raise HTTPException(status_code=500, detail="Internal server error")

    return app


@pytest.fixture
def client():
    app = create_test_app()
    return TestClient(app)


def test_404_returns_problem_details(client):
    """AC #4: 404 must return RFC 7807 shape."""
    response = client.get("/test-404")
    assert response.status_code == 404
    data = response.json()
    assert "type" in data, "RFC 7807 requires 'type' field"
    assert "title" in data, "RFC 7807 requires 'title' field"
    assert "status" in data, "RFC 7807 requires 'status' field"
    assert "detail" in data, "RFC 7807 requires 'detail' field"
    assert data["status"] == 404
    assert "aetherix.io/errors" in data["type"]


def test_422_returns_problem_details(client):
    """Edge case: 422 must also return RFC 7807 shape."""
    response = client.get("/test-422")
    assert response.status_code == 422
    data = response.json()
    assert data["status"] == 422
    assert "type" in data
    assert "title" in data
    assert "detail" in data


def test_500_returns_problem_details(client):
    """Edge case: 500 must also return RFC 7807 shape."""
    response = client.get("/test-500")
    assert response.status_code == 500
    data = response.json()
    assert data["status"] == 500
    assert "type" in data
    assert "title" in data
    assert "detail" in data


def test_problem_details_no_default_fastapi_format(client):
    """Regression: must NOT return FastAPI's default {'detail': '...'} shape."""
    response = client.get("/test-404")
    data = response.json()
    # The response must have MORE than just 'detail' — it must have type, title, status
    assert len(data) >= 4, "RFC 7807 requires at minimum 4 fields: type, title, status, detail"


def test_type_field_is_valid_uri(client):
    """RFC 7807 spec: 'type' field should be a URI."""
    response = client.get("/test-404")
    data = response.json()
    assert data["type"].startswith("https://"), "'type' must be an absolute URI per RFC 7807"
