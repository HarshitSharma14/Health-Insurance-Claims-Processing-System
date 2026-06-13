import React from "react";
import { FileX, FileQuestion, Users } from "lucide-react";
import type { DocumentVerificationResult, VerificationFailureType } from "../types";

const FAILURE_META: Record<VerificationFailureType, { icon: React.ReactNode; label: string }> = {
  WRONG_OR_MISSING_DOCUMENTS: {
    icon: <FileX size={15} />,
    label: "Wrong or missing documents",
  },
  UNREADABLE_DOCUMENT: {
    icon: <FileQuestion size={15} />,
    label: "Document unreadable",
  },
  PATIENT_MISMATCH: {
    icon: <Users size={15} />,
    label: "Patient identity mismatch",
  },
};

function DocTag({ name, variant }: { name: string; variant: "received" | "required" | "missing" | "unreadable" }) {
  const colors: Record<string, string> = {
    received:  "bg-bg text-text-secondary border-border",
    required:  "bg-bg text-text-primary border-border-strong",
    missing:   "bg-fail-bg text-fail border-fail",
    unreadable:"bg-warn-bg text-warn border-warn",
  };
  return (
    <span className={`inline-block font-mono text-[11px] px-2 py-0.5 rounded border ${colors[variant]} mr-1.5 mb-1.5`}>
      {name.replace(/_/g, " ")}
    </span>
  );
}

export function VerificationFailureView({ data }: { data: DocumentVerificationResult }) {
  const ft = data.failure_type as VerificationFailureType;
  const meta = ft ? FAILURE_META[ft] : null;
  const isPatientMismatch = ft === "PATIENT_MISMATCH";

  return (
    <div className="border-l-2 border-warn bg-surface rounded-r border border-l-0 border-border">
      {/* Header */}
      <div className="flex items-center gap-2.5 px-5 py-3.5 border-b border-border">
        <span className="text-warn">{meta?.icon}</span>
        <div>
          <p className="text-xs font-medium text-warn uppercase tracking-wide">{meta?.label}</p>
          <p className="text-[11px] text-text-muted mt-px">Claim stopped before processing</p>
        </div>
      </div>

      {/* Message */}
      <div className="px-5 py-4 border-b border-border">
        <p className="text-sm text-text-primary leading-relaxed">{data.message}</p>
      </div>

      {/* Document comparison */}
      <div className="px-5 py-4">
        {isPatientMismatch ? (
          // TC003: name-per-document comparison
          <div>
            <p className="label mb-3">Identity discrepancy</p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-[11px] text-text-muted mb-1.5">Received documents</p>
                {data.received_documents.map((doc, i) => (
                  <DocTag key={i} name={doc} variant="received" />
                ))}
              </div>
              <div>
                <p className="text-[11px] text-text-muted mb-1.5">Required documents</p>
                {data.required_documents.map((doc, i) => (
                  <DocTag key={i} name={doc} variant="required" />
                ))}
              </div>
            </div>
          </div>
        ) : (
          // TC001 (wrong/missing) and TC002 (unreadable)
          <div className="grid grid-cols-2 gap-6">
            <div>
              <p className="label mb-2">Received</p>
              {data.received_documents.length > 0
                ? data.received_documents.map((doc, i) => (
                    <DocTag key={i} name={doc} variant="received" />
                  ))
                : <span className="text-xs text-text-muted">None</span>
              }
              {data.unreadable_documents.map((id, i) => (
                <div key={i} className="mt-1">
                  <DocTag name={id} variant="unreadable" />
                </div>
              ))}
            </div>
            <div>
              <p className="label mb-2">Required</p>
              {data.required_documents.map((doc, i) => {
                const isMissing = data.missing_documents.includes(doc);
                return <DocTag key={i} name={doc} variant={isMissing ? "missing" : "required"} />;
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
