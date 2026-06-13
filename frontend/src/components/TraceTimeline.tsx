import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { TraceEvent, ClaimTrace } from "../types";

const STATUS_LABEL: Record<string, string> = {
  ok:       "text-ok",
  degraded: "text-degraded",
  failed:   "text-fail",
};

const STATUS_BORDER: Record<string, string> = {
  ok:       "",
  degraded: "border-l-2 border-degraded",
  failed:   "border-l-2 border-fail",
};

// ── PolicyCheckResult row ─────────────────────────────────────────────────────

interface PolicyCheck {
  check_name: string;
  passed: boolean;
  detail: string;
  relevant_policy_clause?: string | null;
}

function PolicyCheckRow({ check }: { check: PolicyCheck }) {
  return (
    <div className="flex gap-3 py-1.5 border-b border-border last:border-0">
      <div className="mt-1.5 flex-shrink-0">
        <div className={check.passed ? "status-dot-ok" : "status-dot-fail"} />
      </div>
      <div className="min-w-0">
        <span className="font-mono text-xs text-text-primary">{check.check_name}</span>
        {check.relevant_policy_clause && (
          <span className="policy-ref ml-2">{check.relevant_policy_clause}</span>
        )}
        <p className="text-xs text-text-secondary mt-0.5 leading-snug">{check.detail}</p>
      </div>
    </div>
  );
}

// ── Expanded details renderer ─────────────────────────────────────────────────

function EventDetails({ event }: { event: TraceEvent }) {
  const d = event.details;

  // Policy evaluation: render checks as checklist if present
  if (d.checks && Array.isArray(d.checks)) {
    return (
      <div className="mt-2 ml-0 bg-bg rounded border border-border p-3">
        {(d.checks as PolicyCheck[]).map((c, i) => (
          <PolicyCheckRow key={i} check={c} />
        ))}
      </div>
    );
  }

  // Single check (most stages emit one check)
  if (d.check && typeof d.check === "string") {
    const detail = d.detail != null ? String(d.detail) : null;
    const clause = d.policy_clause != null ? String(d.policy_clause) : null;
    return (
      <div className="mt-2 bg-bg rounded border border-border p-3 space-y-1.5">
        {detail && <p className="text-xs text-text-secondary leading-snug">{detail}</p>}
        {clause && <span className="policy-ref">{clause}</span>}
        {Object.entries(d)
          .filter(([k]) => !["check", "detail", "policy_clause"].includes(k))
          .map(([k, v]) => (
            <div key={k} className="flex gap-2 items-baseline">
              <span className="label text-[10px]">{k}</span>
              <span className="font-mono text-xs text-text-primary">
                {typeof v === "object" ? JSON.stringify(v) : String(v as string | number | boolean)}
              </span>
            </div>
          ))}
      </div>
    );
  }

  // Extraction details: field_confidence map
  if (d.overall_confidence !== undefined) {
    const fc = d.field_confidence as Record<string, number> | undefined;
    const isPartial = Boolean(d.is_partial);
    const notes = d.extraction_notes != null ? String(d.extraction_notes) : null;
    return (
      <div className="mt-2 bg-bg rounded border border-border p-3 space-y-1.5">
        <div className="flex gap-2 items-baseline">
          <span className="label text-[10px]">overall_confidence</span>
          <span className="font-mono text-xs text-text-primary tabular">
            {Number(d.overall_confidence).toFixed(2)}
          </span>
          {isPartial && <span className="font-mono text-xs text-warn">partial</span>}
        </div>
        {fc && Object.keys(fc).length > 0 && (
          <div>
            <p className="label text-[10px] mb-1">field confidence</p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
              {Object.entries(fc).map(([field, conf]) => (
                <div key={field} className="flex justify-between gap-2">
                  <span className="font-mono text-[11px] text-text-secondary">{field}</span>
                  <span className="font-mono text-[11px] tabular text-text-primary">
                    {Number(conf).toFixed(2)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
        {notes && <p className="text-xs text-warn italic">{notes}</p>}
      </div>
    );
  }

  // Fallback: key/value pairs
  const entries = Object.entries(d).filter(([, v]) => v !== null && v !== undefined);
  if (entries.length === 0) return null;
  return (
    <div className="mt-2 bg-bg rounded border border-border p-3 space-y-1">
      {entries.map(([k, v]) => (
        <div key={k} className="flex gap-2 items-baseline">
          <span className="label text-[10px]">{k}</span>
          <span className="font-mono text-xs text-text-primary break-all">
            {typeof v === "object" ? JSON.stringify(v, null, 0) : String(v as string | number | boolean)}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Single trace event row ────────────────────────────────────────────────────

function TraceEventRow({ event, defaultOpen }: { event: TraceEvent; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const hasDetails = Object.keys(event.details).length > 0;

  return (
    <div className={`relative pl-6 pb-4 ${STATUS_BORDER[event.status]}`}>
      {/* Vertical rule */}
      <div className="absolute left-[7px] top-3 bottom-0 w-px bg-border" />

      {/* Dot */}
      <div className="absolute left-0 top-[5px]">
        <div className={`w-3.5 h-3.5 rounded-full border-2 border-bg flex items-center justify-center`}
          style={{ background: event.status === "ok" ? "#4A7C59" : event.status === "degraded" ? "#4A6275" : "#8B3A3A" }}
        />
      </div>

      {/* Header row */}
      <button
        onClick={() => hasDetails && setOpen(o => !o)}
        className={`w-full text-left flex items-start gap-2 group ${hasDetails ? "cursor-pointer" : "cursor-default"}`}
      >
        <span className="font-mono text-xs font-medium text-text-primary mt-px min-w-[160px]">
          {event.stage}
        </span>
        <span className="text-xs text-text-secondary flex-1 leading-snug">{event.summary}</span>
        <span className={`text-[10px] font-mono font-medium mt-px ${STATUS_LABEL[event.status] ?? "text-text-muted"}`}>
          {event.status}
        </span>
        {hasDetails && (
          <span className="text-text-muted ml-1 mt-px flex-shrink-0">
            {open
              ? <ChevronDown size={12} />
              : <ChevronRight size={12} />
            }
          </span>
        )}
      </button>

      {/* Timestamp */}
      <div className="font-mono text-[10px] text-text-muted mt-0.5 ml-0">
        {new Date(event.timestamp).toLocaleTimeString("en-IN", { hour12: false })}
        {" · "}
        {event.component}
      </div>

      {/* Expanded details */}
      {open && hasDetails && <EventDetails event={event} />}
    </div>
  );
}

// ── Main timeline ─────────────────────────────────────────────────────────────

export function TraceTimeline({ trace }: { trace: ClaimTrace }) {
  return (
    <div>
      <div className="flex items-baseline justify-between mb-3">
        <p className="label">Processing Trace</p>
        <span className="font-mono text-[10px] text-text-muted">{trace.events.length} events</span>
      </div>

      <div className="space-y-0">
        {trace.events.map((ev, i) => (
          <TraceEventRow
            key={i}
            event={ev}
            defaultOpen={ev.status !== "ok"}
          />
        ))}
      </div>

      {trace.final_decision_explanation && (
        <div className="mt-4 pt-4 border-t border-border">
          <p className="label mb-1.5">Explanation</p>
          <p className="text-sm text-text-primary leading-relaxed">
            {trace.final_decision_explanation}
          </p>
        </div>
      )}

      <div className="mt-3 flex items-center gap-1.5">
        <span className="label text-[10px]">Claim ID</span>
        <span className="font-mono text-[11px] text-text-muted">{trace.claim_id}</span>
      </div>
    </div>
  );
}
