"""Unit tests for the Extraction Agent.

Test coverage plan (testing.md):
- Happy path: full structured LLM response → all fields populated,
  overall_confidence close to 1.0
- Partial response: some fields null → is_partial=True, partial confidence
- Malformed JSON from LLM → triggers degradation (overall_confidence=0.0,
  is_partial=True, extraction_notes describes failure)
- LLM timeout / exception → same degradation as malformed JSON
- force_degraded=True → returns degraded result without calling LLM
"""

from __future__ import annotations

import pytest

from app.agents import extractor  # noqa: F401


def test_module_imports_cleanly() -> None:
    """Ensure the module loads and exposes an async run() callable."""
    import inspect

    assert callable(extractor.run)
    assert inspect.iscoroutinefunction(extractor.run)
