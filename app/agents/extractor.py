"""Extraction Agent.

One async call per uploaded document, designed to be run concurrently via
asyncio.gather for multi-document claims.

Sends the document (image or PDF page) as base64 to a vision-capable Claude
model using forced tool-call / structured output.  The model MUST call the
extract_document_data tool — free-text responses are never parsed.

On any failure (timeout, API error, tool-schema validation failure) the agent:
  1. Retries once with a brief backoff (configurable).
  2. On second failure returns a typed degraded ExtractedDocumentData with
     overall_confidence=0.0, is_partial=True, and extraction_notes explaining
     the failure.  Never raises to the caller.

force_failure=True (TC011 test seam):
  Skips the LLM call entirely and returns the degraded result immediately.
  The orchestrator sets this flag when simulate_component_failure is active.

Contract (data-contracts.md):
    Input:  UploadedDocument, ClaimCategory (prompt context), ClaimTrace
    Output: ExtractedDocumentData
    Errors: None raised to caller.
"""

import asyncio
import base64
import logging
from datetime import date as date_type
from typing import Any

import anthropic
from pydantic import ValidationError

from app.config import settings
from app.schemas.claim import ClaimCategory, UploadedDocument
from app.schemas.extraction import ExtractedDocumentData, LineItem
from app.schemas.claim import DocumentType
from app.schemas.trace import ClaimTrace
from app.trace.trace import append_event

logger = logging.getLogger(__name__)

_STAGE = "extraction"
_COMPONENT = "ExtractionAgent"

# ---------------------------------------------------------------------------
# Tool schema — matches ExtractedDocumentData exactly.
# Every LLM call that feeds downstream logic uses forced tool-call output
# (tech-stack.md); never parse free-text.
# ---------------------------------------------------------------------------

EXTRACT_TOOL: dict[str, Any] = {
    "name": "extract_document_data",
    "description": (
        "Extract all structured fields from the medical document image. "
        "Return null for any field that is not present or cannot be read. "
        "Set is_partial=true and populate extraction_notes if any portion of the "
        "document is illegible, cut off, obscured, or ambiguous."
    ),
    "input_schema": {
        "type": "object",
        "required": ["document_type", "overall_confidence"],
        "properties": {
            "document_type": {
                "type": "string",
                "enum": [
                    "PRESCRIPTION",
                    "HOSPITAL_BILL",
                    "LAB_REPORT",
                    "PHARMACY_BILL",
                    "DENTAL_REPORT",
                    "DIAGNOSTIC_REPORT",
                    "DISCHARGE_SUMMARY",
                    "UNKNOWN",
                ],
                "description": "Classify the document type based on its content and layout.",
            },
            "patient_name": {
                "type": ["string", "null"],
                "description": "Full patient name as written on the document.",
            },
            "diagnosis": {
                "type": ["string", "null"],
                "description": (
                    "Primary diagnosis. Expand common shorthand: "
                    "HTN->Hypertension, T2DM->Type 2 Diabetes Mellitus, "
                    "URI->Upper Respiratory Infection, GERD->Gastroesophageal Reflux Disease."
                ),
            },
            "treatment": {
                "type": ["string", "null"],
                "description": "Treatment or procedure described (e.g. Panchakarma Therapy).",
            },
            "doctor_name": {
                "type": ["string", "null"],
                "description": "Doctor/physician name including title.",
            },
            "doctor_registration": {
                "type": ["string", "null"],
                "description": (
                    "Medical registration number. Indian formats: KA/XXXXX/YYYY, "
                    "MH/XXXXX/YYYY, DL/XXXXX/YYYY, TN/XXXXX/YYYY, GJ/XXXXX/YYYY, "
                    "AP/XXXXX/YYYY, WB/XXXXX/YYYY, KL/XXXXX/YYYY, "
                    "AYUR/[STATE]/XXXXX/YYYY for Ayurveda practitioners."
                ),
            },
            "hospital_name": {
                "type": ["string", "null"],
                "description": "Hospital, clinic, or pharmacy name.",
            },
            "date": {
                "type": ["string", "null"],
                "description": "Primary document date in ISO 8601 format (YYYY-MM-DD).",
            },
            "line_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["description", "amount"],
                    "properties": {
                        "description": {"type": "string"},
                        "amount": {"type": "number"},
                    },
                },
                "description": "Itemized charges or medicines with amounts.",
            },
            "total": {
                "type": ["number", "null"],
                "description": "Total billed amount.",
            },
            "tests_ordered": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of diagnostic tests ordered or performed.",
            },
            "field_confidence": {
                "type": "object",
                "additionalProperties": {"type": "number"},
                "description": (
                    "Per-field confidence score in [0.0, 1.0]. Provide a score for "
                    "every field you attempted to extract. "
                    "0.0 = unreadable/missing, 0.5 = partially legible, "
                    "1.0 = clearly readable. "
                    "Lower confidence for: handwritten text, rubber-stamped areas, "
                    "blurry regions, partially visible text."
                ),
            },
            "overall_confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": (
                    "Overall extraction confidence for this document. "
                    "Weight heavily towards fields critical for the claim "
                    "(diagnosis, amount, patient_name). "
                    "0.0 = entirely illegible, 1.0 = fully clear."
                ),
            },
            "is_partial": {
                "type": "boolean",
                "description": (
                    "True if the document is cut off, has illegible sections, "
                    "has rubber stamps obscuring key fields, or if the extraction "
                    "is otherwise incomplete."
                ),
            },
            "extraction_notes": {
                "type": ["string", "null"],
                "description": (
                    "Human-readable notes about extraction quality. Required when "
                    "is_partial=true. Examples: 'Rubber stamp obscures diagnosis field', "
                    "'Amount partially illegible — possible 1500 or 1800', "
                    "'Handwritten prescription — doctor name inferred from stamp'."
                ),
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_prompt(claim_category: ClaimCategory, file_name: str | None) -> str:
    category = claim_category.value
    fname = file_name or "document"
    return (
        f"You are an expert medical document OCR and data extraction system for Indian "
        f"health insurance claims. Extract all structured fields from the attached "
        f"document image ('{fname}').\n\n"
        f"This document is submitted as part of a {category} insurance claim. "
        f"Focus particularly on fields relevant to this claim type.\n\n"
        "## Extraction guidelines\n"
        "- Read handwritten text carefully — Indian prescriptions are often fully or "
        "  partially handwritten.\n"
        "- Expand medical shorthand: HTN=Hypertension, T2DM=Type 2 Diabetes Mellitus, "
        "  T1DM=Type 1 Diabetes, URI=Upper Respiratory Infection, URTI=Upper Respiratory "
        "  Tract Infection, GERD=Gastroesophageal Reflux Disease, IBS=Irritable Bowel "
        "  Syndrome, HTN=Hypertension, CAD=Coronary Artery Disease.\n"
        "- Indian doctor registration formats: KA/XXXXX/YYYY (Karnataka), "
        "  MH/XXXXX/YYYY (Maharashtra), DL/XXXXX/YYYY (Delhi), TN/XXXXX/YYYY (Tamil Nadu), "
        "  GJ/XXXXX/YYYY (Gujarat), AP/XXXXX/YYYY (Andhra Pradesh), "
        "  WB/XXXXX/YYYY (West Bengal), KL/XXXXX/YYYY (Kerala), "
        "  AYUR/[STATE]/XXXXX/YYYY (Ayurveda).\n"
        "- If a rubber stamp partially obscures text, extract what is visible and "
        "  note the obstruction in extraction_notes.\n"
        "- For bills: extract each line item separately with its description and amount.\n"
        "- Dates should be in YYYY-MM-DD format; convert from DD-Mon-YYYY or DD/MM/YYYY.\n"
        "- Set field_confidence for every field you attempted to extract. "
        "  Reduce confidence for: handwritten text (0.6-0.8), rubber stamp over text (0.3-0.5), "
        "  blurry/low-contrast areas (0.4-0.7), partially visible text (0.2-0.5).\n"
        "- Set is_partial=true and populate extraction_notes whenever anything is "
        "  illegible, cut off, obscured, or ambiguous.\n\n"
        "Call the extract_document_data tool with everything you can read. "
        "Do not return a text response — use the tool."
    )


# ---------------------------------------------------------------------------
# Degraded result factory
# ---------------------------------------------------------------------------

def _degraded(file_id: str, notes: str) -> ExtractedDocumentData:
    return ExtractedDocumentData(
        file_id=file_id,
        document_type=DocumentType.UNKNOWN,
        overall_confidence=0.0,
        is_partial=True,
        extraction_notes=notes,
        field_confidence={},
    )


# ---------------------------------------------------------------------------
# Raw tool input → ExtractedDocumentData
# ---------------------------------------------------------------------------

def _parse_tool_input(
    file_id: str,
    raw: dict[str, Any],
) -> ExtractedDocumentData:
    """Validate and coerce the raw tool_use input dict into ExtractedDocumentData.

    Raises ValidationError if the model returned a schema-incompatible response.
    """
    # Coerce date string to date object if present
    if isinstance(raw.get("date"), str):
        try:
            raw["date"] = date_type.fromisoformat(raw["date"])
        except (ValueError, AttributeError):
            raw["date"] = None

    # Coerce line_items list of dicts into LineItem objects
    raw_items = raw.get("line_items", [])
    if isinstance(raw_items, list):
        raw["line_items"] = [
            LineItem(description=str(li.get("description", "")),
                     amount=float(li.get("amount", 0.0)))
            for li in raw_items
            if isinstance(li, dict)
        ]

    # Inject file_id
    raw["file_id"] = file_id

    return ExtractedDocumentData(**raw)


# ---------------------------------------------------------------------------
# Single LLM attempt
# ---------------------------------------------------------------------------

async def _call_llm(
    client: anthropic.AsyncAnthropic,
    document: UploadedDocument,
    claim_category: ClaimCategory,
) -> dict[str, Any]:
    """Make one LLM call and return the raw tool_use input dict.

    Raises:
        anthropic.APIError, anthropic.APITimeoutError, anthropic.APIConnectionError,
        ValueError (no tool_use block in response), ValidationError (bad schema).
    """
    # Build image content block
    if not document.file_bytes:
        raise ValueError(f"Document '{document.file_id}' has no file_bytes.")

    encoded = base64.standard_b64encode(document.file_bytes).decode("ascii")

    # Determine media type
    content_type = document.content_type or "image/jpeg"
    if content_type == "application/pdf":
        # Claude supports PDF as base64 via the document source type (SDK 0.40+)
        image_block: dict[str, Any] = {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": encoded,
            },
        }
    else:
        # image/jpeg, image/png, image/gif, image/webp
        valid_image_types = {"image/jpeg", "image/png", "image/gif", "image/webp"}
        if content_type not in valid_image_types:
            content_type = "image/jpeg"  # safe fallback
        image_block = {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": content_type,
                "data": encoded,
            },
        }

    prompt = _build_prompt(claim_category, document.file_name)
    response = await client.messages.create(
        model=settings.extraction_model,
        max_tokens=2048,
        tools=[EXTRACT_TOOL],
        tool_choice={"type": "tool", "name": "extract_document_data"},
        messages=[
            {
                "role": "user",
                "content": [
                    image_block,
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        timeout=settings.llm_timeout_seconds,
    )

    # Extract tool_use block
    tool_block = next(
        (b for b in response.content if b.type == "tool_use"),
        None,
    )
    if tool_block is None:
        raise ValueError(
            f"LLM response contained no tool_use block. "
            f"stop_reason={response.stop_reason}, "
            f"content types={[b.type for b in response.content]}"
        )

    return dict(tool_block.input)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run(
    document: UploadedDocument,
    claim_category: ClaimCategory,
    trace: ClaimTrace,
    *,
    force_failure: bool = False,
) -> ExtractedDocumentData:
    """Extract structured data from a single *document*.

    Args:
        document:      The uploaded document with file_bytes populated.
        claim_category: Category hint for the extraction prompt.
        trace:         Shared ClaimTrace; one TraceEvent appended per call.
        force_failure: Test seam (TC011 / simulate_component_failure).
                       When True, skip LLM call, return degraded result.

    Returns:
        ExtractedDocumentData — fully populated on success, degraded
        (overall_confidence=0.0, is_partial=True) on failure.

    Raises:
        Nothing — all failures return a degraded result.
    """
    file_id = document.file_id

    # -- Test seam: forced degradation (TC011) --------------------------------
    if force_failure:
        result = _degraded(
            file_id,
            "Extraction skipped: simulated component failure",
        )
        append_event(
            trace,
            stage=_STAGE,
            component=_COMPONENT,
            status="degraded",
            summary=f"Extraction skipped for '{file_id}': simulated component failure.",
            details={
                "file_id": file_id,
                "force_failure": True,
                "overall_confidence": 0.0,
            },
        )
        return result

    # -- Normal path ----------------------------------------------------------
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    last_error: str = "unknown error"

    for attempt in range(settings.llm_max_retries + 1):  # 0, 1
        if attempt > 0:
            backoff = 2.0 ** attempt  # 2s on retry 1
            logger.info(
                "Extraction retry %d/%d for '%s' after %.1fs backoff.",
                attempt, settings.llm_max_retries, file_id, backoff,
            )
            await asyncio.sleep(backoff)

        try:
            raw = await _call_llm(client, document, claim_category)
            extracted = _parse_tool_input(file_id, raw)

            # Success — emit trace event and return
            append_event(
                trace,
                stage=_STAGE,
                component=_COMPONENT,
                status="degraded" if extracted.is_partial else "ok",
                summary=(
                    f"Extracted '{extracted.document_type.value}' from '{file_id}' "
                    f"(confidence={extracted.overall_confidence:.2f}"
                    + (", partial" if extracted.is_partial else "")
                    + ")."
                ),
                details={
                    "file_id": file_id,
                    "document_type": extracted.document_type.value,
                    "overall_confidence": extracted.overall_confidence,
                    "is_partial": extracted.is_partial,
                    "field_confidence": extracted.field_confidence,
                    "extraction_notes": extracted.extraction_notes,
                    "attempt": attempt,
                },
            )
            return extracted

        except ValidationError as exc:
            last_error = f"Schema validation failed: {exc.error_count()} errors"
            logger.warning(
                "Extraction attempt %d: schema validation failed for '%s': %s",
                attempt, file_id, exc,
            )
            # Retry with stricter prompt on next iteration

        except (
            anthropic.APITimeoutError,
            anthropic.APIConnectionError,
        ) as exc:
            last_error = f"API timeout/connection error: {type(exc).__name__}"
            logger.warning(
                "Extraction attempt %d: timeout/connection error for '%s': %s",
                attempt, file_id, exc,
            )

        except anthropic.APIError as exc:
            last_error = f"API error {exc.status_code}: {exc.message}"
            logger.warning(
                "Extraction attempt %d: API error for '%s': %s",
                attempt, file_id, exc,
            )

        except ValueError as exc:
            last_error = f"No tool_use block: {exc}"
            logger.warning(
                "Extraction attempt %d: no tool_use block for '%s': %s",
                attempt, file_id, exc,
            )

        except Exception as exc:  # unexpected — log and continue to degraded
            last_error = f"Unexpected error: {type(exc).__name__}: {exc}"
            logger.exception(
                "Extraction attempt %d: unexpected error for '%s'.",
                attempt, file_id,
            )

    # All retries exhausted — return degraded result
    notes = f"Extraction failed after retry: {last_error}"
    result = _degraded(file_id, notes)
    append_event(
        trace,
        stage=_STAGE,
        component=_COMPONENT,
        status="degraded",
        summary=f"Extraction failed for '{file_id}' after {settings.llm_max_retries + 1} attempts: {last_error}",
        details={
            "file_id": file_id,
            "overall_confidence": 0.0,
            "is_partial": True,
            "extraction_notes": notes,
            "attempts": settings.llm_max_retries + 1,
            "last_error": last_error,
        },
    )
    return result
