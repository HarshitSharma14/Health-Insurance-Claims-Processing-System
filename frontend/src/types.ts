// Mirrors backend schemas exactly — see .kiro/steering/data-contracts.md

export type ClaimCategory =
  | "CONSULTATION" | "DIAGNOSTIC" | "PHARMACY"
  | "DENTAL" | "VISION" | "ALTERNATIVE_MEDICINE";

export type VerificationFailureType =
  | "WRONG_OR_MISSING_DOCUMENTS" | "UNREADABLE_DOCUMENT" | "PATIENT_MISMATCH";

export interface DocumentVerificationResult {
  passed: boolean;
  required_documents: string[];
  received_documents: string[];
  missing_documents: string[];
  unreadable_documents: string[];
  failure_type: VerificationFailureType | null;
  message: string | null;
}

export interface TraceEvent {
  stage: string;
  component: string;
  timestamp: string;
  status: "ok" | "degraded" | "failed";
  summary: string;
  details: Record<string, unknown>;
}

export interface ClaimTrace {
  claim_id: string;
  events: TraceEvent[];
  final_decision_explanation: string;
}

export interface FinancialBreakdown {
  base_amount: number;
  sub_limit_applied: number | null;
  amount_after_sub_limit: number;
  network_discount_percent: number | null;
  amount_after_discount: number;
  co_pay_percent: number | null;
  co_pay_amount: number | null;
  final_amount: number;
}

export interface LineItemEvaluation {
  description: string;
  amount: number;
  covered: boolean;
  reason: string;
}

export type DecisionOutcome = "APPROVED" | "PARTIAL" | "REJECTED" | "MANUAL_REVIEW";

export interface ClaimDecision {
  decision: DecisionOutcome;
  approved_amount: number | null;
  reason: string;
  rejection_reasons: string[];
  confidence_score: number;
  financial_breakdown: FinancialBreakdown | null;
  line_item_evaluations: LineItemEvaluation[];
  trace: ClaimTrace;
}

export interface PipelineResponse {
  type: "verification_failure" | "decision";
  data: DocumentVerificationResult | ClaimDecision;
}
