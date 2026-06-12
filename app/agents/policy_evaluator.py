"""Policy Evaluation Agent.

Stages 1–8 of the pipeline — pure deterministic rules engine over
policy_terms.json, with one LLM-assisted fuzzy-match step for waiting-period
and exclusion classification.

Stages (in order, decision-logic.md):
    1. Member & Policy Lookup
    2. Waiting Period Check
    3. Exclusion Check
    4. Pre-Authorization Check
    5. Per-Claim Limit Check
    6. Fraud Signal Check
    7. Coverage, Sub-Limits & Line-Item Evaluation
    8. Financial Calculation (network discount first, then co-pay)

Each stage appends its own PolicyCheckResult to the list AND a TraceEvent to
the shared trace. Stages never collapse into a single entry.

The LLM is used ONLY in Stages 2 and 3 for fuzzy text→policy-key matching.
All arithmetic (co-pay, sub-limits, waiting-period math) is plain Python.

Contract (data-contracts.md):
    Input:  ClaimSubmission, list[ExtractedDocumentData], ClaimTrace
    Output: PolicyEvaluationResult
    Errors: MemberNotFoundError (caught by orchestrator → MANUAL_REVIEW).
            All other failures return PolicyEvaluationResult with appropriate
            check results rather than raising.
"""

from app.schemas.claim import ClaimSubmission
from app.schemas.extraction import ExtractedDocumentData
from app.schemas.policy import MemberNotFoundError, PolicyEvaluationResult  # noqa: F401
from app.schemas.trace import ClaimTrace


async def run(
    submission: ClaimSubmission,
    extractions: list[ExtractedDocumentData],
    trace: ClaimTrace,
) -> PolicyEvaluationResult:
    """Evaluate all policy rules for *submission* given *extractions*.

    Args:
        submission:  Original claim submission (member_id, policy_id, dates,
                     claimed_amount, claims_history, hospital_name).
        extractions: List of ExtractedDocumentData, one per uploaded document.
                     May include partial/degraded entries — handle gracefully.
        trace:       Shared ClaimTrace; one TraceEvent is appended per stage/rule.

    Returns:
        PolicyEvaluationResult with all stage results, rejection_reasons,
        fraud_flags, line_item_evaluations, and financial parameters.

    Raises:
        MemberNotFoundError: when member_id is not in the policy roster.
            The orchestrator catches this and routes to MANUAL_REVIEW.
    """
    raise NotImplementedError("PolicyEvaluationAgent.run() not yet implemented.")
