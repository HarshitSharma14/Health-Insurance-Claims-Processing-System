import type { PipelineResponse } from "./types";

const TS = new Date().toISOString();

export const DEMO_APPROVED: PipelineResponse = {
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
      claim_id: "demo-tc004-approved",
      events: [
        {
          stage: "document_verification",
          component: "DocumentVerificationAgent",
          timestamp: TS,
          status: "ok",
          summary: "All 2 required documents verified — types match, legible, patient names consistent.",
          details: { check: "document_verification", detail: "Passed", policy_clause: "document_requirements.CONSULTATION" },
        },
        {
          stage: "extraction",
          component: "ExtractionAgent",
          timestamp: TS,
          status: "ok",
          summary: "Extracted PRESCRIPTION — confidence 0.95",
          details: { overall_confidence: 0.95, is_partial: false, field_confidence: { patient_name: 0.97, diagnosis: 0.93, doctor_name: 0.91 } },
        },
        {
          stage: "extraction",
          component: "ExtractionAgent",
          timestamp: TS,
          status: "ok",
          summary: "Extracted HOSPITAL_BILL — confidence 0.96",
          details: { overall_confidence: 0.96, is_partial: false, field_confidence: { total: 0.98, hospital_name: 0.94 } },
        },
        {
          stage: "policy_evaluation",
          component: "PolicyEvaluationAgent",
          timestamp: TS,
          status: "ok",
          summary: "All 8 policy checks passed — no rejections, no fraud signals.",
          details: {
            checks: [
              { check_name: "member_lookup",           passed: true,  detail: "Member EMP001 (Rajesh Kumar) found. Policy PLUM_GHI_2024 ACTIVE 2024-04-01–2025-03-31.",     relevant_policy_clause: "policy_holder.renewal_status" },
              { check_name: "exclusion",               passed: true,  detail: "No global exclusions matched for 'Viral Fever'.",                                            relevant_policy_clause: "exclusions.conditions" },
              { check_name: "waiting_period",          passed: true,  detail: "Initial 30-day period passed. No specific condition waiting period applies.",                relevant_policy_clause: "waiting_periods.initial_waiting_period_days" },
              { check_name: "pre_authorization",       passed: true,  detail: "No high-value diagnostic tests requiring pre-auth detected.",                                relevant_policy_clause: "opd_categories.diagnostic.high_value_tests_requiring_pre_auth" },
              { check_name: "fraud_signals",           passed: true,  detail: "No fraud signals detected.",                                                                 relevant_policy_clause: "fraud_thresholds" },
              { check_name: "sub_limit_and_line_items",passed: true,  detail: "Coverage evaluated for CONSULTATION: approved base ₹1,500.00",                              relevant_policy_clause: "opd_categories.consultation" },
              { check_name: "per_claim_limit",         passed: true,  detail: "Claimed amount ₹1,500 is within the per-claim limit of ₹5,000.",                            relevant_policy_clause: "coverage.per_claim_limit" },
              { check_name: "financial_calculation",   passed: true,  detail: "Base ₹1,500 → co-pay 10% (₹150) → final ₹1,350",                                            relevant_policy_clause: "opd_categories.consultation" },
            ],
          },
        },
        {
          stage: "decision",
          component: "DecisionAgent",
          timestamp: TS,
          status: "ok",
          summary: "APPROVED — ₹1,350.00, confidence 1.00",
          details: { decision: "APPROVED", approved_amount: 1350.0, confidence_score: 1.0 },
        },
      ],
      final_decision_explanation:
        "Approved: EMP001 policy PLUM_GHI_2024 active; Viral Fever has no exclusions or waiting periods; no pre-auth required; ₹1,500 within per-claim limit. Co-pay 10% (₹150) per opd_categories.consultation. Final: ₹1,350.00.",
    },
  },
};

export const DEMO_REJECTED: PipelineResponse = {
  type: "decision",
  data: {
    decision: "REJECTED",
    approved_amount: null,
    reason: "Diagnosis matches excluded condition 'Obesity and weight loss programs'. This treatment is not covered under the policy.",
    rejection_reasons: ["EXCLUDED_CONDITION"],
    confidence_score: 0.95,
    financial_breakdown: null,
    line_item_evaluations: [],
    trace: {
      claim_id: "demo-tc012-rejected",
      events: [
        {
          stage: "document_verification",
          component: "DocumentVerificationAgent",
          timestamp: TS,
          status: "ok",
          summary: "Documents verified — 2 documents, types match, patient identity consistent.",
          details: { check: "document_verification", detail: "Passed" },
        },
        {
          stage: "extraction",
          component: "ExtractionAgent",
          timestamp: TS,
          status: "ok",
          summary: "Extracted PRESCRIPTION — confidence 0.94",
          details: { overall_confidence: 0.94, is_partial: false, field_confidence: { diagnosis: 0.95, treatment: 0.92 } },
        },
        {
          stage: "policy_evaluation",
          component: "PolicyEvaluationAgent",
          timestamp: TS,
          status: "failed",
          summary: "EXCLUDED_CONDITION — Obesity and weight loss programs / Bariatric surgery",
          details: {
            checks: [
              { check_name: "member_lookup", passed: true,  detail: "Member EMP009 (Anita Desai) found. Policy active.", relevant_policy_clause: "policy_holder.renewal_status" },
              { check_name: "exclusion",     passed: false, detail: "Diagnosis 'Morbid Obesity — BMI 37 / Bariatric Consultation' matches excluded condition 'Obesity and weight loss programs'.", relevant_policy_clause: "exclusions.conditions['Obesity and weight loss programs']" },
            ],
          },
        },
        {
          stage: "decision",
          component: "DecisionAgent",
          timestamp: TS,
          status: "failed",
          summary: "REJECTED — EXCLUDED_CONDITION, confidence 0.95",
          details: { decision: "REJECTED", rejection_reasons: ["EXCLUDED_CONDITION"], confidence_score: 0.95 },
        },
      ],
      final_decision_explanation:
        "Rejected: 'Morbid Obesity — BMI 37' with Bariatric Consultation matched global exclusion 'Obesity and weight loss programs' (exclusions.conditions). Confidence 0.95 — deterministic keyword match, high certainty.",
    },
  },
};

export const DEMO_VERIFICATION_FAILURE: PipelineResponse = {
  type: "verification_failure",
  data: {
    passed: false,
    required_documents: ["PRESCRIPTION", "HOSPITAL_BILL"],
    received_documents: ["PRESCRIPTION", "PRESCRIPTION"],
    missing_documents: ["HOSPITAL_BILL"],
    unreadable_documents: [],
    failure_type: "WRONG_OR_MISSING_DOCUMENTS",
    message:
      "You uploaded prescription and prescription, but a CONSULTATION claim requires a PRESCRIPTION and HOSPITAL_BILL. Please re-upload with the missing document(s): hospital bill.",
  },
};
