"""Decision Agent output schema.

Matches ClaimDecision / FinancialBreakdown in data-contracts.md.
FinancialBreakdown lives in app.schemas.financial to avoid circular imports
with app.schemas.policy (both need it). It is re-exported from here for
backwards compatibility.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.financial import FinancialBreakdown  # noqa: F401 — re-exported
from app.schemas.policy import LineItemEvaluation
from app.schemas.trace import ClaimTrace


class ClaimDecision(BaseModel):
    """Final output of the pipeline for a processable claim.

    Only produced when Stage 0 (Document Verification) passes. When Stage 0
    fails, the pipeline returns DocumentVerificationResult instead.

    decision values:
        APPROVED     — all checks pass, full amount approved after discount/co-pay
        PARTIAL      — some line items excluded or amount capped by sub-limit
        REJECTED     — hard policy failure (waiting period, exclusion, per-claim
                       limit, or pre-auth missing)
        MANUAL_REVIEW— ambiguous data, low confidence, fraud signals, or missing member

    confidence_score is in [0, 1]. Below the MANUAL_REVIEW_CONFIDENCE_THRESHOLD
    (see config.py) the Decision Agent overrides the raw policy verdict to
    MANUAL_REVIEW. The threshold is documented in docs/assumptions.md.
    """

    decision: Literal["APPROVED", "PARTIAL", "REJECTED", "MANUAL_REVIEW"]
    approved_amount: float | None
    reason: str
    rejection_reasons: list[str] = Field(
        default_factory=list,
        description="Rejection reason codes: WAITING_PERIOD, EXCLUDED_CONDITION, "
        "PRE_AUTH_MISSING, PER_CLAIM_EXCEEDED",
    )
    confidence_score: float = Field(ge=0.0, le=1.0)
    financial_breakdown: FinancialBreakdown | None = None
    line_item_evaluations: list[LineItemEvaluation] = []
    trace: ClaimTrace
