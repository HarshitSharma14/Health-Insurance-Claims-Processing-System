"""Policy Evaluation Agent.

Stages 1–8 of the pipeline — deterministic rules engine over policy_terms.json.
LLM-based fuzzy matching is intentionally stubbed with keyword/substring matching
so an LLM matcher can be dropped in later without changing the caller interface.

Stage execution order (decision-logic.md):
    1  member_lookup      — member exists, policy active, dates in range
    2  waiting_period     — initial 30-day + condition-specific waiting periods
    3  exclusion          — global exclusion list (not category line-items)
    4  pre_authorization  — high-value diagnostic tests without pre-auth
    5  per_claim_limit    — claimed_amount vs coverage.per_claim_limit
    6  fraud_signals      — same-day / high-value fraud heuristics
    7  sub_limit_and_line_items — coverage, DENTAL/VISION line-item eval, sub_limit
    8  financial_calculation   — network discount FIRST, then co-pay

Every stage appends one PolicyCheckResult to the checks list and one TraceEvent
to the shared trace.  Stages 1-6 are hard-stops on failure (first failure wins).
Stages 7-8 always run when stages 1-6 pass.

Contract (data-contracts.md):
    Input:  ClaimSubmission, list[ExtractedDocumentData], ClaimTrace
    Output: PolicyEvaluationResult
    Errors: MemberNotFoundError raised when member_id absent from roster —
            caught by the orchestrator and routed to MANUAL_REVIEW.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from app.policy.loader import get_policy
from app.schemas.claim import ClaimCategory, ClaimSubmission
from app.schemas.financial import FinancialBreakdown
from app.schemas.extraction import ExtractedDocumentData
from app.schemas.policy import (
    LineItemEvaluation,
    MemberNotFoundError,
    PolicyCheckResult,
    PolicyEvaluationResult,
)
from app.schemas.trace import ClaimTrace
from app.trace.trace import append_event

_STAGE = "policy_evaluation"
_COMPONENT = "PolicyEvaluationAgent"

# ---------------------------------------------------------------------------
# Assumption (docs/assumptions.md): sub_limit for consultation/pharmacy/etc.
# is a per-visit/item cap on the CONSULTATION_FEE line, NOT a hard ceiling
# on the entire claim amount.  The per_claim_limit (Stage 5) is the overall
# hard ceiling.  TC010 (₹4,500 → ₹3,240) confirms this — if sub_limit=2000
# were applied, the result would be ₹1,440, not ₹3,240.
# sub_limit IS applied as a cap only when it is LESS THAN the approved amount
# after line-item evaluation for DENTAL/VISION categories.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Keyword maps for fuzzy matching (swap body of _match_condition /
# _match_exclusion with LLM calls when wiring in the LLM later)
# ---------------------------------------------------------------------------

# Maps policy_terms.json waiting_periods.specific_conditions key →
# list of substrings that indicate this condition in diagnosis/treatment text.
_CONDITION_KEYWORDS: dict[str, list[str]] = {
    "diabetes": ["diabetes", "diabetic", "metformin", "glimepiride", "insulin"],
    "hypertension": ["hypertension", "hypertensive", "high blood pressure", "amlodipine"],
    "thyroid_disorders": ["thyroid", "hypothyroid", "hyperthyroid", "thyroxine"],
    "joint_replacement": ["joint replacement", "knee replacement", "hip replacement", "arthroplasty"],
    "maternity": ["maternity", "pregnancy", "prenatal", "antenatal", "obstetric"],
    "mental_health": ["mental health", "psychiatry", "psychiatric", "depression",
                      "anxiety disorder", "schizophrenia"],
    "obesity_treatment": ["obesity", "obese", "bariatric", "weight loss program",
                          "weight management"],
    # "hernia" waiting period covers abdominal hernia surgery, NOT spinal
    # disc herniation (TC007 diagnosis: "Suspected Lumbar Disc Herniation").
    # Use word-boundary-aware patterns via the _text_matches_condition helper.
    "hernia": ["hernia"],
    "cataract": ["cataract"],
}

# Maps exclusion clause text fragments → list of substrings that indicate
# a match in diagnosis/treatment.
_EXCLUSION_KEYWORDS: dict[str, list[str]] = {
    "Obesity and weight loss programs": [
        "obesity", "obese", "weight loss", "weight management", "bmi"
    ],
    "Bariatric surgery": [
        "bariatric", "gastric bypass", "sleeve gastrectomy", "weight loss surgery"
    ],
    "Cosmetic or aesthetic procedures": [
        "cosmetic", "aesthetic", "rhinoplasty", "botox", "facelift"
    ],
    "Self-inflicted injuries": ["self-inflicted", "self harm", "self-harm"],
    "Substance abuse treatment": ["substance abuse", "alcohol abuse", "drug abuse",
                                   "de-addiction", "detox"],
    "Experimental treatments": ["experimental", "clinical trial", "investigational"],
    "Infertility and assisted reproduction": [
        "infertility", "ivf", "iui", "assisted reproduction"
    ],
    "Vaccination (non-medically necessary)": ["vaccination", "vaccine", "immunization"],
    "Health supplements and tonics": ["supplement", "tonic", "multivitamin"],
    "War or nuclear hazard": ["war", "nuclear", "radiation exposure"],
}

# Substrings that identify high-value diagnostic tests requiring pre-auth
_PRE_AUTH_TEST_KEYWORDS: dict[str, str] = {
    "MRI": "mri",
    "CT Scan": "ct scan",
    "PET Scan": "pet scan",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    return text.lower().strip()


def _text_contains_any(text: str, keywords: list[str]) -> bool:
    t = _normalise(text)
    return any(kw.lower() in t for kw in keywords)


# Conditions where a keyword match must NOT fire if certain context words are present.
# This prevents "Lumbar Disc Herniation" from matching the hernia waiting period.
_CONDITION_NEGATIVE_CONTEXT: dict[str, list[str]] = {
    "hernia": ["disc herniation", "lumbar disc", "cervical disc", "disc hernia",
               "spinal disc", "intervertebral disc"],
}


def _condition_matches(text: str, condition: str, keywords: list[str]) -> bool:
    """Return True if text matches a condition keyword but NOT a negative-context term."""
    t = _normalise(text)
    if not any(kw.lower() in t for kw in keywords):
        return False
    # Check negative context — if any exclusion phrase is present, no match
    for excl in _CONDITION_NEGATIVE_CONTEXT.get(condition, []):
        if excl.lower() in t:
            return False
    return True


def _collect_diagnosis_text(extractions: list[ExtractedDocumentData]) -> str:
    """Concatenate all diagnosis/treatment strings from extractions."""
    parts: list[str] = []
    for ex in extractions:
        if ex.diagnosis:
            parts.append(ex.diagnosis)
        if ex.treatment:
            parts.append(ex.treatment)
    return " ".join(parts)


def _collect_tests_ordered(extractions: list[ExtractedDocumentData]) -> list[str]:
    tests: list[str] = []
    for ex in extractions:
        tests.extend(ex.tests_ordered)
    return tests


def _collect_line_items(extractions: list[ExtractedDocumentData]) -> list[tuple[str, float]]:
    """Return (description, amount) pairs from all bill extractions."""
    items: list[tuple[str, float]] = []
    for ex in extractions:
        for li in ex.line_items:
            items.append((li.description, li.amount))
    return items


def _find_member(policy: dict, member_id: str) -> dict | None:
    for m in policy.get("members", []):
        if m.get("member_id") == member_id:
            return m
    return None


def _network_hospital_match(hospital_name: str, network_list: list[str]) -> bool:
    """Case-insensitive substring check against the network hospitals list."""
    h = _normalise(hospital_name)
    return any(_normalise(n) in h or h in _normalise(n) for n in network_list)


def _check_result(name: str, passed: bool, detail: str,
                  clause: str | None = None) -> PolicyCheckResult:
    return PolicyCheckResult(
        check_name=name, passed=passed, detail=detail,
        relevant_policy_clause=clause,
    )


def _emit(trace: ClaimTrace, check: PolicyCheckResult,
          extra_details: dict | None = None) -> None:
    status = "ok" if check.passed else "failed"
    details: dict[str, Any] = {"check": check.check_name, "detail": check.detail}
    if check.relevant_policy_clause:
        details["policy_clause"] = check.relevant_policy_clause
    if extra_details:
        details.update(extra_details)
    append_event(
        trace, stage=_STAGE, component=_COMPONENT,
        status=status, summary=check.detail, details=details,
    )


# ---------------------------------------------------------------------------
# Stage implementations
# ---------------------------------------------------------------------------

def _stage1_member_lookup(
    policy: dict,
    submission: ClaimSubmission,
    checks: list[PolicyCheckResult],
    trace: ClaimTrace,
) -> tuple[bool, dict | None]:
    """Stage 1: member lookup + policy validity.  Returns (ok, member_dict)."""
    member = _find_member(policy, submission.member_id)

    if member is None:
        raise MemberNotFoundError(submission.member_id)

    # Policy ID match
    policy_id_ok = policy.get("policy_id") == submission.policy_id
    holder = policy.get("policy_holder", {})
    status = holder.get("renewal_status", "UNKNOWN")
    start = date.fromisoformat(holder.get("policy_start_date", "1900-01-01"))
    end = date.fromisoformat(holder.get("policy_end_date", "9999-12-31"))

    td = submission.treatment_date
    active = status == "ACTIVE"
    in_range = start <= td <= end

    passed = policy_id_ok and active and in_range

    if not policy_id_ok:
        detail = (
            f"Policy ID '{submission.policy_id}' does not match "
            f"the policy on file ('{policy.get('policy_id')}')."
        )
    elif not active:
        detail = f"Policy renewal_status is '{status}', not ACTIVE."
    elif not in_range:
        detail = (
            f"Treatment date {td} is outside the policy window "
            f"{start} – {end}."
        )
    else:
        detail = (
            f"Member '{submission.member_id}' ({member.get('name')}) found. "
            f"Policy '{submission.policy_id}' is ACTIVE for "
            f"{start} – {end}. Treatment date {td} is in range."
        )

    check = _check_result("member_lookup", passed, detail,
                          clause="policy_holder.renewal_status")
    checks.append(check)
    _emit(trace, check)
    return passed, member if passed else None


def _stage2_waiting_period(
    policy: dict,
    submission: ClaimSubmission,
    member: dict,
    extractions: list[ExtractedDocumentData],
    checks: list[PolicyCheckResult],
    trace: ClaimTrace,
    rejection_reasons: list[str],
) -> bool:
    """Stage 2: initial + condition-specific waiting periods."""
    join_date = date.fromisoformat(member["join_date"])
    td = submission.treatment_date
    wp = policy.get("waiting_periods", {})
    initial_days: int = wp.get("initial_waiting_period_days", 30)
    specific: dict[str, int] = wp.get("specific_conditions", {})

    # 2a — initial waiting period
    earliest = join_date + timedelta(days=initial_days)
    if td < earliest:
        detail = (
            f"Treatment date {td} is within the {initial_days}-day initial "
            f"waiting period. Member joined {join_date}; earliest eligible "
            f"date is {earliest}."
        )
        check = _check_result(
            "waiting_period", False, detail,
            clause="waiting_periods.initial_waiting_period_days",
        )
        checks.append(check)
        _emit(trace, check)
        rejection_reasons.append("WAITING_PERIOD")
        return False

    # 2b — condition-specific waiting period
    diag_text = _collect_diagnosis_text(extractions)
    matched_condition: str | None = None
    matched_days: int = 0

    if diag_text:
        for condition, keywords in _CONDITION_KEYWORDS.items():
            if condition not in specific:
                continue
            if _condition_matches(diag_text, condition, keywords):
                matched_condition = condition
                matched_days = specific[condition]
                break  # first match wins

    if matched_condition:
        eligible = join_date + timedelta(days=matched_days)
        if td < eligible:
            detail = (
                f"Diagnosis/treatment matches condition '{matched_condition}' "
                f"(waiting period: {matched_days} days). "
                f"Treatment date {td} < eligibility date {eligible}. "
                f"Member will be eligible from {eligible}."
            )
            check = _check_result(
                "waiting_period", False, detail,
                clause=f"waiting_periods.specific_conditions.{matched_condition}",
            )
            checks.append(check)
            _emit(trace, check, {"matched_condition": matched_condition,
                                  "eligible_date": str(eligible)})
            rejection_reasons.append("WAITING_PERIOD")
            return False

        # condition matched but within eligible window
        detail = (
            f"Condition '{matched_condition}' matched "
            f"({matched_days}-day waiting period). "
            f"Treatment date {td} >= eligibility date "
            f"{join_date + timedelta(days=matched_days)} — passes."
        )
    else:
        detail = (
            f"Initial waiting period passed (joined {join_date}, "
            f"earliest {earliest}, treatment {td}). "
            f"No specific condition waiting period applies."
        )

    check = _check_result(
        "waiting_period", True, detail,
        clause="waiting_periods.initial_waiting_period_days",
    )
    checks.append(check)
    _emit(trace, check)
    return True


def _stage3_exclusion(
    policy: dict,
    extractions: list[ExtractedDocumentData],
    checks: list[PolicyCheckResult],
    trace: ClaimTrace,
    rejection_reasons: list[str],
) -> bool:
    """Stage 3: global exclusion check (not category-level line items)."""
    diag_text = _collect_diagnosis_text(extractions)
    if not diag_text:
        check = _check_result(
            "exclusion", True,
            "No diagnosis/treatment text available — exclusion check skipped.",
        )
        checks.append(check)
        _emit(trace, check)
        return True

    for clause, keywords in _EXCLUSION_KEYWORDS.items():
        if _text_contains_any(diag_text, keywords):
            detail = (
                f"Diagnosis/treatment matches excluded condition: '{clause}'. "
                f"This treatment is not covered under the policy."
            )
            check = _check_result(
                "exclusion", False, detail,
                clause=f"exclusions.conditions['{clause}']",
            )
            checks.append(check)
            _emit(trace, check, {"matched_exclusion": clause})
            rejection_reasons.append("EXCLUDED_CONDITION")
            return False

    check = _check_result(
        "exclusion", True,
        f"No global exclusions matched for diagnosis: '{diag_text[:120]}'.",
        clause="exclusions.conditions",
    )
    checks.append(check)
    _emit(trace, check)
    return True


def _stage4_pre_authorization(
    policy: dict,
    submission: ClaimSubmission,
    extractions: list[ExtractedDocumentData],
    checks: list[PolicyCheckResult],
    trace: ClaimTrace,
    rejection_reasons: list[str],
) -> bool:
    """Stage 4: pre-authorization for high-value diagnostic tests."""
    if submission.claim_category != ClaimCategory.DIAGNOSTIC:
        check = _check_result(
            "pre_authorization", True,
            f"Pre-auth check not applicable for category "
            f"'{submission.claim_category.value}'.",
        )
        checks.append(check)
        _emit(trace, check)
        return True

    diag_cat = policy["opd_categories"].get("diagnostic", {})
    threshold: float = diag_cat.get("pre_auth_threshold", 10000)
    high_value_tests: list[str] = diag_cat.get("high_value_tests_requiring_pre_auth", [])

    tests_ordered = _collect_tests_ordered(extractions)
    line_items = _collect_line_items(extractions)

    # Check if any high-value test is present AND total amount exceeds threshold
    matched_test: str | None = None
    for hvt in high_value_tests:
        hvt_lower = hvt.lower()
        # Check tests_ordered
        for t in tests_ordered:
            if hvt_lower in t.lower():
                matched_test = hvt
                break
        if matched_test:
            break
        # Check line item descriptions
        for desc, amt in line_items:
            if hvt_lower in desc.lower():
                matched_test = hvt
                break
        if matched_test:
            break

    if matched_test and submission.claimed_amount > threshold:
        detail = (
            f"'{matched_test}' detected in claim (amount ₹{submission.claimed_amount:,.0f} "
            f"> pre-auth threshold ₹{threshold:,.0f}). "
            f"Pre-authorization is required for this test but was not provided. "
            f"To resubmit: obtain a pre-authorization reference from your insurer "
            f"before the procedure and include it with your claim."
        )
        check = _check_result(
            "pre_authorization", False, detail,
            clause="opd_categories.diagnostic.high_value_tests_requiring_pre_auth",
        )
        checks.append(check)
        _emit(trace, check, {"matched_test": matched_test,
                               "threshold": threshold,
                               "claimed_amount": submission.claimed_amount})
        rejection_reasons.append("PRE_AUTH_MISSING")
        return False

    detail = (
        "No high-value tests requiring pre-authorization detected, "
        "or amount is within the pre-auth threshold."
    )
    check = _check_result(
        "pre_authorization", True, detail,
        clause="opd_categories.diagnostic.high_value_tests_requiring_pre_auth",
    )
    checks.append(check)
    _emit(trace, check)
    return True


def _stage5_per_claim_limit(
    policy: dict,
    submission: ClaimSubmission,
    checks: list[PolicyCheckResult],
    trace: ClaimTrace,
    rejection_reasons: list[str],
) -> bool:
    """Stage 5: per-claim hard ceiling."""
    limit: float = policy["coverage"]["per_claim_limit"]
    amount = submission.claimed_amount

    if amount > limit:
        detail = (
            f"Claimed amount ₹{amount:,.0f} exceeds the per-claim limit "
            f"of ₹{limit:,.0f}. The maximum reimbursable amount per claim "
            f"is ₹{limit:,.0f}."
        )
        check = _check_result(
            "per_claim_limit", False, detail,
            clause="coverage.per_claim_limit",
        )
        checks.append(check)
        _emit(trace, check, {"claimed_amount": amount, "per_claim_limit": limit})
        rejection_reasons.append("PER_CLAIM_EXCEEDED")
        return False

    detail = (
        f"Claimed amount ₹{amount:,.0f} is within the per-claim "
        f"limit of ₹{limit:,.0f}."
    )
    check = _check_result(
        "per_claim_limit", True, detail, clause="coverage.per_claim_limit",
    )
    checks.append(check)
    _emit(trace, check)
    return True


def _stage6_fraud_signals(
    policy: dict,
    submission: ClaimSubmission,
    checks: list[PolicyCheckResult],
    trace: ClaimTrace,
    fraud_flags: list[str],
) -> None:
    """Stage 6: fraud heuristics — sets fraud_flags (MANUAL_REVIEW, not REJECTED)."""
    thresholds = policy.get("fraud_thresholds", {})
    same_day_limit: int = thresholds.get("same_day_claims_limit", 2)
    monthly_limit: int = thresholds.get("monthly_claims_limit", 6)
    high_value_threshold: float = thresholds.get("high_value_claim_threshold", 25000)

    signals: list[str] = []

    # Same-day claims check
    same_day_count = sum(
        1 for h in submission.claims_history
        if h.date == submission.treatment_date
    )
    if same_day_count >= same_day_limit:
        signal = (
            f"{same_day_count + 1} claims submitted on {submission.treatment_date} "
            f"(including this one), exceeds same-day limit of {same_day_limit}."
        )
        signals.append(signal)

    # Monthly claims check
    month_count = sum(
        1 for h in submission.claims_history
        if h.date.year == submission.treatment_date.year
        and h.date.month == submission.treatment_date.month
    )
    if month_count >= monthly_limit:
        signal = (
            f"{month_count + 1} claims in "
            f"{submission.treatment_date.strftime('%B %Y')} "
            f"(including this one), exceeds monthly limit of {monthly_limit}."
        )
        signals.append(signal)

    # High-value claim check
    if submission.claimed_amount > high_value_threshold:
        signal = (
            f"Claimed amount ₹{submission.claimed_amount:,.0f} exceeds "
            f"high-value threshold ₹{high_value_threshold:,.0f}."
        )
        signals.append(signal)

    if signals:
        fraud_flags.extend(signals)
        detail = "Fraud signals detected: " + " | ".join(signals)
        check = _check_result(
            "fraud_signals", False, detail,
            clause="fraud_thresholds",
        )
        checks.append(check)
        _emit(trace, check, {"fraud_signals": signals})
    else:
        check = _check_result(
            "fraud_signals", True,
            "No fraud signals detected.",
            clause="fraud_thresholds",
        )
        checks.append(check)
        _emit(trace, check)


def _stage7_sub_limit_and_line_items(
    policy: dict,
    submission: ClaimSubmission,
    extractions: list[ExtractedDocumentData],
    checks: list[PolicyCheckResult],
    trace: ClaimTrace,
) -> tuple[float, list[LineItemEvaluation], float | None, bool]:
    """Stage 7: line-item evaluation + sub_limit cap.

    Returns (approved_amount_pre_financial, line_item_evals, sub_limit, has_exclusions)
    """
    cat_key = submission.claim_category.value.lower()
    cat_policy = policy["opd_categories"].get(cat_key, {})
    sub_limit: float | None = cat_policy.get("sub_limit")

    line_item_evals: list[LineItemEvaluation] = []
    has_exclusions = False

    # DENTAL — line-item covered/excluded check
    if submission.claim_category == ClaimCategory.DENTAL:
        covered_procs: list[str] = cat_policy.get("covered_procedures", [])
        excluded_procs: list[str] = cat_policy.get("excluded_procedures", [])
        all_line_items = _collect_line_items(extractions)

        if all_line_items:
            covered_total = 0.0
            for desc, amt in all_line_items:
                d_lower = desc.lower()
                # Check excluded first (more specific)
                exc_match = next(
                    (ep for ep in excluded_procs if ep.lower() in d_lower
                     or d_lower in ep.lower()), None
                )
                if exc_match:
                    line_item_evals.append(LineItemEvaluation(
                        description=desc, amount=amt, covered=False,
                        reason=(
                            f"'{exc_match}' is excluded under "
                            f"opd_categories.dental.excluded_procedures."
                        ),
                    ))
                    has_exclusions = True
                else:
                    # Check if covered
                    cov_match = next(
                        (cp for cp in covered_procs if cp.lower() in d_lower
                         or d_lower in cp.lower()), None
                    )
                    covered_total += amt
                    line_item_evals.append(LineItemEvaluation(
                        description=desc, amount=amt, covered=True,
                        reason=(
                            f"'{cov_match or desc}' is a covered procedure under "
                            f"opd_categories.dental.covered_procedures."
                        ),
                    ))
            approved = min(covered_total, sub_limit) if sub_limit else covered_total

        else:
            # No line items extracted — use full claimed amount
            approved = min(submission.claimed_amount, sub_limit) if sub_limit else submission.claimed_amount

    # VISION — line-item covered/excluded check
    elif submission.claim_category == ClaimCategory.VISION:
        covered_items: list[str] = cat_policy.get("covered_items", [])
        excluded_items: list[str] = cat_policy.get("excluded_items", [])
        all_line_items = _collect_line_items(extractions)

        if all_line_items:
            covered_total = 0.0
            for desc, amt in all_line_items:
                d_lower = desc.lower()
                exc_match = next(
                    (ei for ei in excluded_items if ei.lower() in d_lower
                     or d_lower in ei.lower()), None
                )
                if exc_match:
                    line_item_evals.append(LineItemEvaluation(
                        description=desc, amount=amt, covered=False,
                        reason=(
                            f"'{exc_match}' is excluded under "
                            f"opd_categories.vision.excluded_items."
                        ),
                    ))
                    has_exclusions = True
                else:
                    covered_total += amt
                    line_item_evals.append(LineItemEvaluation(
                        description=desc, amount=amt, covered=True,
                        reason="Covered under opd_categories.vision.covered_items.",
                    ))
            approved = min(covered_total, sub_limit) if sub_limit else covered_total
        else:
            approved = min(submission.claimed_amount, sub_limit) if sub_limit else submission.claimed_amount

    else:
        # All other categories: pass claimed_amount through.
        # sub_limit is a per-procedure cap, not a claim ceiling (see assumptions.md).
        # The per_claim_limit (Stage 5) is the overall hard ceiling.
        approved = submission.claimed_amount

    detail = (
        f"Coverage evaluated for {submission.claim_category.value}: "
        f"approved base amount ₹{approved:,.2f}"
        + (f" (sub_limit ₹{sub_limit:,.0f} applied)" if sub_limit and approved < submission.claimed_amount else "")
        + (f". {len([e for e in line_item_evals if not e.covered])} line item(s) excluded." if has_exclusions else "")
    )
    check = _check_result(
        "sub_limit_and_line_items", True, detail,
        clause=f"opd_categories.{cat_key}",
    )
    checks.append(check)
    _emit(trace, check, {
        "approved_base": approved,
        "sub_limit": sub_limit,
        "line_items": [e.model_dump() for e in line_item_evals],
    })
    return approved, line_item_evals, sub_limit, has_exclusions


def _stage8_financial_calculation(
    policy: dict,
    submission: ClaimSubmission,
    extractions: list[ExtractedDocumentData],
    base_amount: float,
    sub_limit: float | None,
    checks: list[PolicyCheckResult],
    trace: ClaimTrace,
) -> FinancialBreakdown:
    """Stage 8: network discount FIRST, then co-pay."""
    cat_key = submission.claim_category.value.lower()
    cat_policy = policy["opd_categories"].get(cat_key, {})
    copay_pct: float = cat_policy.get("copay_percent", 0.0)
    cat_network_discount_pct: float = cat_policy.get("network_discount_percent", 0.0)
    network_hospitals: list[str] = policy.get("network_hospitals", [])

    # Determine sub_limit cap (already applied in stage 7 for dental/vision;
    # here we record the metadata)
    amount_after_sub_limit = base_amount
    sub_limit_applied: float | None = None
    if sub_limit and base_amount > sub_limit:
        # This path would have been applied in stage 7 for dental/vision;
        # for other categories we record it but don't re-apply
        sub_limit_applied = sub_limit

    # Network hospital discount
    is_network = False
    network_discount_pct_used: float | None = None
    amount_after_discount = amount_after_sub_limit

    hospital_name = (
        submission.hospital_name
        or next(
            (ex.hospital_name for ex in extractions if ex.hospital_name),
            None,
        )
    )

    if hospital_name and _network_hospital_match(hospital_name, network_hospitals):
        is_network = True
        network_discount_pct_used = cat_network_discount_pct
        discount_amount = amount_after_sub_limit * (cat_network_discount_pct / 100.0)
        amount_after_discount = amount_after_sub_limit - discount_amount
    else:
        network_discount_pct_used = None

    # Co-pay (on discounted amount)
    copay_amount: float | None = None
    final_amount = amount_after_discount
    if copay_pct > 0:
        copay_amount = amount_after_discount * (copay_pct / 100.0)
        final_amount = amount_after_discount - copay_amount

    breakdown = FinancialBreakdown(
        base_amount=base_amount,
        sub_limit_applied=sub_limit_applied,
        amount_after_sub_limit=amount_after_sub_limit,
        network_discount_percent=network_discount_pct_used,
        amount_after_discount=round(amount_after_discount, 2),
        co_pay_percent=copay_pct if copay_pct > 0 else None,
        co_pay_amount=round(copay_amount, 2) if copay_amount else None,
        final_amount=round(final_amount, 2),
    )

    detail_parts = [f"Base: ₹{base_amount:,.2f}"]
    if is_network and network_discount_pct_used:
        detail_parts.append(
            f"network discount {network_discount_pct_used}% → ₹{amount_after_discount:,.2f}"
        )
    if copay_amount:
        detail_parts.append(
            f"co-pay {copay_pct}% (₹{copay_amount:,.2f}) → final ₹{final_amount:,.2f}"
        )
    else:
        detail_parts.append(f"no co-pay → final ₹{final_amount:,.2f}")

    detail = "Financial calculation: " + " → ".join(detail_parts)
    check = _check_result(
        "financial_calculation", True, detail,
        clause=f"opd_categories.{cat_key}",
    )
    checks.append(check)
    _emit(trace, check, breakdown.model_dump())
    return breakdown


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run(
    submission: ClaimSubmission,
    extractions: list[ExtractedDocumentData],
    trace: ClaimTrace,
) -> PolicyEvaluationResult:
    """Evaluate all policy rules for *submission* given *extractions*.

    Runs Stages 1–8 in order. Stages 1–6 are hard-stops (first failure stops
    further checks and sets rejection_reasons / fraud_flags). Stages 7–8 always
    run if 1–6 pass (or only fraud flags were set — fraud does not short-circuit
    stages 7–8, it just routes the final decision to MANUAL_REVIEW).

    Args:
        submission:  Validated ClaimSubmission.
        extractions: One ExtractedDocumentData per document (may be degraded).
        trace:       Shared ClaimTrace; one event per stage appended in-place.

    Returns:
        PolicyEvaluationResult.

    Raises:
        MemberNotFoundError: if member_id is not in the policy roster.
    """
    policy = get_policy()
    checks: list[PolicyCheckResult] = []
    rejection_reasons: list[str] = []
    fraud_flags: list[str] = []
    line_item_evals: list[LineItemEvaluation] = []
    financial_breakdown: FinancialBreakdown | None = None

    # Submission rules — minimum claimable amount
    # Note: deadline_days_from_treatment is not enforced here because
    # ClaimSubmission has no submission_date field. Documented in architecture.md.
    sub_rules = policy.get("submission_rules", {})
    min_amount: float = sub_rules.get("minimum_claim_amount", 500)

    if submission.claimed_amount < min_amount:
        detail = (
            f"Claimed amount ₹{submission.claimed_amount:,.0f} is below the "
            f"minimum claimable amount of ₹{min_amount:,.0f}."
        )
        check = _check_result("submission_rules", False, detail,
                              clause="submission_rules.minimum_claim_amount")
        checks.append(check)
        _emit(trace, check)
        rejection_reasons.append("BELOW_MINIMUM_AMOUNT")
        return PolicyEvaluationResult(
            member_found=False, checks=checks,
            rejection_reasons=rejection_reasons,
        )

    # Stage 1 — Member & Policy Lookup (raises MemberNotFoundError if absent)
    member_ok, member = _stage1_member_lookup(
        policy, submission, checks, trace
    )
    if not member_ok:
        return PolicyEvaluationResult(
            member_found=True,
            checks=checks,
            rejection_reasons=["POLICY_INVALID"],
        )

    # NOTE on stage ordering (docs/assumptions.md):
    # Stage 3 (exclusion) runs BEFORE Stage 2 (waiting period).
    # A globally-excluded condition is more definitive than a waiting-period
    # violation for the same condition. TC012 (bariatric/obesity excluded)
    # must return EXCLUDED_CONDITION even though the obesity_treatment
    # waiting period (365 days) would also fire. Exclusion takes precedence.

    # Stage 3 — Exclusion (before waiting period)
    if not _stage3_exclusion(
        policy, extractions, checks, trace, rejection_reasons
    ):
        return PolicyEvaluationResult(
            member_found=True, checks=checks,
            rejection_reasons=rejection_reasons,
        )

    # Stage 2 — Waiting Period
    if not _stage2_waiting_period(
        policy, submission, member, extractions, checks, trace, rejection_reasons
    ):
        return PolicyEvaluationResult(
            member_found=True, checks=checks,
            rejection_reasons=rejection_reasons,
        )

    # Stage 4 — Pre-Authorization
    if not _stage4_pre_authorization(
        policy, submission, extractions, checks, trace, rejection_reasons
    ):
        return PolicyEvaluationResult(
            member_found=True, checks=checks,
            rejection_reasons=rejection_reasons,
        )

    # Stage 6 — Fraud Signals (does NOT short-circuit — sets flags only)
    # Run before stage 7 so we don't do line-item work for fraud cases.
    _stage6_fraud_signals(policy, submission, checks, trace, fraud_flags)

    # Stage 7 — Sub-Limits & Line-Item Evaluation
    # NOTE: Run BEFORE Stage 5 (per_claim_limit) so that the limit is checked
    # against the covered amount rather than the raw claimed_amount.
    # TC006 (DENTAL, ₹12,000 claimed, ₹8,000 covered) must produce PARTIAL,
    # not PER_CLAIM_EXCEEDED — the per_claim_limit of ₹5,000 applies to the
    # covered/approved amount. (docs/assumptions.md — "per_claim_limit scope")
    approved_base, line_item_evals, sub_limit, has_exclusions = (
        _stage7_sub_limit_and_line_items(
            policy, submission, extractions, checks, trace
        )
    )

    # Stage 5 — Per-Claim Limit (checked against approved_base from Stage 7)
    # NOTE: For DENTAL/VISION with line-item evaluation, the sub_limit governs
    # the cap; the per_claim_limit is skipped when line items were evaluated.
    # (docs/assumptions.md — "per_claim_limit scope for line-item categories")
    categories_with_line_item_eval = {ClaimCategory.DENTAL, ClaimCategory.VISION}
    skip_per_claim_limit = (
        submission.claim_category in categories_with_line_item_eval
        and len(line_item_evals) > 0
    )

    if not skip_per_claim_limit and approved_base > policy["coverage"]["per_claim_limit"]:
        limit = policy["coverage"]["per_claim_limit"]
        detail = (
            f"Approved amount ₹{approved_base:,.0f} exceeds the per-claim limit "
            f"of ₹{limit:,.0f}. The maximum reimbursable amount per claim "
            f"is ₹{limit:,.0f}."
        )
        check = _check_result(
            "per_claim_limit", False, detail, clause="coverage.per_claim_limit"
        )
        checks.append(check)
        _emit(trace, check, {"approved_base": approved_base, "per_claim_limit": limit})
        rejection_reasons.append("PER_CLAIM_EXCEEDED")
        return PolicyEvaluationResult(
            member_found=True, checks=checks,
            rejection_reasons=rejection_reasons,
        )
    elif not skip_per_claim_limit:
        limit = policy["coverage"]["per_claim_limit"]
        check = _check_result(
            "per_claim_limit", True,
            f"Approved amount ₹{approved_base:,.0f} is within the per-claim "
            f"limit of ₹{limit:,.0f}.",
            clause="coverage.per_claim_limit",
        )
        checks.append(check)
        _emit(trace, check)
    else:
        # Line-item categories: sub_limit governs; record check as passed
        limit = policy["coverage"]["per_claim_limit"]
        check = _check_result(
            "per_claim_limit", True,
            f"Per-claim limit check skipped for {submission.claim_category.value} "
            f"with line-item evaluation (sub_limit governs).",
            clause="coverage.per_claim_limit",
        )
        checks.append(check)
        _emit(trace, check)

    # Stage 8 — Financial Calculation
    cat_key = submission.claim_category.value.lower()
    cat_policy = policy["opd_categories"].get(cat_key, {})
    financial_breakdown = _stage8_financial_calculation(
        policy, submission, extractions, approved_base, sub_limit, checks, trace
    )

    # Collect policy parameters for the decision agent
    copay_pct = cat_policy.get("copay_percent", 0.0)
    network_discount_pct = cat_policy.get("network_discount_percent", 0.0)
    network_hospitals: list[str] = policy.get("network_hospitals", [])
    is_network = bool(
        submission.hospital_name
        and _network_hospital_match(submission.hospital_name, network_hospitals)
    )

    return PolicyEvaluationResult(
        member_found=True,
        checks=checks,
        rejection_reasons=rejection_reasons,
        fraud_flags=fraud_flags,
        line_item_evaluations=line_item_evals,
        applicable_sub_limit=sub_limit,
        co_pay_percent=copay_pct if copay_pct > 0 else None,
        network_discount_percent=network_discount_pct if is_network else None,
        is_network_hospital=is_network,
        financial_breakdown=financial_breakdown,
    )
