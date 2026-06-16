# Component Contracts

This is the interface for each component: what it takes, what it gives back, and how it
fails. The aim is that someone could rebuild any single component from this page without
reading the existing code. All the shapes are Pydantic models and live in
`app/schemas/`.

A rule that holds across everything: no component throws an unhandled exception across
its public boundary. If something goes wrong internally, it catches it, returns a
degraded result, and writes a note to the trace. The one exception is the member lookup,
which raises a typed error the orchestrator is expected to catch.

## The inputs

A claim coming in is a `ClaimSubmission`. The field names match `test_cases.json` on
purpose, so the eval harness can feed cases straight in.

```python
class ClaimSubmission(BaseModel):
    member_id: str
    policy_id: str
    claim_category: ClaimCategory          # CONSULTATION, DIAGNOSTIC, PHARMACY,
                                            # DENTAL, VISION, ALTERNATIVE_MEDICINE
    treatment_date: date
    claimed_amount: float
    hospital_name: str | None = None       # used for the network hospital check
    ytd_claims_amount: float | None = None
    claims_history: list[ClaimsHistoryEntry] = []
    documents: list[UploadedDocument]
    simulate_component_failure: bool = False   # test hook for graceful degradation
```

A document is an `UploadedDocument` with a file id, optional name and content type, and
the raw bytes (or a storage reference). The content type is one of the image types or
application/pdf.

## Document verification

Input: the claim category and the list of uploaded documents.

Output: a `DocumentVerificationResult`.

```python
class DocumentVerificationResult(BaseModel):
    passed: bool
    required_documents: list[DocumentType]
    received_documents: list[DocumentType]
    missing_documents: list[DocumentType]
    unreadable_documents: list[str] = []      # file ids that need re-uploading
    failure_type: VerificationFailureType | None = None
    message: str | None = None                # specific and actionable, set only on fail
```

The failure type is one of `WRONG_OR_MISSING_DOCUMENTS`, `UNREADABLE_DOCUMENT`, or
`PATIENT_MISMATCH`. When `passed` is false, the pipeline ends here and no claim decision
is produced. The message is always specific. It names the documents you uploaded and the
ones you still need, or the exact file that was unreadable, or the conflicting patient
names it found.

Errors: none. It always returns a result. If a document can't be classified at all, it
is treated as a missing required document and the message explains that.

## Extraction

Input: one document.

Output: one `ExtractedDocumentData`.

```python
class ExtractedDocumentData(BaseModel):
    file_id: str
    document_type: DocumentType
    patient_name: str | None = None
    diagnosis: str | None = None
    treatment: str | None = None
    doctor_name: str | None = None
    doctor_registration: str | None = None
    hospital_name: str | None = None
    date: date | None = None
    line_items: list[LineItem] = []           # each is a description plus an amount
    total: float | None = None
    tests_ordered: list[str] = []
    field_confidence: dict[str, float] = {}   # per field, 0 to 1
    overall_confidence: float
    is_partial: bool = False
    extraction_notes: str | None = None
```

Errors: none thrown to the caller. On an LLM timeout or a parse failure it retries once,
and if that also fails it returns this same object with `overall_confidence` set to 0.0,
`is_partial` set to true, and `extraction_notes` describing what went wrong. Anything
that could legitimately be unknown is left as None rather than a placeholder string.

## Policy evaluation

Input: the claim submission plus the list of extracted documents.

Output: a `PolicyEvaluationResult`.

```python
class PolicyEvaluationResult(BaseModel):
    member_found: bool
    checks: list[PolicyCheckResult]
    rejection_reasons: list[str] = []         # e.g. WAITING_PERIOD, EXCLUDED_CONDITION,
                                              # PRE_AUTH_MISSING, PER_CLAIM_EXCEEDED
    fraud_flags: list[str] = []
    line_item_evaluations: list[LineItemEvaluation] = []
    applicable_sub_limit: float | None = None
    co_pay_percent: float | None = None
    network_discount_percent: float | None = None
    is_network_hospital: bool | None = None
```

Each individual rule produces a `PolicyCheckResult` with a check name, a passed flag, a
human readable detail string, and a reference to the relevant clause in
`policy_terms.json` (for example `waiting_periods.specific_conditions.diabetes`). The
list of these is the backbone of the trace. Line item evaluations carry, per item,
whether it was covered and why, referencing the policy clause that decided it.

Errors: it raises `MemberNotFoundError` when the member id isn't in the roster. The
orchestrator catches this and routes to manual review. It does not crash the pipeline and
it never silently approves.

## Decision

Input: the policy evaluation result and the list of extracted documents.

Output: a `ClaimDecision`.

```python
class ClaimDecision(BaseModel):
    decision: Literal["APPROVED", "PARTIAL", "REJECTED", "MANUAL_REVIEW"]
    approved_amount: float | None
    reason: str
    rejection_reasons: list[str] = []
    confidence_score: float                   # 0 to 1
    financial_breakdown: FinancialBreakdown | None = None
    line_item_evaluations: list[LineItemEvaluation] = []
    trace: ClaimTrace
```

The financial breakdown shows the work: the base amount, the sub limit if one applied,
the amount after the network discount, the co-pay percent and amount, and the final
figure, which equals the approved amount. The order is always discount first, then
co-pay.

Errors: none. This stage always returns a decision.

## Trace

Every stage writes `TraceEvent` objects into a shared `ClaimTrace` as it runs.

```python
class TraceEvent(BaseModel):
    stage: str          # document_verification, extraction, policy_evaluation,
                        # decision, orchestrator
    component: str
    timestamp: datetime
    status: Literal["ok", "degraded", "failed"]
    summary: str        # one readable line
    details: dict       # structured, stage specific

class ClaimTrace(BaseModel):
    claim_id: str
    events: list[TraceEvent]
    final_decision_explanation: str
```

The final explanation is mandatory and specific. It names the clauses, amounts, and
field names that mattered, never a generic "rejected due to policy".

## The API wrapper

Both API endpoints return a discriminated wrapper so the frontend can tell which kind of
result it got without inspecting fields:

```json
{ "type": "verification_failure" | "decision", "data": { ... } }
```

The endpoints are `POST /claims` for the real multipart upload flow, `POST /claims/json`
for the eval harness and tests (it accepts pre extracted documents to skip the LLM), and
`GET /claims/{claim_id}` to fetch a stored result.
