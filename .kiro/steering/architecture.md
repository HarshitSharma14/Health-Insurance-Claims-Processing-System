---
inclusion: always
---

# Architecture: Multi-Agent Claims Pipeline

## High-level shape
A pipeline of focused agents/components orchestrated by a central
**Claim Orchestrator**, each appending structured events to a shared
**Trace** object. The orchestrator decides whether to proceed, retry,
degrade, or short-circuit at each stage.

```
Claim Submission
      │
      ▼
[1] Document Verification Agent  ──(fail)──► STOP, return actionable error
      │ (pass)
      ▼
[2] Extraction Agent(s)  (one per document, can run concurrently)
      │
      ▼
[3] Policy Evaluation Agent  (reads policy_terms.json)
      │
      ▼
[4] Decision Agent  (combines extraction + policy results)
      │
      ▼
[5] Trace Compiler  (assembles full explainability record)
      │
      ▼
Claim Decision + Trace  →  UI
```

## Component responsibilities

### 1. Document Verification Agent
- Input: claim type + list of uploaded documents (with quick classification —
  e.g. "looks like a prescription" vs "looks like a hospital bill").
- Determines required document set for the claim type from
  `policy_terms.json` → `document_requirements[claim_category]`.
- Three distinct failure modes, each with its own message shape (see
  `decision-logic.md` Stage 0 and `data-contracts.md`
  `VerificationFailureType`):
  1. Wrong/missing document type → name what was uploaded and what's
     required instead.
  2. A required document is present but unreadable → ask for that specific
     document to be re-uploaded (do NOT reject the claim).
  3. Documents disagree on patient identity → surface the specific names
     found on each document.
- Any of these returns `passed: false` and STOPS the pipeline before
  extraction/policy evaluation — `decision` is `null`, not `MANUAL_REVIEW`.
- This is the ONLY stage that can hard-stop the pipeline before extraction.

### 2. Extraction Agent(s)
- One extraction call per document (parallelizable — use async/concurrent
  execution since these are independent LLM calls).
- Uses vision-capable LLM with a structured output schema (see
  `data-contracts.md`) to pull patient details, diagnosis, treatment, amounts,
  dates, doctor details, hospital/network info.
- Each extraction returns a per-field confidence and an `is_legible` /
  `partial` flag so downstream stages know what to trust.
- On failure (timeout, bad parse), returns a degraded result rather than
  throwing — see `error-handling.md`.

### 3. Policy Evaluation Agent
- Pure rules engine (NOT an LLM call, except where noted below) operating
  over `policy_terms.json`. Implements Stages 1-8 from `decision-logic.md`
  in order: member/policy lookup → waiting periods → exclusions →
  pre-authorization → per-claim limit → fraud signals → sub-limits &
  line-item evaluation → financial calculation (network discount, then
  co-pay).
- The waiting-period and exclusion stages need fuzzy/semantic matching of
  free-text diagnosis/treatment strings against `policy_terms.json` keys
  (e.g. "Type 2 Diabetes Mellitus" → `diabetes`, "Morbid Obesity" →
  "Obesity and weight loss programs"). This is the one place an LLM call is
  appropriate inside this agent — log the matched key + confidence as part
  of the relevant `PolicyCheckResult`.
- Returns a list of discrete `PolicyCheckResult` items (one per stage/rule),
  plus `rejection_reasons`, `fraud_flags`, and `line_item_evaluations` as
  defined in `data-contracts.md`. This list IS the backbone of the trace.
- See `decision-logic.md` for the full, test-case-derived specification of
  every stage — do not re-derive this logic from `policy_terms.json` alone
  without cross-checking against `test_cases.json`.

### 4. Decision Agent
- Combines extraction confidence + policy check results into the final
  `ClaimDecision`.
- Decision logic (illustrative — refine against `test_cases.json`):
  - Any hard policy failure (exclusion, waiting period not met) →
    `REJECTED`.
  - All checks pass, high extraction confidence, amount within sub-limits →
    `APPROVED` (approved_amount = claimed amount minus co-pay).
  - Amount exceeds sub-limit but claim otherwise valid → `PARTIAL`
    (approved_amount = sub-limit minus co-pay).
  - Low extraction confidence, ambiguous policy mapping, or missing
    pre-authorization on a borderline case → `MANUAL_REVIEW`.
- Confidence score = function of (extraction confidence, number/severity of
  ambiguous policy checks, document legibility).

### 5. Trace Compiler
- Not really a separate "agent" — a structural guarantee. Every component
  above writes to a shared trace list as it executes. This component just
  assembles/orders/serializes the final trace for the API response and UI.
- See `observability.md` for the exact trace schema.

## Why this shape (document rejected alternatives here as you make them)
- Single mega-prompt to "do everything" was rejected: impossible to make
  individual failures explainable or gracefully degradable, and policy math
  (co-pay, sub-limits) should be deterministic code, not LLM arithmetic.
- Orchestrator + shared trace was chosen over peer-to-peer agent messaging
  for simplicity and easier debugging within the assignment timeline — note
  in the architecture doc that a message-bus/event-driven version would be
  the 10x-scale evolution.

## Scaling notes (for the architecture document)
- Extraction agents are the bottleneck (LLM-bound) — design them to be
  stateless and horizontally scalable (e.g. queue + worker pool).
- Policy evaluation is cheap/deterministic — can run synchronously even at
  scale.
- At 10x load: move orchestration to an async job queue (claim submitted →
  202 Accepted → poll/webhook for result), cache policy_terms.json in memory
  per worker, consider a vector/db lookup for member roster instead of
  scanning JSON.

## Project structure (adjust as the codebase grows, keep this updated)
```
/app
  /agents
    document_verifier.py
    extractor.py
    policy_evaluator.py
    decision_maker.py
  /orchestrator
    pipeline.py
  /schemas        # Pydantic models — see data-contracts.md
  /policy
    loader.py     # reads policy_terms.json, never hardcode rules
  /trace
    trace.py
  /api
    routes.py
/frontend
/tests
policy_terms.json
test_cases.json
```
