"""Tests for FastAPI endpoints (SPEC §4)."""

import pytest
from fastapi.testclient import TestClient

from ClawGraph.main import app


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"

    def test_health_reports_backend(self, client):
        response = client.get("/api/health")
        data = response.json()
        assert "graph_backend" in data


class TestGraphStatsEndpoint:
    def test_stats_returns_200(self, client):
        response = client.get("/api/graph/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_nodes" in data
        assert "total_relationships" in data


class TestQueryEndpoint:
    def test_query_without_api_key_returns_503(self, client):
        response = client.post("/api/query", json={"question": "What is OpenClaw?"})
        # Without GEMINI_API_KEY, RAG is not initialized
        assert response.status_code == 503

    def test_query_empty_question_returns_422(self, client):
        response = client.post("/api/query", json={"question": ""})
        assert response.status_code == 422


class TestSecurityAuditEndpoint:
    def test_audit_returns_200(self, client):
        response = client.get("/api/security/audit")
        assert response.status_code == 200
        data = response.json()
        assert "events" in data


class TestVisualizeEndpoint:
    def test_visualize_returns_png(self, client):
        response = client.get("/api/graph/visualize")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        
        # Verify it's a valid PNG (starts with PNG signature bytes)
        content = response.read()
        assert content.startswith(b"\x89PNG\r\n\x1a\n")
