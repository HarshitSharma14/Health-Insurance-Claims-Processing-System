# Architecture

## The problem in one line

Take a claim submission, member details plus uploaded documents, and turn it into a
decision that a person can fully understand: approved, partial, rejected, or manual
review, with an amount, a reason, a confidence score, and a trace that explains the
whole thing.

## How I shaped it

I built it as a pipeline of focused agents with a central orchestrator wiring them
together. Each stage does one job and writes to a shared trace object as it runs. The
orchestrator decides whether to keep going, degrade, or stop early.

The flow looks like this:

```
Claim submission
      |
      v
Document verification   -> if it fails, stop here and return an actionable error
      |
      v
Extraction (one call per document, run concurrently)
      |
      v
Policy evaluation (deterministic rules over policy_terms.json)
      |
      v
Decision (combines extraction confidence and policy results)
      |
      v
Claim decision + full trace  ->  UI
```

The trace is not something I assemble at the end. Every stage appends to it as it goes,
so even if something blows up halfway through, the trace still shows everything that
happened up to that point. That turned out to matter a lot for the graceful degradation
behaviour.

## The components

### Document verification

This runs first, before any LLM call, and it is the only stage allowed to hard stop the
pipeline. It returns a verification result, not a claim decision. There are three ways
it can fail, and each one gets its own specific message instead of a generic "invalid
document":

- Wrong or missing documents. It names what you uploaded and what the claim category
  actually requires. For example, if you send two prescriptions for a consultation
  claim that needs a prescription and a hospital bill, it says exactly that and tells
  you which document to add.
- Unreadable document. A required document is there but illegible. This does not reject
  the claim. It asks you to re-upload that one specific file by name.
- Patient mismatch. The names on the documents don't agree. It surfaces the actual
  names it found on each document so the member can sort it out.

When verification fails, the decision field is null. This is deliberately not a manual
review outcome, because a blurry photo is a document quality problem, not a policy
judgment.

### Extraction

One call per document. They run concurrently with `asyncio.gather` because the
documents are independent and the LLM call is the slow part. Each call sends the
document image or PDF to a vision capable Gemini model and asks for structured JSON back
using a response schema, so there is no regex parsing of free text.

Every extraction returns per field confidence and an `is_partial` flag so the stages
downstream know how much to trust it. If a call times out or the output won't parse, it
retries once with backoff and then returns a degraded result with confidence 0.0 rather
than throwing. The caller never sees an exception from this stage during normal
operation.

For the simulated failure test case, there is a flag that makes the first document's
extraction skip the real call and go straight to the degraded result. That lets us prove
the rest of the pipeline copes with a dead component.

### Policy evaluation

This is a plain rules engine, no LLM, reading everything from `policy_terms.json`. None
of the policy numbers are hardcoded. It runs eight stages in order, and each one
produces its own check result and trace event so a rejection for a waiting period looks
different in the trace from a rejection for an exclusion.

The stages are member and policy lookup, waiting period, exclusion, pre authorization,
per claim limit, fraud signals, sub limits with line item evaluation, and finally the
financial calculation. A member who isn't in the roster doesn't crash anything; the
agent raises a typed error that the orchestrator catches and turns into manual review.

Two ordering decisions are worth calling out. Exclusion is checked before waiting
period, because an excluded condition is permanent and a clearer message than "you
haven't waited long enough yet". And the financial calculation applies the network
discount first and then the co-pay, in that order, because doing it the other way around
produces a different and wrong number.

### Decision

This combines the policy result and the extraction confidence into the final answer.
The routing is: any rejection reason means rejected, a fraud flag means manual review, a
member not found means manual review, a confidence score below 0.60 means manual review
regardless of what the policy math said, some excluded line items or a sub limit cap
means partial, and everything clean means approved.

Confidence starts at 1.0 and comes down based on how degraded the extraction was. A
fully degraded document costs more than a partial one, which costs more than a merely
low confidence read. There are two deliberate exceptions. A clear exclusion match keeps
high confidence even if some unrelated field on the document was illegible, because the
keyword match itself is certain. And the simulated failure case applies its penalty once
instead of stacking, so a legitimately approvable claim doesn't get knocked below the
manual review line by double counting.

### Orchestrator and trace

The orchestrator wires the stages together, runs extraction concurrently, catches the
member not found error, and stores each result in an in memory dictionary keyed by claim
id so it can be fetched back later. The trace object accumulates events the whole way
through, and it carries a plain English final explanation that names the actual policy
clauses and amounts that drove the decision.

## What I considered and didn't do

I thought about doing the whole thing as one big prompt: read the documents, check the
policy, decide, all in one model call. I rejected it. You can't explain individual
failures, you can't degrade gracefully, and you really don't want a language model doing
the co-pay arithmetic. Splitting it into stages means each failure is isolated, traced,
and survivable.

I also considered an event driven setup with a message bus between agents. For a two to
three day assignment that would have been over engineering and harder to debug. The
synchronous orchestrator is simpler and good enough at this scale. The event driven
version is the right move at much higher load, which I cover below.

For the fuzzy matching in waiting periods and exclusions, I used keyword matching rather
than an LLM. It is deterministic, fast, and testable with no API calls in CI. It is also
the most brittle part of the system, and I'm honest about that. "Lumbar Disc Herniation"
nearly matched the abdominal hernia waiting period until I added a guard for it.

## Limitations and what I'd fix

- Keyword matching for conditions will miss diagnoses phrased differently from the exact
  policy keywords. The real fix is to replace it with an LLM classifier that returns a
  structured match plus confidence. The functions are already shaped for that swap.
- The claim store is in memory, so claims are lost on restart. A SQLite or Postgres
  store behind the existing interface would fix it.
- There is no authentication. Anyone can submit a claim or read any claim by id. A real
  deployment needs an API key or JWT at the route layer.
- The pipeline is synchronous, so the caller waits while the LLM runs. At scale this
  should become a job queue.
- The extraction model was picked for being free and vision capable, not because it won
  a benchmark on real Indian medical documents. That benchmark should happen before this
  goes near production.

## Scaling to 10x

Today this handles a small synchronous load in a single process with in memory state. To
take it to ten times the volume and beyond:

Make claim submission asynchronous. The POST returns a 202 with a job id right away, and
a worker pool picks jobs off a queue. The client polls or gets a webhook when the
decision is ready. That decouples response time from how long the LLM takes.

Scale extraction horizontally. Each extraction call is a stateless request, so with a
queue in place the extraction workers scale on their own, separate from the
orchestrator, and multiple documents per claim can run on different workers instead of
sharing one event loop.

Move the policy file into per worker memory with a versioned reload mechanism so updates
can be rolled out without a restart. Move the claim store to Postgres with object storage
for the document bytes, and index on member id and treatment date for the fraud history
lookups. Stream trace events to a log aggregation system so you can alert on a spike in
degraded outcomes before anyone files a complaint. And add a pre submission throttle as a
first line of fraud defence, since the current fraud check is reactive.

## A couple of implementation notes

The project needs Python 3.12 specifically, because newer versions don't have
`pydantic-core` wheels yet. And in the extraction schema, the date field is imported as
`date_type` to dodge a Pydantic v2 quirk where a field named `date` shadows the
`datetime.date` type during annotation resolution. Both are the kind of thing that costs
an hour if you don't know about them, so they are written down.
