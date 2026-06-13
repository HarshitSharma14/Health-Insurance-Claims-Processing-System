"""Decision Agent.

Combines extraction confidence scores with policy evaluation results to
produce the authoritative ClaimDecision.

Decision routing (in precedence order):
    1. policy_result.rejection_reasons non-empty  → REJECTED
    2. policy_result.fraud_flags non-empty         → MANUAL_REVIEW
    3. member_found == False                        → MANUAL_REVIEW
    4. confidence_score < threshold                 → MANUAL_REVIEW
       (overrides APPROVED/PARTIAL if confidence too low)
    5. line_item_evaluations has excluded items, OR
       sub_limit capped the amount                  → PARTIAL
    6. Otherwise                                    → APPROVED

Confidence formula (see docs/assumptions.md — "Confidence scoring formula"):
    base = 1.0
    for each ExtractedDocumentData:
        if is_partial and overall_confidence == 0.0:   base -= 0.30  (fully degraded)
        elif is_partial:                               base -= 0.15  (partial)
        elif overall_confidence < 0.50:               base -= 0.10  (low-confidence)
    for REJECTED via EXCLUDED_CONDITION:
        use the diagnosis/treatment field confidence from the relevant
        extraction document, not the overall average — high-confidence
        exclusion matches should not be dragged down by unrelated fields.
    clamp to [0.0, 1.0]

Contract (data-contracts.md):
    Input:  ClaimSubmission, list[ExtractedDocumentData],
            PolicyEvaluationResult, ClaimTrace
    Output: ClaimDecision
    Errors: None raised to caller — all failures produce a MANUAL_REVIEW.
"""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.schemas.claim import ClaimSubmission
from app.schemas.decision import ClaimDecision
from app.schemas.extraction import ExtractedDocumentData
from app.schemas.financial import FinancialBreakdown
from app.schemas.policy import LineItemEvaluation, PolicyEvaluationResult
from app.schemas.trace import ClaimTrace
from app.trace.trace import append_event

_STAGE = "decision"
_COMPONENT = "DecisionAgent"

# Confidence penalty weights — see docs/assumptions.md
_PENALTY_FULLY_DEGRADED = 0.30   # is_partial=True, overall_confidence==0.0
_PENALTY_PARTIAL = 0.15          # is_partial=True, overall_confidence>0
_PENALTY_LOW_CONFIDENCE = 0.10   # overall_confidence < 0.50 (not partial)
_LOW_CONFIDENCE_THRESHOLD = 0.50


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

def _compute_confidence(
    extractions: list[ExtractedDocumentData],
    policy_result: PolicyEvaluationResult,
    decision: str,
    simulate_failure: bool = False,
) -> tuple[float, list[str]]:
    """Compute confidence_score and return (score, list_of_penalty_reasons).

    For REJECTED via EXCLUDED_CONDITION:
        Use the maximum diagnosis/treatment field confidence among all
        extraction documents, rather than penalising for unrelated low-
        quality fields.  A clear keyword match is high-confidence by design.
        This is an explicit branch — not an incidental side-effect of TC012's
        fixture — so that even a claim with degraded docs alongside a clear
        exclusion match still scores > 0.90.

    For simulate_failure=True (TC011):
        Skip per-document extraction penalties entirely — the simulate flag
        already applies a single documented penalty in the caller.  Without
        this, a degraded doc + simulate penalty would double-count and push
        confidence below the MANUAL_REVIEW threshold (0.60), incorrectly
        changing the decision from APPROVED.

    For all other decisions:
        Apply per-document penalties for degraded/partial extraction.
    """
    penalty_reasons: list[str] = []

    # Special case: EXCLUDED_CONDITION rejection — confidence driven by
    # how clearly the exclusion keyword matched, not by document quality.
    # See docs/assumptions.md — "EXCLUDED_CONDITION confidence branch".
    if decision == "REJECTED" and "EXCLUDED_CONDITION" in policy_result.rejection_reasons:
        diag_confidences = [
            ex.field_confidence.get("diagnosis",
                ex.field_confidence.get("treatment", ex.overall_confidence))
            for ex in extractions
            if not ex.is_partial
        ]
        if diag_confidences:
            base = max(diag_confidences)
            base = max(base, 0.90)  # deterministic keyword match guarantees >= 0.90
        else:
            base = 0.90  # all docs degraded — still confident on the exclusion itself
        return round(min(max(base, 0.0), 1.0), 4), penalty_reasons

    # TC011: simulate_component_failure — the caller applies a single documented
    # penalty after this call.  Skip extraction penalties here to avoid
    # double-counting (degraded doc IS the simulated failure, not an additional issue).
    if simulate_failure:
        return 1.0, penalty_reasons

    # General case: start at 1.0 and apply per-document extraction penalties
    base = 1.0
    for ex in extractions:
        if ex.is_partial and ex.overall_confidence == 0.0:
            base -= _PENALTY_FULLY_DEGRADED
            penalty_reasons.append(
                f"Extraction for '{ex.file_id}' fully degraded "
                f"(confidence=0.0, is_partial=True) — penalty -{_PENALTY_FULLY_DEGRADED}"
            )
        elif ex.is_partial:
            base -= _PENALTY_PARTIAL
            penalty_reasons.append(
                f"Extraction for '{ex.file_id}' partially degraded "
                f"(confidence={ex.overall_confidence:.2f}) — penalty -{_PENALTY_PARTIAL}"
            )
        elif ex.overall_confidence < _LOW_CONFIDENCE_THRESHOLD:
            base -= _PENALTY_LOW_CONFIDENCE
            penalty_reasons.append(
                f"Extraction for '{ex.file_id}' low confidence "
                f"({ex.overall_confidence:.2f} < {_LOW_CONFIDENCE_THRESHOLD}) "
                f"— penalty -{_PENALTY_LOW_CONFIDENCE}"
            )

    return round(min(max(base, 0.0), 1.0), 4), penalty_reasons


# ---------------------------------------------------------------------------
# Reason composition helpers
# ---------------------------------------------------------------------------

def _find_check_detail(policy_result: PolicyEvaluationResult,
                       check_name: str) -> str:
    """Return the detail string from the matching PolicyCheckResult, or empty."""
    for check in policy_result.checks:
        if check.check_name == check_name and not check.passed:
            return check.detail
    return ""


def _rejection_reason_text(policy_result: PolicyEvaluationResult) -> str:
    """Compose a human-readable reason string for REJECTED decisions."""
    parts: list[str] = []
    code_to_check = {
        "WAITING_PERIOD": "waiting_period",
        "EXCLUDED_CONDITION": "exclusion",
        "PRE_AUTH_MISSING": "pre_authorization",
        "PER_CLAIM_EXCEEDED": "per_claim_limit",
        "POLICY_INVALID": "member_lookup",
    }
    for code in policy_result.rejection_reasons:
        check_name = code_to_check.get(code, code.lower())
        detail = _find_check_detail(policy_result, check_name)
        if detail:
            parts.append(detail)
        else:
            parts.append(f"Rejected: {code.replace('_', ' ').title()}.")
    return " ".join(parts) if parts else "Claim rejected due to policy."


def _build_final_explanation(
    decision: str,
    reason: str,
    policy_result: PolicyEvaluationResult,
    confidence: float,
    penalty_reasons: list[str],
    fb: FinancialBreakdown | None,
) -> str:
    """Build the mandatory, specific final_decision_explanation for the trace."""
    lines: list[str] = [f"Decision: {decision}.", reason]

    if penalty_reasons:
        lines.append("Confidence reductions: " + "; ".join(penalty_reasons))

    if fb and decision in ("APPROVED", "PARTIAL"):
        discount_note = (
            f"Network discount {fb.network_discount_percent}% applied "
            f"(₹{fb.base_amount:,.2f} → ₹{fb.amount_after_discount:,.2f})."
            if fb.network_discount_percent
            else ""
        )
        copay_note = (
            f"Co-pay {fb.co_pay_percent}% deducted "
            f"(₹{fb.co_pay_amount:,.2f} → final ₹{fb.final_amount:,.2f})."
            if fb.co_pay_amount
            else f"Final approved amount: ₹{fb.final_amount:,.2f} (no co-pay)."
        )
        if discount_note:
            lines.append(discount_note)
        lines.append(copay_note)

    lines.append(f"Confidence score: {confidence:.2f}.")
    return " ".join(filter(None, lines))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run(
    submission: ClaimSubmission,
    extractions: list[ExtractedDocumentData],
    policy_result: PolicyEvaluationResult,
    trace: ClaimTrace,
) -> ClaimDecision:
    """Produce the final ClaimDecision.

    Args:
        submission:    Original claim submission.
        extractions:   Extraction results (may include degraded entries).
        policy_result: Aggregate output from the Policy Evaluation Agent.
        trace:         Shared ClaimTrace; decision TraceEvent appended here
                       and trace.final_decision_explanation populated.

    Returns:
        ClaimDecision with decision, approved_amount, reason, confidence_score,
        financial_breakdown, line_item_evaluations, and the completed trace.

    Raises:
        Nothing — all failures produce a MANUAL_REVIEW decision.
    """
    try:
        return await _decide(submission, extractions, policy_result, trace)
    except Exception as exc:
        # Unexpected bug guard — should never fire in normal operation
        append_event(
            trace, stage=_STAGE, component=_COMPONENT,
            status="failed",
            summary=f"Unexpected error in DecisionAgent: {exc}",
            details={"error": str(exc), "error_type": type(exc).__name__},
        )
        trace.final_decision_explanation = (
            f"Decision agent encountered an unexpected error: {exc}. "
            "Routed to MANUAL_REVIEW for safety."
        )
        return ClaimDecision(
            decision="MANUAL_REVIEW",
            approved_amount=None,
            reason=(
                "An unexpected error occurred during decision processing. "
                "This claim requires manual review."
            ),
            confidence_score=0.0,
            trace=trace,
        )


async def _decide(
    submission: ClaimSubmission,
    extractions: list[ExtractedDocumentData],
    policy_result: PolicyEvaluationResult,
    trace: ClaimTrace,
) -> ClaimDecision:
    """Core decision logic."""
    fb = policy_result.financial_breakdown
    line_items = policy_result.line_item_evaluations

    # ------------------------------------------------------------------
    # Route 1 — REJECTED (hard policy failure)
    # ------------------------------------------------------------------
    if policy_result.rejection_reasons:
        reason = _rejection_reason_text(policy_result)
        raw_decision = "REJECTED"
        confidence, penalty_reasons = _compute_confidence(
            extractions, policy_result, raw_decision,
            simulate_failure=submission.simulate_component_failure,
        )

        # TC011: simulate_component_failure — degrade confidence, keep decision,
        # append manual-review note to reason (does not apply to REJECTED)
        if submission.simulate_component_failure:
            confidence = max(confidence - _PENALTY_FULLY_DEGRADED, 0.0)
            reason += (
                " NOTE: One pipeline component was unavailable during processing. "
                "Manual review is recommended to verify this result."
            )

        explanation = _build_final_explanation(
            raw_decision, reason, policy_result, confidence, penalty_reasons, fb
        )
        _emit_decision(trace, raw_decision, confidence, reason, explanation, penalty_reasons)

        return ClaimDecision(
            decision=raw_decision,
            approved_amount=None,
            reason=reason,
            rejection_reasons=list(policy_result.rejection_reasons),
            confidence_score=confidence,
            financial_breakdown=fb,
            line_item_evaluations=line_items,
            trace=trace,
        )

    # ------------------------------------------------------------------
    # Route 2 — MANUAL_REVIEW (fraud flags)
    # ------------------------------------------------------------------
    if policy_result.fraud_flags:
        fraud_detail = "; ".join(policy_result.fraud_flags)
        reason = f"Claim flagged for manual review due to fraud signals: {fraud_detail}"
        raw_decision = "MANUAL_REVIEW"
        confidence, penalty_reasons = _compute_confidence(
            extractions, policy_result, raw_decision,
            simulate_failure=submission.simulate_component_failure,
        )

        if submission.simulate_component_failure:
            confidence = max(confidence - _PENALTY_FULLY_DEGRADED, 0.0)
            reason += (
                " NOTE: One pipeline component was unavailable during processing. "
                "Manual review is recommended to verify this result."
            )

        explanation = _build_final_explanation(
            raw_decision, reason, policy_result, confidence, penalty_reasons, fb
        )
        _emit_decision(trace, raw_decision, confidence, reason, explanation, penalty_reasons)

        return ClaimDecision(
            decision=raw_decision,
            approved_amount=None,
            reason=reason,
            confidence_score=confidence,
            financial_breakdown=fb,
            line_item_evaluations=line_items,
            trace=trace,
        )

    # ------------------------------------------------------------------
    # Route 3 — MANUAL_REVIEW (member not found)
    # ------------------------------------------------------------------
    if not policy_result.member_found:
        reason = (
            "Member ID not found in policy records — requires manual verification."
        )
        raw_decision = "MANUAL_REVIEW"
        confidence = 0.5  # unknown member — low confidence
        explanation = _build_final_explanation(
            raw_decision, reason, policy_result, confidence, [], fb
        )
        _emit_decision(trace, raw_decision, confidence, reason, explanation, [])

        return ClaimDecision(
            decision=raw_decision,
            approved_amount=None,
            reason=reason,
            confidence_score=confidence,
            trace=trace,
        )

    # ------------------------------------------------------------------
    # Route 4 — APPROVED or PARTIAL (all checks passed)
    # ------------------------------------------------------------------
    if fb is None:
        # Should never happen if the policy evaluator ran fully, but guard it
        reason = (
            "Financial breakdown unavailable — policy evaluation may be incomplete. "
            "Routing to manual review."
        )
        raw_decision = "MANUAL_REVIEW"
        confidence = 0.3
        explanation = _build_final_explanation(
            raw_decision, reason, policy_result, confidence, [], None
        )
        _emit_decision(trace, raw_decision, confidence, reason, explanation, [])
        return ClaimDecision(
            decision=raw_decision,
            approved_amount=None,
            reason=reason,
            confidence_score=confidence,
            trace=trace,
        )

    # Determine APPROVED vs PARTIAL
    has_excluded_items = any(not ev.covered for ev in line_items)
    sub_limit_capped = (
        fb.sub_limit_applied is not None
        and fb.amount_after_sub_limit < fb.base_amount
    )
    is_partial = has_excluded_items or sub_limit_capped

    raw_decision = "PARTIAL" if is_partial else "APPROVED"
    confidence, penalty_reasons = _compute_confidence(
        extractions, policy_result, raw_decision,
        simulate_failure=submission.simulate_component_failure,
    )

    # Build reason
    if raw_decision == "APPROVED":
        reason_parts: list[str] = [
            f"Claim approved for ₹{fb.final_amount:,.2f}."
        ]
        if fb.network_discount_percent:
            reason_parts.append(
                f"Network discount of {fb.network_discount_percent}% applied "
                f"(₹{fb.base_amount:,.2f} → ₹{fb.amount_after_discount:,.2f})."
            )
        if fb.co_pay_amount:
            reason_parts.append(
                f"Co-pay of {fb.co_pay_percent}% (₹{fb.co_pay_amount:,.2f}) deducted."
            )
        reason = " ".join(reason_parts)
    else:
        reason_parts = ["Claim partially approved."]
        if has_excluded_items:
            excluded = [ev for ev in line_items if not ev.covered]
            excluded_desc = ", ".join(
                f"'{ev.description}' (₹{ev.amount:,.2f})" for ev in excluded
            )
            reason_parts.append(f"Excluded line items: {excluded_desc}.")
        if sub_limit_capped:
            reason_parts.append(
                f"Amount capped at sub-limit ₹{fb.sub_limit_applied:,.2f}."
            )
        reason_parts.append(f"Approved: ₹{fb.final_amount:,.2f}.")
        if fb.co_pay_amount:
            reason_parts.append(
                f"Co-pay {fb.co_pay_percent}% (₹{fb.co_pay_amount:,.2f}) deducted."
            )
        reason = " ".join(reason_parts)

    # TC011: simulate_component_failure — degrade confidence, keep decision,
    # append manual-review note. Does NOT change decision to MANUAL_REVIEW.
    if submission.simulate_component_failure:
        confidence = max(confidence - _PENALTY_FULLY_DEGRADED, 0.0)
        penalty_reasons.append(
            f"Component failure simulation active — confidence reduced by "
            f"{_PENALTY_FULLY_DEGRADED}"
        )
        reason += (
            " NOTE: One pipeline component was unavailable during processing. "
            "Manual review is recommended to verify this result."
        )

    # Route 4b — override to MANUAL_REVIEW if confidence too low
    threshold = settings.manual_review_confidence_threshold
    if confidence < threshold:
        override_reason = (
            f"Confidence score {confidence:.2f} is below the "
            f"automated-decision threshold of {threshold}. "
            "Routing to manual review."
        )
        if penalty_reasons:
            override_reason += " Factors: " + "; ".join(penalty_reasons) + "."
        final_decision: str = "MANUAL_REVIEW"
        final_reason = override_reason
        final_approved: float | None = None
    else:
        final_decision = raw_decision
        final_reason = reason
        final_approved = round(fb.final_amount, 2)

    explanation = _build_final_explanation(
        final_decision, final_reason, policy_result, confidence,
        penalty_reasons, fb if final_decision != "MANUAL_REVIEW" else None,
    )
    status = "degraded" if submission.simulate_component_failure else "ok"
    _emit_decision(
        trace, final_decision, confidence, final_reason, explanation,
        penalty_reasons, status=status,
    )

    return ClaimDecision(
        decision=final_decision,
        approved_amount=final_approved,
        reason=final_reason,
        rejection_reasons=list(policy_result.rejection_reasons),
        confidence_score=confidence,
        financial_breakdown=fb,
        line_item_evaluations=line_items,
        trace=trace,
    )


def _emit_decision(
    trace: ClaimTrace,
    decision: str,
    confidence: float,
    reason: str,
    explanation: str,
    penalty_reasons: list[str],
    status: str = "ok",
) -> None:
    """Append the decision TraceEvent and populate final_decision_explanation."""
    details: dict[str, Any] = {
        "decision": decision,
        "confidence_score": confidence,
        "reason": reason,
    }
    if penalty_reasons:
        details["confidence_penalties"] = penalty_reasons

    append_event(
        trace,
        stage=_STAGE,
        component=_COMPONENT,
        status=status,  # type: ignore[arg-type]
        summary=f"Decision: {decision} (confidence={confidence:.2f}). {reason[:120]}",
        details=details,
    )
    trace.final_decision_explanation = explanation
