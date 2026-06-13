#!/usr/bin/env python3
"""Evaluation harness for the Plum Claims Processing System.

Loads test_cases.json, runs each of the 12 cases through the full pipeline,
compares actual vs expected, and writes eval/eval_report.md.

Usage:
    python eval/run_eval.py

Output:
    - eval/eval_report.md  (full per-case trace + analysis)
    - stdout summary table + N/12 score
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from textwrap import indent
from typing import Any

# Make sure repo root is on sys.path when run directly
REPO_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.orchestrator.pipeline import process_claim
from app.policy.loader import load_policy
from app.schemas.decision import ClaimDecision
from app.schemas.extraction import ExtractedDocumentData
from app.schemas.verification import DocumentVerificationResult
from eval.fixtures import build_inputs, load_test_cases

# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------

def _actual_decision(result: DocumentVerificationResult | ClaimDecision) -> str | None:
    if isinstance(result, DocumentVerificationResult):
        return None
    return result.decision


def _actual_approved_amount(result: DocumentVerificationResult | ClaimDecision) -> float | None:
    if isinstance(result, ClaimDecision):
        return result.approved_amount
    return None


def _passes(tc: dict[str, Any],
            result: DocumentVerificationResult | ClaimDecision) -> tuple[bool, list[str]]:
    """Return (passed, list_of_failure_reasons)."""
    expected = tc["expected"]
    failures: list[str] = []
    exp_decision = expected.get("decision")

    actual_dec = _actual_decision(result)

    # Decision match
    if exp_decision != actual_dec:
        failures.append(
            f"decision: expected {exp_decision!r}, got {actual_dec!r}"
        )

    # approved_amount (exact, within 1 rupee tolerance)
    if "approved_amount" in expected and expected["approved_amount"] is not None:
        exp_amt = float(expected["approved_amount"])
        act_amt = _actual_approved_amount(result)
        if act_amt is None:
            failures.append(f"approved_amount: expected {exp_amt}, got None")
        elif abs(act_amt - exp_amt) > 1.0:
            failures.append(
                f"approved_amount: expected {exp_amt}, got {act_amt:.2f}"
            )

    # rejection_reasons
    if "rejection_reasons" in expected:
        exp_reasons = set(expected["rejection_reasons"])
        if isinstance(result, ClaimDecision):
            act_reasons = set(result.rejection_reasons)
        else:
            act_reasons = set()
        missing = exp_reasons - act_reasons
        if missing:
            failures.append(
                f"rejection_reasons: expected {sorted(exp_reasons)}, "
                f"got {sorted(act_reasons)}"
            )

    # confidence_score threshold (e.g. "above 0.90")
    if "confidence_score" in expected:
        cs_spec = expected["confidence_score"]
        if isinstance(cs_spec, str) and cs_spec.startswith("above "):
            threshold = float(cs_spec.split("above ")[1])
            if isinstance(result, ClaimDecision):
                if result.confidence_score <= threshold:
                    failures.append(
                        f"confidence_score: expected > {threshold}, "
                        f"got {result.confidence_score:.4f}"
                    )
            else:
                failures.append("confidence_score: no ClaimDecision produced")

    # For TC001-TC003 (decision: null), additionally check message quality
    if exp_decision is None and isinstance(result, DocumentVerificationResult):
        if not result.message:
            failures.append("message: expected a specific actionable message, got None")
        elif len(result.message) < 30:
            failures.append(
                f"message: too short ({len(result.message)} chars) — "
                "likely not specific enough"
            )

    return (len(failures) == 0), failures


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _fmt_rupees(amount: float | None) -> str:
    if amount is None:
        return "—"
    return f"Rs{amount:,.2f}"


def _render_result_summary(result: DocumentVerificationResult | ClaimDecision) -> str:
    lines: list[str] = []
    if isinstance(result, DocumentVerificationResult):
        lines.append(f"**Type:** Verification Failure")
        lines.append(f"**Passed:** {result.passed}")
        lines.append(f"**Failure type:** `{result.failure_type}`")
        if result.message:
            lines.append(f"**Message:** {result.message}")
        lines.append(f"**Missing documents:** {[d.value for d in result.missing_documents]}")
        lines.append(f"**Unreadable documents:** {result.unreadable_documents}")
    else:
        icon = {
            "APPROVED": "✅", "PARTIAL": "🔶",
            "REJECTED": "❌", "MANUAL_REVIEW": "🔍",
        }.get(result.decision, "❓")
        lines.append(f"**Decision:** {icon} `{result.decision}`")
        lines.append(f"**Approved amount:** {_fmt_rupees(result.approved_amount)}")
        lines.append(f"**Confidence score:** {result.confidence_score:.4f}")
        lines.append(f"**Rejection reasons:** {result.rejection_reasons or '—'}")
        lines.append(f"**Reason:** {result.reason}")
        if result.financial_breakdown:
            fb = result.financial_breakdown
            lines.append(f"**Financial breakdown:**")
            lines.append(f"  - Base: {_fmt_rupees(fb.base_amount)}")
            if fb.network_discount_percent:
                lines.append(
                    f"  - Network discount ({fb.network_discount_percent}%): "
                    f"{_fmt_rupees(fb.amount_after_discount)} after discount"
                )
            if fb.co_pay_amount:
                lines.append(
                    f"  - Co-pay ({fb.co_pay_percent}%): "
                    f"Rs{fb.co_pay_amount:,.2f} deducted"
                )
            lines.append(f"  - **Final: {_fmt_rupees(fb.final_amount)}**")
        if result.line_item_evaluations:
            lines.append(f"**Line items:**")
            for ev in result.line_item_evaluations:
                symbol = "✓" if ev.covered else "✗"
                lines.append(
                    f"  - {symbol} `{ev.description}` Rs{ev.amount:,.2f} — {ev.reason}"
                )
    return "\n".join(lines)


def _render_trace(result: DocumentVerificationResult | ClaimDecision) -> str:
    if isinstance(result, DocumentVerificationResult):
        return "_Trace not available — pipeline stopped at document verification stage._"
    trace = result.trace
    lines: list[str] = []
    for ev in trace.events:
        icon = {"ok": "✓", "degraded": "⚠", "failed": "✗"}.get(ev.status, "?")
        ts = ev.timestamp.strftime("%H:%M:%S.%f")[:-3]
        lines.append(
            f"| `{ts}` | `{ev.stage}` | `{ev.component}` | "
            f"{icon} `{ev.status}` | {ev.summary} |"
        )
    header = (
        "| Time | Stage | Component | Status | Summary |\n"
        "|------|-------|-----------|--------|---------|\n"
    )
    events_table = header + "\n".join(lines) if lines else "_No trace events._"
    explanation = trace.final_decision_explanation or "_No explanation recorded._"
    return f"{events_table}\n\n**Final explanation:** {explanation}"


def _render_case(
    tc: dict[str, Any],
    result: DocumentVerificationResult | ClaimDecision,
    passed: bool,
    failures: list[str],
    idx: int,
) -> str:
    case_id = tc["case_id"]
    case_name = tc["case_name"]
    description = tc["description"]
    expected = tc["expected"]
    verdict = "PASS" if passed else "FAIL"
    verdict_icon = "✅ PASS" if passed else "❌ FAIL"

    lines: list[str] = [
        f"## {idx}. {case_id} — {case_name}",
        "",
        f"**Description:** {description}",
        "",
        f"**Expected outcome:** decision=`{expected.get('decision')}`, "
        + (f"approved_amount=`{expected.get('approved_amount')}`" if 'approved_amount' in expected else "")
        + (f", rejection_reasons=`{expected.get('rejection_reasons')}`" if 'rejection_reasons' in expected else "")
        + (f", confidence_score=`{expected.get('confidence_score')}`" if 'confidence_score' in expected else ""),
        "",
        "### Actual Result",
        "",
        _render_result_summary(result),
        "",
        "### Trace",
        "",
        _render_trace(result),
        "",
        f"### Verdict: {verdict_icon}",
    ]
    if not passed:
        lines.append("")
        lines.append("**Mismatch details:**")
        for f in failures:
            lines.append(f"- {f}")
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_eval() -> None:
    load_policy(REPO_ROOT / "policy_terms.json")
    test_cases = load_test_cases()

    results_data: list[tuple[dict, DocumentVerificationResult | ClaimDecision, bool, list[str]]] = []

    print("\nRunning evaluation harness against test_cases.json...\n")

    for tc in test_cases:
        case_id = tc["case_id"]
        case_name = tc["case_name"]
        print(f"  [{case_id}] {case_name}...", end=" ", flush=True)

        submission, pre_extracted = build_inputs(tc)

        try:
            result = await process_claim(
                submission,
                pre_extracted_documents=pre_extracted,
            )
        except Exception as exc:
            # Unexpected crash — create a synthetic failure result
            from app.trace.trace import new_trace
            trace = new_trace(case_id)
            result = ClaimDecision(
                decision="MANUAL_REVIEW",
                approved_amount=None,
                reason=f"PIPELINE CRASHED: {exc}",
                confidence_score=0.0,
                trace=trace,
            )

        passed, failures = _passes(tc, result)
        results_data.append((tc, result, passed, failures))
        print("PASS" if passed else f"FAIL — {'; '.join(failures)}")

    # ------------------------------------------------------------------
    # Build eval_report.md
    # ------------------------------------------------------------------
    report_lines: list[str] = [
        "# Plum Claims Processing — Eval Report",
        "",
        f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_",
        "",
        f"**Score: {sum(1 for _, _, p, _ in results_data if p)}/{len(results_data)} cases passing**",
        "",
        "---",
        "",
        "## Summary Table",
        "",
        "| Case ID | Name | Expected Decision | Actual Decision | Verdict |",
        "|---------|------|-------------------|-----------------|---------|",
    ]

    for tc, result, passed, _ in results_data:
        exp_dec = tc["expected"].get("decision", "null (verification stop)")
        act_dec = _actual_decision(result)
        act_dec_str = act_dec if act_dec is not None else "null (verification stop)"
        verdict_icon = "✅ PASS" if passed else "❌ FAIL"
        row = (
            f"| `{tc['case_id']}` | {tc['case_name']} "
            f"| `{exp_dec}` | `{act_dec_str}` | {verdict_icon} |"
        )
        report_lines.append(row)

    report_lines += [
        "",
        "---",
        "",
        "## Per-Case Detail",
        "",
    ]

    for idx, (tc, result, passed, failures) in enumerate(results_data, start=1):
        report_lines.append(_render_case(tc, result, passed, failures, idx))

    report_path = REPO_ROOT / "eval" / "eval_report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    # ------------------------------------------------------------------
    # Stdout summary
    # ------------------------------------------------------------------
    n_pass = sum(1 for _, _, p, _ in results_data if p)
    n_total = len(results_data)

    print("\n" + "=" * 60)
    print(f"  EVAL SUMMARY: {n_pass}/{n_total} PASSING")
    print("=" * 60)
    print(f"\n{'Case ID':<8} {'Name':<45} {'Result'}")
    print("-" * 70)
    for tc, result, passed, _ in results_data:
        verdict = "PASS" if passed else "FAIL"
        print(f"{tc['case_id']:<8} {tc['case_name'][:44]:<45} {verdict}")
    print("-" * 70)
    print(f"\nReport written to: {report_path.relative_to(REPO_ROOT)}\n")


if __name__ == "__main__":
    asyncio.run(run_eval())
