# Documented Assumptions

This file records every judgment call made during implementation — what was
assumed, why, and what we'd do differently with more time. Per
`coding-standards.md`, this feeds directly into the architecture document
and the demo video.

---

## LLM model selection
**Assumption:** Use `claude-sonnet-4-5` for document extraction/reasoning (vision-capable,
supports multi-modal input) and `claude-haiku-4-5` for lightweight document-type
classification (cheaper and faster for simple tasks).

**Why:** Extraction needs high accuracy on messy real-world documents; classification
is a simpler task that doesn't justify the cost of Sonnet. Both are in the
`claude-sonnet-4-x` / `claude-haiku-4-x` families specified in tech-stack.md.

**Would change:** Benchmark both models on a held-out document set to validate the
cost/accuracy tradeoff before committing to the split.

---

## MANUAL_REVIEW confidence threshold
**Assumption:** `MANUAL_REVIEW_CONFIDENCE_THRESHOLD = 0.60`

**Why:** A 60% confidence floor gives the system room to approve high-confidence
claims while routing genuinely ambiguous ones (multiple degraded documents,
borderline policy matches) to manual review. Chosen as a starting point to be
calibrated against the eval test results from `test_cases.json`.

**Would change:** Run the 12 test cases and adjust the threshold to minimise
false MANUAL_REVIEW outcomes while keeping all borderline cases routed correctly.

---

## Confidence penalty weights
**Assumption:**
- Degraded extraction (overall_confidence=0.0, is_partial=True): **−0.30** per document
- Partial extraction (0 < overall_confidence < 0.5, is_partial=True): **−0.15** per document
- Ambiguous/borderline policy check (e.g. fuzzy exclusion match with low confidence): **−0.10** per check

**Why:** Missing the primary bill amount is more damaging than a missing doctor name.
These weights are rough but documented so they can be tuned against the eval data.

**Would change:** Assign different weights to different missing fields (e.g.
`amount` > `diagnosis` > `doctor_name`) rather than a flat per-document penalty.

---

## simulate_component_failure target component
**Assumption:** When `simulate_component_failure=True`, the **Extraction Agent** for
the first uploaded document is forced into its degraded path. The orchestrator
detects the flag and passes `force_degraded=True` to that extraction call only.

**Why:** TC011 expects `APPROVED` with lower confidence — forcing extraction degradation
is more realistic than forcing fraud-check degradation (which would produce MANUAL_REVIEW
instead of APPROVED). Extraction degradation reduces confidence but the policy checks
can still pass and produce an APPROVED outcome.

**Would change:** Make the targeted component configurable in the flag payload
(e.g. `{"simulate_component_failure": "extraction"}`) for more precise test control.

---

## Stage ordering: Exclusion before Waiting Period
**Assumption:** Stage 3 (global exclusion check) runs **before** Stage 2 (waiting period).

**Why:** A globally-excluded condition is more definitive than a waiting-period violation for the same condition. TC012 (bariatric/obesity) must return `EXCLUDED_CONDITION` even though the `obesity_treatment` waiting period (365 days) would also fire for the same diagnosis. The exclusion takes precedence because: (a) waiting periods eventually expire but exclusions never do, (b) it gives the member a clearer actionable message.

**Would change:** If the spec is updated to make waiting period take precedence, swap the order back and update TC012 to expect `WAITING_PERIOD`.

---

## per_claim_limit scope for line-item categories
**Assumption:** The `per_claim_limit` (₹5,000) hard-stop **does not apply** to DENTAL and VISION claims when line-item evaluation is performed. The `sub_limit` for those categories (DENTAL: ₹10,000, VISION: ₹5,000) governs the cap instead.

**Why:** TC006 shows a DENTAL claim with ₹12,000 claimed (root canal ₹8,000 + whitening ₹4,000) expected to produce `PARTIAL` with ₹8,000 approved — not `PER_CLAIM_EXCEEDED`. If the per_claim_limit were applied to the approved_base of ₹8,000, it would incorrectly reject the claim. The sub_limit (₹10,000) is the governing ceiling for DENTAL.

**Would change:** Make this configurable per-category in policy_terms.json rather than hardcoded in logic.

---
**Assumption:** Corrupted or unopenable files (e.g. truncated PDF, unsupported format)
are mapped to `VerificationFailureType.UNREADABLE_DOCUMENT` — not a separate enum value.

**Why:** The enum has three values exactly as defined in `data-contracts.md`. The
error-handling spec describes this case as "a missing-document case with a specific
message" — UNREADABLE_DOCUMENT is the closest semantic fit and keeps the enum minimal.

**Would change:** A fourth `CORRUPTED_FILE` type would make the distinction clearer
in the trace/message; worth adding if ops feedback shows confusion between the two.
