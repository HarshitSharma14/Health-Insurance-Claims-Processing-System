"""Decision Agent.

Stage 4 (final) of the pipeline — combines extraction confidence scores with
policy evaluation results to produce the authoritative ClaimDecision.

Decision logic (decision-logic.md):
    REJECTED     — any hard policy failure (WAITING_PERIOD, EXCLUDED_CONDITION,
                   PRE_AUTH_MISSING, PER_CLAIM_EXCEEDED).
    MANUAL_REVIEW— fraud signals flagged, member not found, OR confidence_score
                   falls below Settings.manual_review_confidence_threshold.
    PARTIAL      — no hard failures, but amount capped by sub-limit or some
                   line items excluded.
    APPROVED     — all checks pass, full amount approved after discount/co-pay.

Confidence score calculation:
    Starts at 1.0. Penalties applied per degraded/partial extraction and per
    ambiguous policy check. Weights documented in config.py and
    docs/assumptions.md.

    If confidence_score < manual_review_confidence_threshold, the decision
    is overridden to MANUAL_REVIEW regardless of the raw policy verdict.

Contract (data-contracts.md):
    Input:  ClaimSubmission, list[ExtractedDocumentData],
            PolicyEvaluationResult, ClaimTrace
    Output: ClaimDecision
    Errors: None raised to caller.
"""

from app.schemas.claim import ClaimSubmission
from app.schemas.decision import ClaimDecision
from app.schemas.extraction import ExtractedDocumentData
from app.schemas.policy import PolicyEvaluationResult
from app.schemas.trace import ClaimTrace


async def run(
    submission: ClaimSubmission,
    extractions: list[ExtractedDocumentData],
    policy_result: PolicyEvaluationResult,
    trace: ClaimTrace,
) -> ClaimDecision:
    """Produce the final ClaimDecision.

    Args:
        submission:    Original claim submission.
        extractions:   All extraction results (including any degraded ones).
        policy_result: Aggregate output from the Policy Evaluation Agent.
        trace:         Shared ClaimTrace; the decision TraceEvent is appended
                       here, and trace.final_decision_explanation is populated.

    Returns:
        ClaimDecision with decision, approved_amount, reason, confidence_score,
        financial_breakdown, line_item_evaluations, and the completed trace.

    Raises:
        Nothing — all failures produce a MANUAL_REVIEW decision.
    """
    raise NotImplementedError("DecisionAgent.run() not yet implemented.")
