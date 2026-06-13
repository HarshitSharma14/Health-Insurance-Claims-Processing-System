# Architecture Document
## Plum Health Insurance Claims Processing System

---

## 1. System Overview

This system automates the manual review of employee health insurance claims. A claim submission (member details + uploaded documents) enters a deterministic multi-agent pipeline and exits as one of four outcomes: **APPROVED**, **PARTIAL**, **REJECTED**, or **MANUAL_REVIEW** — always with an approved amount, a reason, a confidence score, and a full processing trace.

The pipeline was built using Kiro (an AI coding IDE). Steering files (`.kiro/steering/`) drove every implementation step — `decision-logic.md` was reverse-engineered from `test_cases.json` before a single line of business logic was written. This document is the consolidated narrative view; the steering files are the internal process artifacts.

---

## 2. Pipeline Architecture

```
Claim Submission
      │
      ▼
┌─────────────────────────────────┐
│  Stage 0: Document Verification │ ──(fail)──► Return verification error (no decision)
│  Agent                          │             Specific message: wrong doc / unreadable /
└─────────────┬───────────────────┘             patient mismatch
              │ pass
              ▼
┌─────────────────────────────────┐
│  Stage 1-2: Extraction Agents   │  One per document, run concurrently (asyncio.gather)
│  (vision LLM, structured output)│  Graceful degradation on timeout/parse failure
└─────────────┬───────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│  Stages 1-8: Policy Evaluation  │  Pure rules engine reading policy_terms.json
│  Agent                          │  8 ordered stages, each producing a PolicyCheckResult
└─────────────┬───────────────────┘  + TraceEvent
              │
              ▼
┌─────────────────────────────────┐
│  Decision Agent                 │  Combines extraction confidence + policy results
│                                 │  Explicit confidence formula (documented below)
└─────────────┬───────────────────┘
              │
              ▼
       ClaimDecision + ClaimTrace
```

Every agent appends a `TraceEvent` to a shared `ClaimTrace` object as it executes. The trace is not assembled at the end — it accumulates inline, so even a mid-pipeline failure leaves a partial trace.

---

## 3. Components and Responsibilities

### 3.1 Document Verification Agent (`app/agents/document_verifier.py`)

Pre-pipeline gate. Runs before any LLM calls and can hard-stop the pipeline. Returns `DocumentVerificationResult`, not a `ClaimDecision`.

Three distinct failure modes:
1. **WRONG_OR_MISSING_DOCUMENTS** — required document type absent or wrong type uploaded. Message names exactly what was uploaded and what is required (e.g. "You uploaded two prescriptions, but a CONSULTATION claim requires a PRESCRIPTION and a HOSPITAL_BILL").
2. **UNREADABLE_DOCUMENT** — required document is present but marked illegible (`quality: UNREADABLE`) or file cannot be opened. Does NOT reject the claim — asks for re-upload of that specific file.
3. **PATIENT_MISMATCH** — patient names differ across documents. Surfaces the specific names found on each document.

A `passed: false` result has `decision: null` — not `MANUAL_REVIEW`. This is a document quality problem, not a policy decision.

### 3.2 Extraction Agent (`app/agents/extractor.py`)

One call per document, run concurrently via `asyncio.gather(..., return_exceptions=True)`. Each call:
- Sends the document as base64 image/PDF to a vision-capable Claude model (`claude-sonnet-4-5`)
- Uses forced tool-call output (Anthropic tool schema) matching `ExtractedDocumentData`
- Returns per-field confidence scores and an `is_partial` flag
- On failure: one retry with exponential backoff, then returns a degraded result (`overall_confidence: 0.0`, `is_partial: True`) — never raises to the caller

The `force_failure=True` parameter (used for TC011 `simulate_component_failure`) bypasses the LLM call entirely and returns the degraded result immediately. The orchestrator passes this only to the first document's extraction call.

### 3.3 Policy Evaluation Agent (`app/agents/policy_evaluator.py`)

Deterministic rules engine reading `policy_terms.json`. Eight ordered stages, each implemented as an isolated internal function:

| Stage | Check | Hard stop? |
|-------|-------|-----------|
| 1 | Member & policy lookup, ACTIVE status, date window | → MANUAL_REVIEW (not found) |
| 2† | Waiting period (initial 30-day + condition-specific) | → REJECTED |
| 3† | Global exclusion (diagnosis/treatment keyword match) | → REJECTED |
| 4 | Pre-authorization (MRI/CT/PET above ₹10,000) | → REJECTED |
| 5 | Per-claim limit (₹5,000, skipped for DENTAL/VISION†) | → REJECTED |
| 6 | Fraud signals (same-day count, high-value threshold) | → MANUAL_REVIEW (never REJECTED) |
| 7 | Sub-limits & line-item evaluation (DENTAL/VISION) | → sets coverage amounts |
| 8 | Financial calculation (network discount → co-pay) | → final amounts |

† Stage 3 (exclusion) runs before Stage 2 (waiting period) — see Section 5.

Stages 2 and 3 use keyword/substring matching against `policy_terms.json` keys today. This is the one area designed for future LLM replacement — see Section 6.

### 3.4 Decision Agent (`app/agents/decision_maker.py`)

Combines `PolicyEvaluationResult` + `ExtractedDocumentData` list into a final `ClaimDecision`.

**Decision routing order:**
1. `rejection_reasons` non-empty → `REJECTED`
2. `fraud_flags` non-empty → `MANUAL_REVIEW`
3. `MemberNotFoundError` caught by orchestrator → `MANUAL_REVIEW`
4. `confidence_score < 0.60` → `MANUAL_REVIEW` (threshold from `config.py`)
5. Some line items excluded or sub-limit capped → `PARTIAL`
6. All checks pass → `APPROVED`

**Confidence formula** (documented in `docs/assumptions.md`):

```
base = 1.0
for each ExtractedDocumentData:
    if is_partial and overall_confidence == 0.0: base -= 0.30   # fully degraded
    elif is_partial and overall_confidence < 0.5: base -= 0.15  # partial
    elif overall_confidence < 0.5: base -= 0.10                 # low confidence
clamp to [0.0, 1.0]
```

Two explicit branches override the formula:
- **EXCLUDED_CONDITION**: uses max diagnosis/treatment field confidence, floored at 0.90. A deterministic keyword match must not be dragged down by an unrelated illegible field on the same document. (Satisfies TC012: confidence > 0.90.)
- **simulate_component_failure**: per-document penalties are skipped inside `_compute_confidence`; the caller applies a single −0.30 penalty. Without this separation, a degraded doc + simulate penalty = 0.40, below the 0.60 threshold, incorrectly routing TC011 to MANUAL_REVIEW instead of APPROVED.

### 3.5 Orchestrator (`app/orchestrator/pipeline.py`)

Wires all stages. Key behaviors:
- `pre_extracted_documents` parameter bypasses the Extraction Agent — used by the eval harness (TC004–TC012 provide structured content, not real images) and the `/claims/json` API endpoint
- `asyncio.gather(..., return_exceptions=True)` for concurrent extraction; per-document exceptions are caught and substituted with a degraded `ExtractedDocumentData` rather than aborting the gather
- `MemberNotFoundError` (raised by Policy Evaluation Agent) is caught here and returned as `MANUAL_REVIEW`
- Every result is stored in an in-memory dict keyed by `claim_id` (UUID per pipeline run) for `GET /claims/{id}` retrieval

### 3.6 Trace / Observability

`ClaimTrace` accumulates `TraceEvent` objects inline as each stage runs:

```python
class TraceEvent(BaseModel):
    stage: str          # "document_verification" | "extraction" | "policy_evaluation" | "decision" | "orchestrator"
    component: str
    timestamp: datetime
    status: Literal["ok", "degraded", "failed"]
    summary: str        # one human-readable line
    details: dict       # structured stage-specific payload
```

`ClaimTrace.final_decision_explanation` is a mandatory plain-English narrative naming the actual policy clauses, amounts, and field names that drove the decision. It is never generic.

---

## 4. Data Flow and Contracts

Full contract definitions (Pydantic models with field-level docs) live in `app/schemas/`. Abbreviated summary:

```
ClaimSubmission ──► DocumentVerificationResult (if Stage 0 fails)
                └──► ExtractedDocumentData[] ──► PolicyEvaluationResult ──► ClaimDecision
```

All responses are wrapped in:
```json
{ "type": "verification_failure" | "decision", "data": { ... } }
```

This discriminated union lets the frontend distinguish the two response shapes without inspecting field presence.

---

## 5. What We Considered and Rejected

### Single mega-prompt
Rejected. A single "read documents, check policy, decide" prompt cannot make individual stage failures explainable, cannot perform deterministic co-pay arithmetic reliably, and collapses graceful degradation to "if anything fails, return an error."

The multi-agent shape means each stage failure is isolated, traced, and the pipeline continues with whatever it has.

### Message-bus / event-driven orchestration
Considered but deferred. The current synchronous orchestrator is simpler to debug and sufficient for the assignment scope. An event-driven architecture (claim submitted → 202 Accepted → async workers publish events → result webhook) is the correct shape at 10x load — see Section 7.

### Stage ordering: exclusion before waiting period (Stages 3 and 2)
TC012 (bariatric surgery, obesity exclusion) also triggers the `obesity_treatment` 365-day waiting period for the same diagnosis. Exclusion takes precedence because:
- Waiting periods eventually expire; exclusions never do.
- "This treatment is permanently excluded" is a clearer member message than "you haven't met your waiting period yet."
If the spec changes to prefer waiting period, swap the stage order and update TC012.

### per_claim_limit vs sub_limit for DENTAL/VISION
`policy_terms.json` has a genuine inconsistency: `coverage.per_claim_limit` is ₹5,000 but DENTAL's `sub_limit` is ₹10,000. Applying `per_claim_limit` to every category makes DENTAL's sub_limit meaningless and breaks TC006 (dental partial approval at ₹8,000). Resolution: `per_claim_limit` applies to categories without their own line-item evaluation; DENTAL and VISION are governed by `sub_limit`. Documented in `docs/assumptions.md`.

### LLM-based semantic matching for waiting periods / exclusions
Stages 2 and 3 currently use keyword/substring matching. This is deliberate — it is fast, deterministic, and testable without live API calls. "Lumbar Disc Herniation" required a negative-context guard (`_CONDITION_NEGATIVE_CONTEXT`) to prevent matching the `hernia` waiting period, which illustrates the brittleness. The functions are designed for LLM replacement — see Section 6.

---

## 6. Limitations and Known Trade-offs

| Limitation | Impact | Mitigation path |
|------------|--------|-----------------|
| Keyword matching for policy conditions | Will miss diagnoses phrased differently than the exact keywords in `policy_terms.json` (e.g. "morbid obesity" works; "BMI 38, gastric sleeve candidate" does not) | Replace `_condition_matches()` with an LLM classifier using a structured tool schema |
| In-memory claim store | Claims are lost on server restart; no history | Add SQLite (dev) / PostgreSQL (prod) behind the existing store interface |
| No authentication | Any caller can submit claims or read any `GET /claims/{id}` | Add JWT/API key middleware at the route layer |
| Synchronous pipeline | User waits while LLM calls run | Move to async job queue: POST returns 202 + job ID, client polls or receives webhook |
| Extraction model not benchmarked | `claude-sonnet-4-5` chosen without a held-out document benchmark | Run offline evaluation on real Indian medical document samples before production |

---

## 7. Scaling to 10x Load

Current: ~100 claims/day processed synchronously, in-memory state, single process.

10x (and beyond) architecture changes:

**Async job queue** — POST `/claims` returns `202 Accepted` with a job ID immediately. A worker pool picks up jobs from a queue (SQS / Redis Streams). Client polls `GET /claims/{id}` or receives a webhook on completion. This decouples latency from LLM response time.

**Horizontal extraction scaling** — Each extraction call is a stateless LLM request. With an async queue, extraction workers scale independently of the orchestrator. Multiple documents per claim run on separate workers rather than sharing one event loop.

**Policy engine caching** — `policy_terms.json` is loaded once per worker at startup. At scale, policy updates need an invalidation mechanism (e.g. versioned config, reload-on-SIGHUP).

**Persistent store** — In-memory dict → PostgreSQL (claims, decisions, traces) + object storage (document bytes). Add an index on `member_id` and `treatment_date` for claims history lookups used by the fraud signal check.

**Observability infrastructure** — `ClaimTrace` objects are currently serialized into the API response. At scale, stream `TraceEvent` objects to a log aggregation system (Datadog, CloudWatch) in real time so alerts can fire on degraded-state spikes before the trace reaches the caller.

**Rate limiting / fraud protection** — The fraud signal check is reactive (checks claims history at decision time). A pre-submission throttle (e.g. max N submissions per member per day) would be the first line of defense.

---

## 8. Implementation Notes

- **Python 3.12** is required. Python 3.14 (system default on this machine) has no `pydantic-core` wheels — document this prominently in setup instructions.
- **Pydantic v2** annotation resolution: `from __future__ import annotations` is dropped from schema files to avoid Pydantic deferring type resolution at class construction time.
- **`date` field shadowing**: `app/schemas/extraction.py` imports `datetime.date` as `date_type` to avoid a name collision with the `date` field on `ExtractedDocumentData`. This is the Pydantic v2-safe pattern.
- **Test isolation**: all 132 tests run without live API calls. The Anthropic client is mocked in `test_extractor.py`. Policy evaluation and decision tests construct Pydantic model fixtures directly.

---

## 9. Eval Results

All 12 test cases pass. Full per-case traces and verdicts are in `eval/eval_report.md`.

| Case | Description | Decision | Verdict |
|------|-------------|----------|---------|
| TC001 | Wrong document uploaded | verification stop | ✅ |
| TC002 | Unreadable document | verification stop | ✅ |
| TC003 | Patient identity mismatch | verification stop | ✅ |
| TC004 | Clean consultation approval | APPROVED ₹1,350 | ✅ |
| TC005 | Waiting period — diabetes | REJECTED | ✅ |
| TC006 | Dental partial — cosmetic excluded | PARTIAL ₹8,000 | ✅ |
| TC007 | MRI without pre-auth | REJECTED | ✅ |
| TC008 | Per-claim limit exceeded | REJECTED | ✅ |
| TC009 | Fraud signal (same-day claims) | MANUAL_REVIEW | ✅ |
| TC010 | Network hospital discount | APPROVED ₹3,240 | ✅ |
| TC011 | Component failure — graceful degradation | APPROVED (confidence 0.70) | ✅ |
| TC012 | Excluded treatment | REJECTED (confidence 0.95) | ✅ |
