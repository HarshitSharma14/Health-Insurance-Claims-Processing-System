"""Pydantic schemas — single source of truth for all cross-component data shapes.

Keep in sync with .kiro/steering/data-contracts.md and observability.md.
"""

from app.schemas.claim import (
    ClaimCategory,
    ClaimsHistoryEntry,
    ClaimSubmission,
    DocumentQuality,
    DocumentType,
    UploadedDocument,
)
from app.schemas.decision import ClaimDecision
from app.schemas.extraction import ExtractedDocumentData, LineItem
from app.schemas.financial import FinancialBreakdown
from app.schemas.policy import (
    LineItemEvaluation,
    MemberNotFoundError,
    PolicyCheckResult,
    PolicyEvaluationResult,
)
from app.schemas.trace import ClaimTrace, TraceEvent
from app.schemas.verification import DocumentVerificationResult, VerificationFailureType

__all__ = [
    # claim
    "ClaimCategory",
    "ClaimsHistoryEntry",
    "ClaimSubmission",
    "DocumentQuality",
    "DocumentType",
    "UploadedDocument",
    # verification
    "DocumentVerificationResult",
    "VerificationFailureType",
    # extraction
    "ExtractedDocumentData",
    "LineItem",
    # policy
    "LineItemEvaluation",
    "MemberNotFoundError",
    "PolicyCheckResult",
    "PolicyEvaluationResult",
    # financial
    "FinancialBreakdown",
    # decision
    "ClaimDecision",
    # trace
    "ClaimTrace",
    "TraceEvent",
]
