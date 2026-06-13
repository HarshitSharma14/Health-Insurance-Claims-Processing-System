"""Tests for the FastAPI routes layer."""

from __future__ import annotations

import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.routes import app
from app.schemas.claim import DocumentType


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# Minimal valid 1×1 white JPEG bytes
JPEG_1PX = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
    b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
    b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\x1e"
    b"CF7F\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11"
    b"\x00\xff\xd9"
)


def test_health_check(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def _make_multipart(document_types: list[str] | None = None):
    """Build multipart form data for POST /claims with two placeholder files."""
    files = [
        ("files", ("prescription.jpg", io.BytesIO(JPEG_1PX), "image/jpeg")),
        ("files", ("hospital_bill.jpg", io.BytesIO(JPEG_1PX), "image/jpeg")),
    ]
    data = {
        "member_id": "EMP001",
        "policy_id": "PLUM_GHI_2024",
        "claim_category": "CONSULTATION",
        "treatment_date": "2024-11-01",
        "claimed_amount": "1500",
    }
    if document_types:
        for i, dt in enumerate(document_types):
            data[f"document_type_{i}"] = dt
    return files, data


def test_declared_document_types_skip_classification(client: TestClient) -> None:
    """When document_type_{i} fields are provided, Gemini classification is skipped."""
    files, data = _make_multipart(["PRESCRIPTION", "HOSPITAL_BILL"])

    # Mock process_claim to capture what UploadedDocuments were built
    captured = {}

    async def fake_process(submission, **kwargs):
        captured["docs"] = submission.documents
        # Return a minimal verification failure to avoid full pipeline
        from app.schemas.verification import DocumentVerificationResult
        from app.trace.trace import new_trace
        from app.schemas.claim import DocumentType as DT
        return DocumentVerificationResult(
            passed=True,
            required_documents=[DT.PRESCRIPTION, DT.HOSPITAL_BILL],
            received_documents=[DT.PRESCRIPTION, DT.HOSPITAL_BILL],
            missing_documents=[],
        )

    with patch("app.api.routes.process_claim", side_effect=fake_process):
        with patch("app.api.routes._classify_document") as mock_classify:
            response = client.post("/claims", files=files, data=data)

    # Classification should NOT have been called for either file
    mock_classify.assert_not_called()
    assert captured["docs"][0].document_type == DocumentType.PRESCRIPTION
    assert captured["docs"][1].document_type == DocumentType.HOSPITAL_BILL


def test_missing_declared_types_fall_back_to_classification(client: TestClient) -> None:
    """When no document_type_{i} fields are sent, classification runs as before."""
    files, data = _make_multipart()  # no declared types

    async def fake_process(submission, **kwargs):
        from app.schemas.verification import DocumentVerificationResult
        from app.schemas.claim import DocumentType as DT
        return DocumentVerificationResult(
            passed=True,
            required_documents=[DT.PRESCRIPTION, DT.HOSPITAL_BILL],
            received_documents=[DT.PRESCRIPTION, DT.HOSPITAL_BILL],
            missing_documents=[],
        )

    with patch("app.api.routes.process_claim", side_effect=fake_process):
        with patch(
            "app.api.routes._classify_document",
            new=AsyncMock(return_value=DocumentType.UNKNOWN),
        ) as mock_classify:
            response = client.post("/claims", files=files, data=data)

    # Classification should have been called once per file
    assert mock_classify.call_count == 2


def test_partial_declared_types_only_classify_undeclared(client: TestClient) -> None:
    """If only document_type_0 is provided, only file 1 goes through classification."""
    files, data = _make_multipart(["PRESCRIPTION"])  # only first file declared

    async def fake_process(submission, **kwargs):
        from app.schemas.verification import DocumentVerificationResult
        from app.schemas.claim import DocumentType as DT
        return DocumentVerificationResult(
            passed=True,
            required_documents=[DT.PRESCRIPTION, DT.HOSPITAL_BILL],
            received_documents=[DT.PRESCRIPTION, DT.HOSPITAL_BILL],
            missing_documents=[],
        )

    captured = {}

    async def fake_classify(file_bytes, content_type):
        captured["called"] = True
        return DocumentType.HOSPITAL_BILL

    with patch("app.api.routes.process_claim", side_effect=fake_process):
        with patch("app.api.routes._classify_document", side_effect=fake_classify):
            response = client.post("/claims", files=files, data=data)

    # Only the undeclared second file should have been classified
    assert captured.get("called") is True


def test_invalid_declared_type_falls_back_to_classification(client: TestClient) -> None:
    """An invalid document_type_{i} value is ignored and classification runs."""
    files, data = _make_multipart()
    data["document_type_0"] = "NOT_A_VALID_TYPE"

    async def fake_process(submission, **kwargs):
        from app.schemas.verification import DocumentVerificationResult
        from app.schemas.claim import DocumentType as DT
        return DocumentVerificationResult(
            passed=True,
            required_documents=[],
            received_documents=[],
            missing_documents=[],
        )

    with patch("app.api.routes.process_claim", side_effect=fake_process):
        with patch(
            "app.api.routes._classify_document",
            new=AsyncMock(return_value=DocumentType.UNKNOWN),
        ) as mock_classify:
            response = client.post("/claims", files=files, data=data)

    # Both files should fall back to classification since the declared type was invalid
    assert mock_classify.call_count == 2
