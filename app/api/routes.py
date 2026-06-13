"""FastAPI application and API routes.

Exposes:
    POST /claims          -- submit a claim (multipart form + file uploads)
    POST /claims/json     -- submit a claim as JSON body with optional
                             pre_extracted_documents (eval harness / testing)
    GET  /claims/{id}     -- retrieve a past decision + trace (stub)
    GET  /health          -- readiness probe

POST /claims flow:
  1. Parse multipart form data (member details + uploaded files).
  2. Assemble ClaimSubmission.
  3. Delegate to process_claim().
  4. Return DocumentVerificationResult (Stage 0 failure, no decision) or
     ClaimDecision (APPROVED / PARTIAL / REJECTED / MANUAL_REVIEW).

Response shape:
  Both endpoints return a discriminated union wrapped in PipelineResponse so
  the frontend can tell which type it received without inspecting fields:
    {"type": "verification_failure", "data": DocumentVerificationResult}
    {"type": "decision",             "data": ClaimDecision}
"""

import logging
from contextlib import asynccontextmanager
from datetime import date
from typing import Any, AsyncIterator, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.orchestrator.pipeline import process_claim
from app.policy.loader import load_policy
from app.schemas.claim import ClaimCategory, ClaimSubmission, UploadedDocument
from app.schemas.decision import ClaimDecision
from app.schemas.extraction import ExtractedDocumentData
from app.schemas.verification import DocumentVerificationResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response wrapper — lets the frontend discriminate result type cheaply
# ---------------------------------------------------------------------------

class PipelineResponse(BaseModel):
    """Discriminated wrapper around the two possible pipeline outcomes."""
    type: Literal["verification_failure", "decision"]
    data: DocumentVerificationResult | ClaimDecision


def _wrap(result: DocumentVerificationResult | ClaimDecision) -> PipelineResponse:
    if isinstance(result, DocumentVerificationResult):
        return PipelineResponse(type="verification_failure", data=result)
    return PipelineResponse(type="decision", data=result)


# ---------------------------------------------------------------------------
# JSON body schema for the /claims/json endpoint
# ---------------------------------------------------------------------------

class ClaimSubmissionJSON(BaseModel):
    """JSON-body version of ClaimSubmission for the eval harness.

    pre_extracted_documents is ONLY accepted on this endpoint (not the
    multipart form endpoint) to prevent it being an accidental public footgun.
    It is used by test_cases.json evaluation and orchestrator tests to supply
    structured extraction results without needing real document images.
    """
    member_id: str
    policy_id: str
    claim_category: ClaimCategory
    treatment_date: date
    claimed_amount: float
    hospital_name: str | None = None
    ytd_claims_amount: float | None = None
    claims_history: list[Any] = []
    simulate_component_failure: bool = False
    # Inline document descriptors (actual_type used as document_type)
    documents: list[dict[str, Any]] = []
    # Pre-built extraction results — skips the Extraction Agent entirely
    pre_extracted_documents: list[ExtractedDocumentData] | None = None


# ---------------------------------------------------------------------------
# App + lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load policy_terms.json at startup; fail fast if missing/malformed."""
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


# ---------------------------------------------------------------------------
# POST /claims — multipart form + file uploads (real document flow)
# ---------------------------------------------------------------------------

@app.post(
    "/claims",
    response_model=PipelineResponse,
    summary="Submit a claim (multipart form with file uploads)",
)
async def submit_claim(
    member_id: str = Form(...),
    policy_id: str = Form(...),
    claim_category: ClaimCategory = Form(...),
    treatment_date: str = Form(..., description="ISO 8601 date e.g. 2024-11-01"),
    claimed_amount: float = Form(..., gt=0),
    hospital_name: str | None = Form(None),
    simulate_component_failure: bool = Form(False),
    files: list[UploadFile] = File(..., description="One or more claim documents"),
) -> PipelineResponse:
    """Process a claim submitted as multipart form data with document uploads."""
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
    except Exception as exc:
        logger.exception("Unexpected pipeline error for member %s", member_id)
        raise HTTPException(status_code=500, detail="Internal processing error.") from exc

    return _wrap(result)


# ---------------------------------------------------------------------------
# POST /claims/json — JSON body (eval harness / testing)
# ---------------------------------------------------------------------------

@app.post(
    "/claims/json",
    response_model=PipelineResponse,
    summary="Submit a claim as JSON (eval harness / testing only)",
    description=(
        "Accepts a JSON body ClaimSubmission with an optional "
        "`pre_extracted_documents` field that bypasses the Extraction Agent. "
        "Intended for test_cases.json evaluation and integration tests. "
        "Do not expose to untrusted callers in production."
    ),
)
async def submit_claim_json(body: ClaimSubmissionJSON) -> PipelineResponse:
    """Process a JSON-body claim, optionally with pre-extracted document data."""
    from app.schemas.claim import DocumentType, DocumentQuality
    from app.schemas.claim import ClaimsHistoryEntry as CHE

    # Build UploadedDocument list from inline document descriptors
    documents: list[UploadedDocument] = []
    for d in body.documents:
        raw_type = d.get("actual_type", "UNKNOWN")
        try:
            doc_type = DocumentType(raw_type)
        except ValueError:
            doc_type = DocumentType.UNKNOWN
        documents.append(
            UploadedDocument(
                file_id=d.get("file_id", f"doc_{len(documents)}"),
                file_name=d.get("file_name"),
                document_type=doc_type,
                patient_name=d.get("patient_name_on_doc"),
            )
        )

    # Build claims history
    history = []
    for h in body.claims_history:
        if isinstance(h, dict):
            try:
                history.append(CHE(**h))
            except Exception:
                pass

    try:
        submission = ClaimSubmission(
            member_id=body.member_id,
            policy_id=body.policy_id,
            claim_category=body.claim_category,
            treatment_date=body.treatment_date,
            claimed_amount=body.claimed_amount,
            hospital_name=body.hospital_name,
            ytd_claims_amount=body.ytd_claims_amount,
            claims_history=history,
            simulate_component_failure=body.simulate_component_failure,
            documents=documents if documents else [
                UploadedDocument(file_id="placeholder", document_type=DocumentType.UNKNOWN)
            ],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = await process_claim(
            submission,
            pre_extracted_documents=body.pre_extracted_documents,
        )
    except Exception as exc:
        logger.exception("Unexpected pipeline error for member %s", body.member_id)
        raise HTTPException(status_code=500, detail="Internal processing error.") from exc

    return _wrap(result)


# ---------------------------------------------------------------------------
# GET /claims/{claim_id}
# ---------------------------------------------------------------------------

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
        detail="Claim retrieval not yet implemented.",
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
