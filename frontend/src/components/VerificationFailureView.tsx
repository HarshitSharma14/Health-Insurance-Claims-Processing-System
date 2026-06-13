import { FileX, FileQuestion, Users } from "lucide-react";
import type { DocumentVerificationResult, VerificationFailureType } from "../types";

const META: Record<VerificationFailureType, { Icon: typeof FileX; label: string }> = {
  WRONG_OR_MISSING_DOCUMENTS: { Icon: FileX,       label: "Wrong or missing documents" },
  UNREADABLE_DOCUMENT:        { Icon: FileQuestion, label: "Document unreadable"         },
  PATIENT_MISMATCH:           { Icon: Users,        label: "Patient identity mismatch"   },
};

function DocChip({ name, variant }: { name: string; variant: "received" | "required" | "missing" | "unreadable" }) {
  const styles: Record<string, string> = {
    received:   "bg-paper border-border text-ink-muted",
    required:   "bg-paper border-border-strong text-ink",
    missing:    "bg-fail-bg border-fail text-fail",
    unreadable: "bg-warn-bg border-warn text-warn",
  };
  return (
    <span className={`inline-block font-mono text-[10px] px-2 py-0.5 rounded border mr-1.5 mb-1.5 ${styles[variant]}`}>
      {name.replace(/_/g, " ")}
    </span>
  );
}

export function VerificationFailureView({ data }: { data: DocumentVerificationResult }) {
  const ft        = data.failure_type as VerificationFailureType;
  const meta      = ft ? META[ft] : null;
  const Icon      = meta?.Icon ?? FileX;
  const isMismatch = ft === "PATIENT_MISMATCH";

  return (
    <div className="border-l-2 border-warn rounded-r border border-l-0 border-border bg-surface">
      <div className="flex items-center gap-2.5 px-5 py-3 border-b border-border">
        <Icon size={14} className="text-warn flex-shrink-0" />
        <div>
          <p className="text-[10px] font-semibold text-warn uppercase tracking-wide font-sans">{meta?.label}</p>
          <p className="text-[10px] text-ink-muted mt-px font-sans">Claim stopped before processing</p>
        </div>
      </div>

      <div className="px-5 py-3.5 border-b border-border">
        <p className="text-sm text-ink leading-relaxed font-sans">{data.message}</p>
      </div>

      <div className="px-5 py-3.5">
        {isMismatch ? (
          <div>
            <p className="label mb-2.5">Identity discrepancy by document</p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-[10px] text-ink-muted mb-1.5 font-sans">Documents received</p>
                {data.received_documents.map((d, i) => <DocChip key={i} name={d} variant="received" />)}
              </div>
              <div>
                <p className="text-[10px] text-ink-muted mb-1.5 font-sans">Documents required</p>
                {data.required_documents.map((d, i) => <DocChip key={i} name={d} variant="required" />)}
              </div>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-5">
            <div>
              <p className="label mb-2">Received</p>
              {data.received_documents.length > 0
                ? data.received_documents.map((d, i) => <DocChip key={i} name={d} variant="received" />)
                : <span className="text-xs text-ink-muted font-sans">None</span>
              }
              {data.unreadable_documents.map((id, i) => (
                <div key={i}><DocChip name={id} variant="unreadable" /></div>
              ))}
            </div>
            <div>
              <p className="label mb-2">Required</p>
              {data.required_documents.map((d, i) => (
                <DocChip key={i} name={d} variant={data.missing_documents.includes(d) ? "missing" : "required"} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
