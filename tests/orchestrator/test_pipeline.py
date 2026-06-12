"""Unit/integration tests for the claim processing orchestrator.

Test coverage plan:
- Stage 0 hard-stop: verification failure returns DocumentVerificationResult,
  no ClaimDecision produced
- Full pipeline happy path (all stages pass) → ClaimDecision with decision
  matching expected value
- simulate_component_failure=True → pipeline completes, trace contains a
  'degraded' event, confidence_score lower than non-degraded equivalent
- MemberNotFoundError from policy agent → MANUAL_REVIEW decision
- Each stage short-circuit: first hard failure wins (e.g. waiting period
  stops before exclusion check)
"""

from __future__ import annotations

import pytest

from app.orchestrator import pipeline  # noqa: F401


def test_module_imports_cleanly() -> None:
    """Ensure the module loads and exposes an async process_claim() callable."""
    import inspect

    assert callable(pipeline.process_claim)
    assert inspect.iscoroutinefunction(pipeline.process_claim)
