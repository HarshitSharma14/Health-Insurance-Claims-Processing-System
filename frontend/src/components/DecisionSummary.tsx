import type { ClaimDecision, DecisionOutcome, FinancialBreakdown, LineItemEvaluation } from "../types";

// ── Decision verdict badge (text + left-border, not a colored pill) ───────────

const OUTCOME_STYLE: Record<DecisionOutcome, { label: string; textColor: string; borderColor: string; bgColor: string }> = {
  APPROVED:      { label: "Approved",      textColor: "text-ok",       borderColor: "border-ok",       bgColor: "bg-ok-bg" },
  PARTIAL:       { label: "Partial",       textColor: "text-warn",     borderColor: "border-warn",     bgColor: "bg-warn-bg" },
  REJECTED:      { label: "Rejected",      textColor: "text-fail",     borderColor: "border-fail",     bgColor: "bg-fail-bg" },
  MANUAL_REVIEW: { label: "Manual Review", textColor: "text-degraded", borderColor: "border-degraded", bgColor: "bg-degraded-bg" },
};

function fmt(n: number) {
  return "₹" + n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ── Confidence bar ────────────────────────────────────────────────────────────

function ConfidenceBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const barColor = score >= 0.85 ? "bg-ok" : score >= 0.6 ? "bg-warn" : "bg-fail";
  return (
    <div className="flex items-center gap-2.5">
      <span className="font-mono text-sm text-text-primary tabular">{score.toFixed(2)}</span>
      <div className="w-20 h-1.5 bg-border rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] text-text-muted font-mono">{pct}%</span>
    </div>
  );
}

// ── Financial breakdown receipt ───────────────────────────────────────────────

export function FinancialBreakdownTable({ fb }: { fb: FinancialBreakdown }) {
  return (
    <div>
      <p className="label mb-2">Financial breakdown</p>
      <table className="w-full text-xs tabular">
        <tbody className="divide-y divide-border">
          <tr>
            <td className="py-1.5 text-text-secondary">Base amount</td>
            <td className="py-1.5 text-right font-mono text-text-primary">{fmt(fb.base_amount)}</td>
          </tr>
          {fb.sub_limit_applied != null && (
            <tr>
              <td className="py-1.5 text-text-secondary">Sub-limit cap</td>
              <td className="py-1.5 text-right font-mono text-warn">− {fmt(fb.base_amount - fb.amount_after_sub_limit)}</td>
            </tr>
          )}
          {fb.network_discount_percent != null && (
            <tr>
              <td className="py-1.5 text-text-secondary">
                Network discount
                <span className="font-mono text-text-muted ml-1">({fb.network_discount_percent}%)</span>
              </td>
              <td className="py-1.5 text-right font-mono text-ok">
                − {fmt(fb.amount_after_sub_limit - fb.amount_after_discount)}
              </td>
            </tr>
          )}
          {fb.co_pay_amount != null && (
            <tr>
              <td className="py-1.5 text-text-secondary">
                Co-pay
                <span className="font-mono text-text-muted ml-1">({fb.co_pay_percent}%)</span>
              </td>
              <td className="py-1.5 text-right font-mono text-warn">− {fmt(fb.co_pay_amount)}</td>
            </tr>
          )}
          <tr className="border-t-2 border-border-strong">
            <td className="pt-2 pb-1 font-semibold text-text-primary font-serif">Approved</td>
            <td className="pt-2 pb-1 text-right font-serif font-semibold text-text-primary text-sm">
              {fmt(fb.final_amount)}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

// ── Line items table ──────────────────────────────────────────────────────────

export function LineItemTable({ items }: { items: LineItemEvaluation[] }) {
  return (
    <div>
      <p className="label mb-2">Line items</p>
      <table className="w-full text-xs tabular">
        <thead>
          <tr className="border-b border-border">
            <th className="text-left pb-1.5 font-medium text-text-muted">Description</th>
            <th className="text-right pb-1.5 font-medium text-text-muted pr-3">Amount</th>
            <th className="text-right pb-1.5 font-medium text-text-muted">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {items.map((item, i) => (
            <tr key={i} className={item.covered ? "" : "opacity-60"}>
              <td className="py-1.5 text-text-primary leading-snug">
                <div>{item.description}</div>
                <div className="text-[10px] text-text-muted mt-0.5 leading-snug">{item.reason}</div>
              </td>
              <td className="py-1.5 text-right font-mono pr-3 text-text-primary align-top">
                {fmt(item.amount)}
              </td>
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
  const style = OUTCOME_STYLE[data.decision];

  return (
    <div>
      {/* Verdict row */}
      <div className={`border-l-[3px] ${style.borderColor} ${style.bgColor} px-4 py-3.5 rounded-r mb-5`}>
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <p className={`font-serif font-semibold text-xl ${style.textColor}`}>{style.label}</p>
            {data.approved_amount != null && (
              <p className="font-serif text-2xl font-semibold text-text-primary tabular mt-1">
                {fmt(data.approved_amount)}
              </p>
            )}
          </div>
          <div className="text-right">
            <p className="label mb-1">Confidence</p>
            <ConfidenceBar score={data.confidence_score} />
          </div>
        </div>

        {/* Rejection reasons */}
        {data.rejection_reasons.length > 0 && (
          <div className="flex gap-1.5 mt-2.5 flex-wrap">
            {data.rejection_reasons.map(r => (
              <span key={r} className="font-mono text-[10px] border border-fail text-fail px-1.5 py-0.5 rounded">
                {r}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Reason */}
      <div className="mb-5">
        <p className="label mb-1.5">Decision reason</p>
        <p className="text-sm text-text-primary leading-relaxed">{data.reason}</p>
      </div>

      {/* Two-column: financial + line items */}
      {(data.financial_breakdown || data.line_item_evaluations.length > 0) && (
        <div className="grid grid-cols-1 gap-6 mb-5 sm:grid-cols-2">
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
