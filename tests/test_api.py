"""
tests/test_api.py
=================
Contract tests for the GlucoTwin API endpoints.
Uses TestClient (no live server required).
"""
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# We test the FastAPI app
try:
    from fastapi.testclient import TestClient
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _FASTAPI_AVAILABLE,
    reason="fastapi[testclient] not installed"
)


@pytest.fixture(scope="module")
def client():
    """Create a test client with mocked auth."""
    from app.main import app
    from app.core.deps import get_current_user
    from app.models.user import User, UserRole
    import uuid

    mock_user = MagicMock(spec=User)
    mock_user.id = uuid.uuid4()
    mock_user.role = UserRole.DOCTOR
    mock_user.is_active = True

    app.dependency_overrides[get_current_user] = lambda: mock_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestGlucoTwinHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "SYNTHETIC DATA" in data["disclaimer"]


class TestListPatients:
    def test_returns_200(self, client):
        resp = client.get("/api/v1/patients")
        assert resp.status_code == 200

    def test_returns_paginated_structure(self, client):
        resp = client.get("/api/v1/patients")
        data = resp.json()
        assert "total" in data
        assert "items" in data
        assert "page" in data
        assert "page_size" in data

    def test_pagination_params(self, client):
        resp = client.get("/api/v1/patients", params={"page": 1, "page_size": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 5


class TestIngestReadings:
    def test_ingest_valid_readings(self, client):
        payload = {
            "readings": [
                {
                    "patient_id": "SYN-TEST-API",
                    "timestamp": "2026-10-17T10:00:00Z",
                    "glucose_mg_dl": 120.5,
                    "heart_rate": 72.0,
                    "hrv_rmssd": 35.0,
                    "steps": 50.0,
                    "sleep_stage": 0,
                }
            ]
        }
        resp = client.post("/api/v1/stream/readings", json=payload)
        assert resp.status_code == 202
        data = resp.json()
        assert data["accepted"] == 1

    def test_ingest_with_null_glucose(self, client):
        """Sensor dropout (null glucose) should be accepted."""
        payload = {
            "readings": [
                {
                    "patient_id": "SYN-TEST-API",
                    "timestamp": "2026-10-17T10:05:00Z",
                    "glucose_mg_dl": None,  # dropout
                }
            ]
        }
        resp = client.post("/api/v1/stream/readings", json=payload)
        assert resp.status_code == 202

    def test_empty_readings_rejected(self, client):
        resp = client.post("/api/v1/stream/readings", json={"readings": []})
        assert resp.status_code == 422  # Pydantic validation error


class TestDecisions:
    def test_record_decision(self, client):
        payload = {
            "patient_id": "SYN-TEST-API",
            "suggestion_type": "HbA1c recency check",
            "rule_id": "R1",
            "rule_version": "1.0",
            "decision": "defer",
            "reason": "Patient travelling",
        }
        resp = client.post("/api/v1/decisions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["decision"] == "defer"

    def test_invalid_decision_rejected(self, client):
        payload = {
            "patient_id": "SYN-TEST-API",
            "suggestion_type": "test",
            "decision": "invalid_decision_type",
        }
        resp = client.post("/api/v1/decisions", json=payload)
        assert resp.status_code == 422  # Pydantic validation


class TestAuditLog:
    def test_audit_log_accessible(self, client):
        resp = client.get("/api/v1/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data

    def test_audit_log_patient_filter(self, client):
        resp = client.get("/api/v1/audit", params={"patient_id": "SYN-TEST-API"})
        assert resp.status_code == 200


class TestExistingApiNotBroken:
    """Verify existing MedIntel endpoints still work."""
    def test_health_still_works(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_patients_list_still_works(self, client):
        resp = client.get("/api/patients")
        assert resp.status_code == 200

    def test_analytics_executive_works(self, client):
        resp = client.get("/api/analytics/executive")
        assert resp.status_code == 200
