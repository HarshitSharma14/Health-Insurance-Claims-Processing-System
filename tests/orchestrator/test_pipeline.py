"""End-to-end orchestrator tests using pre_extracted_documents injection.

Strategy:
- TC001-TC003: verification failures (document_verifier catches them before
  extraction even runs). Extractor is NOT called -- asserted via mock.
- TC004-TC010, TC012: pre_extracted_documents supplied, real policy_evaluator
  and decision_maker run against real policy_terms.json.
- TC011: pre_extracted_documents + simulate_component_failure=True.
- Concurrency: two-document claim, extractor mocked with delay -- assert
  wall-time is closer to one call than the sum.

All tests load real policy_terms.json. No live Anthropic API calls.
"""

import asyncio
import time
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.orchestrator.pipeline import process_claim
from app.policy.loader import load_policy
from app.schemas.claim import (
    ClaimCategory,
    ClaimSubmission,
    ClaimsHistoryEntry,
    DocumentQuality,
    DocumentType,
    UploadedDocument,
)
from app.schemas.decision import ClaimDecision
from app.schemas.extraction import ExtractedDocumentData, LineItem
from app.schemas.verification import DocumentVerificationResult, VerificationFailureType

POLICY_PATH = Path(__file__).parents[2] / "policy_terms.json"


@pytest.fixture(autouse=True)
def _load_policy():
    load_policy(POLICY_PATH)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _doc(file_id: str, doc_type: DocumentType = DocumentType.PRESCRIPTION,
         quality: DocumentQuality = DocumentQuality.GOOD,
         patient_name: str | None = None) -> UploadedDocument:
    return UploadedDocument(
        file_id=file_id,
        file_name=f"{file_id}.jpg",
        document_type=doc_type,
        quality=quality,
        patient_name=patient_name,
    )


def _sub(member_id, category, treatment_date, claimed_amount,
         docs, hospital_name=None, claims_history=None,
         simulate_failure=False):
    return ClaimSubmission(
        member_id=member_id,
        policy_id="PLUM_GHI_2024",
        claim_category=category,
        treatment_date=treatment_date,
        claimed_amount=claimed_amount,
        hospital_name=hospital_name,
        claims_history=claims_history or [],
        simulate_component_failure=simulate_failure,
        documents=docs,
    )


def _ex(file_id, doc_type=DocumentType.PRESCRIPTION,
        diagnosis=None, treatment=None, patient_name=None,
        line_items=None, total=None, tests_ordered=None,
        hospital_name=None, confidence=0.95):
    return ExtractedDocumentData(
        file_id=file_id,
        document_type=doc_type,
        diagnosis=diagnosis,
        treatment=treatment,
        patient_name=patient_name,
        line_items=[LineItem(description=d, amount=a) for d, a in (line_items or [])],
        total=total,
        tests_ordered=tests_ordered or [],
        hospital_name=hospital_name,
        overall_confidence=confidence,
    )


# ---------------------------------------------------------------------------
# TC001 -- wrong document type (verification fails, extractor never called)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc001_verification_failure_stops_pipeline():
    sub = _sub("EMP001", ClaimCategory.CONSULTATION, date(2024, 11, 1), 1500.0,
               docs=[_doc("F001", DocumentType.PRESCRIPTION),
                     _doc("F002", DocumentType.PRESCRIPTION)])
    with patch("app.orchestrator.pipeline.extractor.run", new_callable=AsyncMock) as mock_ext:
        result = await process_claim(sub)
    assert isinstance(result, DocumentVerificationResult)
    assert result.passed is False
    assert result.failure_type == VerificationFailureType.WRONG_OR_MISSING_DOCUMENTS
    mock_ext.assert_not_called()


@pytest.mark.asyncio
async def test_tc001_message_names_missing_type():
    sub = _sub("EMP001", ClaimCategory.CONSULTATION, date(2024, 11, 1), 1500.0,
               docs=[_doc("F001", DocumentType.PRESCRIPTION),
                     _doc("F002", DocumentType.PRESCRIPTION)])
    with patch("app.orchestrator.pipeline.extractor.run", new_callable=AsyncMock):
        result = await process_claim(sub)
    assert isinstance(result, DocumentVerificationResult)
    assert result.message is not None
    assert "hospital bill" in result.message.lower() or "HOSPITAL_BILL" in result.message


# ---------------------------------------------------------------------------
# TC002 -- unreadable document
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc002_unreadable_document_stops_pipeline():
    sub = _sub("EMP004", ClaimCategory.PHARMACY, date(2024, 10, 25), 800.0,
               docs=[_doc("F003", DocumentType.PRESCRIPTION, DocumentQuality.GOOD),
                     _doc("F004", DocumentType.PHARMACY_BILL, DocumentQuality.UNREADABLE)])
    with patch("app.orchestrator.pipeline.extractor.run", new_callable=AsyncMock) as mock_ext:
        result = await process_claim(sub)
    assert isinstance(result, DocumentVerificationResult)
    assert result.failure_type == VerificationFailureType.UNREADABLE_DOCUMENT
    mock_ext.assert_not_called()


# ---------------------------------------------------------------------------
# TC003 -- patient mismatch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc003_patient_mismatch_stops_pipeline():
    sub = _sub("EMP001", ClaimCategory.CONSULTATION, date(2024, 11, 1), 1500.0,
               docs=[_doc("F005", DocumentType.PRESCRIPTION, patient_name="Rajesh Kumar"),
                     _doc("F006", DocumentType.HOSPITAL_BILL, patient_name="Arjun Mehta")])
    with patch("app.orchestrator.pipeline.extractor.run", new_callable=AsyncMock) as mock_ext:
        result = await process_claim(sub)
    assert isinstance(result, DocumentVerificationResult)
    assert result.failure_type == VerificationFailureType.PATIENT_MISMATCH
    assert "Rajesh Kumar" in result.message
    assert "Arjun Mehta" in result.message
    mock_ext.assert_not_called()


# ---------------------------------------------------------------------------
# TC004 -- clean consultation, APPROVED Rs1350
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc004_approved_exact_amount():
    sub = _sub("EMP001", ClaimCategory.CONSULTATION, date(2024, 11, 1), 1500.0,
               docs=[_doc("F007"), _doc("F008", DocumentType.HOSPITAL_BILL)])
    pre = [
        _ex("F007", diagnosis="Viral Fever", patient_name="Rajesh Kumar"),
        _ex("F008", DocumentType.HOSPITAL_BILL, patient_name="Rajesh Kumar",
            line_items=[("Consultation Fee", 1000.0), ("CBC Test", 300.0),
                        ("Dengue NS1 Test", 200.0)], total=1500.0),
    ]
    result = await process_claim(sub, pre_extracted_documents=pre)
    assert isinstance(result, ClaimDecision)
    assert result.decision == "APPROVED"
    assert result.approved_amount == pytest.approx(1350.0, abs=0.01)


@pytest.mark.asyncio
async def test_tc004_confidence_above_085():
    sub = _sub("EMP001", ClaimCategory.CONSULTATION, date(2024, 11, 1), 1500.0,
               docs=[_doc("F007"), _doc("F008", DocumentType.HOSPITAL_BILL)])
    pre = [_ex("F007", diagnosis="Viral Fever"),
           _ex("F008", DocumentType.HOSPITAL_BILL, total=1500.0)]
    result = await process_claim(sub, pre_extracted_documents=pre)
    assert isinstance(result, ClaimDecision)
    assert result.confidence_score > 0.85


@pytest.mark.asyncio
async def test_tc004_trace_has_all_stages():
    sub = _sub("EMP001", ClaimCategory.CONSULTATION, date(2024, 11, 1), 1500.0,
               docs=[_doc("F007"), _doc("F008", DocumentType.HOSPITAL_BILL)])
    pre = [_ex("F007", diagnosis="Viral Fever"),
           _ex("F008", DocumentType.HOSPITAL_BILL, total=1500.0)]
    result = await process_claim(sub, pre_extracted_documents=pre)
    assert isinstance(result, ClaimDecision)
    stages = {e.stage for e in result.trace.events}
    assert "document_verification" in stages
    assert "policy_evaluation" in stages
    assert "decision" in stages
    assert result.trace.final_decision_explanation != ""


# ---------------------------------------------------------------------------
# TC005 -- REJECTED WAITING_PERIOD (diabetes, EMP005 joined 2024-09-01)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc005_rejected_waiting_period():
    sub = _sub("EMP005", ClaimCategory.CONSULTATION, date(2024, 10, 15), 3000.0,
               docs=[_doc("F009"), _doc("F010", DocumentType.HOSPITAL_BILL)])
    pre = [
        _ex("F009", diagnosis="Type 2 Diabetes Mellitus", patient_name="Vikram Joshi"),
        _ex("F010", DocumentType.HOSPITAL_BILL, patient_name="Vikram Joshi", total=3000.0),
    ]
    result = await process_claim(sub, pre_extracted_documents=pre)
    assert isinstance(result, ClaimDecision)
    assert result.decision == "REJECTED"
    assert "WAITING_PERIOD" in result.rejection_reasons


@pytest.mark.asyncio
async def test_tc005_reason_contains_eligibility_date():
    sub = _sub("EMP005", ClaimCategory.CONSULTATION, date(2024, 10, 15), 3000.0,
               docs=[_doc("F009"), _doc("F010", DocumentType.HOSPITAL_BILL)])
    pre = [_ex("F009", diagnosis="Type 2 Diabetes Mellitus"),
           _ex("F010", DocumentType.HOSPITAL_BILL, total=3000.0)]
    result = await process_claim(sub, pre_extracted_documents=pre)
    # EMP005 join_date=2024-09-01 + 90 days = 2024-11-30
    assert "2024-11-30" in result.reason


# ---------------------------------------------------------------------------
# TC006 -- PARTIAL Rs8000 (dental: root canal covered, whitening excluded)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc006_partial_approved_amount():
    sub = _sub("EMP002", ClaimCategory.DENTAL, date(2024, 10, 15), 12000.0,
               docs=[_doc("F011", DocumentType.HOSPITAL_BILL)])
    pre = [
        _ex("F011", DocumentType.HOSPITAL_BILL, patient_name="Priya Singh",
            line_items=[("Root Canal Treatment", 8000.0), ("Teeth Whitening", 4000.0)],
            total=12000.0),
    ]
    result = await process_claim(sub, pre_extracted_documents=pre)
    assert isinstance(result, ClaimDecision)
    assert result.decision == "PARTIAL"
    assert result.approved_amount == pytest.approx(8000.0, abs=0.01)


@pytest.mark.asyncio
async def test_tc006_line_items_present_in_result():
    sub = _sub("EMP002", ClaimCategory.DENTAL, date(2024, 10, 15), 12000.0,
               docs=[_doc("F011", DocumentType.HOSPITAL_BILL)])
    pre = [_ex("F011", DocumentType.HOSPITAL_BILL,
               line_items=[("Root Canal Treatment", 8000.0), ("Teeth Whitening", 4000.0)],
               total=12000.0)]
    result = await process_claim(sub, pre_extracted_documents=pre)
    assert isinstance(result, ClaimDecision)
    assert len(result.line_item_evaluations) == 2
    covered = [e for e in result.line_item_evaluations if e.covered]
    excluded = [e for e in result.line_item_evaluations if not e.covered]
    assert len(covered) == 1
    assert len(excluded) == 1


# ---------------------------------------------------------------------------
# TC007 -- REJECTED PRE_AUTH_MISSING (MRI Rs15000)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc007_rejected_pre_auth_missing():
    sub = _sub("EMP007", ClaimCategory.DIAGNOSTIC, date(2024, 11, 2), 15000.0,
               docs=[_doc("F012"), _doc("F013", DocumentType.LAB_REPORT),
                     _doc("F014", DocumentType.HOSPITAL_BILL)])
    pre = [
        _ex("F012", tests_ordered=["MRI Lumbar Spine"]),
        _ex("F013", DocumentType.LAB_REPORT),
        _ex("F014", DocumentType.HOSPITAL_BILL,
            line_items=[("MRI Lumbar Spine", 15000.0)], total=15000.0),
    ]
    result = await process_claim(sub, pre_extracted_documents=pre)
    assert isinstance(result, ClaimDecision)
    assert result.decision == "REJECTED"
    assert "PRE_AUTH_MISSING" in result.rejection_reasons


# ---------------------------------------------------------------------------
# TC008 -- REJECTED PER_CLAIM_EXCEEDED (Rs7500 > Rs5000 limit)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc008_rejected_per_claim_exceeded():
    sub = _sub("EMP003", ClaimCategory.CONSULTATION, date(2024, 10, 20), 7500.0,
               docs=[_doc("F015"), _doc("F016", DocumentType.HOSPITAL_BILL)])
    pre = [
        _ex("F015", diagnosis="Gastroenteritis"),
        _ex("F016", DocumentType.HOSPITAL_BILL,
            line_items=[("Consultation Fee", 2000.0), ("Medicines", 5500.0)],
            total=7500.0),
    ]
    result = await process_claim(sub, pre_extracted_documents=pre)
    assert isinstance(result, ClaimDecision)
    assert result.decision == "REJECTED"
    assert "PER_CLAIM_EXCEEDED" in result.rejection_reasons


# ---------------------------------------------------------------------------
# TC009 -- MANUAL_REVIEW fraud signals (4th same-day claim)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc009_manual_review_fraud():
    history = [
        ClaimsHistoryEntry(claim_id="CLM_0081", date=date(2024, 10, 30), amount=1200),
        ClaimsHistoryEntry(claim_id="CLM_0082", date=date(2024, 10, 30), amount=1800),
        ClaimsHistoryEntry(claim_id="CLM_0083", date=date(2024, 10, 30), amount=2100),
    ]
    sub = _sub("EMP008", ClaimCategory.CONSULTATION, date(2024, 10, 30), 4800.0,
               docs=[_doc("F017"), _doc("F018", DocumentType.HOSPITAL_BILL)],
               claims_history=history)
    pre = [
        _ex("F017", diagnosis="Migraine"),
        _ex("F018", DocumentType.HOSPITAL_BILL, total=4800.0),
    ]
    result = await process_claim(sub, pre_extracted_documents=pre)
    assert isinstance(result, ClaimDecision)
    assert result.decision == "MANUAL_REVIEW"


@pytest.mark.asyncio
async def test_tc009_fraud_signal_in_reason():
    history = [
        ClaimsHistoryEntry(claim_id="C1", date=date(2024, 10, 30), amount=100),
        ClaimsHistoryEntry(claim_id="C2", date=date(2024, 10, 30), amount=200),
        ClaimsHistoryEntry(claim_id="C3", date=date(2024, 10, 30), amount=300),
    ]
    sub = _sub("EMP008", ClaimCategory.CONSULTATION, date(2024, 10, 30), 4800.0,
               docs=[_doc("F017"), _doc("F018", DocumentType.HOSPITAL_BILL)],
               claims_history=history)
    pre = [_ex("F017"), _ex("F018", DocumentType.HOSPITAL_BILL, total=4800.0)]
    result = await process_claim(sub, pre_extracted_documents=pre)
    assert isinstance(result, ClaimDecision)
    reason_lower = result.reason.lower()
    assert "fraud" in reason_lower or "same-day" in reason_lower or "4" in reason_lower


# ---------------------------------------------------------------------------
# TC010 -- APPROVED Rs3240 (network discount then co-pay)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc010_approved_exact_amount():
    sub = _sub("EMP010", ClaimCategory.CONSULTATION, date(2024, 11, 3), 4500.0,
               docs=[_doc("F019"), _doc("F020", DocumentType.HOSPITAL_BILL)],
               hospital_name="Apollo Hospitals")
    pre = [
        _ex("F019", diagnosis="Acute Bronchitis", patient_name="Deepak Shah"),
        _ex("F020", DocumentType.HOSPITAL_BILL, patient_name="Deepak Shah",
            hospital_name="Apollo Hospitals",
            line_items=[("Consultation Fee", 1500.0), ("Medicines", 3000.0)],
            total=4500.0),
    ]
    result = await process_claim(sub, pre_extracted_documents=pre)
    assert isinstance(result, ClaimDecision)
    assert result.decision == "APPROVED"
    assert result.approved_amount == pytest.approx(3240.0, abs=0.01)


@pytest.mark.asyncio
async def test_tc010_financial_breakdown_discount_before_copay():
    sub = _sub("EMP010", ClaimCategory.CONSULTATION, date(2024, 11, 3), 4500.0,
               docs=[_doc("F019"), _doc("F020", DocumentType.HOSPITAL_BILL)],
               hospital_name="Apollo Hospitals")
    pre = [
        _ex("F019", diagnosis="Acute Bronchitis"),
        _ex("F020", DocumentType.HOSPITAL_BILL, hospital_name="Apollo Hospitals",
            total=4500.0),
    ]
    result = await process_claim(sub, pre_extracted_documents=pre)
    assert isinstance(result, ClaimDecision)
    fb = result.financial_breakdown
    assert fb is not None
    assert fb.network_discount_percent == pytest.approx(20.0)
    assert fb.amount_after_discount == pytest.approx(3600.0, abs=0.01)
    assert fb.co_pay_amount == pytest.approx(360.0, abs=0.01)
    assert fb.final_amount == pytest.approx(3240.0, abs=0.01)


# ---------------------------------------------------------------------------
# TC011 -- simulate_component_failure: APPROVED, lower confidence, note
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc011_approved_despite_failure():
    sub = _sub("EMP006", ClaimCategory.ALTERNATIVE_MEDICINE,
               date(2024, 10, 28), 4000.0,
               docs=[_doc("F021"), _doc("F022", DocumentType.HOSPITAL_BILL)],
               simulate_failure=True)
    pre = [
        _ex("F021", diagnosis="Chronic Joint Pain", treatment="Panchakarma Therapy"),
        _ex("F022", DocumentType.HOSPITAL_BILL,
            line_items=[("Panchakarma Therapy (5 sessions)", 3000.0),
                        ("Consultation", 1000.0)],
            total=4000.0),
    ]
    result = await process_claim(sub, pre_extracted_documents=pre)
    assert isinstance(result, ClaimDecision)
    assert result.decision == "APPROVED"


@pytest.mark.asyncio
async def test_tc011_confidence_lower_than_tc004():
    # TC004 baseline confidence
    sub4 = _sub("EMP001", ClaimCategory.CONSULTATION, date(2024, 11, 1), 1500.0,
                docs=[_doc("F007"), _doc("F008", DocumentType.HOSPITAL_BILL)])
    pre4 = [_ex("F007", diagnosis="Viral Fever"),
            _ex("F008", DocumentType.HOSPITAL_BILL, total=1500.0)]
    r4 = await process_claim(sub4, pre_extracted_documents=pre4)
    assert isinstance(r4, ClaimDecision)

    # TC011 with simulate_failure
    sub11 = _sub("EMP006", ClaimCategory.ALTERNATIVE_MEDICINE,
                 date(2024, 10, 28), 4000.0,
                 docs=[_doc("F021"), _doc("F022", DocumentType.HOSPITAL_BILL)],
                 simulate_failure=True)
    pre11 = [
        _ex("F021", diagnosis="Chronic Joint Pain", treatment="Panchakarma Therapy"),
        _ex("F022", DocumentType.HOSPITAL_BILL, total=4000.0),
    ]
    r11 = await process_claim(sub11, pre_extracted_documents=pre11)
    assert isinstance(r11, ClaimDecision)
    assert r11.confidence_score < r4.confidence_score


@pytest.mark.asyncio
async def test_tc011_manual_review_note_in_reason():
    sub = _sub("EMP006", ClaimCategory.ALTERNATIVE_MEDICINE,
               date(2024, 10, 28), 4000.0,
               docs=[_doc("F021"), _doc("F022", DocumentType.HOSPITAL_BILL)],
               simulate_failure=True)
    pre = [
        _ex("F021", treatment="Panchakarma Therapy"),
        _ex("F022", DocumentType.HOSPITAL_BILL, total=4000.0),
    ]
    result = await process_claim(sub, pre_extracted_documents=pre)
    assert isinstance(result, ClaimDecision)
    assert "manual review" in result.reason.lower()


@pytest.mark.asyncio
async def test_tc011_trace_has_degraded_event():
    sub = _sub("EMP006", ClaimCategory.ALTERNATIVE_MEDICINE,
               date(2024, 10, 28), 4000.0,
               docs=[_doc("F021"), _doc("F022", DocumentType.HOSPITAL_BILL)],
               simulate_failure=True)
    pre = [
        _ex("F021", treatment="Panchakarma Therapy"),
        _ex("F022", DocumentType.HOSPITAL_BILL, total=4000.0),
    ]
    result = await process_claim(sub, pre_extracted_documents=pre)
    assert isinstance(result, ClaimDecision)
    degraded = [e for e in result.trace.events if e.status == "degraded"]
    assert len(degraded) >= 1


# ---------------------------------------------------------------------------
# TC012 -- REJECTED EXCLUDED_CONDITION, confidence > 0.90
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc012_excluded_condition_rejected():
    sub = _sub("EMP009", ClaimCategory.CONSULTATION, date(2024, 10, 18), 8000.0,
               docs=[_doc("F023"), _doc("F024", DocumentType.HOSPITAL_BILL)])
    pre = [
        _ex("F023", diagnosis="Morbid Obesity — BMI 37",
            treatment="Bariatric Consultation and Customised Diet Plan"),
        _ex("F024", DocumentType.HOSPITAL_BILL,
            line_items=[("Bariatric Consultation", 3000.0),
                        ("Personalised Diet and Nutrition Program", 5000.0)],
            total=8000.0),
    ]
    result = await process_claim(sub, pre_extracted_documents=pre)
    assert isinstance(result, ClaimDecision)
    assert result.decision == "REJECTED"
    assert "EXCLUDED_CONDITION" in result.rejection_reasons


@pytest.mark.asyncio
async def test_tc012_confidence_above_090():
    sub = _sub("EMP009", ClaimCategory.CONSULTATION, date(2024, 10, 18), 8000.0,
               docs=[_doc("F023"), _doc("F024", DocumentType.HOSPITAL_BILL)])
    pre = [
        _ex("F023", diagnosis="Morbid Obesity — BMI 37",
            treatment="Bariatric Consultation and Customised Diet Plan"),
        _ex("F024", DocumentType.HOSPITAL_BILL, total=8000.0),
    ]
    result = await process_claim(sub, pre_extracted_documents=pre)
    assert isinstance(result, ClaimDecision)
    assert result.confidence_score > 0.90


# ---------------------------------------------------------------------------
# Member not found -> MANUAL_REVIEW (orchestrator catches MemberNotFoundError)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unknown_member_routes_to_manual_review():
    sub = _sub("EMP_UNKNOWN", ClaimCategory.CONSULTATION, date(2024, 11, 1), 1000.0,
               docs=[_doc("F001"), _doc("F002", DocumentType.HOSPITAL_BILL)])
    pre = [_ex("F001", diagnosis="Fever"), _ex("F002", DocumentType.HOSPITAL_BILL)]
    result = await process_claim(sub, pre_extracted_documents=pre)
    assert isinstance(result, ClaimDecision)
    assert result.decision == "MANUAL_REVIEW"
    assert "manual" in result.reason.lower()


# ---------------------------------------------------------------------------
# Concurrency: multi-document extraction runs concurrently, not serially
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extraction_runs_concurrently():
    """Two-doc claim with 0.2s delay per extraction. Concurrent = ~0.2s total,
    serial = ~0.4s. Assert wall time < 0.35s."""
    import asyncio as aio

    async def delayed_extract(document, claim_category, trace, *, force_failure=False):
        await aio.sleep(0.2)
        return ExtractedDocumentData(
            file_id=document.file_id,
            document_type=DocumentType.PRESCRIPTION,
            diagnosis="Viral Fever",
            overall_confidence=0.95,
        )

    sub = _sub("EMP001", ClaimCategory.CONSULTATION, date(2024, 11, 1), 1500.0,
               docs=[_doc("F001"), _doc("F002", DocumentType.HOSPITAL_BILL)])

    with patch("app.orchestrator.pipeline.extractor.run", side_effect=delayed_extract):
        t0 = time.monotonic()
        result = await process_claim(sub)
        elapsed = time.monotonic() - t0

    # Pipeline may fail at policy step because extractions have no detailed data,
    # but what matters is that elapsed time reflects concurrency
    assert elapsed < 0.35, (
        f"Extraction took {elapsed:.2f}s — expected concurrent (~0.2s), "
        "not serial (~0.4s)"
    )


# ---------------------------------------------------------------------------
# API route smoke test (PipelineResponse wrapper)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_json_endpoint_verification_failure():
    """POST /claims/json returns type=verification_failure for TC001."""
    from httpx import AsyncClient, ASGITransport
    from app.api.routes import app

    payload = {
        "member_id": "EMP001",
        "policy_id": "PLUM_GHI_2024",
        "claim_category": "CONSULTATION",
        "treatment_date": "2024-11-01",
        "claimed_amount": 1500,
        "documents": [
            {"file_id": "F001", "actual_type": "PRESCRIPTION"},
            {"file_id": "F002", "actual_type": "PRESCRIPTION"},
        ],
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/claims/json", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "verification_failure"
    assert body["data"]["passed"] is False


@pytest.mark.asyncio
async def test_api_json_endpoint_approved():
    """POST /claims/json with pre_extracted_documents returns type=decision."""
    from httpx import AsyncClient, ASGITransport
    from app.api.routes import app

    pre = [
        {"file_id": "F007", "document_type": "PRESCRIPTION",
         "diagnosis": "Viral Fever", "overall_confidence": 0.95,
         "is_partial": False, "field_confidence": {}, "line_items": [],
         "tests_ordered": []},
        {"file_id": "F008", "document_type": "HOSPITAL_BILL",
         "total": 1500.0, "overall_confidence": 0.95,
         "is_partial": False, "field_confidence": {}, "line_items": [],
         "tests_ordered": []},
    ]
    payload = {
        "member_id": "EMP001",
        "policy_id": "PLUM_GHI_2024",
        "claim_category": "CONSULTATION",
        "treatment_date": "2024-11-01",
        "claimed_amount": 1500,
        "documents": [
            {"file_id": "F007", "actual_type": "PRESCRIPTION"},
            {"file_id": "F008", "actual_type": "HOSPITAL_BILL"},
        ],
        "pre_extracted_documents": pre,
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/claims/json", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "decision"
    assert body["data"]["decision"] == "APPROVED"
