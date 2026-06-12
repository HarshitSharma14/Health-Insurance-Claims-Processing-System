"""Unit tests for the Document Verification Agent.

Test coverage plan (testing.md):
- Correct documents for each claim type → passed=True
- Missing required document → passed=False, WRONG_OR_MISSING_DOCUMENTS,
  message names both uploaded and missing types
- Wrong document type uploaded (e.g. prescription for a diagnostic claim
  that needs a diagnostic_report) → WRONG_OR_MISSING_DOCUMENTS
- Unreadable document → passed=False, UNREADABLE_DOCUMENT, message names
  the specific file
- Corrupted/unopenable file → UNREADABLE_DOCUMENT (not a separate type)
- Patient identity mismatch across documents → PATIENT_MISMATCH, message
  names the differing names found on each doc
"""

from __future__ import annotations

import pytest

from app.agents import document_verifier  # noqa: F401 — import validates module loads


def test_module_imports_cleanly() -> None:
    """Ensure the module loads and exposes a run() callable."""
    import inspect

    assert callable(document_verifier.run)
    assert inspect.iscoroutinefunction(document_verifier.run)
