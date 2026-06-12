"""FastAPI application and API routes.

Exposes:
    POST /claims  — submit a claim for processing
    GET  /claims/{claim_id} — retrieve a past decision + trace (stub)

The POST /claims endpoint:
1. Parses and validates the multipart form data (member details + file uploads).
2. Assembles a ClaimSubmission.
3. Delegates to process_claim() in the orchestrator.
4. Returns either a DocumentVerificationResult (Stage 0 failure) or a
   ClaimDecision (all other outcomes).

Error handling:
    400 — ClaimSubmission validation errors (Pydantic).
    422 — Unprocessable entity (FastAPI default for body parse failures).
    500 — Unexpected pipeline errors (logged, generic message returned).
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

import logging

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.orchestrator.pipeline import process_claim
from app.policy.loader import load_policy
from app.schemas.claim import ClaimCategory, ClaimSubmission, UploadedDocument
from app.schemas.decision import ClaimDecision
from app.schemas.verification import DocumentVerificationResult

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load policy data on startup; fail fast if missing/malformed."""
    load_policy()
    logger.info("Application startup complete — policy data loaded.")
    yield


app = FastAPI(
    title="Plum Health Insurance Claims API",
    version="0.1.0",
    description="Automated health insurance claims processing pipeline.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post(
    "/claims",
    response_model=DocumentVerificationResult | ClaimDecision,
    summary="Submit a claim for automated processing",
    description=(
        "Accepts member details, a claim category, the claimed amount, "
        "treatment date, and one or more document uploads. "
        "Returns a DocumentVerificationResult if document issues are detected "
        "before processing, or a ClaimDecision (APPROVED / PARTIAL / "
        "REJECTED / MANUAL_REVIEW) otherwise."
    ),
)
async def submit_claim(
    member_id: str = Form(...),
    policy_id: str = Form(...),
    claim_category: ClaimCategory = Form(...),
    treatment_date: str = Form(..., description="ISO 8601 date, e.g. 2024-03-15"),
    claimed_amount: float = Form(..., gt=0),
    hospital_name: str | None = Form(None),
    simulate_component_failure: bool = Form(False),
    files: list[UploadFile] = File(..., description="One or more claim documents"),
) -> DocumentVerificationResult | ClaimDecision:
    """Process a claim submission.

    This endpoint is a placeholder — the multipart parsing and orchestrator
    wiring will be completed once the orchestrator stub is implemented.
    """
    # Assemble uploaded documents
    documents: list[UploadedDocument] = []
    for upload in files:
        content = await upload.read()
        documents.append(
            UploadedDocument(
                file_id=upload.filename or f"upload_{len(documents)}",
                file_name=upload.filename,
                content_type=upload.content_type,
                file_bytes=content,
            )
        )

    from datetime import date

    try:
        submission = ClaimSubmission(
            member_id=member_id,
            policy_id=policy_id,
            claim_category=claim_category,
            treatment_date=date.fromisoformat(treatment_date),
            claimed_amount=claimed_amount,
            hospital_name=hospital_name,
            simulate_component_failure=simulate_component_failure,
            documents=documents,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = await process_claim(submission)
    except NotImplementedError:
        raise HTTPException(
            status_code=501,
            detail="Pipeline not yet implemented — scaffold only.",
        )
    except Exception as exc:
        logger.exception("Unexpected pipeline error for member %s", member_id)
        raise HTTPException(status_code=500, detail="Internal processing error.") from exc

    return result


@app.get(
    "/claims/{claim_id}",
    response_model=ClaimDecision,
    summary="Retrieve a past claim decision",
)
async def get_claim(claim_id: str) -> ClaimDecision:
    """Retrieve decision + trace for a previously submitted claim.

    Placeholder — requires persistence layer (SQLite / in-memory store).
    """
    raise HTTPException(
        status_code=501,
        detail="Claim retrieval not yet implemented — scaffold only.",
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Simple health check for deployment readiness probes."""
    return {"status": "ok"}
