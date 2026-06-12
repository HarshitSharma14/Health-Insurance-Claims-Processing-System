"""Unit tests for the Decision Agent.

Test coverage plan (testing.md):
- All four decision outcomes are reachable:
    APPROVED     — all checks pass, high confidence, amount within limits
    PARTIAL      — sub-limit or line-item exclusion, otherwise clean
    REJECTED     — hard policy failure (any single rejection reason)
    MANUAL_REVIEW— fraud signals OR confidence below threshold
- Confidence-threshold path: confidence_score < threshold → MANUAL_REVIEW
  overrides an otherwise-APPROVED verdict
- Degraded extraction: one document zero-confidence → lower score, may tip
  into MANUAL_REVIEW
- trace.final_decision_explanation is non-empty and specific
"""

from __future__ import annotations

import pytest

from app.agents import decision_maker  # noqa: F401


def test_module_imports_cleanly() -> None:
    """Ensure the module loads and exposes an async run() callable."""
    import inspect

    assert callable(decision_maker.run)
    assert inspect.iscoroutinefunction(decision_maker.run)
