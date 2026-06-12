---
inclusion: always
---

# Coding Standards & Workflow

## Code style
- Python: type hints everywhere, Pydantic models for all cross-component
  data (no raw dicts crossing boundaries), `ruff` for lint/format.
- Async functions for anything that calls an LLM or does I/O.
- No magic numbers for policy values — everything policy-related comes from
  `policy_terms.json` via the policy loader, even thresholds that feel like
  "constants" (sub-limits, co-pay %, waiting periods).
- Confidence thresholds / scoring weights that are NOT in policy_terms.json
  (e.g. the MANUAL_REVIEW cutoff) should live in one config module, with a
  comment pointing to where they're documented in the architecture doc as an
  assumption.

## Commit hygiene
The assignment explicitly asks for "clean commit history" — this matters for
grading. Guidelines:
- One logical change per commit (e.g. "Add document verification agent +
  tests", not "wip" x20).
- Conventional-commit-ish prefixes: `feat:`, `fix:`, `test:`, `docs:`,
  `refactor:`.
- Don't commit secrets/API keys — use `.env` + `.env.example`, add `.env` to
  `.gitignore` immediately.
- Commit steering/spec files too — they're part of the project's design
  record and reviewers may look at `.kiro/` to understand your process.

## File/module organization
- Follow the structure in `architecture.md`. If you deviate, update that
  file in the same commit so it never goes stale.
- Keep each agent in its own module with a single public `run(...)`
  function matching its contract in `data-contracts.md`.

## Documenting assumptions
Whenever a judgment call is made (confidence weights, what counts as
"network hospital match", how to handle an ambiguous test case), add a short
note to `docs/assumptions.md` with: what was assumed, why, and what you'd do
differently with more time/information. This feeds directly into the
architecture document and the demo video's "one thing I'd change" segment.

## Security / secrets
- Steering files are part of the repo — never put API keys or sample PII
  from real documents into `.kiro/steering/` or any committed file.
- Use environment variables for the Anthropic API key and any deployment
  secrets.
