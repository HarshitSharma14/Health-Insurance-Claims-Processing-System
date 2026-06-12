"""Document Verification Agent.

Stage 0 of the pipeline — runs BEFORE extraction or policy evaluation.
Three sequential checks; the first failure short-circuits and returns
immediately (no ClaimDecision is produced for any of these failures).

Check 1 — Required documents:
    Look up document_requirements[claim_category].required in policy_terms.json.
    Every required DocumentType must be present in the uploaded documents.
    UNKNOWN-typed documents count as missing for the required-type they're
    supposed to fill. → VerificationFailureType.WRONG_OR_MISSING_DOCUMENTS

Check 2 — Legibility:
    Any uploaded document (required or optional) whose quality is UNREADABLE
    triggers this check. Corrupted/unopenable files are also mapped here
    (see docs/assumptions.md — "Corrupted/unopenable file handling").
    → VerificationFailureType.UNREADABLE_DOCUMENT

Check 3 — Cross-document patient identity:
    Compare patient_name across all documents that have one. Names are
    normalised (stripped, lowercased, collapsed whitespace) before comparison.
    A mismatch stops the pipeline and names the offending documents.
    → VerificationFailureType.PATIENT_MISMATCH

Contract (data-contracts.md):
    Input:  ClaimSubmission, ClaimTrace
    Output: DocumentVerificationResult
    Errors: None raised to caller — all internal exceptions become
            UNREADABLE_DOCUMENT failures.
"""

import re
from typing import Optional

from app.policy.loader import get_policy
from app.schemas.claim import ClaimSubmission, DocumentQuality, DocumentType
from app.schemas.trace import ClaimTrace
from app.schemas.verification import DocumentVerificationResult, VerificationFailureType
from app.trace.trace import append_event

_STAGE = "document_verification"
_COMPONENT = "DocumentVerificationAgent"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalise_name(name: str) -> str:
    """Lowercase, strip, collapse internal whitespace for fuzzy name comparison."""
    return re.sub(r"\s+", " ", name.strip().lower())


def _human_type(doc_type: DocumentType) -> str:
    """Convert enum value to a readable label, e.g. HOSPITAL_BILL → 'hospital bill'."""
    return doc_type.value.replace("_", " ").lower()


def _format_type_list(types: list[DocumentType]) -> str:
    """Format a list of document types as a readable English string."""
    labels = [_human_type(t) for t in types]
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + " and " + labels[-1]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run(
    submission: ClaimSubmission,
    trace: ClaimTrace,
) -> DocumentVerificationResult:
    """Verify documents attached to *submission*.

    Checks performed in order (decision-logic.md Stage 0):
    1. Required-documents check — all required types for claim_category present?
    2. Legibility check — any document UNREADABLE or corrupted?
    3. Cross-document identity check — do all documents agree on patient_name?

    A TraceEvent is appended for every check (pass or fail), per observability.md.

    Args:
        submission: The incoming claim submission including uploaded documents.
        trace:      Shared ClaimTrace; events are appended in-place.

    Returns:
        DocumentVerificationResult(passed=True)  — all checks pass.
        DocumentVerificationResult(passed=False) — first failing check, with
        failure_type and a specific, actionable message.

    Raises:
        Nothing — all internal exceptions are caught and surfaced as
        UNREADABLE_DOCUMENT failures.
    """
    try:
        return await _run_checks(submission, trace)
    except Exception as exc:  # unexpected bug guard — should never happen in practice
        append_event(
            trace,
            stage=_STAGE,
            component=_COMPONENT,
            status="failed",
            summary=f"Unexpected error during document verification: {exc}",
            details={"error": str(exc), "error_type": type(exc).__name__},
        )
        # Surface as unreadable rather than crashing the pipeline
        return DocumentVerificationResult(
            passed=False,
            required_documents=[],
            received_documents=[],
            missing_documents=[],
            failure_type=VerificationFailureType.UNREADABLE_DOCUMENT,
            message=(
                "An unexpected error occurred while verifying your documents. "
                "Please re-upload all documents and try again."
            ),
        )


async def _run_checks(
    submission: ClaimSubmission,
    trace: ClaimTrace,
) -> DocumentVerificationResult:
    """Core verification logic (no exception guard — that's in run())."""
    policy = get_policy()
    docs = submission.documents
    category = submission.claim_category.value  # e.g. "CONSULTATION"

    # Resolve required / optional document types from policy
    doc_reqs: dict = policy.get("document_requirements", {}).get(category, {})
    required_types: list[DocumentType] = [
        DocumentType(t) for t in doc_reqs.get("required", [])
    ]

    # Build lists of what was actually received
    received_types: list[DocumentType] = [d.document_type for d in docs]

    # -----------------------------------------------------------------------
    # Check 1 — Required documents
    # -----------------------------------------------------------------------
    missing_types = [t for t in required_types if t not in received_types]

    if missing_types:
        # Build a precise, actionable message (TC001 style)
        uploaded_labels = _format_type_list(received_types) if received_types else "no documents"
        missing_labels = _format_type_list(missing_types)
        required_labels = _format_type_list(required_types)

        message = (
            f"You uploaded {uploaded_labels}, but a {category.lower()} claim "
            f"requires a {required_labels}. "
            f"Please re-upload with the missing document(s): {missing_labels}."
        )

        append_event(
            trace,
            stage=_STAGE,
            component=_COMPONENT,
            status="failed",
            summary=f"Required document check failed: missing {missing_labels}",
            details={
                "check": "required_documents",
                "required": [t.value for t in required_types],
                "received": [t.value for t in received_types],
                "missing": [t.value for t in missing_types],
                "message": message,
            },
        )
        return DocumentVerificationResult(
            passed=False,
            required_documents=required_types,
            received_documents=received_types,
            missing_documents=missing_types,
            failure_type=VerificationFailureType.WRONG_OR_MISSING_DOCUMENTS,
            message=message,
        )

    # Check 1 passed
    append_event(
        trace,
        stage=_STAGE,
        component=_COMPONENT,
        status="ok",
        summary=(
            f"Required document check passed: "
            f"{_format_type_list(required_types)} present for {category} claim."
        ),
        details={
            "check": "required_documents",
            "required": [t.value for t in required_types],
            "received": [t.value for t in received_types],
        },
    )

    # -----------------------------------------------------------------------
    # Check 2 — Legibility
    # -----------------------------------------------------------------------
    unreadable: list[str] = []
    for doc in docs:
        if doc.quality == DocumentQuality.UNREADABLE:
            unreadable.append(doc.file_id)

    if unreadable:
        # Build per-file message (TC002 style — name the specific document)
        unreadable_names = [
            (d.file_name or d.file_id)
            for d in docs
            if d.file_id in unreadable
        ]
        if len(unreadable_names) == 1:
            file_label = f"'{unreadable_names[0]}'"
            verb = "could not be read"
        else:
            file_label = ", ".join(f"'{n}'" for n in unreadable_names)
            verb = "could not be read"

        message = (
            f"The document {file_label} {verb}. "
            f"Please re-upload a clear, legible photo or scan of "
            f"{'that document' if len(unreadable_names) == 1 else 'those documents'}."
        )

        append_event(
            trace,
            stage=_STAGE,
            component=_COMPONENT,
            status="failed",
            summary=f"Legibility check failed: {len(unreadable)} unreadable document(s)",
            details={
                "check": "legibility",
                "unreadable_file_ids": unreadable,
                "unreadable_file_names": unreadable_names,
                "message": message,
            },
        )
        return DocumentVerificationResult(
            passed=False,
            required_documents=required_types,
            received_documents=received_types,
            missing_documents=[],
            unreadable_documents=unreadable,
            failure_type=VerificationFailureType.UNREADABLE_DOCUMENT,
            message=message,
        )

    # Check 2 passed
    append_event(
        trace,
        stage=_STAGE,
        component=_COMPONENT,
        status="ok",
        summary="Legibility check passed: all documents are readable.",
        details={"check": "legibility", "document_count": len(docs)},
    )

    # -----------------------------------------------------------------------
    # Check 3 — Cross-document patient identity
    # -----------------------------------------------------------------------
    named_docs: list[tuple[str, str]] = []  # (file_name_or_id, normalised_name)
    name_groups: dict[str, list[str]] = {}  # normalised_name → list of file labels

    for doc in docs:
        if doc.patient_name:
            norm = _normalise_name(doc.patient_name)
            label = doc.file_name or doc.file_id
            named_docs.append((label, norm))
            name_groups.setdefault(norm, []).append(label)

    if len(name_groups) > 1:
        # Build message naming the specific names on each document (TC003 style)
        # Reconstruct the original (un-normalised) names for the message
        raw_name_by_file: dict[str, str] = {
            (d.file_name or d.file_id): d.patient_name or ""
            for d in docs
            if d.patient_name
        }
        parts = [f"'{raw_name_by_file[f]}' (on {f})" for f, _ in named_docs]
        message = (
            "The documents appear to belong to different patients: "
            + "; ".join(parts)
            + ". Please confirm these documents all belong to the same person "
            "and re-upload the correct documents."
        )

        append_event(
            trace,
            stage=_STAGE,
            component=_COMPONENT,
            status="failed",
            summary=(
                f"Patient identity check failed: "
                f"{len(name_groups)} different patient names found across documents"
            ),
            details={
                "check": "patient_identity",
                "names_found": [
                    {"file": f, "patient_name": raw_name_by_file[f]}
                    for f, _ in named_docs
                ],
                "message": message,
            },
        )
        return DocumentVerificationResult(
            passed=False,
            required_documents=required_types,
            received_documents=received_types,
            missing_documents=[],
            failure_type=VerificationFailureType.PATIENT_MISMATCH,
            message=message,
        )

    # Check 3 passed
    identity_summary = (
        f"Patient identity check passed: "
        + (
            f"all documents name '{next(iter(name_groups))}'."
            if name_groups
            else "no patient names on documents to compare."
        )
    )
    append_event(
        trace,
        stage=_STAGE,
        component=_COMPONENT,
        status="ok",
        summary=identity_summary,
        details={
            "check": "patient_identity",
            "unique_names": list(name_groups.keys()),
        },
    )

    # -----------------------------------------------------------------------
    # All checks passed
    # -----------------------------------------------------------------------
    append_event(
        trace,
        stage=_STAGE,
        component=_COMPONENT,
        status="ok",
        summary=(
            f"Document verification passed: "
            f"{len(docs)} document(s) accepted for {category} claim."
        ),
        details={
            "check": "overall",
            "required": [t.value for t in required_types],
            "received": [t.value for t in received_types],
        },
    )

    return DocumentVerificationResult(
        passed=True,
        required_documents=required_types,
        received_documents=received_types,
        missing_documents=[],
    )
