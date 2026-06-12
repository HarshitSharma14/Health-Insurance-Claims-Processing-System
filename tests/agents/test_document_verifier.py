"""Unit tests for the Document Verification Agent.

Coverage (per testing.md):
- TC001: wrong document type uploaded (two PRESCRIPTIONs for a CONSULTATION
  claim that needs PRESCRIPTION + HOSPITAL_BILL) → WRONG_OR_MISSING_DOCUMENTS,
  message names both uploaded type and required type.
- TC002: unreadable pharmacy bill → UNREADABLE_DOCUMENT, message names the
  specific file and asks for re-upload.
- TC003: prescription names 'Rajesh Kumar', hospital bill names 'Arjun Mehta'
  → PATIENT_MISMATCH, message names both patients.
- TC004 (happy path): PRESCRIPTION + HOSPITAL_BILL for CONSULTATION, same
  patient → passed=True.
- Corrupted/unopenable file → UNREADABLE_DOCUMENT (assumption from
  docs/assumptions.md — maps to same enum, not a separate type).
- Partial mismatch: only one document has a patient name (no mismatch to detect).
- UNKNOWN document type counts as a missing required document.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.agents.document_verifier import run
from app.policy.loader import load_policy
from app.schemas.claim import (
    ClaimCategory,
    ClaimSubmission,
    DocumentQuality,
    DocumentType,
    UploadedDocument,
)
from app.schemas.trace import ClaimTrace
from app.schemas.verification import VerificationFailureType
from app.trace.trace import new_trace

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

POLICY_PATH = Path(__file__).parents[2] / "policy_terms.json"


@pytest.fixture(autouse=True)
def load_real_policy() -> None:
    """Load the actual policy_terms.json before each test."""
    load_policy(POLICY_PATH)


def _trace() -> ClaimTrace:
    return new_trace("test-claim-id")


def _submission(
    category: ClaimCategory,
    docs: list[UploadedDocument],
    member_id: str = "EMP001",
    claimed_amount: float = 1500.0,
    treatment_date: date = date(2024, 11, 1),
) -> ClaimSubmission:
    return ClaimSubmission(
        member_id=member_id,
        policy_id="PLUM_GHI_2024",
        claim_category=category,
        treatment_date=treatment_date,
        claimed_amount=claimed_amount,
        documents=docs,
    )


# ---------------------------------------------------------------------------
# TC001 — Wrong document uploaded
# Input:  two PRESCRIPTIONs for a CONSULTATION claim
# Expect: passed=False, WRONG_OR_MISSING_DOCUMENTS,
#         message names 'prescription' (uploaded) and 'hospital bill' (required)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc001_wrong_document_type_stops_pipeline() -> None:
    docs = [
        UploadedDocument(file_id="F001", file_name="dr_sharma_prescription.jpg",
                         document_type=DocumentType.PRESCRIPTION),
        UploadedDocument(file_id="F002", file_name="another_prescription.jpg",
                         document_type=DocumentType.PRESCRIPTION),
    ]
    trace = _trace()
    result = await run(_submission(ClaimCategory.CONSULTATION, docs), trace)

    assert result.passed is False
    assert result.failure_type == VerificationFailureType.WRONG_OR_MISSING_DOCUMENTS
    assert result.message is not None

    msg = result.message.lower()
    # Message must name what was uploaded
    assert "prescription" in msg
    # Message must name what is required (hospital bill)
    assert "hospital bill" in msg
    # Must name missing document
    assert DocumentType.HOSPITAL_BILL in result.missing_documents


@pytest.mark.asyncio
async def test_tc001_message_is_not_generic() -> None:
    """The message must NOT be a generic 'invalid document' or 'wrong document'."""
    docs = [
        UploadedDocument(file_id="F001", document_type=DocumentType.PRESCRIPTION),
        UploadedDocument(file_id="F002", document_type=DocumentType.PRESCRIPTION),
    ]
    result = await run(_submission(ClaimCategory.CONSULTATION, docs), _trace())

    assert result.message is not None
    assert "invalid document" not in result.message.lower()
    # Must be specific about category
    assert "consultation" in result.message.lower()


@pytest.mark.asyncio
async def test_tc001_trace_event_written() -> None:
    """A TraceEvent with status='failed' must be appended even on failure."""
    docs = [
        UploadedDocument(file_id="F001", document_type=DocumentType.PRESCRIPTION),
        UploadedDocument(file_id="F002", document_type=DocumentType.PRESCRIPTION),
    ]
    trace = _trace()
    await run(_submission(ClaimCategory.CONSULTATION, docs), trace)

    assert len(trace.events) >= 1
    failed_events = [e for e in trace.events if e.status == "failed"]
    assert len(failed_events) >= 1
    assert failed_events[0].stage == "document_verification"


# ---------------------------------------------------------------------------
# TC002 — Unreadable document
# Input:  PRESCRIPTION (GOOD) + PHARMACY_BILL (UNREADABLE) for PHARMACY claim
# Expect: passed=False, UNREADABLE_DOCUMENT, message names 'blurry_bill.jpg'
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc002_unreadable_document_stops_pipeline() -> None:
    docs = [
        UploadedDocument(file_id="F003", file_name="prescription.jpg",
                         document_type=DocumentType.PRESCRIPTION,
                         quality=DocumentQuality.GOOD),
        UploadedDocument(file_id="F004", file_name="blurry_bill.jpg",
                         document_type=DocumentType.PHARMACY_BILL,
                         quality=DocumentQuality.UNREADABLE),
    ]
    trace = _trace()
    result = await run(
        _submission(ClaimCategory.PHARMACY, docs, member_id="EMP004",
                    claimed_amount=800.0, treatment_date=date(2024, 10, 25)),
        trace,
    )

    assert result.passed is False
    assert result.failure_type == VerificationFailureType.UNREADABLE_DOCUMENT
    assert "F004" in result.unreadable_documents


@pytest.mark.asyncio
async def test_tc002_message_names_specific_file() -> None:
    """Message must ask for re-upload of the specific file, not generic rejection."""
    docs = [
        UploadedDocument(file_id="F003", file_name="prescription.jpg",
                         document_type=DocumentType.PRESCRIPTION,
                         quality=DocumentQuality.GOOD),
        UploadedDocument(file_id="F004", file_name="blurry_bill.jpg",
                         document_type=DocumentType.PHARMACY_BILL,
                         quality=DocumentQuality.UNREADABLE),
    ]
    result = await run(
        _submission(ClaimCategory.PHARMACY, docs, member_id="EMP004"),
        _trace(),
    )

    assert result.message is not None
    # Must name the specific file
    assert "blurry_bill.jpg" in result.message
    # Must ask for re-upload, NOT reject the claim
    msg_lower = result.message.lower()
    assert "re-upload" in msg_lower or "upload" in msg_lower
    assert "reject" not in msg_lower


@pytest.mark.asyncio
async def test_tc002_does_not_reject_claim_outright() -> None:
    """UNREADABLE_DOCUMENT is a stop-and-ask, not a claim rejection."""
    docs = [
        UploadedDocument(file_id="F003", file_name="prescription.jpg",
                         document_type=DocumentType.PRESCRIPTION,
                         quality=DocumentQuality.GOOD),
        UploadedDocument(file_id="F004", file_name="blurry_bill.jpg",
                         document_type=DocumentType.PHARMACY_BILL,
                         quality=DocumentQuality.UNREADABLE),
    ]
    result = await run(_submission(ClaimCategory.PHARMACY, docs), _trace())
    # The result is DocumentVerificationResult (decision=null), not a ClaimDecision
    # Absence of 'decision' field confirms this is the pre-pipeline stop
    assert result.failure_type == VerificationFailureType.UNREADABLE_DOCUMENT
    assert result.passed is False


# ---------------------------------------------------------------------------
# TC003 — Documents belong to different patients
# Input:  PRESCRIPTION for "Rajesh Kumar", HOSPITAL_BILL for "Arjun Mehta"
# Expect: passed=False, PATIENT_MISMATCH, message names both patients
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc003_patient_mismatch_stops_pipeline() -> None:
    docs = [
        UploadedDocument(file_id="F005", file_name="prescription_rajesh.jpg",
                         document_type=DocumentType.PRESCRIPTION,
                         patient_name="Rajesh Kumar"),
        UploadedDocument(file_id="F006", file_name="bill_arjun.jpg",
                         document_type=DocumentType.HOSPITAL_BILL,
                         patient_name="Arjun Mehta"),
    ]
    trace = _trace()
    result = await run(_submission(ClaimCategory.CONSULTATION, docs), trace)

    assert result.passed is False
    assert result.failure_type == VerificationFailureType.PATIENT_MISMATCH


@pytest.mark.asyncio
async def test_tc003_message_names_both_patients() -> None:
    """Message must surface the specific names found on each document."""
    docs = [
        UploadedDocument(file_id="F005", file_name="prescription_rajesh.jpg",
                         document_type=DocumentType.PRESCRIPTION,
                         patient_name="Rajesh Kumar"),
        UploadedDocument(file_id="F006", file_name="bill_arjun.jpg",
                         document_type=DocumentType.HOSPITAL_BILL,
                         patient_name="Arjun Mehta"),
    ]
    result = await run(_submission(ClaimCategory.CONSULTATION, docs), _trace())

    assert result.message is not None
    assert "Rajesh Kumar" in result.message
    assert "Arjun Mehta" in result.message


@pytest.mark.asyncio
async def test_tc003_does_not_proceed_to_claim_decision() -> None:
    """Pipeline must not proceed past this check — result is not a ClaimDecision."""
    docs = [
        UploadedDocument(file_id="F005", document_type=DocumentType.PRESCRIPTION,
                         patient_name="Rajesh Kumar"),
        UploadedDocument(file_id="F006", document_type=DocumentType.HOSPITAL_BILL,
                         patient_name="Arjun Mehta"),
    ]
    result = await run(_submission(ClaimCategory.CONSULTATION, docs), _trace())
    # DocumentVerificationResult has no 'decision' field — confirm it's the right type
    assert hasattr(result, "failure_type")
    assert result.failure_type == VerificationFailureType.PATIENT_MISMATCH


# ---------------------------------------------------------------------------
# TC004 (happy path) — Clean consultation, correct documents, same patient
# Input:  PRESCRIPTION + HOSPITAL_BILL for CONSULTATION, both "Rajesh Kumar"
# Expect: passed=True, no failure_type, missing_documents=[]
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc004_clean_consultation_passes_verification() -> None:
    docs = [
        UploadedDocument(file_id="F007", document_type=DocumentType.PRESCRIPTION,
                         quality=DocumentQuality.GOOD, patient_name="Rajesh Kumar"),
        UploadedDocument(file_id="F008", document_type=DocumentType.HOSPITAL_BILL,
                         quality=DocumentQuality.GOOD, patient_name="Rajesh Kumar"),
    ]
    trace = _trace()
    result = await run(_submission(ClaimCategory.CONSULTATION, docs), trace)

    assert result.passed is True
    assert result.failure_type is None
    assert result.message is None
    assert result.missing_documents == []
    assert result.unreadable_documents == []


@pytest.mark.asyncio
async def test_tc004_required_and_received_fields_populated() -> None:
    """required_documents and received_documents must be populated on success."""
    docs = [
        UploadedDocument(file_id="F007", document_type=DocumentType.PRESCRIPTION,
                         quality=DocumentQuality.GOOD),
        UploadedDocument(file_id="F008", document_type=DocumentType.HOSPITAL_BILL,
                         quality=DocumentQuality.GOOD),
    ]
    result = await run(_submission(ClaimCategory.CONSULTATION, docs), _trace())

    assert DocumentType.PRESCRIPTION in result.required_documents
    assert DocumentType.HOSPITAL_BILL in result.required_documents
    assert DocumentType.PRESCRIPTION in result.received_documents
    assert DocumentType.HOSPITAL_BILL in result.received_documents


@pytest.mark.asyncio
async def test_tc004_trace_events_written_on_success() -> None:
    """All three check events should be present in the trace on a passing run."""
    docs = [
        UploadedDocument(file_id="F007", document_type=DocumentType.PRESCRIPTION),
        UploadedDocument(file_id="F008", document_type=DocumentType.HOSPITAL_BILL),
    ]
    trace = _trace()
    await run(_submission(ClaimCategory.CONSULTATION, docs), trace)

    # Should have events for: required check, legibility check, identity check, overall
    assert len(trace.events) >= 3
    # All events on a passing run must be 'ok'
    assert all(e.status == "ok" for e in trace.events)
    assert all(e.stage == "document_verification" for e in trace.events)


# ---------------------------------------------------------------------------
# Corrupted / unopenable file → UNREADABLE_DOCUMENT
# (docs/assumptions.md — corrupted files map onto UNREADABLE_DOCUMENT)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_corrupted_file_maps_to_unreadable() -> None:
    """A file that cannot be opened is represented as UNREADABLE_DOCUMENT."""
    docs = [
        UploadedDocument(file_id="F003", file_name="prescription.jpg",
                         document_type=DocumentType.PRESCRIPTION,
                         quality=DocumentQuality.GOOD),
        # Corrupted file — caller sets quality=UNREADABLE before passing to verifier
        UploadedDocument(file_id="F004", file_name="corrupted_bill.pdf",
                         document_type=DocumentType.PHARMACY_BILL,
                         quality=DocumentQuality.UNREADABLE),
    ]
    result = await run(_submission(ClaimCategory.PHARMACY, docs), _trace())

    assert result.passed is False
    assert result.failure_type == VerificationFailureType.UNREADABLE_DOCUMENT
    assert "F004" in result.unreadable_documents
    assert result.message is not None
    assert "corrupted_bill.pdf" in result.message


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_single_named_document_does_not_trigger_mismatch() -> None:
    """Only one document has a patient name — no mismatch to detect."""
    docs = [
        UploadedDocument(file_id="F007", document_type=DocumentType.PRESCRIPTION,
                         patient_name="Rajesh Kumar"),
        UploadedDocument(file_id="F008", document_type=DocumentType.HOSPITAL_BILL,
                         patient_name=None),  # no name on bill
    ]
    result = await run(_submission(ClaimCategory.CONSULTATION, docs), _trace())

    assert result.passed is True


@pytest.mark.asyncio
async def test_same_name_different_casing_does_not_trigger_mismatch() -> None:
    """'Rajesh Kumar' and 'rajesh kumar' are the same person — must not flag mismatch."""
    docs = [
        UploadedDocument(file_id="F007", document_type=DocumentType.PRESCRIPTION,
                         patient_name="Rajesh Kumar"),
        UploadedDocument(file_id="F008", document_type=DocumentType.HOSPITAL_BILL,
                         patient_name="rajesh kumar"),
    ]
    result = await run(_submission(ClaimCategory.CONSULTATION, docs), _trace())

    assert result.passed is True


@pytest.mark.asyncio
async def test_unknown_document_type_counts_as_missing() -> None:
    """UNKNOWN document type cannot satisfy any required type — treated as missing."""
    docs = [
        UploadedDocument(file_id="F001", document_type=DocumentType.PRESCRIPTION),
        UploadedDocument(file_id="F002", document_type=DocumentType.UNKNOWN),
    ]
    result = await run(_submission(ClaimCategory.CONSULTATION, docs), _trace())

    assert result.passed is False
    assert result.failure_type == VerificationFailureType.WRONG_OR_MISSING_DOCUMENTS
    assert DocumentType.HOSPITAL_BILL in result.missing_documents


@pytest.mark.asyncio
async def test_wrong_required_check_runs_before_legibility_check() -> None:
    """Check 1 (wrong/missing docs) must fire before Check 2 (legibility)."""
    # Wrong doc type AND it's unreadable — check 1 should win
    docs = [
        UploadedDocument(file_id="F001", document_type=DocumentType.PRESCRIPTION,
                         quality=DocumentQuality.UNREADABLE),
        # No HOSPITAL_BILL at all for a CONSULTATION claim
    ]
    result = await run(_submission(ClaimCategory.CONSULTATION, docs), _trace())

    assert result.failure_type == VerificationFailureType.WRONG_OR_MISSING_DOCUMENTS


@pytest.mark.asyncio
async def test_legibility_check_runs_before_identity_check() -> None:
    """Check 2 (legibility) must fire before Check 3 (patient identity)."""
    # Both docs have different patient names AND one is unreadable — check 2 wins
    docs = [
        UploadedDocument(file_id="F001", document_type=DocumentType.PRESCRIPTION,
                         quality=DocumentQuality.UNREADABLE, patient_name="Alice"),
        UploadedDocument(file_id="F002", document_type=DocumentType.HOSPITAL_BILL,
                         quality=DocumentQuality.GOOD, patient_name="Bob"),
    ]
    result = await run(_submission(ClaimCategory.CONSULTATION, docs), _trace())

    assert result.failure_type == VerificationFailureType.UNREADABLE_DOCUMENT


@pytest.mark.asyncio
async def test_pharmacy_claim_requires_prescription_and_pharmacy_bill() -> None:
    """PHARMACY category requires PRESCRIPTION + PHARMACY_BILL per policy."""
    docs = [
        UploadedDocument(file_id="F001", document_type=DocumentType.PRESCRIPTION),
        UploadedDocument(file_id="F002", document_type=DocumentType.PHARMACY_BILL),
    ]
    result = await run(
        _submission(ClaimCategory.PHARMACY, docs, member_id="EMP004"),
        _trace(),
    )
    assert result.passed is True


@pytest.mark.asyncio
async def test_dental_claim_requires_only_hospital_bill() -> None:
    """DENTAL category requires only HOSPITAL_BILL per policy."""
    docs = [
        UploadedDocument(file_id="F011", document_type=DocumentType.HOSPITAL_BILL),
    ]
    result = await run(
        _submission(ClaimCategory.DENTAL, docs, member_id="EMP002",
                    claimed_amount=12000.0, treatment_date=date(2024, 10, 15)),
        _trace(),
    )
    assert result.passed is True
