---
inclusion: always
---

# Observability & Explainability

This is 20% of the grade and the single easiest thing to under-build because
it doesn't feel like "the real logic". Treat the trace as a first-class
artifact, not a logging afterthought.

## Goal
Given ONLY the final trace (no code, no debugger), an ops person must be able
to answer:
- What documents were received and were they the right ones?
- What did extraction read from each document, and how confident was it?
- Which policy rules were checked, which passed/failed, and why?
- Why was the final decision what it was?
- Did anything degrade (timeout, low confidence, partial read) and how did
  that affect the outcome?

## ClaimTrace schema (append-only, every stage writes to this)
```python
class TraceEvent(BaseModel):
    stage: str                 # "document_verification", "extraction",
                                # "policy_evaluation", "decision"
    component: str             # which agent/function produced this
    timestamp: datetime
    status: Literal["ok", "degraded", "failed"]
    summary: str                # one-line human-readable summary
    details: dict               # stage-specific structured payload
                                 # e.g. for policy: the PolicyCheckResult list
                                 # e.g. for extraction: field_confidence map

class ClaimTrace(BaseModel):
    claim_id: str
    events: list[TraceEvent]
    final_decision_explanation: str   # plain-English narrative tying
                                       # together the key events that drove
                                       # the decision
```

## Rules
1. **Every** stage (verification, each extraction call, each policy check
   group, decision) writes at least one `TraceEvent`, even on success — "ok"
   traces matter as much as failure traces for the eval report.
2. **Degraded ≠ silent.** If a stage falls back (e.g. extraction returns
   `overall_confidence: 0.0` after a timeout), the corresponding TraceEvent
   must have `status: "degraded"` and a `summary` explaining what happened
   and how it influenced confidence/decision downstream.
3. **Policy checks are individually traced.** Don't collapse "policy
   evaluation" into one blob — one TraceEvent per check (or one event with a
   `details.checks` list where each item is independently inspectable) so a
   rejection due to "waiting period" is visibly distinct from a rejection
   due to "exclusion".
4. **`final_decision_explanation` is mandatory and specific.** Not "claim
   was rejected due to policy" — instead: "Rejected: cataract surgery falls
   under a 2-year waiting period; member's policy started 8 months ago
   (policy_terms.json → waiting_periods.cataract)."
5. **Confidence is explainable, not just a number.** If `confidence_score`
   on the final decision is low, the trace must show WHICH upstream signal
   pulled it down (e.g. "extraction overall_confidence 0.4 due to illegible
   stamp over diagnosis field on hospital_bill.jpg").
6. **The UI must render the trace as a readable timeline/checklist**, not a
   raw JSON dump — this is explicitly called out as a deliverable
   requirement ("show the full trace visible" in the demo).

## For the eval report
For each of the 12 test cases, capture: input → decision produced → full
trace → expected outcome → match/mismatch + explanation if mismatched. The
trace should make WHY a mismatch happened obvious without re-running the
code.
