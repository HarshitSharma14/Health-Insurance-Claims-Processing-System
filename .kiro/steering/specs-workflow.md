---
inclusion: manual
---

# Spec Workflow Guide (reference with #specs-workflow when starting a new component)

Use Kiro's spec workflow (sidebar → Specs → "Create Spec", or `/spec` in
chat) for each of the components below, one at a time. For each, Kiro will
generate `requirements.md` → `design.md` → `tasks.md` and then execute tasks
incrementally with your approval at each stage.

## Recommended spec order
1. **document-verification** — "Build the document verification agent that
   checks uploaded documents against required documents per claim type from
   policy_terms.json and returns a specific, actionable error when documents
   are wrong or missing, per data-contracts.md and product.md."
2. **extraction-pipeline** — "Build the extraction agent(s) that take
   uploaded documents and return structured ExtractedDocumentData per
   data-contracts.md, using the LLM with structured/tool-call output, vision
   input, retries, and graceful degradation per error-handling.md."
3. **policy-engine** — "Build the policy evaluation agent that loads
   policy_terms.json and runs all applicable checks (member lookup, waiting
   periods, sub-limits, co-pay, exclusions, network hospital, pre-auth),
   returning PolicyEvaluationResult per data-contracts.md."
4. **decision-orchestrator** — "Build the orchestrator that runs the
   pipeline end-to-end: verification → extraction → policy evaluation →
   decision, producing a ClaimDecision and ClaimTrace per observability.md,
   handling all failure modes from error-handling.md."
5. **trace-and-explainability** — only if the trace assembly needs to be its
   own spec beyond what's built in step 4; often this folds into step 4.
6. **frontend** — "Build the claim submission UI and decision/trace review
   UI per tech-stack.md, rendering the trace as a readable timeline."
7. **eval-harness** — "Build a script that runs all 12 cases from
   test_cases.json through the pipeline and produces an eval report
   (actual vs expected decision, full trace, match/mismatch explanation)
   per testing.md."

## Tips for each spec
- Before approving `requirements.md`, sanity-check it against
  `product.md` — make sure document verification, explainability, and
  graceful degradation requirements are reflected for EVERY component, not
  just the ones where they seem obviously relevant.
- Before approving `design.md`, check it doesn't contradict
  `architecture.md`. If it proposes something better, update
  `architecture.md` to match (and note the change) rather than letting them
  diverge.
- Work through `tasks.md` incrementally — don't let Kiro batch-execute
  everything unattended for a component this central to the grade; review
  the policy-engine and decision-orchestrator outputs especially closely
  since they encode the actual business logic being evaluated.
