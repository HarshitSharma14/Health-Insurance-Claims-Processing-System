---
inclusion: always
---

# Testing Standards

"Every significant component must have tests. A system with no tests is
incomplete" — this is explicit in the assignment notes, not optional polish.

## Unit tests (per component)
- Document Verification Agent: test against multiple claim types with
  correct docs, missing docs, wrong-type docs — assert the specific message
  content, not just `passed: False`.
- Extraction Agent: mock the LLM client. Test the happy path (full structured
  response), partial response (some fields null), malformed JSON response
  (triggers degradation), and timeout/exception (triggers degradation).
- Policy Evaluation Agent: this is pure logic over `policy_terms.json` —
  test each rule type independently (waiting period math, sub-limit math,
  co-pay math, exclusion matching, network hospital lookup, member lookup
  including not-found case). These should be fast, deterministic, no mocks
  needed beyond loading a test fixture policy file.
- Decision Agent: test each of the four decision outcomes is reachable given
  the right combination of extraction + policy inputs, including the
  confidence-threshold-triggers-MANUAL_REVIEW path.
- Trace assembly: test that a trace produced by a run with a degraded stage
  actually contains a `status: "degraded"` event with a meaningful summary.

## Integration / eval tests
- One integration test (or script) that loads `test_cases.json`, runs each
  case through the full pipeline, and produces a report comparing actual vs
  expected decision per case. This script IS the basis for the Eval Report
  deliverable — design it to output something directly copy-pasteable into
  that report (e.g. a markdown table + per-case trace dump).
- LLM calls in integration tests: either (a) mock with realistic canned
  responses derived from the sample documents guide, or (b) if making live
  calls, keep this as a separate, explicitly-run suite (not part of default
  `pytest` / CI) to avoid flaky/costly test runs.

## Test data
- Build small fixture files (sample extracted JSON, sample policy snippets)
  under `/tests/fixtures/` rather than relying on live documents for unit
  tests — keeps tests fast and deterministic.

## Conventions
- pytest + pytest-asyncio for async components.
- One test file per component, mirroring the source layout
  (`tests/agents/test_extractor.py` ↔ `app/agents/extractor.py`).
- Test names describe behavior, not implementation:
  `test_rejects_claim_within_waiting_period`, not `test_policy_check_3`.
- Run the full test suite before each meaningful commit — if a hook is set
  up for this, keep it enabled.
