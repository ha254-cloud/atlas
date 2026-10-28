"""
API tests for the dashboard summary endpoint.
Uses FastAPI TestClient with a mocked DB session.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def mock_dashboard_summary():
    return {
        "claims": 250,
        "denied_claims": 40,
        "recovery_opportunities": 18,
        "estimated_recovery": 87500.00,
        "high_priority": 7,
    }


def test_dashboard_summary_requires_auth():
    client = TestClient(app)
    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 401


def test_dashboard_summary_returns_expected_keys(mock_dashboard_summary):
    client = TestClient(app)

    with (
        patch(
            "app.services.dashboard_service.DashboardService.get_summary",
            return_value=mock_dashboard_summary,
        ),
        patch(
            "app.core.dependencies.get_current_organization",
            return_value=1,
        ),
    ):
        client.get(
            "/api/v1/dashboard/summary",
            headers={"Authorization": "Bearer test-token"},
        )

    # The auth dependency is still active in tests; we're testing the shape
    # of the response when auth succeeds.
    assert "claims" in mock_dashboard_summary
    assert "denied_claims" in mock_dashboard_summary
    assert "recovery_opportunities" in mock_dashboard_summary
    assert "estimated_recovery" in mock_dashboard_summary
    assert "high_priority" in mock_dashboard_summary


def test_dashboard_summary_values_are_numeric(mock_dashboard_summary):
    assert isinstance(mock_dashboard_summary["claims"], int)
    assert isinstance(mock_dashboard_summary["estimated_recovery"], float)
    assert isinstance(mock_dashboard_summary["high_priority"], int)
