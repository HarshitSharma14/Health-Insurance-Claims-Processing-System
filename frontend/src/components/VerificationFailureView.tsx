import { FileX, FileQuestion, Users } from "lucide-react";
import type { DocumentVerificationResult, VerificationFailureType } from "../types";

const META: Record<VerificationFailureType, { Icon: typeof FileX; label: string }> = {
  WRONG_OR_MISSING_DOCUMENTS: { Icon: FileX,       label: "Wrong or missing documents" },
  UNREADABLE_DOCUMENT:        { Icon: FileQuestion, label: "Document unreadable"         },
  PATIENT_MISMATCH:           { Icon: Users,        label: "Patient identity mismatch"   },
};

function DocChip({
  name, variant,
}: {
  name: string;
  variant: "received" | "required" | "missing" | "unreadable";
}) {
  const styles: Record<string, string> = {
    received:   "bg-bg border-border text-text-secondary",
    required:   "bg-bg border-border-strong text-text-primary",
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
  const ft   = data.failure_type as VerificationFailureType;
  const meta = ft ? META[ft] : null;
  const Icon = meta?.Icon ?? FileX;
  const isMismatch = ft === "PATIENT_MISMATCH";

  return (
    <div className="border-l-2 border-warn rounded-r border border-l-0 border-border bg-surface">
      {/* Header */}
      <div className="flex items-center gap-2.5 px-5 py-3 border-b border-border">
        <Icon size={14} className="text-warn flex-shrink-0" />
        <div>
          <p className="text-[10px] font-semibold text-warn uppercase tracking-wide">{meta?.label}</p>
          <p className="text-[10px] text-text-muted mt-px">Claim stopped before processing</p>
        </div>
      </div>

      {/* Message */}
      <div className="px-5 py-3.5 border-b border-border">
        <p className="text-sm text-text-primary leading-relaxed">{data.message}</p>
      </div>

      {/* Document comparison */}
      <div className="px-5 py-3.5">
        {isMismatch ? (
          <div>
            <p className="label mb-2.5">Identity discrepancy by document</p>
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div>
                <p className="text-[10px] text-text-muted mb-1.5">Documents received</p>
                {data.received_documents.map((d, i) => (
                  <DocChip key={i} name={d} variant="received" />
                ))}
              </div>
              <div>
                <p className="text-[10px] text-text-muted mb-1.5">Documents required</p>
                {data.required_documents.map((d, i) => (
                  <DocChip key={i} name={d} variant="required" />
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-5">
            <div>
              <p className="label mb-2">Received</p>
              {data.received_documents.length > 0
                ? data.received_documents.map((d, i) => <DocChip key={i} name={d} variant="received" />)
                : <span className="text-xs text-text-muted">None</span>
              }
              {data.unreadable_documents.map((id, i) => (
                <div key={i}><DocChip name={id} variant="unreadable" /></div>
              ))}
            </div>
            <div>
              <p className="label mb-2">Required</p>
              {data.required_documents.map((d, i) => {
                const missing = data.missing_documents.includes(d);
                return <DocChip key={i} name={d} variant={missing ? "missing" : "required"} />;
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
