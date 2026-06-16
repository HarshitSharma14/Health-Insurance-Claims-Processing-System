# Sample Documents

Realistic Indian medical documents for testing the live pipeline (LLM extraction path).
Open any `.html` file in a browser → print/save as PDF → upload via the claim form.

All documents use data that matches `policy_terms.json` members and `test_cases.json`
scenarios, so extracted fields align with the expected decisions.

## Files

| File | Document type | Patient | Test case scenario |
|------|--------------|---------|-------------------|
| `prescription_viral_fever.html` | Prescription | Rajesh Kumar (EMP001) | TC004 — clean APPROVED consultation |
| `hospital_bill_consultation.html` | Hospital Bill | Rajesh Kumar (EMP001) | TC004 — clean APPROVED consultation (₹1,500 → ₹1,350 after co-pay) |
| `dental_bill_partial.html` | Hospital Bill (Dental) | Priya Singh (EMP002) | TC006 — PARTIAL dental (root canal covered, whitening excluded) |
| `pharmacy_bill.html` | Pharmacy Bill | Sneha Reddy (EMP004) | Pharmacy claim with prescription reference |
| `diagnostic_lab_report_mri.html` | Lab Report (MRI) | Suresh Patil (EMP007) | TC007 — REJECTED, pre-auth required for MRI > ₹10,000 |

## How to use

### Happy path (TC004) — expected: APPROVED ₹1,350
1. Open the form, load **TC004** via Fill (or enter fields manually)
2. Upload `prescription_viral_fever.html` (saved as PDF/screenshot) into the **Prescription** slot
3. Upload `hospital_bill_consultation.html` into the **Hospital Bill** slot
4. Hit Submit — the LLM extractor reads both, policy engine approves,
   10% co-pay deducted → approved amount ₹1,350

### Partial dental (TC006) — expected: PARTIAL ₹8,000
1. Fill TC006 into the form
2. Upload `dental_bill_partial.html` into the **Hospital Bill** slot
3. Submit — line-item evaluation excludes Teeth Whitening (₹4,000), approves Root Canal (₹8,000)

### Pre-auth rejection (TC007) — expected: REJECTED
1. Fill TC007
2. Upload `diagnostic_lab_report_mri.html` into the **Lab Report** slot
   + add a simple prescription and hospital bill for the other required slots
3. Submit — MRI > ₹10,000 triggers PRE_AUTH_MISSING rejection

## Tips for screenshots vs PDFs
- **PDF (best):** browser → File → Print → Save as PDF. Keeps text selectable,
  gives the LLM the best chance to extract all fields.
- **Screenshot (good):** full-page screenshot, not a cropped mobile shot.
  The LLM handles images well but stamps/overlapping text reduce confidence.
- **Phone photo (intentionally messy):** if you want to demo the legibility/
  unreadable path, take a blurry phone photo and mark the document slot as
  `PHARMACY_BILL` with quality `UNREADABLE` (or just submit a tiny/empty file).
