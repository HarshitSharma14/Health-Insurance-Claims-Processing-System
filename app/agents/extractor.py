"""Extraction Agent — powered by Google Gemini Flash.

Uses gemini-1.5-flash (free tier: 1500 req/day) with vision input and
response_schema for forced structured JSON output.

On any failure (timeout, API error, schema validation failure) the agent:
  1. Retries once with a brief backoff.
  2. On second failure returns a typed degraded ExtractedDocumentData.
  Never raises to the caller.

force_failure=True (TC011 test seam):
  Skips the LLM call entirely and returns the degraded result immediately.

Contract (data-contracts.md):
    Input:  UploadedDocument, ClaimCategory, ClaimTrace
    Output: ExtractedDocumentData
    Errors: None raised to caller.
"""

import asyncio
import base64
import logging
from datetime import date as date_type
from typing import Any

import google.generativeai as genai
from pydantic import ValidationError

from app.config import settings
from app.schemas.claim import ClaimCategory, DocumentType, UploadedDocument
from app.schemas.extraction import ExtractedDocumentData, LineItem
from app.schemas.trace import ClaimTrace
from app.trace.trace import append_event

logger = logging.getLogger(__name__)

_STAGE = "extraction"
_COMPONENT = "ExtractionAgent"

# ---------------------------------------------------------------------------
# Response schema — tells Gemini exactly what JSON shape to return.
# Maps to ExtractedDocumentData fields.
# ---------------------------------------------------------------------------

_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["document_type", "overall_confidence", "is_partial"],
    "properties": {
        "document_type": {
            "type": "string",
            "enum": [
                "PRESCRIPTION", "HOSPITAL_BILL", "LAB_REPORT", "PHARMACY_BILL",
                "DENTAL_REPORT", "DIAGNOSTIC_REPORT", "DISCHARGE_SUMMARY", "UNKNOWN",
            ],
        },
        "patient_name":        {"type": "string",  "nullable": True},
        "diagnosis":           {"type": "string",  "nullable": True},
        "treatment":           {"type": "string",  "nullable": True},
        "doctor_name":         {"type": "string",  "nullable": True},
        "doctor_registration": {"type": "string",  "nullable": True},
        "hospital_name":       {"type": "string",  "nullable": True},
        "date":                {"type": "string",  "nullable": True},
        "total":               {"type": "number",  "nullable": True},
        "extraction_notes":    {"type": "string",  "nullable": True},
        "overall_confidence":  {"type": "number"},
        "is_partial":          {"type": "boolean"},
        "tests_ordered": {
            "type": "array",
            "items": {"type": "string"},
        },
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "amount":      {"type": "number"},
                },
                "required": ["description", "amount"],
            },
        },
        "field_confidence": {
            "type": "object",
            "additionalProperties": {"type": "number"},
        },
    },
}

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

def _build_prompt(claim_category: ClaimCategory, file_name: str | None) -> str:
    category = claim_category.value
    fname = file_name or "document"
    return (
        f"You are an expert medical document OCR and data extraction system for "
        f"Indian health insurance claims. Extract all structured fields from the "
        f"attached document image ('{fname}').\n\n"
        f"This document is part of a {category} insurance claim.\n\n"
        "## Extraction rules\n"
        "- Expand medical shorthand: HTN=Hypertension, T2DM=Type 2 Diabetes Mellitus, "
        "URI=Upper Respiratory Infection, GERD=Gastroesophageal Reflux Disease.\n"
        "- Indian doctor registration formats: KA/XXXXX/YYYY, MH/XXXXX/YYYY, "
        "DL/XXXXX/YYYY, TN/XXXXX/YYYY, GJ/XXXXX/YYYY, AP/XXXXX/YYYY, "
        "WB/XXXXX/YYYY, KL/XXXXX/YYYY, AYUR/[STATE]/XXXXX/YYYY.\n"
        "- Dates must be in YYYY-MM-DD format.\n"
        "- Extract each bill line item separately with description and amount.\n"
        "- Set field_confidence for every extracted field (0.0-1.0). "
        "Lower for: handwritten text (0.6-0.8), rubber stamps (0.3-0.5), blurry areas (0.4-0.7).\n"
        "- Set is_partial=true and populate extraction_notes if anything is "
        "illegible, cut off, or ambiguous.\n"
        "- Return null for any field that is absent or unreadable.\n"
        "Return the JSON object only, no extra text."
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
# Parse Gemini JSON response → ExtractedDocumentData
# ---------------------------------------------------------------------------

def _parse_response(file_id: str, raw: dict[str, Any]) -> ExtractedDocumentData:
    """Coerce Gemini's JSON dict into a validated ExtractedDocumentData.

    Raises ValidationError on schema mismatch.
    """
    # Coerce date string
    if isinstance(raw.get("date"), str):
        try:
            raw["date"] = date_type.fromisoformat(raw["date"])
        except (ValueError, AttributeError):
            raw["date"] = None

    # Coerce line_items
    raw_items = raw.get("line_items", []) or []
    raw["line_items"] = [
        LineItem(
            description=str(li.get("description", "")),
            amount=float(li.get("amount", 0.0)),
        )
        for li in raw_items
        if isinstance(li, dict)
    ]

    raw["file_id"] = file_id
    return ExtractedDocumentData(**raw)

# ---------------------------------------------------------------------------
# Single Gemini call (run in thread pool — SDK is sync)
# ---------------------------------------------------------------------------

def _call_gemini_sync(
    document: UploadedDocument,
    claim_category: ClaimCategory,
) -> dict[str, Any]:
    """Synchronous Gemini call — wrapped in asyncio.to_thread by the caller."""
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        model_name=settings.extraction_model,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=_RESPONSE_SCHEMA,
            temperature=0.1,
            max_output_tokens=2048,
        ),
    )

    if not document.file_bytes:
        raise ValueError(f"Document '{document.file_id}' has no file_bytes.")

    encoded = base64.standard_b64encode(document.file_bytes).decode("ascii")
    content_type = document.content_type or "image/jpeg"
    if content_type not in {"image/jpeg", "image/png", "image/gif", "image/webp",
                             "application/pdf"}:
        content_type = "image/jpeg"

    image_part = {
        "inline_data": {
            "mime_type": content_type,
            "data": encoded,
        }
    }

    prompt = _build_prompt(claim_category, document.file_name)
    response = model.generate_content([image_part, prompt])

    if not response.text:
        raise ValueError("Gemini returned an empty response.")

    import json
    raw = json.loads(response.text)
    if not isinstance(raw, dict):
        raise ValueError(f"Expected JSON object, got {type(raw).__name__}")
    return raw

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
    """Extract structured data from a single *document* via Gemini Flash.

    Args:
        document:       Uploaded document with file_bytes populated.
        claim_category: Category hint for the extraction prompt.
        trace:          Shared ClaimTrace; one TraceEvent appended per call.
        force_failure:  Test seam (TC011). When True, skip LLM, return degraded.

    Returns:
        ExtractedDocumentData — populated on success, degraded on failure.

    Raises:
        Nothing — all failures return a degraded result.
    """
    file_id = document.file_id

    # Test seam (TC011 / simulate_component_failure)
    if force_failure:
        result = _degraded(file_id, "Extraction skipped: simulated component failure")
        append_event(
            trace, stage=_STAGE, component=_COMPONENT, status="degraded",
            summary=f"Extraction skipped for '{file_id}': simulated component failure.",
            details={"file_id": file_id, "force_failure": True, "overall_confidence": 0.0},
        )
        return result

    last_error = "unknown error"

    for attempt in range(settings.llm_max_retries + 1):  # 0, 1
        if attempt > 0:
            backoff = 2.0 ** attempt
            logger.info("Extraction retry %d for '%s' after %.1fs.", attempt, file_id, backoff)
            await asyncio.sleep(backoff)

        try:
            # Run synchronous Gemini SDK in thread pool to keep FastAPI async
            raw = await asyncio.to_thread(_call_gemini_sync, document, claim_category)
            extracted = _parse_response(file_id, raw)

            append_event(
                trace, stage=_STAGE, component=_COMPONENT,
                status="degraded" if extracted.is_partial else "ok",
                summary=(
                    f"Extracted '{extracted.document_type.value}' from '{file_id}' "
                    f"(confidence={extracted.overall_confidence:.2f}"
                    + (", partial" if extracted.is_partial else "") + ")."
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
            logger.warning("Attempt %d: schema validation failed for '%s': %s", attempt, file_id, exc)

        except ValueError as exc:
            last_error = f"Value error: {exc}"
            logger.warning("Attempt %d: value error for '%s': %s", attempt, file_id, exc)

        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("Attempt %d: error for '%s': %s", attempt, file_id, exc)

    notes = f"Extraction failed after retry: {last_error}"
    result = _degraded(file_id, notes)
    append_event(
        trace, stage=_STAGE, component=_COMPONENT, status="degraded",
        summary=f"Extraction failed for '{file_id}' after {settings.llm_max_retries + 1} attempts: {last_error}",
        details={
            "file_id": file_id, "overall_confidence": 0.0, "is_partial": True,
            "extraction_notes": notes, "attempts": settings.llm_max_retries + 1,
            "last_error": last_error,
        },
    )
    return result
