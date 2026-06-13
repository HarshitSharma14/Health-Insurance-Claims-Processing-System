import { useState } from "react";
import { ChevronDown, ChevronRight, ShieldCheck, ScanSearch, Scale, CheckSquare, Server, AlertTriangle } from "lucide-react";
import type { TraceEvent, ClaimTrace } from "../types";

function StageIcon({ stage }: { stage: string }) {
  const p = { size: 11, className: "flex-shrink-0" };
  if (stage.includes("verification")) return <ShieldCheck  {...p} />;
  if (stage.includes("extraction"))   return <ScanSearch   {...p} />;
  if (stage.includes("policy"))       return <Scale        {...p} />;
  if (stage.includes("decision"))     return <CheckSquare  {...p} />;
  if (stage.includes("orchestrator")) return <Server       {...p} />;
  return <AlertTriangle {...p} />;
}

const DOT_COLOR: Record<string, string> = {
  ok:       "#4e7d6a",
  degraded: "#9c7a94",
  failed:   "#ff4052",
};

const STATUS_TEXT: Record<string, string> = {
  ok:       "text-ok",
  degraded: "text-degraded",
  failed:   "text-fail",
};

interface PolicyCheck {
  check_name: string;
  passed: boolean;
  detail: string;
  relevant_policy_clause?: string | null;
}

function PolicyCheckRow({ check }: { check: PolicyCheck }) {
  return (
    <div className="flex gap-2.5 py-1.5 border-b border-border last:border-0">
      <div className={`mt-1 flex-shrink-0 w-1.5 h-1.5 rounded-full ${check.passed ? "bg-ok" : "bg-fail"}`} />
      <div className="min-w-0">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="font-mono text-[11px] text-ink">{check.check_name}</span>
          {check.relevant_policy_clause && (
            <span className="policy-ref">{check.relevant_policy_clause}</span>
          )}
        </div>
        <p className="text-[11px] text-ink-muted mt-0.5 leading-snug font-sans">{check.detail}</p>
      </div>
    </div>
  );
}

function EventDetails({ event }: { event: TraceEvent }) {
  const d = event.details;

  if (d.checks && Array.isArray(d.checks)) {
    return (
      <div className="mt-2 bg-paper rounded border border-border p-2.5">
        {(d.checks as PolicyCheck[]).map((c, i) => <PolicyCheckRow key={i} check={c} />)}
      </div>
    );
  }

  if (d.check && typeof d.check === "string") {
    const detail = d.detail != null ? String(d.detail) : null;
    const clause = d.policy_clause != null ? String(d.policy_clause) : null;
    return (
      <div className="mt-2 bg-paper rounded border border-border p-2.5 space-y-1.5">
        {detail && <p className="text-[11px] text-ink-muted leading-snug font-sans">{detail}</p>}
        {clause && <span className="policy-ref">{clause}</span>}
        {Object.entries(d)
          .filter(([k]) => !["check", "detail", "policy_clause"].includes(k))
          .map(([k, v]) => (
            <div key={k} className="flex gap-2 items-baseline">
              <span className="label text-[9px]">{k}</span>
              <span className="font-mono text-[11px] text-ink">
                {typeof v === "object" ? JSON.stringify(v) : String(v as string | number | boolean)}
              </span>
            </div>
          ))}
      </div>
    );
  }

  if (d.overall_confidence !== undefined) {
    const fc      = d.field_confidence as Record<string, number> | undefined;
    const partial = Boolean(d.is_partial);
    const notes   = d.extraction_notes != null ? String(d.extraction_notes) : null;
    return (
      <div className="mt-2 bg-paper rounded border border-border p-2.5 space-y-1.5">
        <div className="flex gap-2 items-center">
          <span className="label text-[9px]">overall_confidence</span>
          <span className="font-mono text-[11px] text-ink tabular">{Number(d.overall_confidence).toFixed(2)}</span>
          {partial && <span className="font-mono text-[10px] text-warn">partial</span>}
        </div>
        {fc && Object.keys(fc).length > 0 && (
          <div>
            <p className="label text-[9px] mb-1">field confidence</p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
              {Object.entries(fc).map(([field, conf]) => (
                <div key={field} className="flex justify-between gap-2">
                  <span className="font-mono text-[10px] text-ink-muted">{field}</span>
                  <span className="font-mono text-[10px] tabular text-ink">{Number(conf).toFixed(2)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        {notes && <p className="text-[11px] text-warn italic font-sans">{notes}</p>}
      </div>
    );
  }

  const entries = Object.entries(d).filter(([, v]) => v !== null && v !== undefined);
  if (entries.length === 0) return null;
  return (
    <div className="mt-2 bg-paper rounded border border-border p-2.5 space-y-1">
      {entries.map(([k, v]) => (
        <div key={k} className="flex gap-2 items-baseline">
          <span className="label text-[9px]">{k}</span>
          <span className="font-mono text-[11px] text-ink break-all">
            {typeof v === "object" ? JSON.stringify(v, null, 0) : String(v as string | number | boolean)}
          </span>
        </div>
      ))}
    </div>
  );
}

function TraceEventRow({ event, defaultOpen, animDelay }: { event: TraceEvent; defaultOpen: boolean; animDelay: number }) {
  const [open, setOpen] = useState(defaultOpen);
  const hasDetails = Object.keys(event.details).length > 0;

  return (
    <div className="trace-event relative pl-6 pb-3" style={{ animationDelay: `${animDelay}ms` }}>
      <div className="absolute left-[7px] top-3 bottom-0 w-px bg-border" />
      <div className="absolute left-0 top-[3px] w-3.5 h-3.5 rounded-full flex items-center justify-center"
        style={{ background: DOT_COLOR[event.status] ?? "#bea0b3", border: "2px solid #fffaf2" }} />

      <button
        type="button"
        onClick={() => hasDetails && setOpen(o => !o)}
        className={`w-full text-left flex items-start gap-2 ${hasDetails ? "cursor-pointer" : "cursor-default"}`}
      >
        <div className="flex items-center gap-1.5 min-w-[150px]">
          <StageIcon stage={event.stage} />
          <span className="font-mono text-[11px] font-medium text-ink leading-tight">{event.stage}</span>
        </div>
        <span className="text-[11px] text-ink-muted flex-1 leading-snug font-sans">{event.summary}</span>
        <span className={`text-[10px] font-mono font-semibold flex-shrink-0 mt-px ${STATUS_TEXT[event.status] ?? "text-ink-muted"}`}>
          {event.status}
        </span>
        {hasDetails && (
          <span className="text-ink-muted ml-0.5 mt-px flex-shrink-0">
            {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          </span>
        )}
      </button>

      <div className="font-mono text-[9px] text-ink-muted mt-0.5">
        {new Date(event.timestamp).toLocaleTimeString("en-IN", { hour12: false })}
        {" · "}{event.component}
      </div>

      {open && hasDetails && <EventDetails event={event} />}
    </div>
  );
}

export function TraceTimeline({ trace }: { trace: ClaimTrace }) {
  return (
    <div>
      <div className="flex items-baseline justify-between mb-3">
        <p className="label">Processing Trace</p>
        <span className="font-mono text-[10px] text-ink-muted">{trace.events.length} events</span>
      </div>

      <div>
        {trace.events.map((ev, i) => (
          <TraceEventRow key={i} event={ev} defaultOpen={ev.status !== "ok"} animDelay={i * 55} />
        ))}
      </div>

      {trace.final_decision_explanation && (
        <div className="mt-4 pt-4 border-t border-border">
          <p className="label mb-1.5">Explanation</p>
          <p className="text-xs text-ink leading-relaxed font-sans">{trace.final_decision_explanation}</p>
        </div>
      )}

      <div className="mt-3 flex items-center gap-1.5">
        <span className="label text-[9px]">Claim ID</span>
        <span className="font-mono text-[10px] text-ink-muted">{trace.claim_id}</span>
      </div>
    </div>
  );
}
