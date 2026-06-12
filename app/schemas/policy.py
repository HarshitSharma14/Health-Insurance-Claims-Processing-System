"""Policy Evaluation Agent output schemas.

Matches PolicyCheckResult, LineItemEvaluation, PolicyEvaluationResult
in data-contracts.md.
"""

from pydantic import BaseModel


class MemberNotFoundError(Exception):
    """Raised internally by the Policy Evaluation Agent when member_id is absent
    from the policy_terms.json roster.

    The orchestrator catches this and routes to MANUAL_REVIEW with the message
    "Member ID not found in policy records — requires manual verification."
    It must never propagate to the API layer as an unhandled exception.
    """

    def __init__(self, member_id: str) -> None:
        self.member_id = member_id
        super().__init__(f"Member '{member_id}' not found in policy roster.")


class PolicyCheckResult(BaseModel):
    """Result of a single policy rule evaluation (one per stage/rule).

    check_name values (from decision-logic.md):
        "member_lookup", "policy_active", "waiting_period", "exclusion",
        "pre_authorization", "per_claim_limit", "fraud_signals",
        "sub_limit_and_line_items", "financial_calculation"
    """

    check_name: str
    passed: bool
    detail: str  # human-readable explanation — must be specific, not generic
    relevant_policy_clause: str | None = None  # e.g. "waiting_periods.specific_conditions.diabetes"


class LineItemEvaluation(BaseModel):
    """Coverage verdict for a single line item on a bill.

    Used for DENTAL/VISION claims (and any category with itemised bills).
    The reason field must reference the specific policy clause, e.g.
    "Cosmetic dental work excluded per opd_categories.dental.excluded_procedures".
    """

    description: str
    amount: float
    covered: bool
    reason: str  # why covered/excluded, referencing policy clause


class PolicyEvaluationResult(BaseModel):
    """Aggregate output of the Policy Evaluation Agent after all stages.

    checks contains one PolicyCheckResult per rule evaluated — this list is
    the backbone of the trace and must never be collapsed into a single entry.

    Errors raised: MemberNotFoundError (caught by orchestrator, not caller).
    All other failures return this model with appropriate check results rather
    than raising exceptions.
    """

    member_found: bool
    checks: list[PolicyCheckResult]
    rejection_reasons: list[str] = []  # e.g. ["WAITING_PERIOD"], ["EXCLUDED_CONDITION"]
    fraud_flags: list[str] = []  # specific signal descriptions, TC009
    line_item_evaluations: list[LineItemEvaluation] = []
    applicable_sub_limit: float | None = None
    co_pay_percent: float | None = None
    network_discount_percent: float | None = None
    is_network_hospital: bool | None = None
