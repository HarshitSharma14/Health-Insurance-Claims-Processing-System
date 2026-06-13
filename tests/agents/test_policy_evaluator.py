"""Unit tests for the Policy Evaluation Agent — one test per stage.

Test cases mapped to test_cases.json:
    TC004  — happy-path consultation (all stages pass)
    TC005  — waiting period (diabetes, 90 days)
    TC006  — dental partial approval (line-item exclusion)
    TC007  — pre-authorization missing (MRI > ₹10,000)
    TC008  — per-claim limit exceeded
    TC009  — fraud signals (same-day claims)
    TC010  — network hospital discount + co-pay ordering (exact ₹3,240)
    TC012  — excluded condition (bariatric / obesity)
    Member not found — MemberNotFoundError raised
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.agents.policy_evaluator import run
from app.policy.loader import load_policy
from app.schemas.claim import (
    ClaimCategory,
    ClaimsHistoryEntry,
    ClaimSubmission,
    DocumentType,
    UploadedDocument,
)
from app.schemas.extraction import ExtractedDocumentData, LineItem
from app.schemas.policy import MemberNotFoundError
from app.schemas.trace import ClaimTrace
from app.trace.trace import new_trace

POLICY_PATH = Path(__file__).parents[2] / "policy_terms.json"


@pytest.fixture(autouse=True)
def load_real_policy() -> None:
    load_policy(POLICY_PATH)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trace() -> ClaimTrace:
    return new_trace("test-claim")


def _doc(file_id: str = "F001") -> UploadedDocument:
    return UploadedDocument(file_id=file_id, document_type=DocumentType.PRESCRIPTION)


def _submission(
    member_id: str,
    category: ClaimCategory,
    treatment_date: date,
    claimed_amount: float,
    hospital_name: str | None = None,
    claims_history: list[ClaimsHistoryEntry] | None = None,
) -> ClaimSubmission:
    return ClaimSubmission(
        member_id=member_id,
        policy_id="PLUM_GHI_2024",
        claim_category=category,
        treatment_date=treatment_date,
        submission_date=treatment_date,
        claimed_amount=claimed_amount,
        hospital_name=hospital_name,
        claims_history=claims_history or [],
        documents=[_doc()],
    )


def _extraction(
    file_id: str = "F001",
    doc_type: DocumentType = DocumentType.PRESCRIPTION,
    diagnosis: str | None = None,
    treatment: str | None = None,
    tests_ordered: list[str] | None = None,
    line_items: list[tuple[str, float]] | None = None,
    overall_confidence: float = 0.95,
) -> ExtractedDocumentData:
    return ExtractedDocumentData(
        file_id=file_id,
        document_type=doc_type,
        diagnosis=diagnosis,
        treatment=treatment,
        tests_ordered=tests_ordered or [],
        line_items=[LineItem(description=d, amount=a) for d, a in (line_items or [])],
        overall_confidence=overall_confidence,
    )


# ---------------------------------------------------------------------------
# Stage 1 — Member lookup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_member_not_found_raises_error() -> None:
    """Unknown member_id must raise MemberNotFoundError (orchestrator catches it)."""
    sub = _submission("NONEXISTENT", ClaimCategory.CONSULTATION,
                      date(2024, 11, 1), 1000.0)
    with pytest.raises(MemberNotFoundError):
        await run(sub, [], _trace())


@pytest.mark.asyncio
async def test_member_lookup_passes_for_known_member() -> None:
    sub = _submission("EMP001", ClaimCategory.CONSULTATION,
                      date(2024, 11, 1), 1000.0)
    result = await run(sub, [], _trace())
    assert result.member_found is True
    member_check = next(c for c in result.checks if c.check_name == "member_lookup")
    assert member_check.passed is True


# ---------------------------------------------------------------------------
# Stage 2 — Waiting period  (TC005)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc005_diabetes_within_waiting_period_rejected() -> None:
    """EMP005 joined 2024-09-01; diabetes waiting period = 90 days.
    Treatment 2024-10-15 < 2024-11-30 → REJECTED: WAITING_PERIOD."""
    sub = _submission("EMP005", ClaimCategory.CONSULTATION,
                      date(2024, 10, 15), 3000.0)
    extractions = [_extraction(diagnosis="Type 2 Diabetes Mellitus")]
    result = await run(sub, extractions, _trace())

    assert "WAITING_PERIOD" in result.rejection_reasons
    wp_check = next(c for c in result.checks if c.check_name == "waiting_period")
    assert wp_check.passed is False


@pytest.mark.asyncio
async def test_tc005_waiting_period_detail_states_eligibility_date() -> None:
    """The detail message MUST state the date from which the member is eligible."""
    sub = _submission("EMP005", ClaimCategory.CONSULTATION,
                      date(2024, 10, 15), 3000.0)
    extractions = [_extraction(diagnosis="Type 2 Diabetes Mellitus")]
    result = await run(sub, extractions, _trace())

    wp_check = next(c for c in result.checks if c.check_name == "waiting_period")
    # EMP005 join_date = 2024-09-01 + 90 days = 2024-11-30
    assert "2024-11-30" in wp_check.detail


@pytest.mark.asyncio
async def test_initial_waiting_period_enforced() -> None:
    """Any claim within 30 days of join date must be rejected."""
    # EMP001 joined 2024-04-01; treatment on 2024-04-10 (only 9 days in)
    sub = _submission("EMP001", ClaimCategory.CONSULTATION,
                      date(2024, 4, 10), 500.0)
    result = await run(sub, [], _trace())
    assert "WAITING_PERIOD" in result.rejection_reasons


@pytest.mark.asyncio
async def test_waiting_period_passed_after_threshold() -> None:
    """EMP001 joined 2024-04-01; treatment on 2024-11-01 — well past all windows."""
    sub = _submission("EMP001", ClaimCategory.CONSULTATION,
                      date(2024, 11, 1), 1000.0)
    result = await run(sub, [], _trace())
    assert "WAITING_PERIOD" not in result.rejection_reasons


# ---------------------------------------------------------------------------
# Stage 3 — Exclusion  (TC012)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc012_bariatric_exclusion_rejected() -> None:
    """Bariatric consultation matches global exclusion → EXCLUDED_CONDITION."""
    sub = _submission("EMP009", ClaimCategory.CONSULTATION,
                      date(2024, 10, 18), 8000.0)
    extractions = [
        _extraction(diagnosis="Morbid Obesity — BMI 37",
                    treatment="Bariatric Consultation and Customised Diet Plan"),
    ]
    result = await run(sub, extractions, _trace())

    assert "EXCLUDED_CONDITION" in result.rejection_reasons
    exc_check = next(c for c in result.checks if c.check_name == "exclusion")
    assert exc_check.passed is False


@pytest.mark.asyncio
async def test_tc012_exclusion_policy_clause_referenced() -> None:
    sub = _submission("EMP009", ClaimCategory.CONSULTATION,
                      date(2024, 10, 18), 8000.0)
    extractions = [_extraction(diagnosis="Morbid Obesity",
                               treatment="Bariatric surgery consultation")]
    result = await run(sub, extractions, _trace())

    exc_check = next(c for c in result.checks if c.check_name == "exclusion")
    assert exc_check.relevant_policy_clause is not None
    assert "exclusion" in exc_check.relevant_policy_clause.lower()


@pytest.mark.asyncio
async def test_non_excluded_diagnosis_passes_stage3() -> None:
    sub = _submission("EMP001", ClaimCategory.CONSULTATION,
                      date(2024, 11, 1), 1000.0)
    extractions = [_extraction(diagnosis="Viral Fever")]
    result = await run(sub, extractions, _trace())

    assert "EXCLUDED_CONDITION" not in result.rejection_reasons
    exc_check = next(c for c in result.checks if c.check_name == "exclusion")
    assert exc_check.passed is True


# ---------------------------------------------------------------------------
# Stage 4 — Pre-authorization  (TC007)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc007_mri_without_pre_auth_rejected() -> None:
    """MRI Lumbar Spine ₹15,000 > threshold ₹10,000 without pre-auth → PRE_AUTH_MISSING."""
    sub = _submission("EMP007", ClaimCategory.DIAGNOSTIC,
                      date(2024, 11, 2), 15000.0)
    extractions = [
        _extraction(tests_ordered=["MRI Lumbar Spine"]),
        _extraction(line_items=[("MRI Lumbar Spine", 15000.0)]),
    ]
    result = await run(sub, extractions, _trace())

    assert "PRE_AUTH_MISSING" in result.rejection_reasons
    pa_check = next(c for c in result.checks if c.check_name == "pre_authorization")
    assert pa_check.passed is False


@pytest.mark.asyncio
async def test_tc007_pre_auth_detail_explains_resubmission() -> None:
    """Detail message must tell the member how to resubmit with pre-auth."""
    sub = _submission("EMP007", ClaimCategory.DIAGNOSTIC,
                      date(2024, 11, 2), 15000.0)
    extractions = [_extraction(tests_ordered=["MRI Lumbar Spine"])]
    result = await run(sub, extractions, _trace())

    pa_check = next(c for c in result.checks if c.check_name == "pre_authorization")
    detail_lower = pa_check.detail.lower()
    assert "pre-auth" in detail_lower or "pre_auth" in detail_lower or "preauthori" in detail_lower
    assert "resubmit" in detail_lower or "submit" in detail_lower


@pytest.mark.asyncio
async def test_diagnostic_below_threshold_no_pre_auth_needed() -> None:
    """Diagnostic claim ≤ ₹10,000 does not require pre-auth."""
    sub = _submission("EMP007", ClaimCategory.DIAGNOSTIC,
                      date(2024, 11, 2), 5000.0)
    extractions = [_extraction(line_items=[("X-Ray", 5000.0)])]
    result = await run(sub, extractions, _trace())

    assert "PRE_AUTH_MISSING" not in result.rejection_reasons


# ---------------------------------------------------------------------------
# Stage 5 — Per-claim limit  (TC008)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc008_per_claim_limit_exceeded_rejected() -> None:
    """₹7,500 claimed, all covered (CONSULTATION no line-item exclusions)
    → approved_base=₹7,500 > per_claim_limit ₹5,000 → PER_CLAIM_EXCEEDED."""
    sub = _submission("EMP003", ClaimCategory.CONSULTATION,
                      date(2024, 10, 20), 7500.0)
    result = await run(sub, [], _trace())

    assert "PER_CLAIM_EXCEEDED" in result.rejection_reasons
    pcl_check = next(c for c in result.checks if c.check_name == "per_claim_limit")
    assert pcl_check.passed is False


@pytest.mark.asyncio
async def test_tc008_per_claim_limit_detail_states_both_amounts() -> None:
    """Detail must state both the limit (₹5,000) and the amount."""
    sub = _submission("EMP003", ClaimCategory.CONSULTATION,
                      date(2024, 10, 20), 7500.0)
    result = await run(sub, [], _trace())

    pcl_check = next(c for c in result.checks if c.check_name == "per_claim_limit")
    assert "5,000" in pcl_check.detail or "5000" in pcl_check.detail
    # The detail references the approved/claimed amount
    assert "7,500" in pcl_check.detail or "7500" in pcl_check.detail


@pytest.mark.asyncio
async def test_claim_at_limit_passes() -> None:
    sub = _submission("EMP001", ClaimCategory.CONSULTATION,
                      date(2024, 11, 1), 5000.0)
    result = await run(sub, [], _trace())
    assert "PER_CLAIM_EXCEEDED" not in result.rejection_reasons


# ---------------------------------------------------------------------------
# Stage 6 — Fraud signals  (TC009)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc009_same_day_claims_flag_set() -> None:
    """3 existing same-day claims + this one = 4th → exceeds limit of 2 → fraud flag."""
    history = [
        ClaimsHistoryEntry(claim_id="CLM_0081", date=date(2024, 10, 30), amount=1200),
        ClaimsHistoryEntry(claim_id="CLM_0082", date=date(2024, 10, 30), amount=1800),
        ClaimsHistoryEntry(claim_id="CLM_0083", date=date(2024, 10, 30), amount=2100),
    ]
    sub = _submission("EMP008", ClaimCategory.CONSULTATION,
                      date(2024, 10, 30), 4800.0,
                      claims_history=history)
    result = await run(sub, [], _trace())

    assert len(result.fraud_flags) > 0
    # Should NOT set a rejection_reason — fraud → MANUAL_REVIEW not REJECTED
    assert "WAITING_PERIOD" not in result.rejection_reasons
    assert "EXCLUDED_CONDITION" not in result.rejection_reasons


@pytest.mark.asyncio
async def test_tc009_fraud_flag_describes_specific_signal() -> None:
    """Fraud flag must name the count vs limit (not a generic message)."""
    history = [
        ClaimsHistoryEntry(claim_id="C1", date=date(2024, 10, 30), amount=100),
        ClaimsHistoryEntry(claim_id="C2", date=date(2024, 10, 30), amount=200),
        ClaimsHistoryEntry(claim_id="C3", date=date(2024, 10, 30), amount=300),
    ]
    sub = _submission("EMP008", ClaimCategory.CONSULTATION,
                      date(2024, 10, 30), 4800.0, claims_history=history)
    result = await run(sub, [], _trace())

    combined = " ".join(result.fraud_flags).lower()
    assert "4" in combined or "same-day" in combined or "same day" in combined


@pytest.mark.asyncio
async def test_no_fraud_flags_for_clean_history() -> None:
    sub = _submission("EMP001", ClaimCategory.CONSULTATION,
                      date(2024, 11, 1), 1000.0)
    result = await run(sub, [], _trace())
    assert result.fraud_flags == []


# ---------------------------------------------------------------------------
# Stage 7 — Line-item evaluation  (TC006)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc006_dental_partial_covered_excluded_split() -> None:
    """Root canal covered, teeth whitening excluded → PARTIAL."""
    sub = _submission("EMP002", ClaimCategory.DENTAL,
                      date(2024, 10, 15), 12000.0)
    extractions = [
        _extraction(
            doc_type=DocumentType.HOSPITAL_BILL,
            line_items=[
                ("Root Canal Treatment", 8000.0),
                ("Teeth Whitening", 4000.0),
            ],
        )
    ]
    result = await run(sub, extractions, _trace())

    assert len(result.line_item_evaluations) == 2
    covered = [e for e in result.line_item_evaluations if e.covered]
    excluded = [e for e in result.line_item_evaluations if not e.covered]
    assert len(covered) == 1
    assert len(excluded) == 1
    assert covered[0].amount == 8000.0
    assert excluded[0].amount == 4000.0


@pytest.mark.asyncio
async def test_tc006_line_item_reason_references_policy_clause() -> None:
    sub = _submission("EMP002", ClaimCategory.DENTAL,
                      date(2024, 10, 15), 12000.0)
    extractions = [
        _extraction(
            line_items=[("Root Canal Treatment", 8000.0), ("Teeth Whitening", 4000.0)]
        )
    ]
    result = await run(sub, extractions, _trace())

    for ev in result.line_item_evaluations:
        assert ev.reason != ""
        assert "opd_categories" in ev.reason.lower() or "dental" in ev.reason.lower()


@pytest.mark.asyncio
async def test_tc006_financial_breakdown_reflects_covered_amount() -> None:
    """Approved base should be ₹8,000 (covered only), not ₹12,000."""
    sub = _submission("EMP002", ClaimCategory.DENTAL,
                      date(2024, 10, 15), 12000.0)
    extractions = [
        _extraction(
            line_items=[("Root Canal Treatment", 8000.0), ("Teeth Whitening", 4000.0)]
        )
    ]
    result = await run(sub, extractions, _trace())

    assert result.financial_breakdown is not None
    assert result.financial_breakdown.base_amount == 8000.0
    assert result.financial_breakdown.final_amount == 8000.0  # dental copay=0%


# ---------------------------------------------------------------------------
# Stage 8 — Financial calculation  (TC010)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc010_network_discount_before_copay_exact_amount() -> None:
    """Apollo Hospitals (network): ₹4,500 → 20% discount → ₹3,600 → 10% co-pay → ₹3,240."""
    sub = _submission("EMP010", ClaimCategory.CONSULTATION,
                      date(2024, 11, 3), 4500.0,
                      hospital_name="Apollo Hospitals")
    result = await run(sub, [], _trace())

    assert result.financial_breakdown is not None
    fb = result.financial_breakdown
    assert fb.base_amount == 4500.0
    assert fb.network_discount_percent == 20.0
    assert abs(fb.amount_after_discount - 3600.0) < 0.01
    assert fb.co_pay_percent == 10.0
    assert abs(fb.co_pay_amount - 360.0) < 0.01
    assert abs(fb.final_amount - 3240.0) < 0.01


@pytest.mark.asyncio
async def test_tc010_is_network_hospital_flagged() -> None:
    sub = _submission("EMP010", ClaimCategory.CONSULTATION,
                      date(2024, 11, 3), 4500.0,
                      hospital_name="Apollo Hospitals")
    result = await run(sub, [], _trace())
    assert result.is_network_hospital is True


@pytest.mark.asyncio
async def test_non_network_hospital_no_discount() -> None:
    sub = _submission("EMP001", ClaimCategory.CONSULTATION,
                      date(2024, 11, 1), 1000.0,
                      hospital_name="Random Clinic")
    result = await run(sub, [], _trace())
    assert result.is_network_hospital is False
    assert result.financial_breakdown is not None
    assert result.financial_breakdown.network_discount_percent is None


# ---------------------------------------------------------------------------
# TC004 — Full happy path (all stages pass)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc004_happy_path_all_stages_pass() -> None:
    """Consultation, EMP001, viral fever, ₹1500, no network discount.
    Expected: no rejections, no fraud, copay=10% → final ₹1350."""
    sub = _submission("EMP001", ClaimCategory.CONSULTATION,
                      date(2024, 11, 1), 1500.0)
    extractions = [_extraction(diagnosis="Viral Fever")]
    result = await run(sub, extractions, _trace())

    assert result.rejection_reasons == []
    assert result.fraud_flags == []
    assert result.member_found is True
    assert result.financial_breakdown is not None
    assert abs(result.financial_breakdown.final_amount - 1350.0) < 0.01


@pytest.mark.asyncio
async def test_tc004_every_stage_has_a_trace_event() -> None:
    """Each of the 8 stages must produce at least one TraceEvent."""
    sub = _submission("EMP001", ClaimCategory.CONSULTATION,
                      date(2024, 11, 1), 1500.0)
    trace = _trace()
    await run(sub, [], trace)

    stage_events = [e for e in trace.events if e.stage == "policy_evaluation"]
    # Minimum 8 events: member_lookup, waiting_period, exclusion,
    # pre_authorization, per_claim_limit, fraud_signals,
    # sub_limit_and_line_items, financial_calculation
    assert len(stage_events) >= 8


@pytest.mark.asyncio
async def test_tc004_all_check_names_present() -> None:
    expected_checks = {
        "member_lookup", "waiting_period", "exclusion",
        "pre_authorization", "per_claim_limit", "fraud_signals",
        "sub_limit_and_line_items", "financial_calculation",
    }
    sub = _submission("EMP001", ClaimCategory.CONSULTATION,
                      date(2024, 11, 1), 1500.0)
    result = await run(sub, [], _trace())

    check_names = {c.check_name for c in result.checks}
    assert expected_checks == check_names


# ---------------------------------------------------------------------------
# Financial calculation edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_consultation_copay_10_percent() -> None:
    """Consultation category has copay_percent=10 per policy_terms.json."""
    sub = _submission("EMP001", ClaimCategory.CONSULTATION,
                      date(2024, 11, 1), 2000.0)
    result = await run(sub, [], _trace())
    assert result.co_pay_percent == 10.0
    assert result.financial_breakdown is not None
    assert abs(result.financial_breakdown.final_amount - 1800.0) < 0.01


@pytest.mark.asyncio
async def test_diagnostic_no_copay() -> None:
    """Diagnostic category has copay_percent=0."""
    sub = _submission("EMP007", ClaimCategory.DIAGNOSTIC,
                      date(2024, 11, 2), 3000.0)
    extractions = [_extraction(line_items=[("Blood Test", 3000.0)])]
    result = await run(sub, extractions, _trace())

    assert result.co_pay_percent is None or result.co_pay_percent == 0
    assert result.financial_breakdown is not None
    assert result.financial_breakdown.co_pay_amount is None


@pytest.mark.asyncio
async def test_alternative_medicine_sub_limit_applied_at_8000() -> None:
    """ALTERNATIVE_MEDICINE sub_limit = ₹8,000, copay=0."""
    sub = _submission("EMP006", ClaimCategory.ALTERNATIVE_MEDICINE,
                      date(2024, 10, 28), 4000.0)
    result = await run(sub, [], _trace())

    assert result.financial_breakdown is not None
    # ₹4,000 is below ₹8,000 sub_limit, no cap applied
    assert result.financial_breakdown.final_amount == 4000.0
