"""Extraction Agent output schema.

Matches ExtractedDocumentData in data-contracts.md.
One instance is produced per uploaded document (calls run concurrently).
"""

from datetime import date as date_type
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.claim import DocumentType


class LineItem(BaseModel):
    """A single line item from a bill or invoice."""

    description: str
    amount: float


class ExtractedDocumentData(BaseModel):
    """Structured data extracted from one document via vision LLM.

    Per-field confidence values in field_confidence allow downstream stages
    to weight unreliable fields accordingly.

    On LLM failure (timeout, malformed JSON) the agent returns this model with:
        overall_confidence = 0.0
        is_partial = True
        extraction_notes = "Extraction failed after retry: <error type>"
    This is the typed degraded output — no exception is raised to the caller.
    """

    file_id: str
    document_type: DocumentType
    patient_name: Optional[str] = None
    diagnosis: Optional[str] = None
    treatment: Optional[str] = None
    doctor_name: Optional[str] = None
    doctor_registration: Optional[str] = None
    hospital_name: Optional[str] = None
    date: Optional[date_type] = None
    line_items: list[LineItem] = []
    total: Optional[float] = None
    tests_ordered: list[str] = []
    field_confidence: dict[str, float] = Field(
        default_factory=dict,
        description="Per-field confidence scores in [0, 1]. Missing key = unknown.",
    )
    overall_confidence: float = Field(ge=0.0, le=1.0)
    is_partial: bool = False  # True if document was illegible or extraction degraded
    extraction_notes: Optional[str] = None  # e.g. "stamp obscured diagnosis field"
