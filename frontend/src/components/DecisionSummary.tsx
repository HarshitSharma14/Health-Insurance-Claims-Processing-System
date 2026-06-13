import type { ClaimDecision, DecisionOutcome, FinancialBreakdown, LineItemEvaluation } from "../types";

// ── Outcome metadata ──────────────────────────────────────────────────────────

const OUTCOME: Record<DecisionOutcome, {
  label: string;
  textColor: string;
  borderColor: string;
  bgColor: string;
  stampBorder: string;  // CSS border color for stamp
  stampBg: string;      // stamp background (very low opacity)
}> = {
  APPROVED: {
    label: "APPROVED",
    textColor:   "text-ok",
    borderColor: "border-ok",
    bgColor:     "bg-ok-bg",
    stampBorder: "#4A7C59",
    stampBg:     "rgba(74,124,89,0.07)",
  },
  PARTIAL: {
    label: "PARTIAL",
    textColor:   "text-warn",
    borderColor: "border-warn",
    bgColor:     "bg-warn-bg",
    stampBorder: "#92610A",
    stampBg:     "rgba(146,97,10,0.07)",
  },
  REJECTED: {
    label: "REJECTED",
    textColor:   "text-fail",
    borderColor: "border-fail",
    bgColor:     "bg-fail-bg",
    stampBorder: "#8B3A3A",
    stampBg:     "rgba(139,58,58,0.07)",
  },
  MANUAL_REVIEW: {
    label: "MANUAL REVIEW",
    textColor:   "text-degraded",
    borderColor: "border-degraded",
    bgColor:     "bg-degraded-bg",
    stampBorder: "#4A6275",
    stampBg:     "rgba(74,98,117,0.07)",
  },
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(n: number) {
  return "₹" + n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ── Rubber stamp ──────────────────────────────────────────────────────────────

function DecisionStamp({ outcome }: { outcome: DecisionOutcome }) {
  const o = OUTCOME[outcome];
  return (
    <div
      className="animate-stamp-press stamp-clip inline-flex items-center justify-center px-5 py-2.5"
      style={{
        transform: "rotate(-3deg)",
        background: o.stampBg,
        border: `2.5px solid ${o.stampBorder}`,
        transformOrigin: "center center",
      }}
    >
      <span
        className="font-mono font-semibold tracking-[0.2em] uppercase select-none"
        style={{ color: o.stampBorder, fontSize: "15px", letterSpacing: "0.22em" }}
      >
        {o.label}
      </span>
    </div>
  );
}

// ── Confidence bar ────────────────────────────────────────────────────────────

function ConfidenceBar({ score }: { score: number }) {
  const pct   = Math.round(score * 100);
  const color = score >= 0.85 ? "#4A7C59" : score >= 0.6 ? "#92610A" : "#8B3A3A";
  return (
    <div className="flex items-center gap-2">
      <span className="font-mono text-xs text-text-primary tabular">{score.toFixed(2)}</span>
      <div className="w-16 h-1 bg-border rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-[10px] font-mono text-text-muted">{pct}%</span>
    </div>
  );
}

// ── Financial breakdown receipt ───────────────────────────────────────────────

export function FinancialBreakdownTable({ fb }: { fb: FinancialBreakdown }) {
  const rows: { label: string; value: string; mod?: "deduct" | "credit" | "total" }[] = [
    { label: "Base amount", value: fmt(fb.base_amount) },
  ];
  if (fb.sub_limit_applied != null) {
    rows.push({ label: "Sub-limit cap", value: "− " + fmt(fb.base_amount - fb.amount_after_sub_limit), mod: "deduct" });
  }
  if (fb.network_discount_percent != null) {
    rows.push({
      label: `Network discount (${fb.network_discount_percent}%)`,
      value: "− " + fmt(fb.amount_after_sub_limit - fb.amount_after_discount),
      mod: "credit",
    });
  }
  if (fb.co_pay_amount != null) {
    rows.push({ label: `Co-pay (${fb.co_pay_percent}%)`, value: "− " + fmt(fb.co_pay_amount), mod: "deduct" });
  }
  rows.push({ label: "Approved", value: fmt(fb.final_amount), mod: "total" });

  return (
    <div>
      <p className="label mb-2">Financial breakdown</p>
      <table className="w-full tabular text-xs border-t border-border">
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className={r.mod === "total" ? "border-t-2 border-border-strong" : "border-t border-border"}>
              <td className={`py-1.5 ${r.mod === "total" ? "font-semibold text-text-primary font-serif text-sm" : "text-text-secondary"}`}>
                {r.label}
              </td>
              <td className={`py-1.5 text-right font-mono ${
                r.mod === "total"   ? "font-semibold text-text-primary text-sm font-serif"
                : r.mod === "deduct" ? "text-fail"
                : r.mod === "credit" ? "text-ok"
                : "text-text-primary"
              }`}>
                {r.value}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Line items ────────────────────────────────────────────────────────────────

export function LineItemTable({ items }: { items: LineItemEvaluation[] }) {
  return (
    <div>
      <p className="label mb-2">Line items</p>
      <table className="w-full tabular text-xs">
        <thead>
          <tr className="border-b border-border">
            <th className="text-left pb-1.5 font-medium text-text-muted">Description</th>
            <th className="text-right pb-1.5 font-medium text-text-muted pr-3">Amount</th>
            <th className="text-right pb-1.5 font-medium text-text-muted">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {items.map((item, i) => (
            <tr key={i} className={item.covered ? "" : "opacity-55"}>
              <td className="py-1.5 text-text-primary">
                <div>{item.description}</div>
                <div className="text-[10px] text-text-muted mt-0.5 leading-snug">{item.reason}</div>
              </td>
              <td className="py-1.5 text-right font-mono pr-3 text-text-primary align-top">{fmt(item.amount)}</td>
              <td className="py-1.5 text-right align-top">
                <span className={`font-mono text-[10px] font-medium ${item.covered ? "text-ok" : "text-fail"}`}>
                  {item.covered ? "covered" : "excluded"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Main decision summary ─────────────────────────────────────────────────────

export function DecisionSummary({ data }: { data: ClaimDecision }) {
  const o = OUTCOME[data.decision];

  return (
    <div>
      {/* Stamp + amount + confidence */}
      <div className="flex items-start justify-between gap-6 mb-5 flex-wrap">
        <div className="flex items-start gap-5 flex-wrap">
          <DecisionStamp outcome={data.decision} />
          {data.approved_amount != null && (
            <div className="pt-1">
              <p className="label mb-1">Approved amount</p>
              <p className="font-serif font-semibold text-2xl text-text-primary tabular">
                {fmt(data.approved_amount)}
              </p>
            </div>
          )}
        </div>
        <div className="pt-1">
          <p className="label mb-1.5">Confidence</p>
          <ConfidenceBar score={data.confidence_score} />
        </div>
      </div>

      {/* Rejection reason codes */}
      {data.rejection_reasons.length > 0 && (
        <div className="flex gap-1.5 mb-4 flex-wrap">
          {data.rejection_reasons.map(r => (
            <span key={r} className="font-mono text-[10px] border border-fail text-fail px-1.5 py-0.5 rounded">
              {r}
            </span>
          ))}
        </div>
      )}

      {/* Reason text */}
      <div className={`border-l-2 ${o.borderColor} pl-3 mb-5`}>
        <p className="text-sm text-text-primary leading-relaxed">{data.reason}</p>
      </div>

      {/* Financial breakdown + line items */}
      {(data.financial_breakdown || data.line_item_evaluations.length > 0) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 pt-4 border-t border-border mb-5">
          {data.financial_breakdown && (
            <FinancialBreakdownTable fb={data.financial_breakdown} />
          )}
          {data.line_item_evaluations.length > 0 && (
            <LineItemTable items={data.line_item_evaluations} />
          )}
        </div>
      )}
    </div>
  );
}
