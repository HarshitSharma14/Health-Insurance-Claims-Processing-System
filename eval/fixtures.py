"""Shared fixture builders for the eval harness and orchestrator tests.

Single source of truth for converting test_cases.json inputs into
ClaimSubmission + optional pre_extracted_documents.  Both eval/run_eval.py
and tests/orchestrator/ import from here so they can never drift apart.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from app.schemas.claim import (
    ClaimCategory,
    ClaimSubmission,
    ClaimsHistoryEntry,
    DocumentQuality,
    DocumentType,
    UploadedDocument,
)
from app.schemas.extraction import ExtractedDocumentData, LineItem


# ---------------------------------------------------------------------------
# Low-level builders (reused by both test helpers and eval harness)
# ---------------------------------------------------------------------------

def make_uploaded_document(raw: dict[str, Any]) -> UploadedDocument:
    """Build an UploadedDocument from a test_cases.json document descriptor."""
    raw_type = raw.get("actual_type", "UNKNOWN")
    try:
        doc_type = DocumentType(raw_type)
    except ValueError:
        doc_type = DocumentType.UNKNOWN

    raw_quality = raw.get("quality", "GOOD")
    try:
        quality = DocumentQuality(raw_quality)
    except ValueError:
        quality = DocumentQuality.UNKNOWN

    return UploadedDocument(
        file_id=raw.get("file_id", "unknown"),
        file_name=raw.get("file_name"),
        document_type=doc_type,
        quality=quality,
        patient_name=raw.get("patient_name_on_doc"),
    )


def make_extracted_document(raw_doc: dict[str, Any],
                             confidence: float = 0.95) -> ExtractedDocumentData:
    """Build an ExtractedDocumentData from a test_cases.json document entry.

    The document entry may have a 'content' sub-dict with structured fields.
    Applies sensible defaults: overall_confidence=0.95, is_partial=False for
    cases that don't specify them (clean test cases).
    """
    raw_type = raw_doc.get("actual_type", "UNKNOWN")
    try:
        doc_type = DocumentType(raw_type)
    except ValueError:
        doc_type = DocumentType.UNKNOWN

    content: dict[str, Any] = raw_doc.get("content", {})

    # Line items
    raw_items = content.get("line_items", [])
    line_items = [
        LineItem(description=li["description"], amount=float(li["amount"]))
        for li in raw_items
        if "description" in li and "amount" in li
    ]

    # Tests ordered — can live on the content or as a top-level list
    tests_ordered: list[str] = content.get("tests_ordered", [])
    if not tests_ordered and "test_name" in content:
        tests_ordered = [content["test_name"]]

    # Date coercion
    raw_date = content.get("date")
    parsed_date = None
    if raw_date:
        try:
            parsed_date = date.fromisoformat(raw_date)
        except (ValueError, AttributeError):
            parsed_date = None

    return ExtractedDocumentData(
        file_id=raw_doc.get("file_id", "unknown"),
        document_type=doc_type,
        patient_name=content.get("patient_name"),
        diagnosis=content.get("diagnosis"),
        treatment=content.get("treatment"),
        doctor_name=content.get("doctor_name"),
        doctor_registration=content.get("doctor_registration"),
        hospital_name=content.get("hospital_name"),
        date=parsed_date,
        line_items=line_items,
        total=float(content["total"]) if "total" in content else None,
        tests_ordered=tests_ordered,
        field_confidence={},
        overall_confidence=confidence,
        is_partial=False,
        extraction_notes=None,
    )


def make_claims_history(raw_history: list[dict[str, Any]]) -> list[ClaimsHistoryEntry]:
    entries = []
    for h in raw_history:
        try:
            entries.append(ClaimsHistoryEntry(
                claim_id=h["claim_id"],
                date=date.fromisoformat(h["date"]),
                amount=float(h["amount"]),
                provider=h.get("provider"),
            ))
        except (KeyError, ValueError):
            pass
    return entries


# ---------------------------------------------------------------------------
# Top-level builder: test_cases.json case -> (ClaimSubmission, pre_extracted | None)
# ---------------------------------------------------------------------------

def build_inputs(
    tc: dict[str, Any],
) -> tuple[ClaimSubmission, list[ExtractedDocumentData] | None]:
    """Convert one test_cases.json test case into pipeline inputs.

    Returns:
        (submission, pre_extracted_documents)

    For TC001-TC003 (no 'content' on documents, verification-layer cases):
        pre_extracted_documents = None  ->  orchestrator will try to extract
        (but verification will fail first, so extractor is never actually called)

    For TC004-TC012 (documents have 'content'):
        pre_extracted_documents = list[ExtractedDocumentData]  ->  skips extractor
    """
    inp = tc["input"]

    # Uploaded documents
    raw_docs: list[dict[str, Any]] = inp.get("documents", [])
    uploaded_docs = [make_uploaded_document(d) for d in raw_docs]

    # Claims history (TC009)
    history = make_claims_history(inp.get("claims_history", []))

    # Submission
    treatment_date = date.fromisoformat(inp["treatment_date"])
    # Default the submission date to the treatment date (same-day filing) unless
    # the case explicitly provides one (e.g. to test the filing-deadline rule).
    submission_date = (
        date.fromisoformat(inp["submission_date"])
        if inp.get("submission_date")
        else treatment_date
    )
    submission = ClaimSubmission(
        member_id=inp["member_id"],
        policy_id=inp["policy_id"],
        claim_category=ClaimCategory(inp["claim_category"]),
        treatment_date=treatment_date,
        submission_date=submission_date,
        claimed_amount=float(inp["claimed_amount"]),
        hospital_name=inp.get("hospital_name"),
        ytd_claims_amount=float(inp["ytd_claims_amount"]) if "ytd_claims_amount" in inp else None,
        claims_history=history,
        simulate_component_failure=inp.get("simulate_component_failure", False),
        documents=uploaded_docs,
    )

    # Pre-extracted documents: only when at least one doc has a 'content' field
    has_content = any("content" in d for d in raw_docs)
    if not has_content:
        # TC001-TC003: let document_verifier catch the problems first
        return submission, None

    pre_extracted = [make_extracted_document(d) for d in raw_docs]
    return submission, pre_extracted


# ---------------------------------------------------------------------------
# Convenience: load all test cases from the repo root test_cases.json
# ---------------------------------------------------------------------------

def load_test_cases(
    path: Path | None = None,
) -> list[dict[str, Any]]:
    if path is None:
        path = Path(__file__).parents[1] / "test_cases.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["test_cases"]
