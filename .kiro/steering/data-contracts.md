---
inclusion: fileMatch
fileMatchPattern: "**/schemas/**|**/models/**|**/agents/**"
---

# Data Contracts (Component Interfaces)

> This file is the single source of truth for input/output shapes between
> components. Keep code and the "Component Contracts" deliverable in sync
> with this file — ideally generate the deliverable doc FROM these schemas.
> Update this file whenever a schema changes; don't let it drift from the
> Pydantic models.

## ClaimSubmission (input to the pipeline)
Field names follow `test_cases.json` so the eval harness can feed cases in
directly without translation.
```python
class ClaimCategory(str, Enum):
    CONSULTATION = "CONSULTATION"
    DIAGNOSTIC = "DIAGNOSTIC"
    PHARMACY = "PHARMACY"
    DENTAL = "DENTAL"
    VISION = "VISION"
    ALTERNATIVE_MEDICINE = "ALTERNATIVE_MEDICINE"

class DocumentType(str, Enum):
    PRESCRIPTION = "PRESCRIPTION"
    HOSPITAL_BILL = "HOSPITAL_BILL"
    LAB_REPORT = "LAB_REPORT"
    PHARMACY_BILL = "PHARMACY_BILL"
    DENTAL_REPORT = "DENTAL_REPORT"
    DIAGNOSTIC_REPORT = "DIAGNOSTIC_REPORT"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    UNKNOWN = "UNKNOWN"        # extraction couldn't classify the document

class UploadedDocument(BaseModel):
    file_id: str
    file_name: str | None = None
    content_type: str | None = None   # image/jpeg, image/png, application/pdf
    file_bytes: bytes | None = None   # or storage reference

class ClaimsHistoryEntry(BaseModel):
    claim_id: str
    date: date
    amount: float
    provider: str | None = None

class ClaimSubmission(BaseModel):
    member_id: str
    policy_id: str
    claim_category: ClaimCategory
    treatment_date: date
    claimed_amount: float
    hospital_name: str | None = None      # used for network-hospital check
    ytd_claims_amount: float | None = None
    claims_history: list[ClaimsHistoryEntry] = []
    documents: list[UploadedDocument]
    simulate_component_failure: bool = False  # test hook, see error-handling.md
```

## DocumentVerificationResult (Document Verification Agent output)
```python
class VerificationFailureType(str, Enum):
    WRONG_OR_MISSING_DOCUMENTS = "WRONG_OR_MISSING_DOCUMENTS"  # TC001
    UNREADABLE_DOCUMENT = "UNREADABLE_DOCUMENT"                # TC002
    PATIENT_MISMATCH = "PATIENT_MISMATCH"                      # TC003

class DocumentVerificationResult(BaseModel):
    passed: bool
    required_documents: list[DocumentType]
    received_documents: list[DocumentType]       # classified types
    missing_documents: list[DocumentType]
    unreadable_documents: list[str] = []          # file_ids needing re-upload
    failure_type: VerificationFailureType | None = None
    message: str | None = None   # specific, actionable, only set if passed=False
                                  # e.g. "You uploaded two prescriptions, but
                                  # a CONSULTATION claim requires a
                                  # PRESCRIPTION and a HOSPITAL_BILL."
                                  # or "The pharmacy bill (blurry_bill.jpg)
                                  # could not be read. Please re-upload a
                                  # clearer photo of that document."
                                  # or "The prescription names 'Rajesh Kumar'
                                  # but the hospital bill names 'Arjun
                                  # Mehta' — please confirm these documents
                                  # belong to the same person."
```
A `passed: false` result with `decision: null` ends the pipeline before any
`ClaimDecision` is produced — see decision-logic.md Stage 0. This is a
distinct response type, not a `ClaimDecision` with `MANUAL_REVIEW`.

Errors raised: none — always returns a result object, even on
classification uncertainty (treat "unclassifiable" as a missing required
document and explain that in `message`).

## ExtractedDocumentData (Extraction Agent output, one per document)
```python
class LineItem(BaseModel):
    description: str
    amount: float

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
    line_items: list[LineItem] = []
    total: float | None = None
    tests_ordered: list[str] = []
    field_confidence: dict[str, float] = {}   # per-field confidence 0-1
    overall_confidence: float
    is_partial: bool = False           # true if document was illegible/cut off
    extraction_notes: str | None = None  # e.g. "stamp obscured diagnosis field"
```
Errors raised: none thrown to caller — on LLM failure, return this object
with `overall_confidence: 0.0`, `is_partial: True`, and a populated
`extraction_notes` describing the failure (see error-handling.md).

## PolicyCheckResult (one per rule evaluated by Policy Evaluation Agent)
```python
class PolicyCheckResult(BaseModel):
    check_name: str          # one of: "member_lookup", "policy_active",
                              # "waiting_period", "exclusion",
                              # "pre_authorization", "per_claim_limit",
                              # "fraud_signals", "sub_limit_and_line_items"
                              # — see decision-logic.md for the full set
    passed: bool
    detail: str               # human-readable explanation
    relevant_policy_clause: str | None = None  # reference into policy_terms.json
                              # e.g. "waiting_periods.specific_conditions.diabetes"
```

## LineItemEvaluation (for DENTAL/VISION and any bill with line items)
```python
class LineItemEvaluation(BaseModel):
    description: str
    amount: float
    covered: bool
    reason: str               # why covered/excluded, referencing policy clause
```

## PolicyEvaluationResult (aggregate)
```python
class PolicyEvaluationResult(BaseModel):
    member_found: bool
    checks: list[PolicyCheckResult]
    rejection_reasons: list[str] = []   # e.g. ["WAITING_PERIOD"],
                                         # ["EXCLUDED_CONDITION"],
                                         # ["PRE_AUTH_MISSING"],
                                         # ["PER_CLAIM_EXCEEDED"]
    fraud_flags: list[str] = []         # specific signal descriptions, TC009
    line_item_evaluations: list[LineItemEvaluation] = []
    applicable_sub_limit: float | None = None
    co_pay_percent: float | None = None
    network_discount_percent: float | None = None
    is_network_hospital: bool | None = None
```
Errors raised: `MemberNotFoundError` if member_id doesn't exist in roster —
this should be caught by the orchestrator and routed to MANUAL_REVIEW, not
crash the pipeline.

## ClaimDecision (final output)
```python
class FinancialBreakdown(BaseModel):
    base_amount: float           # claimed or covered-line-items total, pre-cap
    sub_limit_applied: float | None = None
    amount_after_sub_limit: float
    network_discount_percent: float | None = None
    amount_after_discount: float
    co_pay_percent: float | None = None
    co_pay_amount: float | None = None
    final_amount: float          # == approved_amount

class ClaimDecision(BaseModel):
    decision: Literal["APPROVED", "PARTIAL", "REJECTED", "MANUAL_REVIEW"]
    approved_amount: float | None
    reason: str
    rejection_reasons: list[str] = []
    confidence_score: float            # 0-1
    financial_breakdown: FinancialBreakdown | None = None
    line_item_evaluations: list[LineItemEvaluation] = []
    trace: ClaimTrace                   # see observability.md
```

## General rules for all schemas
- Every field that could legitimately be unknown is `Optional` — never use
  sentinel strings like `"N/A"` or `"unknown"` to mean "missing".
- Every component function signature should be:
  `def run(input: <InputSchema>) -> <OutputSchema>` — pure functions where
  possible, side effects (trace writes) explicit.
- No component raises an unhandled exception across its public boundary.
  Catch internally, return a degraded result, log to trace.
