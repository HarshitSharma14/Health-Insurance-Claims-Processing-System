import type { ClaimDecision, DecisionOutcome, FinancialBreakdown, LineItemEvaluation } from "../types";

const OUTCOME: Record<DecisionOutcome, {
  label: string;
  color: string;       // stamp border + text color
  bgColor: string;     // stamp interior (very low opacity)
  borderLeft: string;  // reason text border
  tagBorder: string;   // rejection reason tags
}> = {
  APPROVED: {
    label:      "APPROVED",
    color:      "#4e7d6a",
    bgColor:    "rgba(78,125,106,0.07)",
    borderLeft: "border-ok",
    tagBorder:  "border-ok text-ok",
  },
  PARTIAL: {
    label:      "PARTIAL",
    color:      "#c49428",
    bgColor:    "rgba(196,148,40,0.07)",
    borderLeft: "border-warn",
    tagBorder:  "border-warn text-warn",
  },
  REJECTED: {
    label:      "REJECTED",
    color:      "#ff4052",
    bgColor:    "rgba(255,64,82,0.06)",
    borderLeft: "border-fail",
    tagBorder:  "border-fail text-fail",
  },
  MANUAL_REVIEW: {
    label:      "MANUAL REVIEW",
    color:      "#9c7a94",
    bgColor:    "rgba(156,122,148,0.07)",
    borderLeft: "border-degraded",
    tagBorder:  "border-degraded text-degraded",
  },
};

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
        transform:       "rotate(-3deg)",
        background:      o.bgColor,
        border:          `2.5px solid ${o.color}`,
        transformOrigin: "center center",
      }}
    >
      <span
        className="font-mono font-semibold uppercase select-none"
        style={{ color: o.color, fontSize: "14px", letterSpacing: "0.22em" }}
      >
        {o.label}
      </span>
    </div>
  );
}

// ── Confidence bar ────────────────────────────────────────────────────────────

function ConfidenceBar({ score }: { score: number }) {
  const pct   = Math.round(score * 100);
  const color = score >= 0.85 ? "#4e7d6a" : score >= 0.6 ? "#c49428" : "#ff4052";
  return (
    <div className="flex items-center gap-2">
      <span className="font-mono text-xs text-ink tabular">{score.toFixed(2)}</span>
      <div className="w-16 h-1 rounded-full overflow-hidden" style={{ backgroundColor: "#f0e4d8" }}>
        <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="text-[10px] font-mono text-ink-muted">{pct}%</span>
    </div>
  );
}

// ── Financial breakdown ───────────────────────────────────────────────────────

export function FinancialBreakdownTable({ fb }: { fb: FinancialBreakdown }) {
  type Row = { label: string; value: string; mod?: "deduct" | "credit" | "total" };
  const rows: Row[] = [{ label: "Base amount", value: fmt(fb.base_amount) }];
  if (fb.sub_limit_applied != null)
    rows.push({ label: "Sub-limit cap", value: "− " + fmt(fb.base_amount - fb.amount_after_sub_limit), mod: "deduct" });
  if (fb.network_discount_percent != null)
    rows.push({ label: `Network discount (${fb.network_discount_percent}%)`, value: "− " + fmt(fb.amount_after_sub_limit - fb.amount_after_discount), mod: "credit" });
  if (fb.co_pay_amount != null)
    rows.push({ label: `Co-pay (${fb.co_pay_percent}%)`, value: "− " + fmt(fb.co_pay_amount), mod: "deduct" });
  rows.push({ label: "Approved", value: fmt(fb.final_amount), mod: "total" });

  return (
    <div>
      <p className="label mb-2">Financial breakdown</p>
      <table className="w-full tabular text-xs border-t border-border">
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className={r.mod === "total" ? "border-t-2 border-border-strong" : "border-t border-border"}>
              <td className={`py-1.5 font-sans ${r.mod === "total" ? "font-semibold text-ink text-sm" : "text-ink-muted"}`}>
                {r.label}
              </td>
              <td className={`py-1.5 text-right font-mono ${
                r.mod === "total"    ? "font-semibold text-ink text-sm"
                : r.mod === "deduct" ? "text-fail"
                : r.mod === "credit" ? "text-ok"
                : "text-ink"
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
            <th className="text-left pb-1.5 font-medium text-ink-muted">Description</th>
            <th className="text-right pb-1.5 font-medium text-ink-muted pr-3">Amount</th>
            <th className="text-right pb-1.5 font-medium text-ink-muted">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {items.map((item, i) => (
            <tr key={i} className={item.covered ? "" : "opacity-55"}>
              <td className="py-1.5 text-ink font-sans">
                <div>{item.description}</div>
                <div className="text-[10px] text-ink-muted mt-0.5 leading-snug">{item.reason}</div>
              </td>
              <td className="py-1.5 text-right font-mono pr-3 text-ink align-top">{fmt(item.amount)}</td>
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
      {/* Stamp + amount + confidence row */}
      <div className="flex items-start justify-between gap-6 mb-5 flex-wrap">
        <div className="flex items-start gap-5 flex-wrap">
          <DecisionStamp outcome={data.decision} />
          {data.approved_amount != null && (
            <div className="pt-1">
              <p className="label mb-1">Approved amount</p>
              {/* Serif display — restrained "verdict" size */}
              <p className="font-serif font-semibold text-[26px] leading-tight text-ink tabular">
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
            <span key={r}
              className={`font-mono text-[10px] border px-1.5 py-0.5 rounded ${o.tagBorder}`}>
              {r}
            </span>
          ))}
        </div>
      )}

      {/* Reason — left border accent in outcome color */}
      <div className={`border-l-2 ${o.borderLeft} pl-3 mb-5`}>
        <p className="text-sm text-ink leading-relaxed font-sans">{data.reason}</p>
      </div>

      {/* Financial breakdown + line items */}
      {(data.financial_breakdown || data.line_item_evaluations.length > 0) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 pt-4 border-t border-border mb-5">
          {data.financial_breakdown && <FinancialBreakdownTable fb={data.financial_breakdown} />}
          {data.line_item_evaluations.length > 0 && <LineItemTable items={data.line_item_evaluations} />}
        </div>
      )}
    </div>
  );
}
