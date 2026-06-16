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

Designated component for simulate_component_failure (TC011):
    The Extraction Agent is forced into its degraded path when
    simulate_component_failure=True (see docs/assumptions.md).
    All extraction calls receive force_failure=True, returning degraded
    ExtractedDocumentData with overall_confidence=0.0 and is_partial=True.
    The pipeline still completes and the Decision Agent produces a decision
    (typically APPROVED if policy checks pass) with a measurably lower
    confidence_score and a manual-review recommendation in the reason.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from app.agents import decision_maker, document_verifier, extractor, policy_evaluator
from app.schemas.claim import ClaimSubmission
from app.schemas.decision import ClaimDecision
from app.schemas.extraction import ExtractedDocumentData
from app.schemas.policy import MemberNotFoundError, PolicyEvaluationResult
from app.schemas.trace import ClaimTrace
from app.schemas.verification import DocumentVerificationResult
from app.trace.trace import append_event, new_trace

logger = logging.getLogger(__name__)

_STAGE = "orchestrator"
_COMPONENT = "ClaimOrchestrator"


def _post_extraction_verification(
    submission: ClaimSubmission,
    extractions: list[ExtractedDocumentData],
    trace: ClaimTrace,
) -> DocumentVerificationResult | None:
    """Verification checks that can only run once documents are extracted.

    Stage 0 runs before extraction and can only compare metadata supplied at
    upload time. On the live path (real uploads) patient names and legibility
    are unknown until the LLM has read each document, so we re-run two checks
    here using the extracted content (see decision-logic.md Stage 0, notes 2 & 3):

      * Legibility — a REQUIRED document the model could read but found
        illegible (is_partial with 0 < confidence < 0.6). A hard extraction
        failure (confidence == 0.0, e.g. timeout or simulate_component_failure)
        is NOT treated as unreadable — that degrades toward MANUAL_REVIEW
        instead, per error-handling.md.
      * Patient identity — extracted patient_name disagrees across documents
        (no shared name token), surfacing the specific names found.

    Returns a DocumentVerificationResult(passed=False) to short-circuit, or
    None to proceed to policy evaluation.
    """
    from app.policy.loader import get_policy
    from app.schemas.verification import VerificationFailureType

    policy = get_policy()
    category = submission.claim_category.value
    required = set(
        policy.get("document_requirements", {}).get(category, {}).get("required", [])
    )
    upload_by_id = {d.file_id: d for d in submission.documents}

    # ── Legibility (skip entirely when a component failure is being simulated)
    if not submission.simulate_component_failure:
        for ex in extractions:
            if ex.is_partial and 0.0 < ex.overall_confidence < 0.6:
                up = upload_by_id.get(ex.file_id)
                declared = up.document_type.value if up else ex.document_type.value
                if required and declared not in required:
                    continue  # an optional doc being unreadable doesn't block
                name = (up.file_name if up and up.file_name else ex.file_id)
                msg = (
                    f"The document '{name}' could not be read clearly "
                    f"(extraction confidence {ex.overall_confidence:.0%}). "
                    "Please re-upload a clear, legible photo or scan of that document."
                )
                append_event(
                    trace, stage="document_verification", component=_COMPONENT,
                    status="failed",
                    summary=f"Post-extraction legibility check failed: '{name}' unreadable.",
                    details={"check": "legibility_post_extraction", "file_id": ex.file_id,
                             "confidence": ex.overall_confidence, "message": msg},
                )
                return DocumentVerificationResult(
                    passed=False,
                    required_documents=[],
                    received_documents=[d.document_type for d in submission.documents],
                    missing_documents=[],
                    unreadable_documents=[ex.file_id],
                    failure_type=VerificationFailureType.UNREADABLE_DOCUMENT,
                    message=msg,
                )

    # ── Cross-document patient identity (token-overlap tolerant)
    named = [
        (upload_by_id.get(ex.file_id), ex.patient_name)
        for ex in extractions
        if ex.patient_name and not ex.is_partial
    ]
    if len(named) >= 2:
        def tokens(n: str) -> set[str]:
            return {t for t in n.lower().replace(".", " ").split() if len(t) > 2}

        names = [n for _, n in named]
        # Mismatch only if some pair shares NO name token at all.
        mismatch = False
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                if not (tokens(names[i]) & tokens(names[j])):
                    mismatch = True
        if mismatch:
            parts = "; ".join(
                f"'{n}' (on {up.file_name if up and up.file_name else 'document'})"
                for up, n in named
            )
            msg = (
                f"The documents appear to belong to different patients: {parts}. "
                "Please confirm these documents all belong to the same person "
                "and re-upload the correct documents."
            )
            append_event(
                trace, stage="document_verification", component=_COMPONENT,
                status="failed",
                summary=f"Post-extraction patient identity check failed: {len(set(names))} names.",
                details={"check": "patient_identity_post_extraction",
                         "names": names, "message": msg},
            )
            return DocumentVerificationResult(
                passed=False,
                required_documents=[],
                received_documents=[d.document_type for d in submission.documents],
                missing_documents=[],
                failure_type=VerificationFailureType.PATIENT_MISMATCH,
                message=msg,
            )

    return None


async def process_claim(
    submission: ClaimSubmission,
    pre_extracted_documents: list[ExtractedDocumentData] | None = None,
) -> DocumentVerificationResult | ClaimDecision:
    """Process a claim submission through the full pipeline.

    Args:
        submission:               Validated ClaimSubmission from the API layer.
        pre_extracted_documents:  Optional pre-built extraction results. When
                                  provided, the Extraction Agent is skipped
                                  entirely and these are used directly as if
                                  extraction had already run. This is the
                                  injection point for test_cases.json cases
                                  TC004-TC012, which supply document content
                                  as structured JSON rather than real image
                                  bytes. Also used in orchestrator unit tests
                                  to avoid live LLM calls.
                                  MUST NOT be accepted from untrusted external
                                  callers in production — gated in routes.py.

    Returns:
        DocumentVerificationResult (passed=False) if Stage 0 fails.
        ClaimDecision for all other outcomes (APPROVED / PARTIAL /
        REJECTED / MANUAL_REVIEW).

    Raises:
        Nothing under normal operation.
    """
    claim_id = str(uuid.uuid4())
    trace = new_trace(claim_id)

    append_event(
        trace,
        stage=_STAGE,
        component=_COMPONENT,
        status="ok",
        summary=(
            f"Pipeline started for member '{submission.member_id}', "
            f"category '{submission.claim_category.value}', "
            f"amount ₹{submission.claimed_amount:,.2f}."
        ),
        details={
            "claim_id": claim_id,
            "member_id": submission.member_id,
            "policy_id": submission.policy_id,
            "claim_category": submission.claim_category.value,
            "treatment_date": str(submission.treatment_date),
            "claimed_amount": submission.claimed_amount,
            "document_count": len(submission.documents),
            "simulate_component_failure": submission.simulate_component_failure,
        },
    )

    # ------------------------------------------------------------------
    # Stage 0 — Document Verification
    # ------------------------------------------------------------------
    verification_result = await document_verifier.run(submission, trace)

    if not verification_result.passed:
        # Hard-stop: return verification failure, no ClaimDecision produced.
        append_event(
            trace,
            stage=_STAGE,
            component=_COMPONENT,
            status="failed",
            summary=(
                f"Pipeline halted at Stage 0: "
                f"{verification_result.failure_type}. "
                f"{verification_result.message}"
            ),
            details={
                "failure_type": (
                    verification_result.failure_type.value
                    if verification_result.failure_type
                    else None
                ),
                "message": verification_result.message,
            },
        )
        return verification_result

    # ------------------------------------------------------------------
    # Stage 0 → Extraction (concurrent, one call per document)
    # When pre_extracted_documents is provided (test injection / eval harness),
    # skip the LLM calls entirely and use those directly.
    # TC011: force_failure=True when simulate_component_failure is set — this
    # forces the Extraction Agent into its degraded path for the first document
    # (see docs/assumptions.md — "simulate_component_failure target component").
    # ------------------------------------------------------------------
    if pre_extracted_documents is not None:
        extractions: list[ExtractedDocumentData] = pre_extracted_documents
        append_event(
            trace,
            stage=_STAGE,
            component=_COMPONENT,
            status="ok",
            summary=(
                f"Extraction skipped — {len(extractions)} pre-extracted document(s) "
                "provided directly (eval harness / test injection)."
            ),
            details={
                "pre_extracted": True,
                "document_count": len(extractions),
            },
        )
        # If simulate_component_failure is also set alongside pre-extracted docs,
        # mark the first document as degraded to honour TC011 semantics.
        if submission.simulate_component_failure and extractions:
            from app.agents.extractor import _degraded as _make_degraded
            first = extractions[0]
            if not first.is_partial:
                degraded_first = _make_degraded(
                    first.file_id,
                    "Extraction skipped: simulated component failure",
                )
                extractions = [degraded_first] + list(extractions[1:])
                append_event(
                    trace,
                    stage=_STAGE,
                    component=_COMPONENT,
                    status="degraded",
                    summary=(
                        f"simulate_component_failure active — first document "
                        f"'{first.file_id}' forced to degraded extraction."
                    ),
                    details={"file_id": first.file_id, "force_failure": True},
                )
    else:
        force_failure = submission.simulate_component_failure
        extraction_coros = [
            extractor.run(
                document=doc,
                claim_category=submission.claim_category,
                trace=trace,
                force_failure=force_failure,
            )
            for doc in submission.documents
        ]
        raw_results = await asyncio.gather(*extraction_coros, return_exceptions=True)

        extractions = []
        for i, res in enumerate(raw_results):
            if isinstance(res, BaseException):
                # Defensive: extractor.run() should never raise, but handle it anyway.
                doc_id = submission.documents[i].file_id if i < len(submission.documents) else f"doc_{i}"
                logger.warning(
                    "Unexpected exception from extractor for doc '%s': %s",
                    doc_id, res,
                )
                from app.agents.extractor import _degraded as _make_degraded
                extractions.append(
                    _make_degraded(doc_id, f"Unexpected extractor error: {res}")
                )
            else:
                extractions.append(res)  # type: ignore[arg-type]

        degraded_count = sum(1 for ex in extractions if ex.is_partial)
        if degraded_count:
            append_event(
                trace,
                stage=_STAGE,
                component=_COMPONENT,
                status="degraded",
                summary=(
                    f"Extraction completed with {degraded_count} degraded document(s) "
                    f"out of {len(extractions)}. "
                    "Pipeline will continue with available data."
                ),
                details={
                    "total_documents": len(extractions),
                    "degraded_documents": degraded_count,
                    "force_failure": force_failure,
                    "degraded_file_ids": [ex.file_id for ex in extractions if ex.is_partial],
                },
            )

    # ------------------------------------------------------------------
    # Post-extraction verification (live path): legibility + patient identity
    # can only be assessed once the documents have been read.
    # ------------------------------------------------------------------
    post_verify = _post_extraction_verification(submission, extractions, trace)
    if post_verify is not None:
        append_event(
            trace, stage=_STAGE, component=_COMPONENT, status="failed",
            summary=(
                f"Pipeline halted after extraction: {post_verify.failure_type}. "
                f"{post_verify.message}"
            ),
            details={
                "failure_type": post_verify.failure_type.value if post_verify.failure_type else None,
                "message": post_verify.message,
            },
        )
        return post_verify

    # ------------------------------------------------------------------
    # Stages 1–8 — Policy Evaluation
    # MemberNotFoundError is raised if member_id is not in the roster;
    # we catch it here and produce a MANUAL_REVIEW ClaimDecision.
    # ------------------------------------------------------------------
    try:
        policy_result: PolicyEvaluationResult = await policy_evaluator.run(
            submission, extractions, trace
        )
    except MemberNotFoundError as exc:
        logger.warning(
            "Member '%s' not found in policy roster — routing to MANUAL_REVIEW.",
            exc.member_id,
        )
        append_event(
            trace,
            stage=_STAGE,
            component=_COMPONENT,
            status="failed",
            summary=(
                f"Member '{exc.member_id}' not found in policy roster. "
                "Routing to MANUAL_REVIEW."
            ),
            details={"member_id": exc.member_id, "error": str(exc)},
        )
        trace.final_decision_explanation = (
            f"Member '{exc.member_id}' is not present in the policy roster. "
            "This claim cannot be processed automatically and requires manual "
            "verification to confirm membership."
        )
        return ClaimDecision(
            decision="MANUAL_REVIEW",
            approved_amount=None,
            reason=(
                "Member ID not found in policy records — "
                "requires manual verification."
            ),
            confidence_score=0.5,
            trace=trace,
        )
    except Exception as exc:
        # Unexpected bug in the policy evaluator — degrade safely.
        logger.exception(
            "Unexpected error in PolicyEvaluationAgent for member '%s'.",
            submission.member_id,
        )
        append_event(
            trace,
            stage=_STAGE,
            component=_COMPONENT,
            status="failed",
            summary=f"Policy evaluation failed unexpectedly: {exc}",
            details={"error": str(exc), "error_type": type(exc).__name__},
        )
        trace.final_decision_explanation = (
            f"An unexpected error occurred during policy evaluation: {exc}. "
            "Routed to MANUAL_REVIEW for safety."
        )
        return ClaimDecision(
            decision="MANUAL_REVIEW",
            approved_amount=None,
            reason=(
                "An unexpected error occurred during policy evaluation. "
                "This claim requires manual review."
            ),
            confidence_score=0.0,
            trace=trace,
        )

    # ------------------------------------------------------------------
    # Stage 9 / Decision Agent — produces the final ClaimDecision
    # (decision_maker.run() never raises; all failures become MANUAL_REVIEW)
    # ------------------------------------------------------------------
    decision: ClaimDecision = await decision_maker.run(
        submission=submission,
        extractions=extractions,
        policy_result=policy_result,
        trace=trace,
    )

    append_event(
        trace,
        stage=_STAGE,
        component=_COMPONENT,
        status="ok",
        summary=(
            f"Pipeline complete — decision: {decision.decision}, "
            f"approved_amount: {decision.approved_amount}, "
            f"confidence: {decision.confidence_score:.2f}."
        ),
        details={
            "decision": decision.decision,
            "approved_amount": decision.approved_amount,
            "confidence_score": decision.confidence_score,
            "rejection_reasons": decision.rejection_reasons,
            "total_trace_events": len(trace.events),
        },
    )

    return decision
