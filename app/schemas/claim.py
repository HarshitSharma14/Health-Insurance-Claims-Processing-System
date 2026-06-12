"""Input schemas for claim submission.

Matches ClaimSubmission shape in data-contracts.md.
Field names mirror test_cases.json so the eval harness can feed cases directly.
"""

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class ClaimCategory(str, Enum):
    """Supported claim categories, sourced from policy_terms.json."""

    CONSULTATION = "CONSULTATION"
    DIAGNOSTIC = "DIAGNOSTIC"
    PHARMACY = "PHARMACY"
    DENTAL = "DENTAL"
    VISION = "VISION"
    ALTERNATIVE_MEDICINE = "ALTERNATIVE_MEDICINE"


class DocumentType(str, Enum):
    """Document types that may be uploaded with a claim.

    UNKNOWN is used when the extraction/classification model cannot
    determine the document type — treat as a missing required document.
    """

    PRESCRIPTION = "PRESCRIPTION"
    HOSPITAL_BILL = "HOSPITAL_BILL"
    LAB_REPORT = "LAB_REPORT"
    PHARMACY_BILL = "PHARMACY_BILL"
    DENTAL_REPORT = "DENTAL_REPORT"
    DIAGNOSTIC_REPORT = "DIAGNOSTIC_REPORT"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    UNKNOWN = "UNKNOWN"


class UploadedDocument(BaseModel):
    """A single document attached to a claim submission."""

    file_id: str
    file_name: str | None = None
    content_type: str | None = None  # e.g. image/jpeg, application/pdf
    file_bytes: bytes | None = None  # raw bytes; use None when storing a reference


class ClaimsHistoryEntry(BaseModel):
    """A single entry from the member's prior claims history.

    Used by the Policy Evaluation Agent for fraud-signal detection (Stage 6).
    """

    claim_id: str
    date: date
    amount: float
    provider: str | None = None


class ClaimSubmission(BaseModel):
    """Top-level input to the pipeline. Sourced from the claim submission form.

    simulate_component_failure is a deliberate test seam (see error-handling.md
    and decision-logic.md Stage 9). When True the orchestrator forces one
    designated component down its degraded path to verify graceful degradation.
    Document the chosen component in docs/assumptions.md.
    """

    member_id: str
    policy_id: str
    claim_category: ClaimCategory
    treatment_date: date
    claimed_amount: float = Field(gt=0)
    hospital_name: str | None = None  # used for network-hospital check (Stage 8)
    ytd_claims_amount: float | None = None
    claims_history: list[ClaimsHistoryEntry] = []
    documents: list[UploadedDocument] = Field(min_length=1)
    simulate_component_failure: bool = False  # test hook — never set True in prod
