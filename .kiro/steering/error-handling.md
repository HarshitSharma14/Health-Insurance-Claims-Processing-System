---
inclusion: always
---

# Error Handling & Graceful Degradation

Requirement #6 ("the system must not crash") is graded as part of System
Design and Engineering Quality. Treat failure handling as a designed
behavior, not a try/except sprinkled in afterward.

## Core principle
Every component has a **typed degraded output** for every way it can fail.
The orchestrator never receives a raw exception from a pipeline stage during
normal operation — only from truly unexpected bugs, which should be rare and
caught at the top level as a last resort.

## Failure-injection test hook (`simulate_component_failure`)
`test_cases.json` TC011 sets `simulate_component_failure: true` on the
claim submission to test graceful degradation end-to-end. When this flag is
present:
- The orchestrator forces ONE designated component (pick one and document
  the choice — e.g. the fraud-signal check, or one extraction call) down its
  degraded path as described above, even if it would otherwise succeed.
- The pipeline must still produce a `ClaimDecision` (TC011 expects
  `APPROVED`), with:
  - A trace event with `status: "degraded"` naming the skipped/failed
    component.
  - `confidence_score` measurably lower than the equivalent non-degraded
    case.
  - `reason` / trace including an explicit note recommending manual review
    due to incomplete processing.
- This flag should be wired through every layer (`ClaimSubmission` →
  orchestrator → the targeted component) as a simple boolean, not a hidden
  global — it's a deliberate test seam, document it as such.

## Failure modes and required handling

### LLM timeout / API error (extraction or fuzzy policy mapping)
- Retry once with backoff (configurable, default 1 retry).
- On second failure: return `ExtractedDocumentData` with
  `overall_confidence: 0.0`, `is_partial: True`,
  `extraction_notes: "Extraction failed after retry: <error type>"`.
- Trace event: `status: "degraded"`, summary explains the timeout and that
  this document's data could not be used — downstream decision should weight
  this toward `MANUAL_REVIEW`.

### Malformed/unparseable LLM output (structured output validation fails)
- Treat identically to a timeout: one retry with a stricter prompt, then
  degrade as above. Never let a Pydantic `ValidationError` propagate past the
  extraction agent boundary.

### Unreadable / corrupted document (e.g. blank scan, unsupported format)
- Document Verification stage should catch this where possible (e.g. file
  can't be opened) and report it as a missing-document case with a specific
  message ("The file `xyz.pdf` could not be opened — please re-upload a
  valid PDF or image of the hospital bill").
- If it slips through to extraction, treat as a partial/zero-confidence
  extraction as above.

### Member not found in policy_terms.json roster
- Policy Evaluation Agent returns `PolicyEvaluationResult(member_found=False, ...)`.
- Decision Agent maps this directly to `MANUAL_REVIEW` with reason "Member
  ID not found in policy records — requires manual verification."
- Never silently default to "approved" or skip policy checks.

### policy_terms.json missing/malformed at startup
- Hard failure at startup is acceptable (fail fast, don't serve traffic with
  no policy data) — but this is the ONE place a hard crash is OK, and it
  should happen before accepting any claims, with a clear startup log.

### Partial pipeline failure with multiple documents
- If 2 of 3 uploaded documents extract successfully and 1 fails, continue
  with the 2 that succeeded. Decision Agent must factor the missing data into
  confidence and reasoning (e.g. "diagnosis confirmed from prescription, but
  hospital bill amount could not be read — confidence reduced, recommend
  manual review for amount verification").

## What "confidence adjustment" means concretely
Maintain a simple, documented scoring approach (don't over-engineer):
- Start at a base confidence (e.g. 1.0).
- Each degraded extraction event reduces confidence by a documented amount
  proportional to how critical that field is to the decision (e.g. missing
  `amount` on the primary bill is more severe than missing `doctor_name`).
- Each ambiguous/borderline policy check reduces confidence similarly.
- Below a documented threshold → `MANUAL_REVIEW` regardless of what the raw
  policy math says.
- Write the exact thresholds/weights you choose into the architecture doc as
  a documented assumption (per the assignment's "make an assumption, document
  it, move on" guidance).

## Testing requirement
Every failure mode above needs at least one test that simulates the failure
(mocked LLM raising/timeouts, malformed JSON, missing member) and asserts the
system returns a valid `ClaimDecision` (likely `MANUAL_REVIEW`) with a trace
that explains the degradation — never an unhandled exception.
