---
inclusion: always
---

# Tech Stack

> Edit this file FIRST, before Kiro writes any code, to match what you actually
> want to use. Kiro will follow whatever is written here — keep it accurate so
> it doesn't drift between sessions or invent new dependencies.

## Backend
- Language: Python 3.11+
- Framework: FastAPI (async-first, good fit for concurrent extraction calls)
- Validation: Pydantic v2 for all schemas (claim input, extraction output,
  policy results, trace events, final decision)
- Async: use `async`/`await` for all LLM calls and document processing so
  multiple documents can be extracted concurrently with `asyncio.gather`

## LLM integration
- Provider: Anthropic Claude API (claude-sonnet family for extraction/
  reasoning; consider a cheaper/faster model for simple classification steps
  like document-type detection)
- Use tool use / structured output (forced JSON via tool schema) for every
  LLM call that feeds downstream logic — never parse free-text LLM output
  with regex
- Vision: send document images/PDF pages directly to the model for
  extraction (base64)
- Wrap every LLM call with: timeout, retry (max 1-2 retries with backoff),
  and a typed fallback result on final failure

## Policy / rules engine
- Plain Python over the loaded `policy_terms.json` — deterministic, unit
  testable, no LLM involved for arithmetic (co-pay, sub-limits, waiting
  periods)
- LLM may assist ONLY for fuzzy mapping (e.g. "which coverage category does
  this treatment fall under") and that mapping decision must itself be
  logged in the trace with confidence

## Storage
- SQLite (or in-memory dict store for the assignment scope) for claim
  records + traces — keep the persistence layer behind an interface so it
  can be swapped for Postgres later
- `policy_terms.json` loaded once at startup, cached in memory

## Frontend
- React + Vite (or plain HTML/JS if time is tight) — needs two views:
  1. Claim submission form (member, treatment type, claimed amount, file
     upload)
  2. Decision review view (decision, approved amount, confidence, full
     trace rendered as a readable timeline/checklist)

## Testing
- pytest + pytest-asyncio
- Mock all LLM calls in unit tests (no live API calls in CI)
- Separate integration test that runs `test_cases.json` end-to-end (this
  becomes your eval report)

## Deployment (pick one and document why)
- Local: `docker-compose up` with a single Dockerfile for backend +
  frontend, or
- Hosted: Render / Railway / Fly.io free tier for a deployed URL

## Things NOT to introduce without updating this file
- New LLM providers, new frontend frameworks, new databases. If a need
  arises mid-build, update this file first so the decision is documented and
  consistent across sessions.
