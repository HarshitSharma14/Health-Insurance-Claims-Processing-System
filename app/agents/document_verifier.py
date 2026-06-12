"""Document Verification Agent.

Stage 0 of the pipeline — runs BEFORE extraction or policy evaluation.
Verifies that the correct document types were uploaded for the claim category,
that all required documents are legible, and that documents agree on patient
identity.

A failure here returns DocumentVerificationResult(passed=False) with a
specific, actionable message and stops the pipeline. No ClaimDecision is
produced for verification failures.

Contract (data-contracts.md):
    Input:  ClaimSubmission, ClaimTrace
    Output: DocumentVerificationResult
    Errors: None raised to caller — always returns a result object.
"""

from app.schemas.claim import ClaimSubmission
from app.schemas.trace import ClaimTrace
from app.schemas.verification import DocumentVerificationResult


async def run(
    submission: ClaimSubmission,
    trace: ClaimTrace,
) -> DocumentVerificationResult:
    """Verify documents attached to *submission*.

    Checks performed in order (decision-logic.md Stage 0):
    1. Required-documents check — all required types for claim_category present?
    2. Legibility check — any required document unreadable or corrupted?
    3. Cross-document identity check — do all documents agree on patient_name?

    Each check appends a TraceEvent to *trace* (even on success).

    Args:
        submission: The incoming claim submission including uploaded documents.
        trace:      Shared ClaimTrace for this claim; events are appended in-place.

    Returns:
        DocumentVerificationResult with passed=True if all checks pass.
        DocumentVerificationResult with passed=False, failure_type set, and a
        specific message if any check fails.

    Raises:
        Nothing — all exceptions are caught internally and represented as
        verification failures with UNREADABLE_DOCUMENT or WRONG_OR_MISSING_DOCUMENTS.
    """
    raise NotImplementedError("DocumentVerificationAgent.run() not yet implemented.")
