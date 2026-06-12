---
inclusion: always
---

# Product: Health Insurance Claims Processing System (Plum AI Engineer Assignment)

## What we're building
An automated pipeline that takes a health insurance claim submission (member details,
treatment type, claimed amount, and one or more uploaded documents) and produces a
fully-explained decision: APPROVED, PARTIAL, REJECTED, or MANUAL_REVIEW, with an
approved amount, a reason, and a confidence score.

This is a real workflow Plum's operations team runs manually today. The system
replaces a human reviewer who checks documents against policy terms.

## Non-negotiable behaviors (do not skip or simplify these)
1. **Accept a claim submission** — member details, treatment type, claimed amount,
   one or more documents (image/PDF).
2. **Catch document problems early** — BEFORE any extraction or policy logic runs,
   verify the right document types were uploaded for the claim type. If wrong,
   stop immediately with a SPECIFIC, ACTIONABLE message (e.g. "You uploaded a
   prescription, but a hospitalization claim requires a final hospital bill and
   discharge summary. Please upload these documents."). Never a generic
   "invalid document" error.
3. **Extract structured data** — patient details, diagnosis, treatment, amounts,
   dates, doctor details — from messy real-world documents (handwritten
   prescriptions, rubber stamps over text, phone photos, inconsistent formats).
4. **Make a claim decision** — APPROVED / PARTIAL / REJECTED / MANUAL_REVIEW,
   derived from extracted data + policy_terms.json rules. Always include
   approved_amount, reason, confidence_score.
5. **Full explainability** — every decision must be traceable: what was checked,
   what passed/failed, why the final call was made (e.g. waiting period
   exclusion, sub-limit breach, low confidence due to unreadable document).
6. **Graceful degradation** — component failures (LLM timeout, parse error, bad
   input) must never crash the system. Continue with partial info, mark the
   degraded state in the output, and lower confidence accordingly.

## Policy data
`policy_terms.json` is the single source of truth for coverage categories,
sub-limits, co-pay rules, waiting periods, exclusions, pre-authorization
requirements, network hospitals, and the member roster. NEVER hardcode policy
numbers/rules in code — always read from this file.

Concrete shapes from the actual file (don't hardcode the values, but know
this is the shape of the data):
- `claim_category` values: `CONSULTATION`, `DIAGNOSTIC`, `PHARMACY`,
  `DENTAL`, `VISION`, `ALTERNATIVE_MEDICINE`
- Document types: `PRESCRIPTION`, `HOSPITAL_BILL`, `LAB_REPORT`,
  `PHARMACY_BILL`, `DENTAL_REPORT`, `DIAGNOSTIC_REPORT`, `DISCHARGE_SUMMARY`
- `document_requirements[claim_category]` defines required/optional doc
  types per category — this drives Document Verification.
- See `decision-logic.md` for the full test-case-derived decision algorithm
  (waiting periods, exclusions, pre-auth, per-claim limit, fraud signals,
  sub-limits, network discount → co-pay ordering, line-item evaluation).

## What "done" looks like (grading weights — keep these front of mind)
- **System Design (30%)** — clean component separation, well-reasoned
  architecture, holds up under failure, scalable story for 10x load.
- **Engineering Quality (25%)** — clear code, error handling, data modeling,
  async where it matters, real test coverage.
- **Observability (20%)** — full reconstruction of "why this decision" from the
  trace alone.
- **AI Integration (15%)** — LLMs used thoughtfully, structured + validated
  outputs, failure handled.
- **Document Verification (10%)** — early detection works, error messages are
  specific and actionable.
- **Bonus** — multi-agent architecture earns extra System Design credit.

## Deliverables to keep in mind while building
- Working system (UI + deployed or local setup instructions), source on
  GitHub/GitLab with clean commit history.
- Architecture document (components, interactions, rejected alternatives,
  limitations, 10x scaling plan).
- Component contracts (input/output/errors per component, precise enough to
  reimplement without reading the code).
- Eval report: all 12 cases from `test_cases.json`, decision + full trace +
  match/mismatch explanation.
- Demo video (8-12 min): early document-error stop, full end-to-end approval
  with trace, one proud decision + one thing you'd change.

## Timeline
2-3 days. If stuck >2 hours on something, make a documented assumption and move on.
