# Plum Claims Processing — Eval Report

_Generated: 2026-06-13 21:54:23_

**Score: 12/12 cases passing**

---

## Summary Table

| Case ID | Name | Expected Decision | Actual Decision | Verdict |
|---------|------|-------------------|-----------------|---------|
| `TC001` | Wrong Document Uploaded | `None` | `null (verification stop)` | ✅ PASS |
| `TC002` | Unreadable Document | `None` | `null (verification stop)` | ✅ PASS |
| `TC003` | Documents Belong to Different Patients | `None` | `null (verification stop)` | ✅ PASS |
| `TC004` | Clean Consultation — Full Approval | `APPROVED` | `APPROVED` | ✅ PASS |
| `TC005` | Waiting Period — Diabetes | `REJECTED` | `REJECTED` | ✅ PASS |
| `TC006` | Dental Partial Approval — Cosmetic Exclusion | `PARTIAL` | `PARTIAL` | ✅ PASS |
| `TC007` | MRI Without Pre-Authorization | `REJECTED` | `REJECTED` | ✅ PASS |
| `TC008` | Per-Claim Limit Exceeded | `REJECTED` | `REJECTED` | ✅ PASS |
| `TC009` | Fraud Signal — Multiple Same-Day Claims | `MANUAL_REVIEW` | `MANUAL_REVIEW` | ✅ PASS |
| `TC010` | Network Hospital — Discount Applied | `APPROVED` | `APPROVED` | ✅ PASS |
| `TC011` | Component Failure — Graceful Degradation | `APPROVED` | `APPROVED` | ✅ PASS |
| `TC012` | Excluded Treatment | `REJECTED` | `REJECTED` | ✅ PASS |

---

## Per-Case Detail

## 1. TC001 — Wrong Document Uploaded

**Description:** Member submits two prescriptions for a consultation claim that requires a prescription and a hospital bill.

**Expected outcome:** decision=`None`, 

### Actual Result

**Type:** Verification Failure
**Passed:** False
**Failure type:** `VerificationFailureType.WRONG_OR_MISSING_DOCUMENTS`
**Message:** You uploaded prescription and prescription, but a consultation claim requires a prescription and hospital bill. Please re-upload with the missing document(s): hospital bill.
**Missing documents:** ['HOSPITAL_BILL']
**Unreadable documents:** []

### Trace

_Trace not available — pipeline stopped at document verification stage._

### Verdict: ✅ PASS

---

## 2. TC002 — Unreadable Document

**Description:** Member uploads a valid prescription but a blurry, unreadable photo of their pharmacy bill.

**Expected outcome:** decision=`None`, 

### Actual Result

**Type:** Verification Failure
**Passed:** False
**Failure type:** `VerificationFailureType.UNREADABLE_DOCUMENT`
**Message:** The document 'blurry_bill.jpg' could not be read. Please re-upload a clear, legible photo or scan of that document.
**Missing documents:** []
**Unreadable documents:** ['F004']

### Trace

_Trace not available — pipeline stopped at document verification stage._

### Verdict: ✅ PASS

---

## 3. TC003 — Documents Belong to Different Patients

**Description:** The prescription is for Rajesh Kumar but the hospital bill is for a different patient, Arjun Mehta.

**Expected outcome:** decision=`None`, 

### Actual Result

**Type:** Verification Failure
**Passed:** False
**Failure type:** `VerificationFailureType.PATIENT_MISMATCH`
**Message:** The documents appear to belong to different patients: 'Rajesh Kumar' (on prescription_rajesh.jpg); 'Arjun Mehta' (on bill_arjun.jpg). Please confirm these documents all belong to the same person and re-upload the correct documents.
**Missing documents:** []
**Unreadable documents:** []

### Trace

_Trace not available — pipeline stopped at document verification stage._

### Verdict: ✅ PASS

---

## 4. TC004 — Clean Consultation — Full Approval

**Description:** Complete, valid consultation claim with correct documents, valid member, covered treatment, within all limits.

**Expected outcome:** decision=`APPROVED`, approved_amount=`1350`, confidence_score=`above 0.85`

### Actual Result

**Decision:** ✅ `APPROVED`
**Approved amount:** Rs1,350.00
**Confidence score:** 1.0000
**Rejection reasons:** —
**Reason:** Claim approved for ₹1,350.00. Co-pay of 10.0% (₹150.00) deducted.
**Financial breakdown:**
  - Base: Rs1,500.00
  - Co-pay (10.0%): Rs150.00 deducted
  - **Final: Rs1,350.00**

### Trace

| Time | Stage | Component | Status | Summary |
|------|-------|-----------|--------|---------|
| `16:24:23.475` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Pipeline started for member 'EMP001', category 'CONSULTATION', amount ₹1,500.00. |
| `16:24:23.475` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Required document check passed: prescription and hospital bill present for CONSULTATION claim. |
| `16:24:23.475` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Legibility check passed: all documents are readable. |
| `16:24:23.475` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Patient identity check passed: no patient names on documents to compare. |
| `16:24:23.475` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Document verification passed: 2 document(s) accepted for CONSULTATION claim. |
| `16:24:23.475` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Extraction skipped — 2 pre-extracted document(s) provided directly (eval harness / test injection). |
| `16:24:23.475` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Member 'EMP001' (Rajesh Kumar) found. Policy 'PLUM_GHI_2024' is ACTIVE for 2024-04-01 – 2025-03-31. Treatment date 2024-11-01 is in range. |
| `16:24:23.475` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | No global exclusions matched for diagnosis: 'Viral Fever'. |
| `16:24:23.475` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Initial waiting period passed (joined 2024-04-01, earliest 2024-05-01, treatment 2024-11-01). No specific condition waiting period applies. |
| `16:24:23.475` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Pre-auth check not applicable for category 'CONSULTATION'. |
| `16:24:23.475` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | No fraud signals detected. |
| `16:24:23.475` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Coverage evaluated for CONSULTATION: approved base amount ₹1,500.00 |
| `16:24:23.475` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Approved amount ₹1,500 is within the per-claim limit of ₹5,000. |
| `16:24:23.475` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Financial calculation: Base: ₹1,500.00 → co-pay 10% (₹150.00) → final ₹1,350.00 |
| `16:24:23.475` | `decision` | `DecisionAgent` | ✓ `ok` | Decision: APPROVED (confidence=1.00). Claim approved for ₹1,350.00. Co-pay of 10.0% (₹150.00) deducted. |
| `16:24:23.475` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Pipeline complete — decision: APPROVED, approved_amount: 1350.0, confidence: 1.00. |

**Final explanation:** Decision: APPROVED. Claim approved for ₹1,350.00. Co-pay of 10.0% (₹150.00) deducted. Co-pay 10.0% deducted (₹150.00 → final ₹1,350.00). Confidence score: 1.00.

### Verdict: ✅ PASS

---

## 5. TC005 — Waiting Period — Diabetes

**Description:** Member joined 2024-09-01. Claims for diabetes treatment on 2024-10-15, which is within the 90-day waiting period for diabetes.

**Expected outcome:** decision=`REJECTED`, , rejection_reasons=`['WAITING_PERIOD']`

### Actual Result

**Decision:** ❌ `REJECTED`
**Approved amount:** —
**Confidence score:** 1.0000
**Rejection reasons:** ['WAITING_PERIOD']
**Reason:** Diagnosis/treatment matches condition 'diabetes' (waiting period: 90 days). Treatment date 2024-10-15 < eligibility date 2024-11-30. Member will be eligible from 2024-11-30.

### Trace

| Time | Stage | Component | Status | Summary |
|------|-------|-----------|--------|---------|
| `16:24:23.475` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Pipeline started for member 'EMP005', category 'CONSULTATION', amount ₹3,000.00. |
| `16:24:23.475` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Required document check passed: prescription and hospital bill present for CONSULTATION claim. |
| `16:24:23.475` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Legibility check passed: all documents are readable. |
| `16:24:23.475` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Patient identity check passed: no patient names on documents to compare. |
| `16:24:23.475` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Document verification passed: 2 document(s) accepted for CONSULTATION claim. |
| `16:24:23.475` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Extraction skipped — 2 pre-extracted document(s) provided directly (eval harness / test injection). |
| `16:24:23.475` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Member 'EMP005' (Vikram Joshi) found. Policy 'PLUM_GHI_2024' is ACTIVE for 2024-04-01 – 2025-03-31. Treatment date 2024-10-15 is in range. |
| `16:24:23.475` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | No global exclusions matched for diagnosis: 'Type 2 Diabetes Mellitus'. |
| `16:24:23.475` | `policy_evaluation` | `PolicyEvaluationAgent` | ✗ `failed` | Diagnosis/treatment matches condition 'diabetes' (waiting period: 90 days). Treatment date 2024-10-15 < eligibility date 2024-11-30. Member will be eligible from 2024-11-30. |
| `16:24:23.475` | `decision` | `DecisionAgent` | ✓ `ok` | Decision: REJECTED (confidence=1.00). Diagnosis/treatment matches condition 'diabetes' (waiting period: 90 days). Treatment date 2024-10-15 < eligibility date |
| `16:24:23.475` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Pipeline complete — decision: REJECTED, approved_amount: None, confidence: 1.00. |

**Final explanation:** Decision: REJECTED. Diagnosis/treatment matches condition 'diabetes' (waiting period: 90 days). Treatment date 2024-10-15 < eligibility date 2024-11-30. Member will be eligible from 2024-11-30. Confidence score: 1.00.

### Verdict: ✅ PASS

---

## 6. TC006 — Dental Partial Approval — Cosmetic Exclusion

**Description:** Bill includes root canal treatment (covered) and teeth whitening (cosmetic, excluded). System must approve only the covered procedure.

**Expected outcome:** decision=`PARTIAL`, approved_amount=`8000`

### Actual Result

**Decision:** 🔶 `PARTIAL`
**Approved amount:** Rs8,000.00
**Confidence score:** 1.0000
**Rejection reasons:** —
**Reason:** Claim partially approved. Excluded line items: 'Teeth Whitening' (₹4,000.00). Approved: ₹8,000.00.
**Financial breakdown:**
  - Base: Rs8,000.00
  - **Final: Rs8,000.00**
**Line items:**
  - ✓ `Root Canal Treatment` Rs8,000.00 — 'Root Canal Treatment' is a covered procedure under opd_categories.dental.covered_procedures.
  - ✗ `Teeth Whitening` Rs4,000.00 — 'Teeth Whitening' is excluded under opd_categories.dental.excluded_procedures.

### Trace

| Time | Stage | Component | Status | Summary |
|------|-------|-----------|--------|---------|
| `16:24:23.475` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Pipeline started for member 'EMP002', category 'DENTAL', amount ₹12,000.00. |
| `16:24:23.475` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Required document check passed: hospital bill present for DENTAL claim. |
| `16:24:23.475` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Legibility check passed: all documents are readable. |
| `16:24:23.475` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Patient identity check passed: no patient names on documents to compare. |
| `16:24:23.475` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Document verification passed: 1 document(s) accepted for DENTAL claim. |
| `16:24:23.475` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Extraction skipped — 1 pre-extracted document(s) provided directly (eval harness / test injection). |
| `16:24:23.475` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Member 'EMP002' (Priya Singh) found. Policy 'PLUM_GHI_2024' is ACTIVE for 2024-04-01 – 2025-03-31. Treatment date 2024-10-15 is in range. |
| `16:24:23.475` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | No diagnosis/treatment text available — exclusion check skipped. |
| `16:24:23.475` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Initial waiting period passed (joined 2024-04-01, earliest 2024-05-01, treatment 2024-10-15). No specific condition waiting period applies. |
| `16:24:23.475` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Pre-auth check not applicable for category 'DENTAL'. |
| `16:24:23.475` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | No fraud signals detected. |
| `16:24:23.475` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Coverage evaluated for DENTAL: approved base amount ₹8,000.00 (sub_limit ₹10,000 applied). 1 line item(s) excluded. |
| `16:24:23.475` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Per-claim limit check skipped for DENTAL with line-item evaluation (sub_limit governs). |
| `16:24:23.475` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Financial calculation: Base: ₹8,000.00 → no co-pay → final ₹8,000.00 |
| `16:24:23.475` | `decision` | `DecisionAgent` | ✓ `ok` | Decision: PARTIAL (confidence=1.00). Claim partially approved. Excluded line items: 'Teeth Whitening' (₹4,000.00). Approved: ₹8,000.00. |
| `16:24:23.475` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Pipeline complete — decision: PARTIAL, approved_amount: 8000.0, confidence: 1.00. |

**Final explanation:** Decision: PARTIAL. Claim partially approved. Excluded line items: 'Teeth Whitening' (₹4,000.00). Approved: ₹8,000.00. Final approved amount: ₹8,000.00 (no co-pay). Confidence score: 1.00.

### Verdict: ✅ PASS

---

## 7. TC007 — MRI Without Pre-Authorization

**Description:** MRI scan costing ₹15,000 submitted without pre-authorization. Policy requires pre-auth for MRI above ₹10,000.

**Expected outcome:** decision=`REJECTED`, , rejection_reasons=`['PRE_AUTH_MISSING']`

### Actual Result

**Decision:** ❌ `REJECTED`
**Approved amount:** —
**Confidence score:** 1.0000
**Rejection reasons:** ['PRE_AUTH_MISSING']
**Reason:** 'MRI' detected in claim (amount ₹15,000 > pre-auth threshold ₹10,000). Pre-authorization is required for this test but was not provided. To resubmit: obtain a pre-authorization reference from your insurer before the procedure and include it with your claim.

### Trace

| Time | Stage | Component | Status | Summary |
|------|-------|-----------|--------|---------|
| `16:24:23.475` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Pipeline started for member 'EMP007', category 'DIAGNOSTIC', amount ₹15,000.00. |
| `16:24:23.475` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Required document check passed: prescription, lab report and hospital bill present for DIAGNOSTIC claim. |
| `16:24:23.475` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Legibility check passed: all documents are readable. |
| `16:24:23.475` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Patient identity check passed: no patient names on documents to compare. |
| `16:24:23.475` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Document verification passed: 3 document(s) accepted for DIAGNOSTIC claim. |
| `16:24:23.475` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Extraction skipped — 3 pre-extracted document(s) provided directly (eval harness / test injection). |
| `16:24:23.475` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Member 'EMP007' (Suresh Patil) found. Policy 'PLUM_GHI_2024' is ACTIVE for 2024-04-01 – 2025-03-31. Treatment date 2024-11-02 is in range. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | No global exclusions matched for diagnosis: 'Suspected Lumbar Disc Herniation'. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Initial waiting period passed (joined 2024-04-01, earliest 2024-05-01, treatment 2024-11-02). No specific condition waiting period applies. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✗ `failed` | 'MRI' detected in claim (amount ₹15,000 > pre-auth threshold ₹10,000). Pre-authorization is required for this test but was not provided. To resubmit: obtain a pre-authorization reference from your insurer before the procedure and include it with your claim. |
| `16:24:23.476` | `decision` | `DecisionAgent` | ✓ `ok` | Decision: REJECTED (confidence=1.00). 'MRI' detected in claim (amount ₹15,000 > pre-auth threshold ₹10,000). Pre-authorization is required for this test but w |
| `16:24:23.476` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Pipeline complete — decision: REJECTED, approved_amount: None, confidence: 1.00. |

**Final explanation:** Decision: REJECTED. 'MRI' detected in claim (amount ₹15,000 > pre-auth threshold ₹10,000). Pre-authorization is required for this test but was not provided. To resubmit: obtain a pre-authorization reference from your insurer before the procedure and include it with your claim. Confidence score: 1.00.

### Verdict: ✅ PASS

---

## 8. TC008 — Per-Claim Limit Exceeded

**Description:** Claimed amount of ₹7,500 exceeds the per-claim limit of ₹5,000.

**Expected outcome:** decision=`REJECTED`, , rejection_reasons=`['PER_CLAIM_EXCEEDED']`

### Actual Result

**Decision:** ❌ `REJECTED`
**Approved amount:** —
**Confidence score:** 1.0000
**Rejection reasons:** ['PER_CLAIM_EXCEEDED']
**Reason:** Approved amount ₹7,500 exceeds the per-claim limit of ₹5,000. The maximum reimbursable amount per claim is ₹5,000.

### Trace

| Time | Stage | Component | Status | Summary |
|------|-------|-----------|--------|---------|
| `16:24:23.476` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Pipeline started for member 'EMP003', category 'CONSULTATION', amount ₹7,500.00. |
| `16:24:23.476` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Required document check passed: prescription and hospital bill present for CONSULTATION claim. |
| `16:24:23.476` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Legibility check passed: all documents are readable. |
| `16:24:23.476` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Patient identity check passed: no patient names on documents to compare. |
| `16:24:23.476` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Document verification passed: 2 document(s) accepted for CONSULTATION claim. |
| `16:24:23.476` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Extraction skipped — 2 pre-extracted document(s) provided directly (eval harness / test injection). |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Member 'EMP003' (Amit Verma) found. Policy 'PLUM_GHI_2024' is ACTIVE for 2024-04-01 – 2025-03-31. Treatment date 2024-10-20 is in range. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | No global exclusions matched for diagnosis: 'Gastroenteritis'. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Initial waiting period passed (joined 2024-04-01, earliest 2024-05-01, treatment 2024-10-20). No specific condition waiting period applies. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Pre-auth check not applicable for category 'CONSULTATION'. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | No fraud signals detected. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Coverage evaluated for CONSULTATION: approved base amount ₹7,500.00 |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✗ `failed` | Approved amount ₹7,500 exceeds the per-claim limit of ₹5,000. The maximum reimbursable amount per claim is ₹5,000. |
| `16:24:23.476` | `decision` | `DecisionAgent` | ✓ `ok` | Decision: REJECTED (confidence=1.00). Approved amount ₹7,500 exceeds the per-claim limit of ₹5,000. The maximum reimbursable amount per claim is ₹5,000. |
| `16:24:23.476` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Pipeline complete — decision: REJECTED, approved_amount: None, confidence: 1.00. |

**Final explanation:** Decision: REJECTED. Approved amount ₹7,500 exceeds the per-claim limit of ₹5,000. The maximum reimbursable amount per claim is ₹5,000. Confidence score: 1.00.

### Verdict: ✅ PASS

---

## 9. TC009 — Fraud Signal — Multiple Same-Day Claims

**Description:** Member EMP008 has already submitted 3 claims today before this one arrives. This is the 4th claim from the same member on the same day.

**Expected outcome:** decision=`MANUAL_REVIEW`, 

### Actual Result

**Decision:** 🔍 `MANUAL_REVIEW`
**Approved amount:** —
**Confidence score:** 1.0000
**Rejection reasons:** —
**Reason:** Claim flagged for manual review due to fraud signals: 4 claims submitted on 2024-10-30 (including this one), exceeds same-day limit of 2.
**Financial breakdown:**
  - Base: Rs4,800.00
  - Co-pay (10.0%): Rs480.00 deducted
  - **Final: Rs4,320.00**

### Trace

| Time | Stage | Component | Status | Summary |
|------|-------|-----------|--------|---------|
| `16:24:23.476` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Pipeline started for member 'EMP008', category 'CONSULTATION', amount ₹4,800.00. |
| `16:24:23.476` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Required document check passed: prescription and hospital bill present for CONSULTATION claim. |
| `16:24:23.476` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Legibility check passed: all documents are readable. |
| `16:24:23.476` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Patient identity check passed: no patient names on documents to compare. |
| `16:24:23.476` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Document verification passed: 2 document(s) accepted for CONSULTATION claim. |
| `16:24:23.476` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Extraction skipped — 2 pre-extracted document(s) provided directly (eval harness / test injection). |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Member 'EMP008' (Ravi Menon) found. Policy 'PLUM_GHI_2024' is ACTIVE for 2024-04-01 – 2025-03-31. Treatment date 2024-10-30 is in range. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | No global exclusions matched for diagnosis: 'Migraine'. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Initial waiting period passed (joined 2024-04-01, earliest 2024-05-01, treatment 2024-10-30). No specific condition waiting period applies. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Pre-auth check not applicable for category 'CONSULTATION'. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✗ `failed` | Fraud signals detected: 4 claims submitted on 2024-10-30 (including this one), exceeds same-day limit of 2. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Coverage evaluated for CONSULTATION: approved base amount ₹4,800.00 |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Approved amount ₹4,800 is within the per-claim limit of ₹5,000. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Financial calculation: Base: ₹4,800.00 → co-pay 10% (₹480.00) → final ₹4,320.00 |
| `16:24:23.476` | `decision` | `DecisionAgent` | ✓ `ok` | Decision: MANUAL_REVIEW (confidence=1.00). Claim flagged for manual review due to fraud signals: 4 claims submitted on 2024-10-30 (including this one), exceeds sam |
| `16:24:23.476` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Pipeline complete — decision: MANUAL_REVIEW, approved_amount: None, confidence: 1.00. |

**Final explanation:** Decision: MANUAL_REVIEW. Claim flagged for manual review due to fraud signals: 4 claims submitted on 2024-10-30 (including this one), exceeds same-day limit of 2. Confidence score: 1.00.

### Verdict: ✅ PASS

---

## 10. TC010 — Network Hospital — Discount Applied

**Description:** Valid claim at Apollo Hospitals, a network hospital. Network discount must be applied before co-pay.

**Expected outcome:** decision=`APPROVED`, approved_amount=`3240`

### Actual Result

**Decision:** ✅ `APPROVED`
**Approved amount:** Rs3,240.00
**Confidence score:** 1.0000
**Rejection reasons:** —
**Reason:** Claim approved for ₹3,240.00. Network discount of 20.0% applied (₹4,500.00 → ₹3,600.00). Co-pay of 10.0% (₹360.00) deducted.
**Financial breakdown:**
  - Base: Rs4,500.00
  - Network discount (20.0%): Rs3,600.00 after discount
  - Co-pay (10.0%): Rs360.00 deducted
  - **Final: Rs3,240.00**

### Trace

| Time | Stage | Component | Status | Summary |
|------|-------|-----------|--------|---------|
| `16:24:23.476` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Pipeline started for member 'EMP010', category 'CONSULTATION', amount ₹4,500.00. |
| `16:24:23.476` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Required document check passed: prescription and hospital bill present for CONSULTATION claim. |
| `16:24:23.476` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Legibility check passed: all documents are readable. |
| `16:24:23.476` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Patient identity check passed: no patient names on documents to compare. |
| `16:24:23.476` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Document verification passed: 2 document(s) accepted for CONSULTATION claim. |
| `16:24:23.476` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Extraction skipped — 2 pre-extracted document(s) provided directly (eval harness / test injection). |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Member 'EMP010' (Deepak Shah) found. Policy 'PLUM_GHI_2024' is ACTIVE for 2024-04-01 – 2025-03-31. Treatment date 2024-11-03 is in range. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | No global exclusions matched for diagnosis: 'Acute Bronchitis'. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Initial waiting period passed (joined 2024-04-01, earliest 2024-05-01, treatment 2024-11-03). No specific condition waiting period applies. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Pre-auth check not applicable for category 'CONSULTATION'. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | No fraud signals detected. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Coverage evaluated for CONSULTATION: approved base amount ₹4,500.00 |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Approved amount ₹4,500 is within the per-claim limit of ₹5,000. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Financial calculation: Base: ₹4,500.00 → network discount 20% → ₹3,600.00 → co-pay 10% (₹360.00) → final ₹3,240.00 |
| `16:24:23.476` | `decision` | `DecisionAgent` | ✓ `ok` | Decision: APPROVED (confidence=1.00). Claim approved for ₹3,240.00. Network discount of 20.0% applied (₹4,500.00 → ₹3,600.00). Co-pay of 10.0% (₹360.00) deduc |
| `16:24:23.476` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Pipeline complete — decision: APPROVED, approved_amount: 3240.0, confidence: 1.00. |

**Final explanation:** Decision: APPROVED. Claim approved for ₹3,240.00. Network discount of 20.0% applied (₹4,500.00 → ₹3,600.00). Co-pay of 10.0% (₹360.00) deducted. Network discount 20.0% applied (₹4,500.00 → ₹3,600.00). Co-pay 10.0% deducted (₹360.00 → final ₹3,240.00). Confidence score: 1.00.

### Verdict: ✅ PASS

---

## 11. TC011 — Component Failure — Graceful Degradation

**Description:** One component of your system fails mid-processing (simulate with the flag below). The overall pipeline must continue, produce a decision, and make the failure visible in the output with an appropriately reduced confidence score.

**Expected outcome:** decision=`APPROVED`, 

### Actual Result

**Decision:** ✅ `APPROVED`
**Approved amount:** Rs4,000.00
**Confidence score:** 0.7000
**Rejection reasons:** —
**Reason:** Claim approved for ₹4,000.00. NOTE: One pipeline component was unavailable during processing. Manual review is recommended to verify this result.
**Financial breakdown:**
  - Base: Rs4,000.00
  - **Final: Rs4,000.00**

### Trace

| Time | Stage | Component | Status | Summary |
|------|-------|-----------|--------|---------|
| `16:24:23.476` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Pipeline started for member 'EMP006', category 'ALTERNATIVE_MEDICINE', amount ₹4,000.00. |
| `16:24:23.476` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Required document check passed: prescription and hospital bill present for ALTERNATIVE_MEDICINE claim. |
| `16:24:23.476` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Legibility check passed: all documents are readable. |
| `16:24:23.476` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Patient identity check passed: no patient names on documents to compare. |
| `16:24:23.476` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Document verification passed: 2 document(s) accepted for ALTERNATIVE_MEDICINE claim. |
| `16:24:23.476` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Extraction skipped — 2 pre-extracted document(s) provided directly (eval harness / test injection). |
| `16:24:23.476` | `orchestrator` | `ClaimOrchestrator` | ⚠ `degraded` | simulate_component_failure active — first document 'F021' forced to degraded extraction. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Member 'EMP006' (Kavita Nair) found. Policy 'PLUM_GHI_2024' is ACTIVE for 2024-04-01 – 2025-03-31. Treatment date 2024-10-28 is in range. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | No diagnosis/treatment text available — exclusion check skipped. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Initial waiting period passed (joined 2024-04-01, earliest 2024-05-01, treatment 2024-10-28). No specific condition waiting period applies. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Pre-auth check not applicable for category 'ALTERNATIVE_MEDICINE'. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | No fraud signals detected. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Coverage evaluated for ALTERNATIVE_MEDICINE: approved base amount ₹4,000.00 |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Approved amount ₹4,000 is within the per-claim limit of ₹5,000. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Financial calculation: Base: ₹4,000.00 → no co-pay → final ₹4,000.00 |
| `16:24:23.476` | `decision` | `DecisionAgent` | ⚠ `degraded` | Decision: APPROVED (confidence=0.70). Claim approved for ₹4,000.00. NOTE: One pipeline component was unavailable during processing. Manual review is recommend |
| `16:24:23.476` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Pipeline complete — decision: APPROVED, approved_amount: 4000.0, confidence: 0.70. |

**Final explanation:** Decision: APPROVED. Claim approved for ₹4,000.00. NOTE: One pipeline component was unavailable during processing. Manual review is recommended to verify this result. Confidence reductions: Component failure simulation active — confidence reduced by 0.3 Final approved amount: ₹4,000.00 (no co-pay). Confidence score: 0.70.

### Verdict: ✅ PASS

---

## 12. TC012 — Excluded Treatment

**Description:** Member claims for bariatric consultation and a diet program. Obesity treatment is explicitly excluded under the policy.

**Expected outcome:** decision=`REJECTED`, , rejection_reasons=`['EXCLUDED_CONDITION']`, confidence_score=`above 0.90`

### Actual Result

**Decision:** ❌ `REJECTED`
**Approved amount:** —
**Confidence score:** 0.9500
**Rejection reasons:** ['EXCLUDED_CONDITION']
**Reason:** Diagnosis/treatment matches excluded condition: 'Obesity and weight loss programs'. This treatment is not covered under the policy.

### Trace

| Time | Stage | Component | Status | Summary |
|------|-------|-----------|--------|---------|
| `16:24:23.476` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Pipeline started for member 'EMP009', category 'CONSULTATION', amount ₹8,000.00. |
| `16:24:23.476` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Required document check passed: prescription and hospital bill present for CONSULTATION claim. |
| `16:24:23.476` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Legibility check passed: all documents are readable. |
| `16:24:23.476` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Patient identity check passed: no patient names on documents to compare. |
| `16:24:23.476` | `document_verification` | `DocumentVerificationAgent` | ✓ `ok` | Document verification passed: 2 document(s) accepted for CONSULTATION claim. |
| `16:24:23.476` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Extraction skipped — 2 pre-extracted document(s) provided directly (eval harness / test injection). |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✓ `ok` | Member 'EMP009' (Anita Desai) found. Policy 'PLUM_GHI_2024' is ACTIVE for 2024-04-01 – 2025-03-31. Treatment date 2024-10-18 is in range. |
| `16:24:23.476` | `policy_evaluation` | `PolicyEvaluationAgent` | ✗ `failed` | Diagnosis/treatment matches excluded condition: 'Obesity and weight loss programs'. This treatment is not covered under the policy. |
| `16:24:23.476` | `decision` | `DecisionAgent` | ✓ `ok` | Decision: REJECTED (confidence=0.95). Diagnosis/treatment matches excluded condition: 'Obesity and weight loss programs'. This treatment is not covered under  |
| `16:24:23.476` | `orchestrator` | `ClaimOrchestrator` | ✓ `ok` | Pipeline complete — decision: REJECTED, approved_amount: None, confidence: 0.95. |

**Final explanation:** Decision: REJECTED. Diagnosis/treatment matches excluded condition: 'Obesity and weight loss programs'. This treatment is not covered under the policy. Confidence score: 0.95.

### Verdict: ✅ PASS

---
