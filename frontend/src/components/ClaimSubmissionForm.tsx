import React, { useState, useRef } from "react";
import { Paperclip, X, Loader2 } from "lucide-react";
import type { PipelineResponse } from "../types";

interface Props {
  onResult: (result: PipelineResponse) => void;
}

const CATEGORIES = [
  "CONSULTATION", "DIAGNOSTIC", "PHARMACY",
  "DENTAL", "VISION", "ALTERNATIVE_MEDICINE",
] as const;

function FieldLabel({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return (
    <label className="block">
      <span className="label block mb-1">
        {children}
        {required && <span className="text-accent ml-0.5">*</span>}
      </span>
    </label>
  );
}

const inputCls = "w-full bg-surface border border-border rounded px-3 py-2 text-sm text-text-primary font-sans placeholder-text-muted focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent transition-colors";

export function ClaimSubmissionForm({ onResult }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFiles = (newFiles: FileList | null) => {
    if (!newFiles) return;
    setFiles(prev => [...prev, ...Array.from(newFiles)]);
  };

  const removeFile = (i: number) => setFiles(prev => prev.filter((_, j) => j !== i));

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (files.length === 0) { setError("Upload at least one document."); return; }
    setError(null);
    setLoading(true);

    const form = e.currentTarget;
    const fd = new FormData();
    fd.append("member_id", (form.elements.namedItem("member_id") as HTMLInputElement).value);
    fd.append("policy_id", (form.elements.namedItem("policy_id") as HTMLInputElement).value);
    fd.append("claim_category", (form.elements.namedItem("claim_category") as HTMLSelectElement).value);
    fd.append("treatment_date", (form.elements.namedItem("treatment_date") as HTMLInputElement).value);
    fd.append("claimed_amount", (form.elements.namedItem("claimed_amount") as HTMLInputElement).value);
    const hospitalName = (form.elements.namedItem("hospital_name") as HTMLInputElement).value;
    if (hospitalName) fd.append("hospital_name", hospitalName);
    files.forEach(f => fd.append("files", f));

    try {
      const res = await fetch("/claims", { method: "POST", body: fd });
      const json = await res.json();
      if (!res.ok) { setError(json.detail ?? `Error ${res.status}`); return; }
      onResult(json as PipelineResponse);
    } catch {
      setError("Network error — is the backend running on port 8000?");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className="border-l-2 border-fail bg-fail-bg px-4 py-3 rounded-r text-sm text-fail">
          {error}
        </div>
      )}

      {/* Member details */}
      <section>
        <p className="label mb-3 text-text-primary border-b border-border pb-1.5">Member</p>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <FieldLabel required>Member ID</FieldLabel>
            <input name="member_id" type="text" required className={inputCls} placeholder="EMP001" />
          </div>
          <div>
            <FieldLabel required>Policy ID</FieldLabel>
            <input name="policy_id" type="text" required className={inputCls} placeholder="PLUM_GHI_2024" />
          </div>
        </div>
      </section>

      {/* Claim details */}
      <section>
        <p className="label mb-3 text-text-primary border-b border-border pb-1.5">Claim</p>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <FieldLabel required>Category</FieldLabel>
            <select name="claim_category" required className={inputCls}>
              <option value="">Select category</option>
              {CATEGORIES.map(c => (
                <option key={c} value={c}>{c.replace(/_/g, " ")}</option>
              ))}
            </select>
          </div>
          <div>
            <FieldLabel required>Treatment Date</FieldLabel>
            <input name="treatment_date" type="date" required className={inputCls} />
          </div>
          <div>
            <FieldLabel required>Claimed Amount (₹)</FieldLabel>
            <input name="claimed_amount" type="number" min={500} step="0.01" required className={inputCls} placeholder="1500.00" />
          </div>
          <div>
            <FieldLabel>Hospital Name</FieldLabel>
            <input name="hospital_name" type="text" className={inputCls} placeholder="Optional — for network discount" />
          </div>
        </div>
      </section>

      {/* Documents */}
      <section>
        <p className="label mb-3 text-text-primary border-b border-border pb-1.5">
          Documents <span className="text-accent">*</span>
        </p>

        {/* File list */}
        {files.length > 0 && (
          <div className="mb-3 space-y-1">
            {files.map((f, i) => (
              <div key={i} className="flex items-center gap-2 text-xs text-text-secondary bg-bg border border-border rounded px-3 py-1.5">
                <Paperclip size={11} className="flex-shrink-0 text-text-muted" />
                <span className="flex-1 font-mono truncate">{f.name}</span>
                <span className="text-text-muted tabular">{(f.size / 1024).toFixed(0)} KB</span>
                <button type="button" onClick={() => removeFile(i)} className="text-text-muted hover:text-fail transition-colors ml-1">
                  <X size={11} />
                </button>
              </div>
            ))}
          </div>
        )}

        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          className="w-full border border-dashed border-border-strong rounded px-4 py-3 text-xs text-text-secondary hover:border-accent hover:text-accent transition-colors text-left flex items-center gap-2"
        >
          <Paperclip size={13} />
          Add documents (image or PDF)
        </button>
        <input
          ref={fileRef}
          type="file"
          multiple
          accept="image/*,application/pdf"
          className="hidden"
          onChange={e => handleFiles(e.target.files)}
        />
      </section>

      {/* Submit */}
      <div className="pt-1">
        <button
          type="submit"
          disabled={loading}
          className="bg-accent hover:bg-accent-hover disabled:opacity-50 text-white font-sans font-medium text-sm px-5 py-2.5 rounded transition-colors flex items-center gap-2"
        >
          {loading && <Loader2 size={14} className="animate-spin" />}
          {loading ? "Processing…" : "Submit Claim"}
        </button>
      </div>
    </form>
  );
}
