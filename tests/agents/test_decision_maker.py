"""Unit tests for the Decision Agent -- all 12 test cases.

Strategy: construct PolicyEvaluationResult and ExtractedDocumentData fixtures
directly rather than running the policy evaluator, so these tests are fast,
deterministic, and don't require the policy file.

Test map:
    TC004  APPROVED  Rs1350   (Rs1500 x 10% co-pay, no network discount)
    TC005  REJECTED  WAITING_PERIOD
    TC006  PARTIAL   Rs8000   (root canal covered, whitening excluded)
    TC007  REJECTED  PRE_AUTH_MISSING
    TC008  REJECTED  PER_CLAIM_EXCEEDED
    TC009  MANUAL_REVIEW  fraud flags in reason (verbatim)
    TC010  APPROVED  Rs3240   (Rs4500 -> 20% network discount -> Rs3600 -> 10% co-pay)
    TC011  APPROVED  confidence lower than TC004, manual-review note in reason
    TC012  REJECTED  EXCLUDED_CONDITION, confidence_score > 0.90
    Member not found -> MANUAL_REVIEW
    Low confidence override -> MANUAL_REVIEW
    Trace final_decision_explanation is specific and non-empty
"""
# -*- coding: utf-8 -*-

from datetime import date
from pathlib import Path

import pytest

from app.agents.decision_maker import run
from app.schemas.claim import (
    ClaimCategory,
    ClaimSubmission,
    DocumentType,
    UploadedDocument,
)
from app.schemas.extraction import ExtractedDocumentData, LineItem
from app.schemas.financial import FinancialBreakdown
from app.schemas.policy import LineItemEvaluation, PolicyCheckResult, PolicyEvaluationResult
from app.trace.trace import new_trace

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trace():
    return new_trace("test-claim")


def _sub(
    member_id: str = "EMP001",
    category: ClaimCategory = ClaimCategory.CONSULTATION,
    treatment_date: date = date(2024, 11, 1),
    claimed_amount: float = 1500.0,
    hospital_name: str | None = None,
    simulate_failure: bool = False,
) -> ClaimSubmission:
    return ClaimSubmission(
        member_id=member_id,
        policy_id="PLUM_GHI_2024",
        claim_category=category,
        treatment_date=treatment_date,
        claimed_amount=claimed_amount,
        hospital_name=hospital_name,
        simulate_component_failure=simulate_failure,
        documents=[UploadedDocument(file_id="F001", document_type=DocumentType.PRESCRIPTION)],
    )


def _good_extraction(file_id: str = "F001", confidence: float = 0.95) -> ExtractedDocumentData:
    return ExtractedDocumentData(
        file_id=file_id,
        document_type=DocumentType.PRESCRIPTION,
        diagnosis="Viral Fever",
        overall_confidence=confidence,
    )


def _degraded_extraction(file_id: str = "F001") -> ExtractedDocumentData:
    """Fully degraded extraction -- simulates LLM failure (TC011)."""
    return ExtractedDocumentData(
        file_id=file_id,
        document_type=DocumentType.PRESCRIPTION,
        overall_confidence=0.0,
        is_partial=True,
        extraction_notes="Extraction failed after retry: timeout",
    )


def _check(name: str, passed: bool, detail: str,
           clause: str | None = None) -> PolicyCheckResult:
    return PolicyCheckResult(
        check_name=name, passed=passed, detail=detail,
        relevant_policy_clause=clause,
    )


def _fb(
    base: float,
    after_sub: float | None = None,
    discount_pct: float | None = None,
    a_disc: float | None = None,
    copay_pct: float | None = None,
    copay_amt: float | None = None,
    final: float | None = None,
    sub_limit: float | None = None,
) -> FinancialBreakdown:
    a_sub = after_sub if after_sub is not None else base
    after_discount = a_disc if a_disc is not None else a_sub
    fin = final if final is not None else after_discount - (copay_amt or 0.0)
    return FinancialBreakdown(
        base_amount=base,
        sub_limit_applied=sub_limit,
        amount_after_sub_limit=a_sub,
        network_discount_percent=discount_pct,
        amount_after_discount=after_discount,
        co_pay_percent=copay_pct,
        co_pay_amount=copay_amt,
        final_amount=fin,
    )


def _all_checks_passed() -> list[PolicyCheckResult]:
    """Minimal passing check list (member_lookup through financial_calculation)."""
    checks = [
        _check("member_lookup", True, "Member found, policy active."),
        _check("exclusion", True, "No exclusions matched."),
        _check("waiting_period", True, "Waiting period satisfied."),
        _check("pre_authorization", True, "No pre-auth required."),
        _check("fraud_signals", True, "No fraud signals."),
        _check("sub_limit_and_line_items", True, "Coverage OK."),
        _check("per_claim_limit", True, "Within per-claim limit."),
        _check("financial_calculation", True, "Calculation complete."),
    ]
    return checks


# ---------------------------------------------------------------------------
# TC004 -- APPROVED Rs1,350 (consultation, Rs1,500, 10% co-pay, no discount)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc004_approved_exact_amount() -> None:
    """Clean consultation: Rs1,500 x (1 - 10% co-pay) = Rs1,350."""
    policy_result = PolicyEvaluationResult(
        member_found=True,
        checks=_all_checks_passed(),
        co_pay_percent=10.0,
        is_network_hospital=False,
        financial_breakdown=_fb(base=1500.0, a_disc=1500.0, copay_pct=10.0,
                                copay_amt=150.0, final=1350.0),
    )
    result = await run(_sub(), [_good_extraction()], policy_result, _trace())

    assert result.decision == "APPROVED"
    assert result.approved_amount == pytest.approx(1350.0, abs=0.01)


@pytest.mark.asyncio
async def test_tc004_confidence_above_085() -> None:
    policy_result = PolicyEvaluationResult(
        member_found=True, checks=_all_checks_passed(),
        financial_breakdown=_fb(base=1500.0, a_disc=1500.0, copay_pct=10.0,
                                copay_amt=150.0, final=1350.0),
    )
    result = await run(_sub(), [_good_extraction()], policy_result, _trace())
    assert result.confidence_score > 0.85


@pytest.mark.asyncio
async def test_tc004_trace_final_explanation_specific() -> None:
    policy_result = PolicyEvaluationResult(
        member_found=True, checks=_all_checks_passed(),
        financial_breakdown=_fb(base=1500.0, a_disc=1500.0, copay_pct=10.0,
                                copay_amt=150.0, final=1350.0),
    )
    trace = _trace()
    result = await run(_sub(), [_good_extraction()], policy_result, trace)

    assert trace.final_decision_explanation != ""
    assert "APPROVED" in trace.final_decision_explanation or "approved" in trace.final_decision_explanation.lower()


# ---------------------------------------------------------------------------
# TC005 -- REJECTED WAITING_PERIOD (diabetes, 90-day wait)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc005_rejected_waiting_period() -> None:
    policy_result = PolicyEvaluationResult(
        member_found=True,
        checks=[
            _check("member_lookup", True, "Member found."),
            _check("exclusion", True, "No exclusions."),
            _check(
                "waiting_period", False,
                "Diagnosis/treatment matches condition 'diabetes' (waiting period: 90 days). "
                "Treatment date 2024-10-15 < eligibility date 2024-11-30. "
                "Member will be eligible from 2024-11-30.",
                clause="waiting_periods.specific_conditions.diabetes",
            ),
        ],
        rejection_reasons=["WAITING_PERIOD"],
    )
    result = await run(
        _sub(member_id="EMP005", treatment_date=date(2024, 10, 15), claimed_amount=3000.0),
        [_good_extraction()],
        policy_result,
        _trace(),
    )

    assert result.decision == "REJECTED"
    assert "WAITING_PERIOD" in result.rejection_reasons


@pytest.mark.asyncio
async def test_tc005_rejection_detail_contains_eligibility_date() -> None:
    """The reason text must mention the eligibility date (2024-11-30)."""
    policy_result = PolicyEvaluationResult(
        member_found=True,
        checks=[
            _check("member_lookup", True, "Member found."),
            _check("exclusion", True, "No exclusions."),
            _check(
                "waiting_period", False,
                "Treatment date 2024-10-15 < eligibility date 2024-11-30. "
                "Member will be eligible from 2024-11-30.",
            ),
        ],
        rejection_reasons=["WAITING_PERIOD"],
    )
    result = await run(
        _sub(member_id="EMP005", treatment_date=date(2024, 10, 15)),
        [_good_extraction()],
        policy_result,
        _trace(),
    )
    assert "2024-11-30" in result.reason


# ---------------------------------------------------------------------------
# TC006 -- PARTIAL Rs8,000 (dental: root canal covered, whitening excluded)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc006_partial_approved_amount() -> None:
    """Root canal Rs8,000 covered, teeth whitening Rs4,000 excluded -> PARTIAL Rs8,000."""
    line_evals = [
        LineItemEvaluation(
            description="Root Canal Treatment", amount=8000.0, covered=True,
            reason="Covered under opd_categories.dental.covered_procedures.",
        ),
        LineItemEvaluation(
            description="Teeth Whitening", amount=4000.0, covered=False,
            reason="'Teeth Whitening' excluded under opd_categories.dental.excluded_procedures.",
        ),
    ]
    policy_result = PolicyEvaluationResult(
        member_found=True,
        checks=_all_checks_passed(),
        line_item_evaluations=line_evals,
        financial_breakdown=_fb(base=8000.0, a_disc=8000.0, final=8000.0),
    )
    result = await run(
        _sub(member_id="EMP002", category=ClaimCategory.DENTAL,
             treatment_date=date(2024, 10, 15), claimed_amount=12000.0),
        [_good_extraction()],
        policy_result,
        _trace(),
    )

    assert result.decision == "PARTIAL"
    assert result.approved_amount == pytest.approx(8000.0, abs=0.01)


@pytest.mark.asyncio
async def test_tc006_line_item_evaluations_in_output() -> None:
    """line_item_evaluations must be present and itemize each line."""
    line_evals = [
        LineItemEvaluation(description="Root Canal Treatment", amount=8000.0,
                           covered=True, reason="Covered."),
        LineItemEvaluation(description="Teeth Whitening", amount=4000.0,
                           covered=False, reason="Excluded."),
    ]
    policy_result = PolicyEvaluationResult(
        member_found=True, checks=_all_checks_passed(),
        line_item_evaluations=line_evals,
        financial_breakdown=_fb(base=8000.0, a_disc=8000.0, final=8000.0),
    )
    result = await run(
        _sub(category=ClaimCategory.DENTAL),
        [_good_extraction()],
        policy_result,
        _trace(),
    )

    assert len(result.line_item_evaluations) == 2
    covered = [e for e in result.line_item_evaluations if e.covered]
    excluded = [e for e in result.line_item_evaluations if not e.covered]
    assert len(covered) == 1
    assert len(excluded) == 1


@pytest.mark.asyncio
async def test_tc006_reason_names_excluded_items() -> None:
    line_evals = [
        LineItemEvaluation(description="Root Canal Treatment", amount=8000.0,
                           covered=True, reason="Covered."),
        LineItemEvaluation(description="Teeth Whitening", amount=4000.0,
                           covered=False, reason="Excluded cosmetic procedure."),
    ]
    policy_result = PolicyEvaluationResult(
        member_found=True, checks=_all_checks_passed(),
        line_item_evaluations=line_evals,
        financial_breakdown=_fb(base=8000.0, a_disc=8000.0, final=8000.0),
    )
    result = await run(
        _sub(category=ClaimCategory.DENTAL),
        [_good_extraction()],
        policy_result,
        _trace(),
    )
    assert "Teeth Whitening" in result.reason or "whitening" in result.reason.lower()


# ---------------------------------------------------------------------------
# TC007 -- REJECTED PRE_AUTH_MISSING (MRI Rs15,000 without pre-auth)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc007_rejected_pre_auth_missing() -> None:
    policy_result = PolicyEvaluationResult(
        member_found=True,
        checks=[
            _check("member_lookup", True, "Member found."),
            _check("exclusion", True, "No exclusions."),
            _check("waiting_period", True, "Waiting period OK."),
            _check(
                "pre_authorization", False,
                "'MRI' detected in claim (amount Rs15,000 > pre-auth threshold Rs10,000). "
                "Pre-authorization is required but was not provided. "
                "To resubmit: obtain a pre-authorization reference from your insurer.",
                clause="opd_categories.diagnostic.high_value_tests_requiring_pre_auth",
            ),
        ],
        rejection_reasons=["PRE_AUTH_MISSING"],
    )
    result = await run(
        _sub(member_id="EMP007", category=ClaimCategory.DIAGNOSTIC,
             treatment_date=date(2024, 11, 2), claimed_amount=15000.0),
        [_good_extraction()],
        policy_result,
        _trace(),
    )

    assert result.decision == "REJECTED"
    assert "PRE_AUTH_MISSING" in result.rejection_reasons


@pytest.mark.asyncio
async def test_tc007_reason_explains_resubmission() -> None:
    policy_result = PolicyEvaluationResult(
        member_found=True,
        checks=[
            _check("member_lookup", True, "Member found."),
            _check("exclusion", True, "No exclusions."),
            _check("waiting_period", True, "Waiting period OK."),
            _check(
                "pre_authorization", False,
                "Pre-authorization required for MRI above Rs10,000. "
                "To resubmit: obtain a pre-auth reference first.",
            ),
        ],
        rejection_reasons=["PRE_AUTH_MISSING"],
    )
    result = await run(
        _sub(category=ClaimCategory.DIAGNOSTIC, claimed_amount=15000.0),
        [_good_extraction()],
        policy_result,
        _trace(),
    )
    reason_lower = result.reason.lower()
    assert "pre-auth" in reason_lower or "pre_auth" in reason_lower or "authorization" in reason_lower


# ---------------------------------------------------------------------------
# TC008 -- REJECTED PER_CLAIM_EXCEEDED (Rs7,500 > Rs5,000 limit)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc008_rejected_per_claim_exceeded() -> None:
    policy_result = PolicyEvaluationResult(
        member_found=True,
        checks=[
            _check("member_lookup", True, "Member found."),
            _check("exclusion", True, "No exclusions."),
            _check("waiting_period", True, "Waiting period OK."),
            _check("pre_authorization", True, "No pre-auth needed."),
            _check("fraud_signals", True, "No fraud."),
            _check("sub_limit_and_line_items", True, "Coverage OK."),
            _check(
                "per_claim_limit", False,
                "Approved amount Rs7,500 exceeds the per-claim limit of Rs5,000. "
                "The maximum reimbursable amount per claim is Rs5,000.",
                clause="coverage.per_claim_limit",
            ),
        ],
        rejection_reasons=["PER_CLAIM_EXCEEDED"],
    )
    result = await run(
        _sub(member_id="EMP003", claimed_amount=7500.0),
        [_good_extraction()],
        policy_result,
        _trace(),
    )

    assert result.decision == "REJECTED"
    assert "PER_CLAIM_EXCEEDED" in result.rejection_reasons


@pytest.mark.asyncio
async def test_tc008_reason_states_limit_and_claimed() -> None:
    policy_result = PolicyEvaluationResult(
        member_found=True,
        checks=[
            _check("member_lookup", True, "Member found."),
            _check("exclusion", True, "No exclusions."),
            _check("waiting_period", True, "Waiting period OK."),
            _check("pre_authorization", True, "No pre-auth needed."),
            _check("fraud_signals", True, "No fraud."),
            _check("sub_limit_and_line_items", True, "Coverage OK."),
            _check(
                "per_claim_limit", False,
                "Approved amount Rs7,500 exceeds the per-claim limit of Rs5,000.",
            ),
        ],
        rejection_reasons=["PER_CLAIM_EXCEEDED"],
    )
    result = await run(
        _sub(claimed_amount=7500.0), [_good_extraction()], policy_result, _trace()
    )
    assert "5,000" in result.reason or "5000" in result.reason
    assert "7,500" in result.reason or "7500" in result.reason


# ---------------------------------------------------------------------------
# TC009 -- MANUAL_REVIEW fraud signals (4 same-day claims)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc009_manual_review_fraud_signals() -> None:
    fraud_flag = (
        "4 claims submitted on 2024-10-30 (including this one), "
        "exceeds same-day limit of 2."
    )
    policy_result = PolicyEvaluationResult(
        member_found=True,
        checks=_all_checks_passed(),
        fraud_flags=[fraud_flag],
        financial_breakdown=_fb(base=4800.0, a_disc=4800.0, final=4320.0,
                                copay_pct=10.0, copay_amt=480.0),
    )
    result = await run(
        _sub(member_id="EMP008", treatment_date=date(2024, 10, 30),
             claimed_amount=4800.0),
        [_good_extraction()],
        policy_result,
        _trace(),
    )

    assert result.decision == "MANUAL_REVIEW"
    assert result.approved_amount is None


@pytest.mark.asyncio
async def test_tc009_fraud_flags_verbatim_in_reason() -> None:
    """TC009 requires the specific fraud signal text to appear in the reason."""
    fraud_flag = (
        "4 claims submitted on 2024-10-30 (including this one), "
        "exceeds same-day limit of 2."
    )
    policy_result = PolicyEvaluationResult(
        member_found=True, checks=_all_checks_passed(),
        fraud_flags=[fraud_flag],
        financial_breakdown=_fb(base=4800.0, a_disc=4800.0, final=4800.0),
    )
    result = await run(
        _sub(member_id="EMP008"), [_good_extraction()], policy_result, _trace()
    )
    # The verbatim fraud signal must appear in the reason
    assert fraud_flag in result.reason


# ---------------------------------------------------------------------------
# TC010 -- APPROVED Rs3,240 (Apollo Hospitals: 20% discount then 10% co-pay)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc010_approved_exact_amount_network_hospital() -> None:
    """Rs4,500 -> 20% network discount -> Rs3,600 -> 10% co-pay -> Rs3,240."""
    policy_result = PolicyEvaluationResult(
        member_found=True,
        checks=_all_checks_passed(),
        is_network_hospital=True,
        network_discount_percent=20.0,
        co_pay_percent=10.0,
        financial_breakdown=_fb(
            base=4500.0,
            discount_pct=20.0, a_disc=3600.0,
            copay_pct=10.0, copay_amt=360.0, final=3240.0,
        ),
    )
    result = await run(
        _sub(member_id="EMP010", claimed_amount=4500.0,
             hospital_name="Apollo Hospitals",
             treatment_date=date(2024, 11, 3)),
        [_good_extraction()],
        policy_result,
        _trace(),
    )

    assert result.decision == "APPROVED"
    assert result.approved_amount == pytest.approx(3240.0, abs=0.01)


@pytest.mark.asyncio
async def test_tc010_financial_breakdown_shows_correct_order() -> None:
    """FinancialBreakdown must show discount applied before co-pay."""
    policy_result = PolicyEvaluationResult(
        member_found=True, checks=_all_checks_passed(),
        is_network_hospital=True, network_discount_percent=20.0, co_pay_percent=10.0,
        financial_breakdown=_fb(
            base=4500.0, discount_pct=20.0, a_disc=3600.0,
            copay_pct=10.0, copay_amt=360.0, final=3240.0,
        ),
    )
    result = await run(
        _sub(claimed_amount=4500.0, hospital_name="Apollo Hospitals"),
        [_good_extraction()], policy_result, _trace(),
    )
    fb = result.financial_breakdown
    assert fb is not None
    assert fb.network_discount_percent == 20.0
    assert abs(fb.amount_after_discount - 3600.0) < 0.01
    assert fb.co_pay_percent == 10.0
    assert abs(fb.co_pay_amount - 360.0) < 0.01
    assert abs(fb.final_amount - 3240.0) < 0.01


# ---------------------------------------------------------------------------
# TC011 -- APPROVED, degraded confidence, manual-review note in reason
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc011_approved_despite_component_failure() -> None:
    """simulate_component_failure=True: decision stays APPROVED, not MANUAL_REVIEW."""
    policy_result = PolicyEvaluationResult(
        member_found=True, checks=_all_checks_passed(),
        financial_breakdown=_fb(base=4000.0, a_disc=4000.0, final=4000.0),
    )
    # One degraded extraction (the simulated failure), one good
    extractions = [
        _degraded_extraction("F021"),
        _good_extraction("F022"),
    ]
    result = await run(
        _sub(member_id="EMP006", category=ClaimCategory.ALTERNATIVE_MEDICINE,
             claimed_amount=4000.0, treatment_date=date(2024, 10, 28),
             simulate_failure=True),
        extractions,
        policy_result,
        _trace(),
    )

    assert result.decision == "APPROVED"
    assert result.approved_amount == pytest.approx(4000.0, abs=0.01)


@pytest.mark.asyncio
async def test_tc011_confidence_lower_than_tc004() -> None:
    """TC011 confidence must be measurably lower than TC004's clean run."""
    # TC004 clean run confidence
    pr_clean = PolicyEvaluationResult(
        member_found=True, checks=_all_checks_passed(),
        financial_breakdown=_fb(base=1500.0, a_disc=1500.0, copay_pct=10.0,
                                copay_amt=150.0, final=1350.0),
    )
    clean_result = await run(
        _sub(), [_good_extraction()], pr_clean, _trace()
    )
    tc004_confidence = clean_result.confidence_score

    # TC011 degraded run
    pr_degraded = PolicyEvaluationResult(
        member_found=True, checks=_all_checks_passed(),
        financial_breakdown=_fb(base=4000.0, a_disc=4000.0, final=4000.0),
    )
    degraded_result = await run(
        _sub(simulate_failure=True),
        [_degraded_extraction("F021"), _good_extraction("F022")],
        pr_degraded,
        _trace(),
    )

    assert degraded_result.confidence_score < tc004_confidence


@pytest.mark.asyncio
async def test_tc011_reason_contains_manual_review_note() -> None:
    """reason must include an explicit note recommending manual review."""
    policy_result = PolicyEvaluationResult(
        member_found=True, checks=_all_checks_passed(),
        financial_breakdown=_fb(base=4000.0, a_disc=4000.0, final=4000.0),
    )
    result = await run(
        _sub(simulate_failure=True),
        [_degraded_extraction("F021"), _good_extraction("F022")],
        policy_result,
        _trace(),
    )

    reason_lower = result.reason.lower()
    assert "manual review" in reason_lower


@pytest.mark.asyncio
async def test_tc011_trace_has_degraded_event() -> None:
    """The decision TraceEvent must have status='degraded' when failure flag is set."""
    policy_result = PolicyEvaluationResult(
        member_found=True, checks=_all_checks_passed(),
        financial_breakdown=_fb(base=4000.0, a_disc=4000.0, final=4000.0),
    )
    trace = _trace()
    await run(
        _sub(simulate_failure=True),
        [_degraded_extraction("F021"), _good_extraction("F022")],
        policy_result,
        trace,
    )
    decision_events = [e for e in trace.events if e.stage == "decision"]
    assert any(e.status == "degraded" for e in decision_events)


# ---------------------------------------------------------------------------
# TC012 -- REJECTED EXCLUDED_CONDITION, confidence > 0.90
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tc012_excluded_condition_rejected() -> None:
    policy_result = PolicyEvaluationResult(
        member_found=True,
        checks=[
            _check("member_lookup", True, "Member found."),
            _check(
                "exclusion", False,
                "Diagnosis/treatment matches excluded condition: "
                "'Obesity and weight loss programs'. Not covered.",
                clause="exclusions.conditions['Obesity and weight loss programs']",
            ),
        ],
        rejection_reasons=["EXCLUDED_CONDITION"],
    )
    result = await run(
        _sub(member_id="EMP009", claimed_amount=8000.0,
             treatment_date=date(2024, 10, 18)),
        [_good_extraction(confidence=0.95)],
        policy_result,
        _trace(),
    )

    assert result.decision == "REJECTED"
    assert "EXCLUDED_CONDITION" in result.rejection_reasons


@pytest.mark.asyncio
async def test_tc012_confidence_above_090() -> None:
    """TC012 spec: confidence_score must be > 0.90 for a clear exclusion match."""
    policy_result = PolicyEvaluationResult(
        member_found=True,
        checks=[
            _check("member_lookup", True, "Member found."),
            _check(
                "exclusion", False,
                "Diagnosis/treatment matches excluded condition: "
                "'Obesity and weight loss programs'.",
                clause="exclusions.conditions['Obesity and weight loss programs']",
            ),
        ],
        rejection_reasons=["EXCLUDED_CONDITION"],
    )
    result = await run(
        _sub(member_id="EMP009", claimed_amount=8000.0),
        [_good_extraction(confidence=0.95)],
        policy_result,
        _trace(),
    )
    assert result.confidence_score > 0.90


@pytest.mark.asyncio
async def test_tc012_exclusion_confidence_not_dragged_down_by_degraded_docs() -> None:
    """Even with a degraded document alongside, EXCLUDED_CONDITION confidence stays > 0.90.

    This tests the explicit EXCLUDED_CONDITION branch in _compute_confidence --
    the degraded doc penalty is intentionally NOT applied when the rejection
    reason is a clear exclusion keyword match.
    """
    policy_result = PolicyEvaluationResult(
        member_found=True,
        checks=[
            _check("member_lookup", True, "Member found."),
            _check(
                "exclusion", False,
                "Diagnosis matches 'Obesity and weight loss programs'.",
                clause="exclusions.conditions",
            ),
        ],
        rejection_reasons=["EXCLUDED_CONDITION"],
    )
    # Mix: good extraction with high diagnosis confidence + one degraded doc
    extractions = [
        ExtractedDocumentData(
            file_id="F023",
            document_type=DocumentType.PRESCRIPTION,
            diagnosis="Morbid Obesity",
            overall_confidence=0.95,
            field_confidence={"diagnosis": 0.97},
        ),
        _degraded_extraction("F024"),  # This penalty must NOT apply for EXCLUDED_CONDITION
    ]
    result = await run(
        _sub(member_id="EMP009", claimed_amount=8000.0),
        extractions,
        policy_result,
        _trace(),
    )
    # The EXCLUDED_CONDITION branch skips document-quality penalties
    assert result.confidence_score > 0.90


# ---------------------------------------------------------------------------
# Member not found -> MANUAL_REVIEW
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_member_not_found_routes_to_manual_review() -> None:
    policy_result = PolicyEvaluationResult(
        member_found=False,
        checks=[],
    )
    result = await run(_sub(), [], policy_result, _trace())

    assert result.decision == "MANUAL_REVIEW"
    assert result.approved_amount is None
    assert "manual" in result.reason.lower()


# ---------------------------------------------------------------------------
# Confidence threshold override -> MANUAL_REVIEW
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_low_confidence_overrides_approved_to_manual_review() -> None:
    """If multiple docs are degraded, confidence falls below threshold -> MANUAL_REVIEW."""
    policy_result = PolicyEvaluationResult(
        member_found=True, checks=_all_checks_passed(),
        financial_breakdown=_fb(base=1000.0, a_disc=1000.0, final=900.0,
                                copay_pct=10.0, copay_amt=100.0),
    )
    # Three fully degraded docs: 1.0 - 3x0.30 = 0.10 < threshold 0.60
    extractions = [
        _degraded_extraction("F001"),
        _degraded_extraction("F002"),
        _degraded_extraction("F003"),
    ]
    result = await run(_sub(), extractions, policy_result, _trace())

    assert result.decision == "MANUAL_REVIEW"
    assert result.approved_amount is None
    assert result.confidence_score < 0.60


# ---------------------------------------------------------------------------
# Trace requirements
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_decision_trace_event_always_written() -> None:
    """Every decision path must write at least one TraceEvent to the trace."""
    for decision_type, pr in [
        ("APPROVED", PolicyEvaluationResult(
            member_found=True, checks=_all_checks_passed(),
            financial_breakdown=_fb(base=1000.0, a_disc=1000.0, final=1000.0),
        )),
        ("REJECTED", PolicyEvaluationResult(
            member_found=True,
            checks=[_check("exclusion", False, "Excluded.")],
            rejection_reasons=["EXCLUDED_CONDITION"],
        )),
        ("MANUAL_REVIEW_FRAUD", PolicyEvaluationResult(
            member_found=True, checks=_all_checks_passed(),
            fraud_flags=["Fraud signal."],
            financial_breakdown=_fb(base=1000.0, a_disc=1000.0, final=1000.0),
        )),
        ("MANUAL_REVIEW_MEMBER", PolicyEvaluationResult(
            member_found=False, checks=[],
        )),
    ]:
        trace = _trace()
        await run(_sub(), [_good_extraction()], pr, trace)
        decision_events = [e for e in trace.events if e.stage == "decision"]
        assert len(decision_events) >= 1, f"No trace event for {decision_type}"


@pytest.mark.asyncio
async def test_final_decision_explanation_is_specific() -> None:
    """final_decision_explanation must be non-empty and contain decision outcome."""
    policy_result = PolicyEvaluationResult(
        member_found=True, checks=_all_checks_passed(),
        financial_breakdown=_fb(base=1500.0, a_disc=1500.0, copay_pct=10.0,
                                copay_amt=150.0, final=1350.0),
    )
    trace = _trace()
    await run(_sub(), [_good_extraction()], policy_result, trace)

    assert len(trace.final_decision_explanation) > 20
    # Must not be a generic placeholder
    assert trace.final_decision_explanation.lower() != "decision made."
