"""Decision Agent output schema.

Matches ClaimDecision / FinancialBreakdown in data-contracts.md.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.policy import LineItemEvaluation
from app.schemas.trace import ClaimTrace


class FinancialBreakdown(BaseModel):
    """Explicit breakdown of the financial calculation (Stage 8).

    Order matters — network discount is applied FIRST, then co-pay on the
    discounted amount. Incorrect ordering (co-pay before discount) produces
    a different wrong number (TC010 directly tests this).

    base_amount           — claimed or covered-line-items total, pre-cap
    sub_limit_applied     — the sub_limit value from policy if capping occurred
    amount_after_sub_limit— base_amount capped at sub_limit (or == base_amount)
    network_discount_percent — from policy_terms.json if is_network_hospital
    amount_after_discount — amount_after_sub_limit × (1 - discount/100)
    co_pay_percent        — from opd_categories[category].copay_percent
    co_pay_amount         — amount_after_discount × (co_pay_percent / 100)
    final_amount          — amount_after_discount - co_pay_amount == approved_amount
    """

    base_amount: float
    sub_limit_applied: float | None = None
    amount_after_sub_limit: float
    network_discount_percent: float | None = None
    amount_after_discount: float
    co_pay_percent: float | None = None
    co_pay_amount: float | None = None
    final_amount: float  # == ClaimDecision.approved_amount


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
