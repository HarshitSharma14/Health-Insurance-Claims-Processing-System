import { chromium } from "@playwright/test";

const BASE = "http://localhost:5175";

// Fixture data mirroring TC004 (APPROVED) and TC012 (REJECTED)
const approvedResult = {
  type: "decision",
  data: {
    decision: "APPROVED",
    approved_amount: 1350.0,
    reason: "Claim approved for ₹1,350.00. Co-pay of 10.0% (₹150.00) deducted.",
    rejection_reasons: [],
    confidence_score: 1.0,
    financial_breakdown: {
      base_amount: 1500.0,
      sub_limit_applied: null,
      amount_after_sub_limit: 1500.0,
      network_discount_percent: null,
      amount_after_discount: 1500.0,
      co_pay_percent: 10.0,
      co_pay_amount: 150.0,
      final_amount: 1350.0,
    },
    line_item_evaluations: [],
    trace: {
      claim_id: "abc123-demo",
      events: [
        {
          stage: "document_verification",
          component: "DocumentVerificationAgent",
          timestamp: new Date().toISOString(),
          status: "ok",
          summary: "All 2 required documents verified — types match, legible, patient names consistent.",
          details: { check: "document_verification", detail: "Passed", policy_clause: "document_requirements.CONSULTATION" },
        },
        {
          stage: "extraction",
          component: "ExtractionAgent",
          timestamp: new Date().toISOString(),
          status: "ok",
          summary: "Extracted PRESCRIPTION with confidence 0.95",
          details: { overall_confidence: 0.95, is_partial: false, field_confidence: { patient_name: 0.97, diagnosis: 0.93, doctor_name: 0.91 } },
        },
        {
          stage: "policy_evaluation",
          component: "PolicyEvaluationAgent",
          timestamp: new Date().toISOString(),
          status: "ok",
          summary: "All 8 policy checks passed — no rejections, no fraud signals.",
          details: {
            checks: [
              { check_name: "member_lookup",           passed: true, detail: "Member EMP001 found. Policy PLUM_GHI_2024 is ACTIVE.",    relevant_policy_clause: "policy_holder.renewal_status" },
              { check_name: "exclusion",                passed: true, detail: "No global exclusions matched.",                           relevant_policy_clause: "exclusions.conditions" },
              { check_name: "waiting_period",           passed: true, detail: "Initial 30-day period passed. No specific conditions.",   relevant_policy_clause: "waiting_periods.initial_waiting_period_days" },
              { check_name: "pre_authorization",        passed: true, detail: "No high-value diagnostic tests requiring pre-auth.",      relevant_policy_clause: "opd_categories.diagnostic.high_value_tests_requiring_pre_auth" },
              { check_name: "fraud_signals",            passed: true, detail: "No fraud signals detected.",                              relevant_policy_clause: "fraud_thresholds" },
              { check_name: "sub_limit_and_line_items", passed: true, detail: "Approved base ₹1,500.00",                                 relevant_policy_clause: "opd_categories.consultation" },
              { check_name: "per_claim_limit",          passed: true, detail: "₹1,500 within per-claim limit ₹5,000.",                  relevant_policy_clause: "coverage.per_claim_limit" },
              { check_name: "financial_calculation",    passed: true, detail: "Base ₹1,500 → co-pay 10% (₹150) → final ₹1,350",        relevant_policy_clause: "opd_categories.consultation" },
            ],
          },
        },
        {
          stage: "decision",
          component: "DecisionAgent",
          timestamp: new Date().toISOString(),
          status: "ok",
          summary: "APPROVED — ₹1,350.00 approved, confidence 1.00",
          details: { decision: "APPROVED", confidence_score: 1.0 },
        },
      ],
      final_decision_explanation:
        "Approved: member EMP001 policy PLUM_GHI_2024 active; no exclusions, waiting periods, fraud signals, or pre-auth requirements triggered. Co-pay 10% (₹150) deducted per opd_categories.consultation.copay_percent. Final approved: ₹1,350.00.",
    },
  },
};

const rejectedResult = {
  type: "decision",
  data: {
    decision: "REJECTED",
    approved_amount: null,
    reason: "Rejected: Bariatric Consultation and Customised Diet Plan matches excluded condition 'Obesity and weight loss programs'. This treatment is not covered under the policy.",
    rejection_reasons: ["EXCLUDED_CONDITION"],
    confidence_score: 0.95,
    financial_breakdown: null,
    line_item_evaluations: [],
    trace: {
      claim_id: "xyz789-demo",
      events: [
        {
          stage: "document_verification",
          component: "DocumentVerificationAgent",
          timestamp: new Date().toISOString(),
          status: "ok",
          summary: "Documents verified.",
          details: { check: "document_verification", detail: "Passed" },
        },
        {
          stage: "policy_evaluation",
          component: "PolicyEvaluationAgent",
          timestamp: new Date().toISOString(),
          status: "failed",
          summary: "EXCLUDED_CONDITION — Obesity and weight loss programs",
          details: {
            checks: [
              { check_name: "member_lookup", passed: true, detail: "Member EMP009 found.", relevant_policy_clause: "policy_holder.renewal_status" },
              { check_name: "exclusion", passed: false, detail: "Diagnosis matches excluded condition 'Obesity and weight loss programs'.", relevant_policy_clause: "exclusions.conditions['Obesity and weight loss programs']" },
            ],
          },
        },
        {
          stage: "decision",
          component: "DecisionAgent",
          timestamp: new Date().toISOString(),
          status: "failed",
          summary: "REJECTED — EXCLUDED_CONDITION, confidence 0.95",
          details: { decision: "REJECTED", confidence_score: 0.95 },
        },
      ],
      final_decision_explanation:
        "Rejected: diagnosis 'Morbid Obesity — BMI 37' matched global exclusion 'Obesity and weight loss programs' (policy_terms.json → exclusions.conditions). Confidence 0.95 — deterministic keyword match, high certainty.",
    },
  },
};

const verificationFailure = {
  type: "verification_failure",
  data: {
    passed: false,
    required_documents: ["PRESCRIPTION", "HOSPITAL_BILL"],
    received_documents: ["PRESCRIPTION", "PRESCRIPTION"],
    missing_documents: ["HOSPITAL_BILL"],
    unreadable_documents: [],
    failure_type: "WRONG_OR_MISSING_DOCUMENTS",
    message: "You uploaded prescription and prescription, but a CONSULTATION claim requires a PRESCRIPTION and HOSPITAL_BILL. Please re-upload with the missing document(s): hospital bill.",
  },
};

async function injectResult(page: any, result: object) {
  await page.evaluate((r: object) => {
    (window as any).__INJECT_RESULT__ = r;
  }, result);
  await page.evaluate(() => {
    const ev = new CustomEvent("inject-result", { detail: (window as any).__INJECT_RESULT__ });
    window.dispatchEvent(ev);
  });
}

(async () => {
  const browser = await chromium.launch();

  for (const [name, viewport] of [["desktop", { width: 1280, height: 900 }], ["narrow", { width: 640, height: 900 }]] as const) {
    const ctx  = await browser.newContext({ viewport: { width: (viewport as any).width, height: (viewport as any).height } });
    const page = await ctx.newPage();

    // 1. Form (initial load)
    await page.goto(BASE);
    await page.waitForTimeout(400);
    await page.screenshot({ path: `screenshots/01-form-${name}.png`, fullPage: true });

    // 2. APPROVED result — inject via localStorage trick
    await page.evaluate((r) => { localStorage.setItem("__pw_result__", JSON.stringify(r)); }, approvedResult);
    await page.addInitScript(() => {
      const r = localStorage.getItem("__pw_result__");
      if (r) {
        window.addEventListener("DOMContentLoaded", () => {
          setTimeout(() => {
            const ev = new CustomEvent("pw-inject", { detail: JSON.parse(r) });
            window.dispatchEvent(ev);
          }, 100);
        });
      }
    });

    // Navigate and use React devtools hook approach — simpler: just screenshot the form
    // then construct a static HTML page for the decision views
    await page.goto(BASE);
    await page.waitForTimeout(300);
    await page.screenshot({ path: `screenshots/01-form-${name}.png`, fullPage: true });
    await ctx.close();
  }

  await browser.close();
  console.log("Screenshots captured.");
})();
