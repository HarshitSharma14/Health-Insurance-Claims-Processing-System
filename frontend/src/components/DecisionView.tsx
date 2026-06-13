import React, { useState } from "react";

// ── Types mirroring the backend schemas ──────────────────────────────────────

interface TraceEvent {
  stage: string;
  component: string;
  timestamp: string;
  status: "ok" | "degraded" | "failed";
  summary: string;
  details: Record<string, unknown>;
}

interface ClaimTrace {
  claim_id: string;
  events: TraceEvent[];
  final_decision_explanation: string;
}

interface FinancialBreakdown {
  base_amount: number;
  sub_limit_applied: number | null;
  amount_after_sub_limit: number;
  network_discount_percent: number | null;
  amount_after_discount: number;
  co_pay_percent: number | null;
  co_pay_amount: number | null;
  final_amount: number;
}

interface LineItemEval {
  description: string;
  amount: number;
  covered: boolean;
  reason: string;
}

interface ClaimDecision {
  decision: "APPROVED" | "PARTIAL" | "REJECTED" | "MANUAL_REVIEW";
  approved_amount: number | null;
  reason: string;
  rejection_reasons: string[];
  confidence_score: number;
  financial_breakdown: FinancialBreakdown | null;
  line_item_evaluations: LineItemEval[];
  trace: ClaimTrace;
}

interface VerificationFailure {
  passed: false;
  required_documents: string[];
  received_documents: string[];
  missing_documents: string[];
  unreadable_documents: string[];
  failure_type: "WRONG_OR_MISSING_DOCUMENTS" | "UNREADABLE_DOCUMENT" | "PATIENT_MISMATCH";
  message: string;
}

interface PipelineResponse {
  type: "decision" | "verification_failure";
  data: ClaimDecision | VerificationFailure;
}

// ── Main component ────────────────────────────────────────────────────────────

interface DecisionViewProps {
  decision: unknown;
  onNewClaim: () => void;
}

const DecisionView: React.FC<DecisionViewProps> = ({ decision, onNewClaim }) => {
  const response = decision as PipelineResponse;

  return (
    <section style={s.section}>
      <div style={s.topBar}>
        <h2 style={s.heading}>Claim Decision</h2>
        <button onClick={onNewClaim} style={s.newClaimBtn}>Submit Another Claim</button>
      </div>

      {response?.type === "verification_failure"
        ? <VerificationFailureView data={response.data as VerificationFailure} />
        : response?.type === "decision"
          ? <DecisionResultView data={response.data as ClaimDecision} />
          : <pre style={s.fallback}>{JSON.stringify(decision, null, 2)}</pre>
      }
    </section>
  );
};

// ── Verification failure ──────────────────────────────────────────────────────

const VerificationFailureView: React.FC<{ data: VerificationFailure }> = ({ data }) => (
  <div>
    <div style={{ ...s.decisionBadge, ...s.badgeRejected }}>DOCUMENT ISSUE</div>
    <div style={s.card}>
      <p style={s.reasonText}>{data.message}</p>
      <table style={s.table}>
        <tbody>
          <tr><td style={s.tdLabel}>Failure type</td><td>{data.failure_type}</td></tr>
          <tr><td style={s.tdLabel}>Required</td><td>{data.required_documents.join(", ") || "—"}</td></tr>
          <tr><td style={s.tdLabel}>Received</td><td>{data.received_documents.join(", ") || "—"}</td></tr>
          {data.missing_documents.length > 0 && (
            <tr><td style={s.tdLabel}>Missing</td><td style={{ color: "#c0392b" }}>{data.missing_documents.join(", ")}</td></tr>
          )}
          {data.unreadable_documents.length > 0 && (
            <tr><td style={s.tdLabel}>Unreadable</td><td style={{ color: "#e67e22" }}>{data.unreadable_documents.join(", ")}</td></tr>
          )}
        </tbody>
      </table>
    </div>
  </div>
);

// ── Full decision result ──────────────────────────────────────────────────────

const DecisionResultView: React.FC<{ data: ClaimDecision }> = ({ data }) => {
  const badgeStyle = {
    APPROVED: s.badgeApproved,
    PARTIAL: s.badgePartial,
    REJECTED: s.badgeRejected,
    MANUAL_REVIEW: s.badgeManual,
  }[data.decision];

  return (
    <div>
      {/* Header */}
      <div style={s.decisionHeader}>
        <span style={{ ...s.decisionBadge, ...badgeStyle }}>{data.decision}</span>
        {data.approved_amount != null && (
          <span style={s.approvedAmount}>₹{data.approved_amount.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</span>
        )}
        <span style={s.confidencePill}>
          {Math.round(data.confidence_score * 100)}% confidence
        </span>
      </div>

      {/* Reason */}
      <div style={s.card}>
        <p style={s.reasonText}>{data.reason}</p>
        {data.rejection_reasons.length > 0 && (
          <div style={s.rejectionReasons}>
            {data.rejection_reasons.map((r) => (
              <span key={r} style={s.rejectionTag}>{r}</span>
            ))}
          </div>
        )}
      </div>

      {/* Financial breakdown */}
      {data.financial_breakdown && <FinancialBreakdownView fb={data.financial_breakdown} />}

      {/* Line items */}
      {data.line_item_evaluations.length > 0 && <LineItemsView items={data.line_item_evaluations} />}

      {/* Trace */}
      <TraceView trace={data.trace} />
    </div>
  );
};

// ── Financial breakdown ───────────────────────────────────────────────────────

const FinancialBreakdownView: React.FC<{ fb: FinancialBreakdown }> = ({ fb }) => (
  <div style={s.card}>
    <h3 style={s.subHeading}>Financial Breakdown</h3>
    <table style={s.table}>
      <tbody>
        <tr><td style={s.tdLabel}>Claimed amount</td><td>₹{fb.base_amount.toLocaleString("en-IN")}</td></tr>
        {fb.sub_limit_applied != null && (
          <tr><td style={s.tdLabel}>Sub-limit cap</td><td>₹{fb.sub_limit_applied.toLocaleString("en-IN")}</td></tr>
        )}
        {fb.network_discount_percent != null && (
          <tr>
            <td style={s.tdLabel}>Network discount ({fb.network_discount_percent}%)</td>
            <td style={{ color: "#27ae60" }}>−₹{(fb.amount_after_sub_limit - fb.amount_after_discount).toLocaleString("en-IN")}</td>
          </tr>
        )}
        {fb.co_pay_percent != null && fb.co_pay_amount != null && (
          <tr>
            <td style={s.tdLabel}>Co-pay ({fb.co_pay_percent}%)</td>
            <td style={{ color: "#e67e22" }}>−₹{fb.co_pay_amount.toLocaleString("en-IN")}</td>
          </tr>
        )}
        <tr>
          <td style={{ ...s.tdLabel, fontWeight: 700 }}>Approved amount</td>
          <td style={{ fontWeight: 700 }}>₹{fb.final_amount.toLocaleString("en-IN")}</td>
        </tr>
      </tbody>
    </table>
  </div>
);

// ── Line items ────────────────────────────────────────────────────────────────

const LineItemsView: React.FC<{ items: LineItemEval[] }> = ({ items }) => (
  <div style={s.card}>
    <h3 style={s.subHeading}>Line Item Evaluation</h3>
    <table style={{ ...s.table, width: "100%" }}>
      <thead>
        <tr style={{ background: "#f0f4ff" }}>
          <th style={s.th}>Item</th>
          <th style={s.th}>Amount</th>
          <th style={s.th}>Status</th>
          <th style={s.th}>Reason</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item, i) => (
          <tr key={i}>
            <td style={s.td}>{item.description}</td>
            <td style={s.td}>₹{item.amount.toLocaleString("en-IN")}</td>
            <td style={s.td}>
              <span style={item.covered ? s.coveredTag : s.excludedTag}>
                {item.covered ? "Covered" : "Excluded"}
              </span>
            </td>
            <td style={s.td}>{item.reason}</td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

// ── Trace timeline ────────────────────────────────────────────────────────────

const STATUS_ICON: Record<string, string> = { ok: "✓", degraded: "⚠", failed: "✗" };
const STATUS_COLOR: Record<string, string> = { ok: "#27ae60", degraded: "#e67e22", failed: "#c0392b" };

const TraceView: React.FC<{ trace: ClaimTrace }> = ({ trace }) => {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  return (
    <div style={s.card}>
      <h3 style={s.subHeading}>Processing Trace</h3>
      <p style={s.claimId}>Claim ID: <code>{trace.claim_id}</code></p>

      <div style={s.traceList}>
        {trace.events.map((ev, i) => {
          const open = expandedIdx === i;
          const color = STATUS_COLOR[ev.status] ?? "#555";
          return (
            <div key={i} style={s.traceRow}>
              <div style={s.traceLeft}>
                <span style={{ ...s.statusDot, background: color }}>{STATUS_ICON[ev.status]}</span>
                <div style={s.traceConnector} />
              </div>
              <div style={s.traceContent}>
                <div style={s.traceHeader} onClick={() => setExpandedIdx(open ? null : i)}>
                  <span style={s.stageLabel}>{ev.stage.replace(/_/g, " ")}</span>
                  <span style={s.traceSummary}>{ev.summary}</span>
                  <span style={{ ...s.statusBadge, color, borderColor: color }}>
                    {ev.status}
                  </span>
                  <span style={s.expandToggle}>{open ? "▲" : "▼"}</span>
                </div>
                {open && (
                  <pre style={s.traceDetails}>{JSON.stringify(ev.details, null, 2)}</pre>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div style={s.explanationBox}>
        <strong>Explanation: </strong>{trace.final_decision_explanation}
      </div>
    </div>
  );
};

// ── Styles ────────────────────────────────────────────────────────────────────

const s: Record<string, React.CSSProperties> = {
  section: { maxWidth: 720 },
  topBar: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 },
  heading: { margin: 0 },
  newClaimBtn: { padding: "8px 16px", background: "#f0f4ff", border: "1px solid #0057ff", color: "#0057ff", borderRadius: 6, cursor: "pointer", fontWeight: 600 },
  card: { background: "#fafafa", border: "1px solid #e0e0e0", borderRadius: 8, padding: 16, marginBottom: 16 },
  subHeading: { margin: "0 0 12px", fontSize: 15, fontWeight: 600 },
  decisionHeader: { display: "flex", alignItems: "center", gap: 12, marginBottom: 16, flexWrap: "wrap" },
  decisionBadge: { padding: "6px 16px", borderRadius: 20, fontWeight: 700, fontSize: 15, letterSpacing: 0.5 },
  badgeApproved: { background: "#d4edda", color: "#155724" },
  badgePartial: { background: "#fff3cd", color: "#856404" },
  badgeRejected: { background: "#f8d7da", color: "#721c24" },
  badgeManual: { background: "#d1ecf1", color: "#0c5460" },
  approvedAmount: { fontSize: 22, fontWeight: 700, color: "#155724" },
  confidencePill: { background: "#e9ecef", borderRadius: 12, padding: "4px 12px", fontSize: 13, color: "#495057" },
  reasonText: { margin: "0 0 8px", lineHeight: 1.5 },
  rejectionReasons: { display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 },
  rejectionTag: { background: "#f8d7da", color: "#721c24", borderRadius: 4, padding: "2px 8px", fontSize: 12, fontWeight: 600 },
  table: { borderCollapse: "collapse", width: "100%" },
  tdLabel: { fontWeight: 500, paddingRight: 16, paddingBottom: 6, color: "#555", whiteSpace: "nowrap" },
  th: { textAlign: "left", padding: "6px 12px", fontWeight: 600, fontSize: 13 },
  td: { padding: "6px 12px", fontSize: 14, borderTop: "1px solid #eee" },
  coveredTag: { background: "#d4edda", color: "#155724", borderRadius: 4, padding: "2px 8px", fontSize: 12, fontWeight: 600 },
  excludedTag: { background: "#f8d7da", color: "#721c24", borderRadius: 4, padding: "2px 8px", fontSize: 12, fontWeight: 600 },
  claimId: { fontSize: 12, color: "#888", margin: "0 0 12px" },
  traceList: { display: "flex", flexDirection: "column" },
  traceRow: { display: "flex", gap: 8, marginBottom: 4 },
  traceLeft: { display: "flex", flexDirection: "column", alignItems: "center", width: 28 },
  statusDot: { width: 22, height: 22, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontSize: 11, fontWeight: 700, flexShrink: 0 },
  traceConnector: { flex: 1, width: 2, background: "#e0e0e0", margin: "2px 0" },
  traceContent: { flex: 1, marginBottom: 4 },
  traceHeader: { display: "flex", alignItems: "center", gap: 8, cursor: "pointer", padding: "6px 8px", borderRadius: 4, background: "#f5f5f5", flexWrap: "wrap" },
  stageLabel: { fontSize: 12, fontWeight: 700, textTransform: "capitalize", color: "#333", minWidth: 140 },
  traceSummary: { fontSize: 13, color: "#444", flex: 1 },
  statusBadge: { fontSize: 11, border: "1px solid", borderRadius: 10, padding: "1px 7px", fontWeight: 600 },
  expandToggle: { fontSize: 10, color: "#888" },
  traceDetails: { background: "#f0f0f0", borderRadius: 4, padding: "8px 12px", fontSize: 12, overflow: "auto", marginTop: 4 },
  explanationBox: { marginTop: 16, padding: "12px 16px", background: "#f0f4ff", borderRadius: 6, fontSize: 14, lineHeight: 1.6 },
  fallback: { background: "#f4f4f4", padding: 16, borderRadius: 6, overflow: "auto", fontSize: 13 },
};

export default DecisionView;
