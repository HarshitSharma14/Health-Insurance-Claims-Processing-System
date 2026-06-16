# Demo Video

This is the outline for the recording. The video runs about 8 to 12 minutes and covers
the three things the assignment asks for: a claim stopped early on a document problem, a
full approval with the trace visible, and one decision I'm proud of plus one I'd change.

Before recording, open the backend health URL once to wake it from sleep, otherwise the
first submission stalls for half a minute.

## Rough timing

### Opening, about 1 minute
Quick framing. What the system does, the four possible outcomes, and the fact that every
decision comes with a full trace. Show the submission screen.

### Part 1, the early document stop, about 2 minutes
Submit a consultation claim but upload the wrong documents, two prescriptions instead of a
prescription and a hospital bill. Show that it stops before any policy work and reads back
the actual message: what was uploaded and which document is still needed. The point to
make out loud is that this is a specific, actionable message, not a generic error, and
that it happens before we spend anything on extraction.

If there is time, also show the unreadable-document case, since it behaves differently. It
asks for a re-upload of the one bad file instead of rejecting the claim.

### Part 2, the full approval with trace, about 3 to 4 minutes
Run the network hospital case (TC010 style). Submit it, land on the decision screen, and
walk the trace top to bottom: document checks passing, policy stages each with their own
line, then the financial breakdown showing 4500, the 20 percent discount to 3600, the 10
percent co-pay of 360, and the final 3240. Make the point that the order matters and the
trace shows it. Close this part by reading the plain English final explanation and the
confidence score.

### Part 3, the proud decision and the one I'd change, about 2 to 3 minutes

The one I'm proud of: keeping the policy math as deterministic code and never letting the
language model do arithmetic. The LLM reads messy documents, which is what it is good at,
and the rules engine does the co-pay and sub limit and discount ordering, which needs to
be exact and testable. The graceful degradation case (TC011) is the proof: a component
dies mid run, the pipeline still produces a correct approval, confidence drops, and the
trace says exactly what was skipped. I would show that case running here.

The one I'd change: the waiting period and exclusion matching is keyword based right now.
It is fast and testable but it has no real understanding of language. The "Lumbar Disc
Herniation" example is the honest illustration, it nearly matched the abdominal hernia
rule until I added a guard. With more time I would replace the keyword matching with an
LLM classifier that returns a structured match and its own confidence, logged in the
trace like everything else. The code is already shaped so that swap doesn't touch the
callers.

### Close, about 30 seconds
One line on the architecture (focused agents, shared trace, deterministic policy core),
one line on where it is deployed, done.

## Things to make sure are on screen at some point
- A specific document error message.
- A full trace timeline, not raw JSON.
- The financial breakdown with discount before co-pay.
- A confidence score, and ideally the degraded case where it drops.
