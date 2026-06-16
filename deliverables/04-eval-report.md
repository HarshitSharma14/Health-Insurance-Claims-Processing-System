# Eval Report

All 12 cases from `test_cases.json` run through the full pipeline and all 12 match their
expected outcome. This is the readable summary. The complete machine generated version,
with every raw trace event, is in `../eval/eval_report.md` and you can regenerate it any
time with `python eval/run_eval.py`.

## Summary

| Case | What it tests | Expected | Got | Match |
|------|---------------|----------|-----|-------|
| TC001 | Wrong document uploaded | no decision, verification stop | verification stop | yes |
| TC002 | Unreadable document | no decision, verification stop | verification stop | yes |
| TC003 | Documents from different patients | no decision, verification stop | verification stop | yes |
| TC004 | Clean consultation | APPROVED, 1350 | APPROVED, 1350 | yes |
| TC005 | Diabetes inside waiting period | REJECTED, WAITING_PERIOD | REJECTED, WAITING_PERIOD | yes |
| TC006 | Dental with a cosmetic line item | PARTIAL, 8000 | PARTIAL, 8000 | yes |
| TC007 | MRI without pre-auth | REJECTED, PRE_AUTH_MISSING | REJECTED, PRE_AUTH_MISSING | yes |
| TC008 | Over the per-claim limit | REJECTED, PER_CLAIM_EXCEEDED | REJECTED, PER_CLAIM_EXCEEDED | yes |
| TC009 | Too many same-day claims | MANUAL_REVIEW | MANUAL_REVIEW | yes |
| TC010 | Network hospital discount | APPROVED, 3240 | APPROVED, 3240 | yes |
| TC011 | A component fails mid-run | APPROVED, lower confidence | APPROVED, confidence 0.70 | yes |
| TC012 | Excluded treatment | REJECTED, high confidence | REJECTED, confidence 0.95 | yes |

## Case by case

### TC001, wrong document
Two prescriptions were uploaded for a consultation claim, which needs a prescription and
a hospital bill. The system stopped at verification and asked for the hospital bill by
name. No decision was produced, which is the expected behaviour for a document problem.

### TC002, unreadable document
A good prescription plus a blurry pharmacy bill. The system did not reject the claim. It
stopped and asked the member to re-upload that one blurry file. Again no decision, which
is correct, because an illegible photo is a quality issue and not a policy call.

### TC003, different patients
The prescription was for Rajesh Kumar and the hospital bill for Arjun Mehta. The system
caught the mismatch, named both people, and stopped before any policy evaluation.

### TC004, clean consultation
Everything valid. Approved at 1350, which is the 1500 base with the 10 percent co-pay of
150 taken off. Confidence 1.0.

### TC005, diabetes waiting period
The member joined on 2024-09-01 and claimed for diabetes on 2024-10-15, inside the 90 day
waiting period for that condition. Rejected for WAITING_PERIOD, and the trace states the
date the member becomes eligible, 2024-11-30, which is what the case asks for.

### TC006, dental partial
The bill had a root canal (covered, 8000) and teeth whitening (cosmetic, excluded, 4000).
The system approved only the root canal and itemised why each line was kept or dropped.
Partial at 8000. This is also the case that proves the dental sub limit governs here
rather than the generic per claim limit.

### TC007, MRI without pre-auth
A 15000 MRI with no pre-authorisation, where the policy requires pre-auth for MRI above
10000. Rejected for PRE_AUTH_MISSING with a message telling the member how to resubmit
with a pre-auth reference. This case also exercises the guard that stops "Lumbar Disc
Herniation" from wrongly tripping the abdominal hernia waiting period.

### TC008, per-claim limit
Claimed 7500 against a per claim ceiling of 5000. Rejected for PER_CLAIM_EXCEEDED, and the
message states both the limit and the claimed amount.

### TC009, same-day fraud signal
The member already had three claims that day, so this fourth one crossed the same-day
limit of two. Flagged as MANUAL_REVIEW, not auto rejected, and the output names the
specific signal that fired.

### TC010, network discount
A valid claim at Apollo Hospitals, a network hospital. The 4500 base got a 20 percent
network discount down to 3600, then a 10 percent co-pay of 360, landing at 3240. The
breakdown shows each step in order, which is the point of the case, since doing co-pay
before discount gives a different number.

### TC011, component failure
The simulate flag forced the first document's extraction into its degraded path. The
pipeline kept going and still approved at 4000, but confidence dropped to 0.70 and the
trace carries a degraded event naming the affected component plus a note recommending
manual review because processing was incomplete. Expected approved with reduced
confidence, which is what happened.

### TC012, excluded treatment
A bariatric and obesity case, which is on the global exclusion list. Rejected for
EXCLUDED_CONDITION at confidence 0.95. The case wants a high confidence rejection here,
and the decision logic deliberately keeps confidence high for a clear exclusion match
even if another field on the document was hard to read.

## Why everything matched

The decision logic was written against these 12 cases from the start, so the cases double
as the acceptance tests for the rules engine. The eval harness feeds pre extracted data
for the cases that aren't about document reading (TC004 onward), which keeps the run fast
and deterministic and means a mismatch would point at the policy or decision logic rather
than at OCR noise.

## Extra cases (added beyond the required 12)

The 12 cases above are the ones the assignment ships. While building the system I
noticed a few behaviours that are fully implemented but that none of the 12 actually
exercise, so I added four more cases to cover them. They live in `eval/extra_cases.json`
and run through the same harness, and they show up in their own section beneath the core
12 in `eval/eval_report.md`. All four pass.

| Case | What it tests | Expected | Got | Match |
|------|---------------|----------|-----|-------|
| EC001 | Member id not in the roster | MANUAL_REVIEW | MANUAL_REVIEW | yes |
| EC002 | Claim below the minimum amount | REJECTED, BELOW_MINIMUM_AMOUNT | REJECTED, BELOW_MINIMUM_AMOUNT | yes |
| EC003 | Vision bill with an excluded LASIK line | PARTIAL, 1000 | PARTIAL, 1000 | yes |
| EC004 | Filed past the submission deadline | REJECTED, SUBMISSION_DEADLINE_EXCEEDED | REJECTED, SUBMISSION_DEADLINE_EXCEEDED | yes |

### EC001, member not found
A consultation claim with correct documents but a member id (EMP999) that isn't in the
policy roster. Document verification passes because the documents themselves are fine, so
the failure happens at the member lookup. The pipeline does not crash. It routes to manual
review and says the member id was not found. This is the path the original 12 never hit,
since every one of them uses a real member.

### EC002, below the minimum amount
A pharmacy claim for 300 rupees against a policy minimum of 500. The submission-rules
check catches it early and rejects with BELOW_MINIMUM_AMOUNT. The trace states the actual
numbers (claimed 300, minimum 500).

### EC003, vision partial with LASIK excluded
A vision bill with an eye examination (covered, 1000) and a LASIK procedure (excluded,
4000). The system approves only the eye examination and itemises why LASIK was dropped.
This is the same line-item logic TC006 tests for dental, but on the vision category, which
the core suite never touches.

### EC004, late submission
A consultation treated on 2024-09-01 but filed on 2024-11-01, well past the 30 day
deadline. Rejected with SUBMISSION_DEADLINE_EXCEEDED, and the trace names both the deadline
and the actual submission date. Wiring this case in needed the harness to accept an explicit
submission date, since the other cases just file same-day.

One small thing these extra cases surfaced: the rejection message for the submission-rules
failures is a touch generic in the decision's top-line reason field, even though the trace
event itself carries the specific numbers. Worth tightening the reason text for those two
codes, but it doesn't affect the outcome and I left the decision logic alone.
