"""Quick smoke test for the Document Verification Agent.

Runs TC001, TC002, TC003, and TC004 directly against the agent
and prints the results. No LLM calls needed — this is pure logic.

Usage:  python scripts/smoke_test_verifier.py
"""

import asyncio
import json
from datetime import date

from app.agents.document_verifier import run
from app.policy.loader import load_policy
from app.schemas.claim import (
    ClaimCategory,
    ClaimSubmission,
    DocumentQuality,
    DocumentType,
    UploadedDocument,
)
from app.trace.trace import new_trace

load_policy("policy_terms.json")

DIVIDER = "\n" + "=" * 60


def _sub(category, docs, member_id="EMP001", amount=1500.0):
    return ClaimSubmission(
        member_id=member_id,
        policy_id="PLUM_GHI_2024",
        claim_category=category,
        treatment_date=date(2024, 11, 1),
        claimed_amount=amount,
        documents=docs,
    )


def print_result(label, result, trace):
    print(f"\n{DIVIDER}")
    print(f"  {label}")
    print(DIVIDER)
    print(f"  passed         : {result.passed}")
    print(f"  failure_type   : {result.failure_type}")
    print(f"  missing_docs   : {[d.value for d in result.missing_documents]}")
    print(f"  unreadable_docs: {result.unreadable_documents}")
    if result.message:
        print(f"\n  MESSAGE:\n  {result.message}")
    print(f"\n  TRACE EVENTS ({len(trace.events)} total):")
    for ev in trace.events:
        icon = "✓" if ev.status == "ok" else "✗"
        print(f"    [{icon} {ev.status:8s}] {ev.summary}")


async def main():
    # ------------------------------------------------------------------
    # TC001 — Two PRESCRIPTIONs for a CONSULTATION claim (needs HOSPITAL_BILL)
    # ------------------------------------------------------------------
    trace = new_trace("TC001")
    result = await run(
        _sub(ClaimCategory.CONSULTATION, [
            UploadedDocument(file_id="F001", file_name="dr_sharma_prescription.jpg",
                             document_type=DocumentType.PRESCRIPTION),
            UploadedDocument(file_id="F002", file_name="another_prescription.jpg",
                             document_type=DocumentType.PRESCRIPTION),
        ]),
        trace,
    )
    print_result("TC001 — Wrong document type", result, trace)

    # ------------------------------------------------------------------
    # TC002 — Unreadable pharmacy bill
    # ------------------------------------------------------------------
    trace = new_trace("TC002")
    result = await run(
        _sub(ClaimCategory.PHARMACY, [
            UploadedDocument(file_id="F003", file_name="prescription.jpg",
                             document_type=DocumentType.PRESCRIPTION,
                             quality=DocumentQuality.GOOD),
            UploadedDocument(file_id="F004", file_name="blurry_bill.jpg",
                             document_type=DocumentType.PHARMACY_BILL,
                             quality=DocumentQuality.UNREADABLE),
        ], member_id="EMP004", amount=800.0),
        trace,
    )
    print_result("TC002 — Unreadable document", result, trace)

    # ------------------------------------------------------------------
    # TC003 — Patient name mismatch
    # ------------------------------------------------------------------
    trace = new_trace("TC003")
    result = await run(
        _sub(ClaimCategory.CONSULTATION, [
            UploadedDocument(file_id="F005", file_name="prescription_rajesh.jpg",
                             document_type=DocumentType.PRESCRIPTION,
                             patient_name="Rajesh Kumar"),
            UploadedDocument(file_id="F006", file_name="bill_arjun.jpg",
                             document_type=DocumentType.HOSPITAL_BILL,
                             patient_name="Arjun Mehta"),
        ]),
        trace,
    )
    print_result("TC003 — Patient mismatch", result, trace)

    # ------------------------------------------------------------------
    # TC004 — Happy path: correct docs, same patient
    # ------------------------------------------------------------------
    trace = new_trace("TC004")
    result = await run(
        _sub(ClaimCategory.CONSULTATION, [
            UploadedDocument(file_id="F007", file_name="prescription.jpg",
                             document_type=DocumentType.PRESCRIPTION,
                             quality=DocumentQuality.GOOD,
                             patient_name="Rajesh Kumar"),
            UploadedDocument(file_id="F008", file_name="hospital_bill.jpg",
                             document_type=DocumentType.HOSPITAL_BILL,
                             quality=DocumentQuality.GOOD,
                             patient_name="Rajesh Kumar"),
        ]),
        trace,
    )
    print_result("TC004 — Happy path (should PASS)", result, trace)

    print(f"\n{DIVIDER}\n  Done.\n{DIVIDER}\n")


asyncio.run(main())
