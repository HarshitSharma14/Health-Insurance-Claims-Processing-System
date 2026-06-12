"""Unit tests for the Policy Evaluation Agent.

Test coverage plan (testing.md) — each rule type tested independently:
- member_lookup: known member found, unknown member → MemberNotFoundError
- policy_active: active policy passes, inactive/expired fails
- waiting_period: treatment within initial 30-day window → REJECTED
- waiting_period: specific condition (e.g. diabetes) within its window → REJECTED
  including correct eligible-date in output (TC005)
- exclusion: clearly excluded condition (e.g. morbid obesity) → REJECTED,
  confidence > 0.90 (TC012)
- pre_authorization: high-value diagnostic without pre-auth ref → REJECTED (TC007)
- per_claim_limit: claimed_amount > per_claim_limit → REJECTED (TC008)
- fraud_signals: same_day_claims ≥ limit → MANUAL_REVIEW (TC009)
- sub_limit_and_line_items: dental with mixed covered/excluded items → PARTIAL (TC006)
- financial_calculation: network discount applied BEFORE co-pay (TC010 math)
- network hospital: hospital in network → discount applied; not in network → no discount
"""

from __future__ import annotations

import pytest

from app.agents import policy_evaluator  # noqa: F401


def test_module_imports_cleanly() -> None:
    """Ensure the module loads and exposes an async run() callable."""
    import inspect

    assert callable(policy_evaluator.run)
    assert inspect.iscoroutinefunction(policy_evaluator.run)
