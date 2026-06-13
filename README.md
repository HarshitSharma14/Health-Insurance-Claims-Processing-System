# Plum Health Insurance Claims Processing System

Automated multi-agent pipeline for processing employee health insurance claims.
Produces APPROVED / PARTIAL / REJECTED / MANUAL_REVIEW decisions with a full processing trace.

**Eval result: 12/12 test cases passing** — see `eval/eval_report.md`.

---

## Quick start

### Prerequisites

- **Python 3.12** (not 3.13/3.14 — `pydantic-core` has no wheels for those versions yet)
- **Node.js 18+** (for the frontend)
- An **Anthropic API key** (`ANTHROPIC_API_KEY`)

### 1. Clone and set up Python environment

```bash
# Use Python 3.12 explicitly (macOS Homebrew example)
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set:  ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Run the backend

```bash
uvicorn app.api.routes:app --reload --port 8000
```

API docs (Swagger UI): http://localhost:8000/docs

### 4. Run the frontend (separate terminal)

```bash
cd frontend
npm install
npm run dev
```

UI: http://localhost:5173 — proxies `/claims` and `/health` to the backend automatically.

### 5. Run tests

```bash
pytest          # 132 tests, no live API calls required
```

### 6. Run the eval harness

```bash
python eval/run_eval.py   # runs all 12 test cases, prints summary, writes eval/eval_report.md
```

---

## Project structure

```
app/
  agents/
    document_verifier.py   # Stage 0: verify doc types, legibility, patient identity
    extractor.py           # LLM vision extraction (one per doc, concurrent)
    policy_evaluator.py    # Stages 1-8: deterministic rules engine
    decision_maker.py      # Confidence scoring + final decision routing
  orchestrator/
    pipeline.py            # Wires all stages; handles failure, trace, persistence
  schemas/                 # All Pydantic v2 models (claim, extraction, policy, decision, trace)
  policy/
    loader.py              # Loads policy_terms.json at startup; fail-fast if missing
  trace/
    trace.py               # ClaimTrace, TraceEvent, new_trace(), append_event()
  api/
    routes.py              # FastAPI: POST /claims, POST /claims/json, GET /claims/{id}
frontend/
  src/
    components/
      ClaimForm.tsx        # Claim submission form (multipart POST /claims)
      DecisionView.tsx     # Decision + trace timeline display
    App.tsx
eval/
  run_eval.py              # Eval harness: runs test_cases.json, writes eval_report.md
  eval_report.md           # Generated report (12/12 passing)
docs/
  architecture.md          # Full architecture document
  assumptions.md           # All documented judgment calls
tests/                     # Mirrors app/ structure, 132 tests, all mocked
policy_terms.json          # Policy configuration, coverage rules, member roster
test_cases.json            # 12 test scenarios with expected outcomes
```

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/claims` | Submit a claim (multipart form + file uploads) |
| `POST` | `/claims/json` | Submit a claim as JSON with optional `pre_extracted_documents` (eval/testing) |
| `GET` | `/claims/{claim_id}` | Retrieve a past decision + trace by ID |
| `GET` | `/health` | Readiness probe |

All responses are wrapped:
```json
{ "type": "verification_failure" | "decision", "data": { ... } }
```

### Example: submit via JSON for testing

```bash
curl -X POST http://localhost:8000/claims/json \
  -H "Content-Type: application/json" \
  -d '{
    "member_id": "EMP001",
    "policy_id": "POL001",
    "claim_category": "CONSULTATION",
    "treatment_date": "2024-11-01",
    "claimed_amount": 1500,
    "hospital_name": "City General Hospital",
    "documents": [
      {"actual_type": "PRESCRIPTION", "file_id": "rx1", "patient_name_on_doc": "Priya Sharma"},
      {"actual_type": "HOSPITAL_BILL", "file_id": "bill1", "patient_name_on_doc": "Priya Sharma"}
    ]
  }'
```

---

## Architecture

See `docs/architecture.md` for the full design document including:
- Component responsibilities and pipeline diagram
- What was considered and rejected (single mega-prompt, event-driven orchestration)
- Key trade-offs (keyword matching vs LLM semantic matching, per_claim_limit vs sub_limit)
- Scaling notes (async job queue, horizontal extraction workers, persistent store)

---

## Deliverables checklist

| Deliverable | Status |
|-------------|--------|
| Working backend system | ✅ All 4 agents + orchestrator |
| Working UI | ✅ Claim form + decision/trace view |
| Architecture document | ✅ `docs/architecture.md` |
| Component contracts | ✅ `.kiro/steering/data-contracts.md` + Pydantic schemas in `app/schemas/` |
| Eval report | ✅ `eval/eval_report.md` (12/12) |
| Clean commit history | ✅ One commit per feature |
| Test coverage | ✅ 132 tests, 0 live API calls |
| Demo video | ⬜ To record |
