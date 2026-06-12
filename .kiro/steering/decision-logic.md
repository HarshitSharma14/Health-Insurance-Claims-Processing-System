---
inclusion: always
---

# Decision Logic (derived from policy_terms.json + test_cases.json)

This is the concrete algorithm the Policy Evaluation Agent + Decision Agent
must implement. It's derived directly from the real `policy_terms.json` and
all 12 cases in `test_cases.json` — treat this as the spec for that logic,
and treat `test_cases.json` as the acceptance tests for it. Every check below
must produce its own `PolicyCheckResult` / `TraceEvent` (see
observability.md) — never collapse these into one opaque "policy check"
step.

## Real domain values (from policy_terms.json)
- Claim categories (`claim_category`): `CONSULTATION`, `DIAGNOSTIC`,
  `PHARMACY`, `DENTAL`, `VISION`, `ALTERNATIVE_MEDICINE`
- Document types (`actual_type`): `PRESCRIPTION`, `HOSPITAL_BILL`,
  `LAB_REPORT`, `PHARMACY_BILL`, `DENTAL_REPORT`, `DIAGNOSTIC_REPORT`,
  `DISCHARGE_SUMMARY`
- `document_requirements` per category defines `required` and `optional`
  doc types — this is the source of truth for Document Verification, not a
  hardcoded map.
- Rejection reason codes seen in test cases (use these exact strings so the
  eval report lines up): `WAITING_PERIOD`, `EXCLUDED_CONDITION`,
  `PRE_AUTH_MISSING`, `PER_CLAIM_EXCEEDED`.

## Stage 0 — Document Verification (pre-pipeline, can hard-stop)
1. **Required documents check**: for `claim_category`, look up
   `document_requirements[claim_category].required` and confirm each
   required type is present among `actual_type`s. If a required type is
   missing or only wrong types were uploaded, STOP with a message naming
   both the uploaded type(s) and the missing required type(s) (TC001).
2. **Legibility check**: if any document has `quality: "UNREADABLE"`
   (or extraction confidence comes back ~0 for a required document), do
   **not** reject — ask the member to re-upload that *specific* document by
   name/type. This is a distinct outcome from "wrong document" (TC002).
3. **Cross-document identity check**: compare `patient_name` extracted from
   each document. If documents disagree on patient identity, STOP and
   surface the specific names found on each document (TC003) — do not
   proceed to policy evaluation.

If all three pass, proceed to Stage 1. Note: TC001-TC003 expect
`decision: null` — i.e. the pipeline returns a verification-failure response,
not a `ClaimDecision`. Model this as a distinct response type/branch, not as
a `MANUAL_REVIEW`.

## Stage 1 — Member & Policy Lookup
- Look up `member_id` in `policy_terms.json members[]`.
- Not found → `MANUAL_REVIEW` ("member not found, requires manual
  verification").
- Confirm `policy_id` matches and policy is `ACTIVE`, and `treatment_date`
  falls within `policy_holder.policy_start_date` .. `policy_end_date`.

## Stage 2 — Waiting Period Check
- `waiting_periods.initial_waiting_period_days` (30): treatment_date must be
  ≥ member's `join_date` + 30 days for ANY claim.
- `waiting_periods.specific_conditions` maps condition keywords (diabetes,
  hypertension, thyroid_disorders, joint_replacement, maternity,
  mental_health, obesity_treatment, hernia, cataract) to day counts. Match
  the extracted `diagnosis`/`treatment` text against these keys (fuzzy/LLM
  match is fine here — log the matched keyword + confidence in the trace).
- If `treatment_date < join_date + applicable_waiting_days` →
  `REJECTED`, `rejection_reasons: ["WAITING_PERIOD"]`. The message/trace
  MUST state the date the member becomes eligible
  (`join_date + waiting_days`) — TC005 explicitly checks for this.

## Stage 3 — Exclusion Check
- Match extracted `diagnosis`/`treatment` text against
  `exclusions.conditions` (e.g. "Morbid Obesity" / "Bariatric Consultation"
  → "Obesity and weight loss programs" / "Bariatric surgery"). This needs
  fuzzy/semantic matching — log the matched exclusion clause and confidence.
- If matched → `REJECTED`, `rejection_reasons: ["EXCLUDED_CONDITION"]`
  (TC012, expects confidence > 0.90 — i.e. this should be a *high-confidence*
  rejection when the match is clear).
- Category-specific exclusion lists (`dental_exclusions`,
  `vision_exclusions`, and `opd_categories.dental.excluded_procedures` /
  `covered_procedures`) are evaluated at the **line-item level** in Stage 6,
  not here — a dental bill with one excluded line item is `PARTIAL`, not a
  full `REJECTED` (see TC006).

## Stage 4 — Pre-Authorization Check
- `opd_categories.diagnostic.high_value_tests_requiring_pre_auth` (MRI, CT
  Scan, PET Scan) above `pre_auth_threshold` (₹10,000) require pre-auth.
- Detect this from extracted `tests_ordered` / line item descriptions +
  amount. If required and no pre-auth reference present in the claim →
  `REJECTED`, `rejection_reasons: ["PRE_AUTH_MISSING"]`. Message must explain
  pre-auth was required and tell the member how to resubmit with it (TC007).

## Stage 5 — Per-Claim Limit Check
- `coverage.per_claim_limit` (₹5,000): if `claimed_amount` exceeds this →
  `REJECTED`, `rejection_reasons: ["PER_CLAIM_EXCEEDED"]`. Message must state
  both the limit and the claimed amount (TC008).
- Note: this is checked on the *claimed* amount, before sub-limits/line-item
  math — it's a hard ceiling per claim regardless of category.

## Stage 6 — Fraud Signal Check
- Inputs: `claims_history` (if provided on the submission) and
  `fraud_thresholds`.
- `same_day_claims_limit` (2): if the member already has ≥2 claims on the
  same `treatment_date`/submission date, this 3rd+ claim is flagged
  (TC009 — 4th claim that day → flag).
- `monthly_claims_limit` (6), `high_value_claim_threshold` (₹25,000),
  `auto_manual_review_above` (₹25,000), `fraud_score_manual_review_threshold`
  (0.80) — apply analogously if you compute a fraud score.
- Any fraud signal → `MANUAL_REVIEW` (not auto-reject). The output must list
  the *specific signals* that triggered it (e.g. "4th consultation claim
  submitted today, exceeds same-day limit of 2") (TC009).

## Stage 7 — Coverage, Sub-Limits & Line-Item Evaluation
- Each `opd_categories[claim_category]` has its own `sub_limit`,
  `copay_percent`, and (for dental/vision) `covered_procedures` /
  `excluded_procedures` or `covered_items` / `excluded_items`.
- **Line-item evaluation** (primarily for DENTAL/VISION, but apply
  generally where line items exist): for each line item in the hospital
  bill, check its description against `covered_procedures` /
  `excluded_procedures`. Sum amounts for covered items separately from
  excluded items.
  - If ALL line items covered → proceed to financial calc on full amount.
  - If SOME line items excluded → `PARTIAL`. `approved_amount` = sum of
    covered line items only (after discount/co-pay below). The output must
    itemize which line items were approved/rejected and WHY, per item
    (TC006).
  - If `requires_prescription` is true for the category and no prescription
    was provided, that's actually a Stage 0 document-verification concern,
    not here.
- Apply `sub_limit`: the amount carried into financial calc is
  `min(covered_line_items_total_or_claimed_amount, sub_limit)`.

## Stage 8 — Financial Calculation (order matters!)
1. Start with the amount from Stage 7 (covered total, capped at sub-limit).
2. **Network discount first**: if `hospital_name` is in
   `network_hospitals`, apply `network_discount_percent` to reduce the
   amount.
3. **Co-pay second**: apply `copay_percent` (category-specific) to the
   *discounted* amount, and deduct it.
4. `approved_amount` = amount after both steps.
5. The trace/output MUST show this breakdown explicitly — discount amount,
   co-pay amount, and final figure (TC010: ₹4,500 → 20% network discount →
   ₹3,600 → 10% co-pay → -₹360 → **₹3,240**). Getting the order wrong
   (co-pay before discount) produces a different, wrong number — this is
   directly tested.
6. If no exclusions/limit issues and the full claimed amount is approved
   after discount/co-pay → `APPROVED`. If capped by a sub-limit or partial
   line items → `PARTIAL`.

## Stage 9 — Component Failure Simulation (`simulate_component_failure: true`)
- TC011 sets this flag to simulate a mid-pipeline component failure (e.g.
  the fraud-check or one extraction call fails).
- Required behavior: pipeline does NOT crash, still reaches a decision
  (TC011 expects `APPROVED`), but:
  - The trace explicitly states which component failed/was skipped.
  - `confidence_score` is measurably lower than an equivalent full-pipeline
    approval.
  - The output includes a note recommending manual review due to incomplete
    processing, even though the decision itself is `APPROVED`.
- Implementation: treat this flag as a test hook — when present, force the
  designated component's `run()` to take its degraded/failure path (per
  error-handling.md) rather than its normal path, and verify the rest of the
  pipeline handles that gracefully.

## Decision precedence summary
Stages 0-6 are sequential hard-stops/flags (first match wins for
REJECTED/MANUAL_REVIEW outcomes, except document-verification failures in
Stage 0 which short-circuit before any `ClaimDecision` is even produced).
Stage 7-8 only run if nothing in 0-6 rejected/flagged the claim, and produce
APPROVED or PARTIAL. Stage 9 is an orthogonal failure-injection concern that
can apply alongside any of the above.
