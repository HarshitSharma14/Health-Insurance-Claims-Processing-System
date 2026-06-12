"""Extraction Agent.

Stage 2 of the pipeline — one async call per uploaded document, run
concurrently via asyncio.gather.

Sends each document (image/PDF base64) to a vision-capable LLM using
structured output (forced JSON via tool schema) and returns typed
ExtractedDocumentData.

On any failure (LLM timeout, API error, malformed JSON, Pydantic
ValidationError) the agent returns a degraded ExtractedDocumentData with
overall_confidence=0.0 and is_partial=True rather than raising. The caller
(orchestrator) factors this into the confidence score and may route the
claim to MANUAL_REVIEW.

Retry policy: one retry with exponential backoff (configurable via
Settings.llm_max_retries). After final failure, degrade as above.

Contract (data-contracts.md):
    Input:  UploadedDocument, ClaimCategory (for prompt context), ClaimTrace
    Output: ExtractedDocumentData
    Errors: None raised to caller.
"""

from app.schemas.claim import ClaimCategory, UploadedDocument
from app.schemas.extraction import ExtractedDocumentData
from app.schemas.trace import ClaimTrace


async def run(
    document: UploadedDocument,
    claim_category: ClaimCategory,
    trace: ClaimTrace,
    *,
    force_degraded: bool = False,
) -> ExtractedDocumentData:
    """Extract structured data from a single *document*.

    Args:
        document:        The uploaded document (bytes or storage reference).
        claim_category:  Category hint passed to the LLM prompt for context.
        trace:           Shared ClaimTrace; a TraceEvent is appended per call.
        force_degraded:  Test seam — when True, skip the LLM call and return a
                         degraded result immediately (used by TC011 /
                         simulate_component_failure). See error-handling.md.

    Returns:
        ExtractedDocumentData with all available fields populated.
        On failure: overall_confidence=0.0, is_partial=True, extraction_notes
        describing the failure.

    Raises:
        Nothing — all failures produce a degraded return value.
    """
    raise NotImplementedError("ExtractionAgent.run() not yet implemented.")
