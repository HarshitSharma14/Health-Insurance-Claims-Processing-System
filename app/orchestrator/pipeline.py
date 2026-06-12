"""Claim processing orchestrator.

Drives the full 9-stage pipeline described in decision-logic.md.
Each stage is delegated to its agent; the orchestrator decides whether to
proceed, degrade, or short-circuit based on stage outputs.

Pipeline overview:
    Stage 0  — Document Verification (DocumentVerificationAgent)
               Hard-stop on failure: return DocumentVerificationResult, no
               ClaimDecision produced.
    Stage 1  — Member & Policy Lookup      ─┐
    Stage 2  — Waiting Period Check         │
    Stage 3  — Exclusion Check              │ PolicyEvaluationAgent
    Stage 4  — Pre-Authorization Check      │ (Stages 1–8 internally)
    Stage 5  — Per-Claim Limit Check        │
    Stage 6  — Fraud Signal Check           │
    Stage 7  — Sub-Limits & Line Items      │
    Stage 8  — Financial Calculation       ─┘
               Concurrent extraction (asyncio.gather, one call per document)
               runs between Stage 0 and the policy stages.
    Stage 9  — Component Failure Simulation (orthogonal, triggered by
               submission.simulate_component_failure — see error-handling.md).

Return type:
    DocumentVerificationResult  — Stage 0 failed
    ClaimDecision               — pipeline ran to completion (APPROVED /
                                  PARTIAL / REJECTED / MANUAL_REVIEW)
"""

import uuid

from app.schemas.claim import ClaimSubmission
from app.schemas.decision import ClaimDecision
from app.schemas.verification import DocumentVerificationResult


async def process_claim(
    submission: ClaimSubmission,
) -> DocumentVerificationResult | ClaimDecision:
    """Process a claim submission through the full pipeline.

    Args:
        submission: Validated ClaimSubmission from the API layer.

    Returns:
        DocumentVerificationResult (passed=False) if Stage 0 fails.
        ClaimDecision for all other outcomes (APPROVED / PARTIAL /
        REJECTED / MANUAL_REVIEW).

    Raises:
        Nothing under normal operation. Unexpected top-level exceptions
        (genuine programming errors) are caught by the FastAPI exception
        handler and logged — they should never reach the caller in production.
    """
    # A unique claim ID is generated here and threaded through the trace
    # so all events for this run are correlated.
    _claim_id = str(uuid.uuid4())
    raise NotImplementedError(
        f"process_claim() not yet implemented. claim_id={_claim_id}"
    )
