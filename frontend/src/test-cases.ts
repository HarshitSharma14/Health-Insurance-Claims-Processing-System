/**
 * Frontend mirror of test_cases.json inputs.
 * Used by the dev quick-loader panel — not part of the production UI.
 *
 * TC001-TC003: no content fields — sent via POST /claims with placeholder file bytes.
 * TC004-TC012: have content fields — sent via POST /claims/json with pre_extracted_documents.
 *
 * ExtractedDocumentData construction mirrors eval/fixtures.py:make_extracted_document.
 */

export interface TCDoc {
  file_id: string;
  actual_type: string;
  file_name?: string;
  quality?: string;
  patient_name_on_doc?: string;
  content?: Record<string, unknown>;
  /** Filename in /public/sample_docs/ to auto-attach when Fill is used. */
  sample_doc?: string;
}

export interface TCHistoryEntry {
  claim_id: string;
  date: string;
  amount: number;
  provider?: string;
}

export interface TCInput {
  member_id: string;
  policy_id: string;
  claim_category: string;
  treatment_date: string;
  claimed_amount: number;
  hospital_name?: string;
  ytd_claims_amount?: number;
  claims_history?: TCHistoryEntry[];
  simulate_component_failure?: boolean;
  documents: TCDoc[];
}

export const TEST_CASES: Record<string, TCInput> = {
  TC001: {
    member_id: "EMP001", policy_id: "PLUM_GHI_2024",
    claim_category: "CONSULTATION", treatment_date: "2024-11-01", claimed_amount: 1500,
    documents: [
      { file_id: "F001", actual_type: "PRESCRIPTION", file_name: "dr_sharma_prescription.jpg",
        sample_doc: "prescription_viral_fever.jpg" },
      { file_id: "F002", actual_type: "PRESCRIPTION", file_name: "another_prescription.jpg",
        sample_doc: "prescription_viral_fever.jpg" },
    ],
  },
  TC002: {
    member_id: "EMP004", policy_id: "PLUM_GHI_2024",
    claim_category: "PHARMACY", treatment_date: "2024-10-25", claimed_amount: 800,
    documents: [
      { file_id: "F003", actual_type: "PRESCRIPTION", file_name: "prescription.jpg",
        quality: "GOOD", sample_doc: "prescription_viral_fever.jpg" },
      { file_id: "F004", actual_type: "PHARMACY_BILL", file_name: "blurry_bill.jpg",
        quality: "UNREADABLE", sample_doc: "pharmacy_bill.jpg" },
    ],
  },
  TC003: {
    member_id: "EMP001", policy_id: "PLUM_GHI_2024",
    claim_category: "CONSULTATION", treatment_date: "2024-11-01", claimed_amount: 1500,
    documents: [
      { file_id: "F005", actual_type: "PRESCRIPTION", file_name: "prescription_rajesh.jpg",
        patient_name_on_doc: "Rajesh Kumar", sample_doc: "prescription_viral_fever.jpg" },
      { file_id: "F006", actual_type: "HOSPITAL_BILL", file_name: "bill_arjun.jpg",
        patient_name_on_doc: "Arjun Mehta", sample_doc: "hospital_bill_consultation.jpg" },
    ],
  },
  TC004: {
    member_id: "EMP001", policy_id: "PLUM_GHI_2024",
    claim_category: "CONSULTATION", treatment_date: "2024-11-01", claimed_amount: 1500,
    ytd_claims_amount: 5000,
    documents: [
      { file_id: "F007", actual_type: "PRESCRIPTION", sample_doc: "prescription_viral_fever.jpg",
        content: { doctor_name: "Dr. Arun Sharma", doctor_registration: "KA/45678/2015", patient_name: "Rajesh Kumar", date: "2024-11-01", diagnosis: "Viral Fever", medicines: ["Paracetamol 650mg", "Vitamin C 500mg"] } },
      { file_id: "F008", actual_type: "HOSPITAL_BILL", sample_doc: "hospital_bill_consultation.jpg",
        content: { hospital_name: "City Clinic, Bengaluru", patient_name: "Rajesh Kumar", date: "2024-11-01", line_items: [{ description: "Consultation Fee", amount: 1000 }, { description: "CBC Test", amount: 300 }, { description: "Dengue NS1 Test", amount: 200 }], total: 1500 } },
    ],
  },
  TC005: {
    member_id: "EMP005", policy_id: "PLUM_GHI_2024",
    claim_category: "CONSULTATION", treatment_date: "2024-10-15", claimed_amount: 3000,
    documents: [
      { file_id: "F009", actual_type: "PRESCRIPTION", sample_doc: "prescription_viral_fever.jpg",
        content: { doctor_name: "Dr. Sunil Mehta", doctor_registration: "GJ/56789/2014", patient_name: "Vikram Joshi", diagnosis: "Type 2 Diabetes Mellitus", medicines: ["Metformin 500mg", "Glimepiride 1mg"] } },
      { file_id: "F010", actual_type: "HOSPITAL_BILL", sample_doc: "hospital_bill_consultation.jpg",
        content: { patient_name: "Vikram Joshi", date: "2024-10-15", total: 3000 } },
    ],
  },
  TC006: {
    member_id: "EMP002", policy_id: "PLUM_GHI_2024",
    claim_category: "DENTAL", treatment_date: "2024-10-15", claimed_amount: 12000,
    documents: [
      { file_id: "F011", actual_type: "HOSPITAL_BILL", sample_doc: "dental_bill_partial.jpg",
        content: { hospital_name: "Smile Dental Clinic", patient_name: "Priya Singh", line_items: [{ description: "Root Canal Treatment", amount: 8000 }, { description: "Teeth Whitening", amount: 4000 }], total: 12000 } },
    ],
  },
  TC007: {
    member_id: "EMP007", policy_id: "PLUM_GHI_2024",
    claim_category: "DIAGNOSTIC", treatment_date: "2024-11-02", claimed_amount: 15000,
    documents: [
      { file_id: "F012", actual_type: "PRESCRIPTION", sample_doc: "prescription_viral_fever.jpg",
        content: { doctor_name: "Dr. Venkat Rao", doctor_registration: "AP/67890/2017", diagnosis: "Suspected Lumbar Disc Herniation", tests_ordered: ["MRI Lumbar Spine"] } },
      { file_id: "F013", actual_type: "LAB_REPORT", sample_doc: "diagnostic_lab_report_mri.jpg",
        content: { test_name: "MRI Lumbar Spine" } },
      { file_id: "F014", actual_type: "HOSPITAL_BILL", sample_doc: "hospital_bill_consultation.jpg",
        content: { line_items: [{ description: "MRI Lumbar Spine", amount: 15000 }], total: 15000 } },
    ],
  },
  TC008: {
    member_id: "EMP003", policy_id: "PLUM_GHI_2024",
    claim_category: "CONSULTATION", treatment_date: "2024-10-20", claimed_amount: 7500,
    ytd_claims_amount: 10000,
    documents: [
      { file_id: "F015", actual_type: "PRESCRIPTION", sample_doc: "prescription_viral_fever.jpg",
        content: { doctor_name: "Dr. R. Gupta", doctor_registration: "DL/34567/2016", diagnosis: "Gastroenteritis", medicines: ["Antibiotics", "Probiotics", "ORS"] } },
      { file_id: "F016", actual_type: "HOSPITAL_BILL", sample_doc: "hospital_bill_consultation.jpg",
        content: { line_items: [{ description: "Consultation Fee", amount: 2000 }, { description: "Medicines", amount: 5500 }], total: 7500 } },
    ],
  },
  TC009: {
    member_id: "EMP008", policy_id: "PLUM_GHI_2024",
    claim_category: "CONSULTATION", treatment_date: "2024-10-30", claimed_amount: 4800,
    claims_history: [
      { claim_id: "CLM_0081", date: "2024-10-30", amount: 1200, provider: "City Clinic A" },
      { claim_id: "CLM_0082", date: "2024-10-30", amount: 1800, provider: "City Clinic B" },
      { claim_id: "CLM_0083", date: "2024-10-30", amount: 2100, provider: "Wellness Center" },
    ],
    documents: [
      { file_id: "F017", actual_type: "PRESCRIPTION", sample_doc: "prescription_viral_fever.jpg",
        content: { diagnosis: "Migraine", doctor_name: "Dr. S. Khan" } },
      { file_id: "F018", actual_type: "HOSPITAL_BILL", sample_doc: "hospital_bill_consultation.jpg",
        content: { total: 4800 } },
    ],
  },
  TC010: {
    member_id: "EMP010", policy_id: "PLUM_GHI_2024",
    claim_category: "CONSULTATION", treatment_date: "2024-11-03", claimed_amount: 4500,
    hospital_name: "Apollo Hospitals",
    ytd_claims_amount: 8000,
    documents: [
      { file_id: "F019", actual_type: "PRESCRIPTION", sample_doc: "prescription_viral_fever.jpg",
        content: { doctor_name: "Dr. S. Iyer", doctor_registration: "TN/56789/2013", patient_name: "Deepak Shah", diagnosis: "Acute Bronchitis", medicines: ["Amoxicillin 500mg", "Salbutamol Inhaler"] } },
      { file_id: "F020", actual_type: "HOSPITAL_BILL", sample_doc: "hospital_bill_consultation.jpg",
        content: { hospital_name: "Apollo Hospitals", patient_name: "Deepak Shah", line_items: [{ description: "Consultation Fee", amount: 1500 }, { description: "Medicines", amount: 3000 }], total: 4500 } },
    ],
  },
  TC011: {
    member_id: "EMP006", policy_id: "PLUM_GHI_2024",
    claim_category: "ALTERNATIVE_MEDICINE", treatment_date: "2024-10-28", claimed_amount: 4000,
    simulate_component_failure: true,
    documents: [
      { file_id: "F021", actual_type: "PRESCRIPTION", sample_doc: "prescription_viral_fever.jpg",
        content: { doctor_name: "Vaidya T. Krishnan", doctor_registration: "AYUR/KL/2345/2019", diagnosis: "Chronic Joint Pain", treatment: "Panchakarma Therapy" } },
      { file_id: "F022", actual_type: "HOSPITAL_BILL", sample_doc: "hospital_bill_consultation.jpg",
        content: { hospital_name: "Ayur Wellness Centre", total: 4000, line_items: [{ description: "Panchakarma Therapy (5 sessions)", amount: 3000 }, { description: "Consultation", amount: 1000 }] } },
    ],
  },
  TC012: {
    member_id: "EMP009", policy_id: "PLUM_GHI_2024",
    claim_category: "CONSULTATION", treatment_date: "2024-10-18", claimed_amount: 8000,
    documents: [
      { file_id: "F023", actual_type: "PRESCRIPTION", sample_doc: "prescription_viral_fever.jpg",
        content: { doctor_name: "Dr. P. Banerjee", doctor_registration: "WB/34567/2015", diagnosis: "Morbid Obesity — BMI 37", treatment: "Bariatric Consultation and Customised Diet Plan" } },
      { file_id: "F024", actual_type: "HOSPITAL_BILL", sample_doc: "hospital_bill_consultation.jpg",
        content: { line_items: [{ description: "Bariatric Consultation", amount: 3000 }, { description: "Personalised Diet and Nutrition Program", amount: 5000 }], total: 8000 } },
    ],
  },

  // ── Extra cases (beyond the 12 required) ─────────────────────────────────

  // EX001 — Vision partial: eye exam + LASIK (excluded) → PARTIAL
  // Glasses and Eye Examination are covered; LASIK Surgery is excluded.
  // Approved amount = ₹3,000 (eye exam + glasses); LASIK ₹4,500 rejected.
  EX001: {
    member_id: "EMP001", policy_id: "PLUM_GHI_2024",
    claim_category: "VISION", treatment_date: "2024-11-10", claimed_amount: 7500,
    documents: [
      { file_id: "EX01A", actual_type: "PRESCRIPTION", sample_doc: "prescription_viral_fever.jpg",
        content: { doctor_name: "Dr. Anand Rao", doctor_registration: "KA/77001/2016",
          patient_name: "Rajesh Kumar", diagnosis: "Myopia + Astigmatism",
          treatment: "Corrective Glasses" } },
      { file_id: "EX01B", actual_type: "HOSPITAL_BILL", sample_doc: "hospital_bill_consultation.jpg",
        content: { hospital_name: "Eye Care Centre", patient_name: "Rajesh Kumar",
          line_items: [
            { description: "Eye Examination", amount: 500 },
            { description: "Glasses (single-vision lenses + frame)", amount: 2500 },
            { description: "LASIK Surgery Consultation", amount: 4500 },
          ], total: 7500 } },
    ],
  },

  // EX002 — Pharmacy clean approval: generic medicines, within ₹15,000 sub-limit
  // No co-pay on pharmacy (0%), full amount approved after sub-limit check.
  EX002: {
    member_id: "EMP004", policy_id: "PLUM_GHI_2024",
    claim_category: "PHARMACY", treatment_date: "2024-11-05", claimed_amount: 750,
    documents: [
      { file_id: "EX02A", actual_type: "PRESCRIPTION", sample_doc: "prescription_viral_fever.jpg",
        content: { doctor_name: "Dr. R. Nair", doctor_registration: "KA/98765/2018",
          patient_name: "Sneha Reddy", diagnosis: "Acute Pharyngitis",
          medicines: ["Amoxicillin 500mg", "Azithromycin 500mg", "Paracetamol 650mg"] } },
      { file_id: "EX02B", actual_type: "PHARMACY_BILL", sample_doc: "pharmacy_bill.jpg",
        content: { patient_name: "Sneha Reddy",
          line_items: [
            { description: "Amoxicillin 500mg (generic)", amount: 108 },
            { description: "Azithromycin 500mg (generic)", amount: 77 },
            { description: "Paracetamol 650mg", amount: 25 },
            { description: "Vitamin C + Zinc effervescent", amount: 114 },
            { description: "ORS Sachets (Electral)", amount: 48 },
            { description: "Gargle solution 100ml", amount: 90 },
          ], total: 462 } },
    ],
  },

  // EX003 — Dental sub-limit cap → PARTIAL
  // All procedures covered (Root Canal + Crown) total ₹13,000, but dental
  // sub_limit is ₹10,000 → approved capped at ₹10,000, decision PARTIAL.
  // (Dental skips the per-claim limit, so the sub_limit governs.)
  EX003: {
    member_id: "EMP006", policy_id: "PLUM_GHI_2024",
    claim_category: "DENTAL", treatment_date: "2024-11-12", claimed_amount: 13000,
    documents: [
      { file_id: "EX03A", actual_type: "HOSPITAL_BILL", sample_doc: "dental_bill_partial.jpg",
        content: { hospital_name: "Smile Dental Clinic", patient_name: "Kavita Nair",
          line_items: [
            { description: "Root Canal Treatment", amount: 8000 },
            { description: "Crown Placement", amount: 5000 },
          ], total: 13000 } },
    ],
  },

  // EX004 — Hypertension waiting period → REJECTED
  // EMP005 joined 2024-09-01. Hypertension waiting period = 90 days.
  // Eligibility = 2024-11-30. Treatment 2024-10-20 < eligibility → REJECTED.
  EX004: {
    member_id: "EMP005", policy_id: "PLUM_GHI_2024",
    claim_category: "CONSULTATION", treatment_date: "2024-10-20", claimed_amount: 2500,
    documents: [
      { file_id: "EX04A", actual_type: "PRESCRIPTION", sample_doc: "prescription_viral_fever.jpg",
        content: { doctor_name: "Dr. Priya Mehta", doctor_registration: "GJ/44321/2016",
          patient_name: "Vikram Joshi", diagnosis: "Essential Hypertension (HTN)",
          medicines: ["Amlodipine 5mg", "Telmisartan 40mg"] } },
      { file_id: "EX04B", actual_type: "HOSPITAL_BILL", sample_doc: "hospital_bill_consultation.jpg",
        content: { patient_name: "Vikram Joshi", date: "2024-10-20",
          line_items: [{ description: "Cardiology Consultation", amount: 2500 }], total: 2500 } },
    ],
  },

  // EX005 — Cataract surgery waiting period → REJECTED
  // EMP005 joined 2024-09-01. Cataract waiting period = 365 days.
  // Eligibility = 2025-09-01. Treatment 2024-12-01 < eligibility → REJECTED.
  EX005: {
    member_id: "EMP005", policy_id: "PLUM_GHI_2024",
    claim_category: "VISION", treatment_date: "2024-12-01", claimed_amount: 4500,
    documents: [
      { file_id: "EX05A", actual_type: "PRESCRIPTION", sample_doc: "prescription_viral_fever.jpg",
        content: { doctor_name: "Dr. Kavitha Iyer", doctor_registration: "GJ/55678/2014",
          patient_name: "Vikram Joshi", diagnosis: "Senile Cataract — right eye",
          treatment: "Phacoemulsification Cataract Surgery" } },
      { file_id: "EX05B", actual_type: "HOSPITAL_BILL", sample_doc: "hospital_bill_consultation.jpg",
        content: { patient_name: "Vikram Joshi", date: "2024-12-01",
          line_items: [{ description: "Cataract Surgery (phaco) RE", amount: 4500 }], total: 4500 } },
    ],
  },

  // EX006 — Infertility / IVF exclusion → REJECTED (high confidence)
  // "Infertility and assisted reproduction" is a global exclusion.
  EX006: {
    member_id: "EMP002", policy_id: "PLUM_GHI_2024",
    claim_category: "CONSULTATION", treatment_date: "2024-10-25", claimed_amount: 3500,
    documents: [
      { file_id: "EX06A", actual_type: "PRESCRIPTION", sample_doc: "prescription_viral_fever.jpg",
        content: { doctor_name: "Dr. Shalini Roy", doctor_registration: "KA/33445/2015",
          patient_name: "Priya Singh",
          diagnosis: "Primary Infertility — IVF Consultation",
          treatment: "IVF Protocol Assessment and Hormonal Stimulation Plan" } },
      { file_id: "EX06B", actual_type: "HOSPITAL_BILL", sample_doc: "hospital_bill_consultation.jpg",
        content: { patient_name: "Priya Singh",
          line_items: [
            { description: "IVF Consultation", amount: 1500 },
            { description: "Hormonal workup (FSH, LH, AMH)", amount: 2000 },
          ], total: 3500 } },
    ],
  },

  // EX007 — Unknown member ID → MANUAL_REVIEW
  // Member "EMP999" does not exist in the policy roster.
  EX007: {
    member_id: "EMP999", policy_id: "PLUM_GHI_2024",
    claim_category: "CONSULTATION", treatment_date: "2024-11-01", claimed_amount: 1200,
    documents: [
      { file_id: "EX07A", actual_type: "PRESCRIPTION", sample_doc: "prescription_viral_fever.jpg",
        content: { doctor_name: "Dr. A. Kumar", patient_name: "Unknown Member",
          diagnosis: "Viral Fever", medicines: ["Paracetamol"] } },
      { file_id: "EX07B", actual_type: "HOSPITAL_BILL", sample_doc: "hospital_bill_consultation.jpg",
        content: { patient_name: "Unknown Member",
          line_items: [{ description: "Consultation", amount: 1200 }], total: 1200 } },
    ],
  },

  // EX008 — Fortis network hospital + diagnostic (10% network discount, 0% co-pay)
  // Diagnostic sub-limit ₹10,000. Claimed ₹4,800. Fortis = network → 10% off.
  // Approved = ₹4,800 × 0.90 = ₹4,320 (no co-pay on diagnostic).
  EX008: {
    member_id: "EMP003", policy_id: "PLUM_GHI_2024",
    claim_category: "DIAGNOSTIC", treatment_date: "2024-11-15", claimed_amount: 4800,
    hospital_name: "Fortis Healthcare",
    documents: [
      { file_id: "EX08A", actual_type: "PRESCRIPTION", sample_doc: "prescription_viral_fever.jpg",
        content: { doctor_name: "Dr. Suresh Rao", doctor_registration: "KA/12345/2013",
          patient_name: "Amit Verma", diagnosis: "Suspected Liver Function Abnormality",
          tests_ordered: ["LFT (Liver Function Tests)", "Ultrasound Abdomen", "CBC"] } },
      { file_id: "EX08B", actual_type: "LAB_REPORT", sample_doc: "diagnostic_lab_report_mri.jpg",
        content: { patient_name: "Amit Verma",
          test_name: "LFT + USG Abdomen + CBC" } },
      { file_id: "EX08C", actual_type: "HOSPITAL_BILL", sample_doc: "hospital_bill_consultation.jpg",
        content: { hospital_name: "Fortis Healthcare", patient_name: "Amit Verma",
          line_items: [
            { description: "Liver Function Tests (LFT)", amount: 1800 },
            { description: "Ultrasound Abdomen", amount: 2000 },
            { description: "CBC (Complete Blood Count)", amount: 1000 },
          ], total: 4800 } },
    ],
  },
};

// Per-case document set for the Fill path — real sample images that the live
// LLM extracts, with content matching each scenario. Paths are relative to
// the public/ root. DENTAL needs only HOSPITAL_BILL; TC001 sends two
// prescriptions (the "wrong documents" scenario); TC002 sends a blurred bill.
export const FILL_DOCS: Record<string, { type: string; file: string }[]> = {
  TC001: [{ type: "PRESCRIPTION", file: "casedocs/tc001_rx.jpg" }, { type: "PRESCRIPTION", file: "casedocs/tc001_rx.jpg" }],
  TC002: [{ type: "PRESCRIPTION", file: "casedocs/tc002_rx.jpg" }, { type: "PHARMACY_BILL", file: "casedocs/tc002_blurry.jpg" }],
  TC003: [{ type: "PRESCRIPTION", file: "casedocs/tc003_rx.jpg" }, { type: "HOSPITAL_BILL", file: "casedocs/tc003_bill.jpg" }],
  TC004: [{ type: "PRESCRIPTION", file: "casedocs/tc004_rx.jpg" }, { type: "HOSPITAL_BILL", file: "casedocs/tc004_bill.jpg" }],
  TC005: [{ type: "PRESCRIPTION", file: "casedocs/tc005_rx.jpg" }, { type: "HOSPITAL_BILL", file: "casedocs/tc005_bill.jpg" }],
  TC006: [{ type: "HOSPITAL_BILL", file: "dental_bill_partial.jpg" }],
  TC007: [{ type: "PRESCRIPTION", file: "casedocs/tc007_rx.jpg" }, { type: "LAB_REPORT", file: "casedocs/tc007_lab.jpg" }, { type: "HOSPITAL_BILL", file: "casedocs/tc007_bill.jpg" }],
  TC008: [{ type: "PRESCRIPTION", file: "casedocs/tc008_rx.jpg" }, { type: "HOSPITAL_BILL", file: "casedocs/tc008_bill.jpg" }],
  TC009: [{ type: "PRESCRIPTION", file: "casedocs/tc009_rx.jpg" }, { type: "HOSPITAL_BILL", file: "casedocs/tc009_bill.jpg" }],
  TC010: [{ type: "PRESCRIPTION", file: "casedocs/tc010_rx.jpg" }, { type: "HOSPITAL_BILL", file: "casedocs/tc010_bill.jpg" }],
  TC011: [{ type: "PRESCRIPTION", file: "casedocs/tc011_rx.jpg" }, { type: "HOSPITAL_BILL", file: "casedocs/tc011_bill.jpg" }],
  TC012: [{ type: "PRESCRIPTION", file: "casedocs/tc012_rx.jpg" }, { type: "HOSPITAL_BILL", file: "casedocs/tc012_bill.jpg" }],
  EX001: [{ type: "PRESCRIPTION", file: "casedocs/ex001_rx.jpg" }, { type: "HOSPITAL_BILL", file: "casedocs/ex001_bill.jpg" }],
  EX002: [{ type: "PRESCRIPTION", file: "casedocs/ex002_rx.jpg" }, { type: "PHARMACY_BILL", file: "casedocs/ex002_pharm.jpg" }],
  EX003: [{ type: "HOSPITAL_BILL", file: "casedocs/ex003_bill.jpg" }],
  EX004: [{ type: "PRESCRIPTION", file: "casedocs/ex004_rx.jpg" }, { type: "HOSPITAL_BILL", file: "casedocs/ex004_bill.jpg" }],
  EX005: [{ type: "PRESCRIPTION", file: "casedocs/ex005_rx.jpg" }, { type: "HOSPITAL_BILL", file: "casedocs/ex005_bill.jpg" }],
  EX006: [{ type: "PRESCRIPTION", file: "casedocs/ex006_rx.jpg" }, { type: "HOSPITAL_BILL", file: "casedocs/ex006_bill.jpg" }],
  EX007: [{ type: "PRESCRIPTION", file: "casedocs/ex007_rx.jpg" }, { type: "HOSPITAL_BILL", file: "casedocs/ex007_bill.jpg" }],
  EX008: [{ type: "PRESCRIPTION", file: "casedocs/ex008_rx.jpg" }, { type: "LAB_REPORT", file: "casedocs/ex008_lab.jpg" }, { type: "HOSPITAL_BILL", file: "casedocs/ex008_bill.jpg" }],
};

// Input-only descriptions for the dev panel — describe the scenario, not the outcome.
export const TC_DESCRIPTIONS: Record<string, string> = {
  TC001: "EMP001 · Consultation · ₹1,500 · 2 prescriptions uploaded",
  TC002: "EMP004 · Pharmacy · ₹800 · one document unreadable",
  TC003: "EMP001 · Consultation · ₹1,500 · patient names differ across docs",
  TC004: "EMP001 · Consultation · ₹1,500 · viral fever, clean claim",
  TC005: "EMP005 · Consultation · ₹3,000 · Type 2 Diabetes (joined Sep 2024)",
  TC006: "EMP002 · Dental · ₹12,000 · root canal + teeth whitening",
  TC007: "EMP007 · Diagnostic · ₹15,000 · MRI lumbar spine, no pre-auth",
  TC008: "EMP003 · Consultation · ₹7,500 · gastroenteritis",
  TC009: "EMP008 · Consultation · ₹4,800 · 3 prior same-day claims",
  TC010: "EMP010 · Consultation · ₹4,500 · Apollo Hospitals (network)",
  TC011: "EMP006 · Alt. Medicine · ₹4,000 · component-failure flag active",
  TC012: "EMP009 · Consultation · ₹8,000 · bariatric consultation",
  EX001: "EMP001 · Vision · ₹7,500 · glasses + LASIK consultation",
  EX002: "EMP004 · Pharmacy · ₹462 · below ₹500 minimum claim amount",
  EX003: "EMP006 · Dental · ₹13,000 · covered procedures exceed sub-limit",
  EX004: "EMP005 · Consultation · ₹2,500 · hypertension (joined Sep 2024)",
  EX005: "EMP005 · Vision · ₹4,500 · cataract surgery (joined Sep 2024)",
  EX006: "EMP002 · Consultation · ₹3,500 · IVF / infertility consultation",
  EX007: "EMP999 · Consultation · ₹1,200 · member not in roster",
  EX008: "EMP003 · Diagnostic · ₹4,800 · Fortis Healthcare (network)",
};

/**
 * Expected outcomes shown in the dev panel for each test case.
 * These match exactly what the deterministic pipeline produces —
 * Run any case to verify.
 */
export interface TCExpected {
  decision: "APPROVED" | "PARTIAL" | "REJECTED" | "MANUAL_REVIEW" | "verification_failure";
  approved_amount?: string;
  reason: string;
}

export const TC_EXPECTED: Record<string, TCExpected> = {
  TC001: {
    decision: "verification_failure",
    reason: "Wrong documents — two prescriptions uploaded; hospital bill required. Pipeline stops before extraction.",
  },
  TC002: {
    decision: "verification_failure",
    reason: "Unreadable document — blurry_bill.jpg cannot be read. Member asked to re-upload.",
  },
  TC003: {
    decision: "verification_failure",
    reason: "Patient mismatch — 'Rajesh Kumar' on prescription vs 'Arjun Mehta' on bill.",
  },
  TC004: {
    decision: "APPROVED",
    approved_amount: "₹1,350",
    reason: "All checks pass. Sub-limit ₹2,000 covers ₹1,500. Co-pay 10% = ₹150 deducted.",
  },
  TC005: {
    decision: "REJECTED",
    reason: "Diabetes waiting period 90 days. EMP005 joined 2024-09-01 → eligible 2024-11-30. Treatment 2024-10-15 too early.",
  },
  TC006: {
    decision: "PARTIAL",
    approved_amount: "₹8,000",
    reason: "Root Canal Treatment ₹8,000 covered. Teeth Whitening ₹4,000 excluded (cosmetic). No co-pay on dental.",
  },
  TC007: {
    decision: "REJECTED",
    reason: "MRI ₹15,000 > ₹10,000 pre-auth threshold. No pre-authorization reference provided.",
  },
  TC008: {
    decision: "REJECTED",
    reason: "Claimed ₹7,500 exceeds per-claim limit of ₹5,000.",
  },
  TC009: {
    decision: "MANUAL_REVIEW",
    reason: "4th claim on 2024-10-30 for EMP008. Same-day limit is 2. Fraud signal flagged.",
  },
  TC010: {
    decision: "APPROVED",
    approved_amount: "₹3,240",
    reason: "Apollo Hospitals = network → 20% discount (₹4,500 → ₹3,600). Co-pay 10% (₹360) → final ₹3,240.",
  },
  TC011: {
    decision: "APPROVED",
    approved_amount: "₹4,000",
    reason: "Pipeline continues despite forced component failure. Confidence 0.70 (reduced). Manual review recommended.",
  },
  TC012: {
    decision: "REJECTED",
    reason: "Bariatric consultation = 'Obesity and weight loss programs' — global exclusion. Confidence > 0.90.",
  },
  EX001: {
    decision: "PARTIAL",
    approved_amount: "₹3,000",
    reason: "Eye Examination ₹500 + Glasses ₹2,500 covered. LASIK Surgery ₹4,500 excluded (vision_exclusions). No co-pay.",
  },
  EX002: {
    decision: "REJECTED",
    reason: "Claimed ₹462 is below the minimum claim amount of ₹500 (submission_rules.minimum_claim_amount).",
  },
  EX003: {
    decision: "PARTIAL",
    approved_amount: "₹10,000",
    reason: "Root Canal ₹8,000 + Crown ₹5,000 = ₹13,000 covered, but dental sub-limit is ₹10,000 → capped. 0% co-pay.",
  },
  EX004: {
    decision: "REJECTED",
    reason: "Hypertension waiting period 90 days. EMP005 joined 2024-09-01 → eligible 2024-11-30. Treatment 2024-10-20 too early.",
  },
  EX005: {
    decision: "REJECTED",
    reason: "Cataract waiting period 365 days. EMP005 joined 2024-09-01 → eligible 2025-09-01. Treatment 2024-12-01 too early.",
  },
  EX006: {
    decision: "REJECTED",
    reason: "IVF / infertility treatment matches global exclusion 'Infertility and assisted reproduction'. High confidence rejection.",
  },
  EX007: {
    decision: "MANUAL_REVIEW",
    reason: "Member ID 'EMP999' not found in policy roster. Cannot evaluate — routed to manual verification.",
  },
  EX008: {
    decision: "APPROVED",
    approved_amount: "₹4,320",
    reason: "Fortis Healthcare = network → 10% discount (₹4,800 → ₹4,320). 0% co-pay on diagnostic.",
  },
};
