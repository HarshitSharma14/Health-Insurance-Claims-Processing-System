"""FinancialBreakdown schema — split out to avoid circular imports.

decision.py and policy.py both need this type; keeping it here breaks
the cycle.
"""

from pydantic import BaseModel


class FinancialBreakdown(BaseModel):
    """Explicit step-by-step financial calculation result (Stage 8).

    Order matters:
        1. base_amount (covered total from Stage 7, before any discount/co-pay)
        2. sub_limit_applied  — if the Stage 7 amount was capped
        3. amount_after_sub_limit
        4. network_discount_percent applied FIRST  → amount_after_discount
        5. co_pay_percent applied on discounted amount → co_pay_amount deducted
        6. final_amount == approved_amount

    TC010 asserts:  ₹4,500 → 20% discount → ₹3,600 → 10% co-pay → ₹3,240.
    Reversing order (co-pay first) gives ₹3,285 — wrong.
    """

    base_amount: float
    sub_limit_applied: float | None = None
    amount_after_sub_limit: float
    network_discount_percent: float | None = None
    amount_after_discount: float
    co_pay_percent: float | None = None
    co_pay_amount: float | None = None
    final_amount: float  # == ClaimDecision.approved_amount
