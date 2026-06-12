"""Document Verification Agent output schema.

Matches DocumentVerificationResult in data-contracts.md.

Key contract: a passed=False result ends the pipeline BEFORE any ClaimDecision
is produced. The response type is DocumentVerificationResult, NOT a ClaimDecision
with decision=MANUAL_REVIEW (see decision-logic.md Stage 0).

Corrupted/unopenable files: map onto UNREADABLE_DOCUMENT (not a separate enum
value) — caller supplies a message naming the file and asking for re-upload.
"""

from enum import Enum

from pydantic import BaseModel

from app.schemas.claim import DocumentType


class VerificationFailureType(str, Enum):
    """Three distinct verification failure modes, each with its own message shape.

    WRONG_OR_MISSING_DOCUMENTS — TC001: required doc type absent or only wrong
        types uploaded. Message names what was uploaded and what is required.
    UNREADABLE_DOCUMENT — TC002: required doc is present but illegible
        (quality≈UNREADABLE or ~0 extraction confidence) OR file cannot be opened.
        Message asks for re-upload of the specific document; does NOT reject claim.
    PATIENT_MISMATCH — TC003: documents disagree on patient identity. Message
        surfaces the specific names found on each document.
    """

    WRONG_OR_MISSING_DOCUMENTS = "WRONG_OR_MISSING_DOCUMENTS"
    UNREADABLE_DOCUMENT = "UNREADABLE_DOCUMENT"
    PATIENT_MISMATCH = "PATIENT_MISMATCH"


class DocumentVerificationResult(BaseModel):
    """Output of the Document Verification Agent.

    When passed=True, all three checks (required docs, legibility, identity)
    passed and the pipeline may proceed to extraction.

    When passed=False:
    - failure_type indicates which check failed.
    - message is specific and actionable (never a generic "invalid document" error).
    - The orchestrator returns this directly to the caller without producing a
      ClaimDecision.

    Errors raised: none — always returns a result object, even on classification
    uncertainty (treat unclassifiable as a missing required document).
    """

    passed: bool
    required_documents: list[DocumentType]
    received_documents: list[DocumentType]  # classified types from uploaded files
    missing_documents: list[DocumentType]
    unreadable_documents: list[str] = []  # file_ids that need re-upload
    failure_type: VerificationFailureType | None = None
    message: str | None = None  # only set when passed=False; must be actionable
