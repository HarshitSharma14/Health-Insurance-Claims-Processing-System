"""Tests for the FastAPI routes layer.

Test coverage plan:
- POST /claims with valid form data returns 200 or 501 (scaffold state)
- POST /claims with missing required fields returns 422
- GET  /health returns 200 {"status": "ok"}
- GET  /claims/{claim_id} returns 501 (scaffold state)
- CORS headers present on responses
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.routes import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_health_check(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
