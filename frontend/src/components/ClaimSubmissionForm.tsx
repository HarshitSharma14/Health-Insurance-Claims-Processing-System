import React, { useState, useRef } from "react";
import {
  Upload, X, Loader2, FileText, FileImage,
  Stethoscope, FlaskConical, Pill, Smile, Eye, Leaf,
} from "lucide-react";
import type { PipelineResponse } from "../types";

interface Props {
  onResult: (result: PipelineResponse) => void;
}

const CATEGORIES = [
  { value: "CONSULTATION",         label: "Consultation",   Icon: Stethoscope },
  { value: "DIAGNOSTIC",           label: "Diagnostic",     Icon: FlaskConical },
  { value: "PHARMACY",             label: "Pharmacy",       Icon: Pill },
  { value: "DENTAL",               label: "Dental",         Icon: Smile },
  { value: "VISION",               label: "Vision",         Icon: Eye },
  { value: "ALTERNATIVE_MEDICINE", label: "Alt. Medicine",  Icon: Leaf },
] as const;

type CategoryValue = typeof CATEGORIES[number]["value"];

function FileIcon({ name }: { name: string }) {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  if (["jpg", "jpeg", "png", "gif", "webp"].includes(ext))
    return <FileImage size={12} className="flex-shrink-0 text-ink-muted" />;
  return <FileText size={12} className="flex-shrink-0 text-ink-muted" />;
}

const inputCls =
  "w-full bg-surface border border-border rounded px-2.5 py-1.5 text-sm text-ink " +
  "font-sans placeholder-ink-muted focus:outline-none transition-colors";

const labelCls = "label block mb-1";

export function ClaimSubmissionForm({ onResult }: Props) {
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState<string | null>(null);
  const [files,    setFiles]    = useState<File[]>([]);
  const [category, setCategory] = useState<CategoryValue | "">("");
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const addFiles = (incoming: FileList | null) => {
    if (!incoming) return;
    setFiles(prev => {
      const existing = new Set(prev.map(f => f.name + f.size));
      return [...prev, ...Array.from(incoming).filter(f => !existing.has(f.name + f.size))];
    });
  };

  const removeFile = (i: number) => setFiles(prev => prev.filter((_, j) => j !== i));

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!category)          { setError("Select a claim category."); return; }
    if (files.length === 0) { setError("Upload at least one document."); return; }
    setError(null);
    setLoading(true);

    const form = e.currentTarget;
    const fd   = new FormData();
    const get  = (n: string) => (form.elements.namedItem(n) as HTMLInputElement).value;
    fd.append("member_id",      get("member_id"));
    fd.append("policy_id",      get("policy_id"));
    fd.append("claim_category", category);
    fd.append("treatment_date", get("treatment_date"));
    fd.append("claimed_amount", get("claimed_amount"));
    const hospital = get("hospital_name");
    if (hospital) fd.append("hospital_name", hospital);
    files.forEach(f => fd.append("files", f));

    try {
      const res  = await fetch("/claims", { method: "POST", body: fd });
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
    <form onSubmit={handleSubmit} className="divide-y divide-border">

      {/* ── Member ── */}
      <div className="px-5 py-4 section-1">
        <p className="label text-ink border-b border-border pb-1 mb-3">Member</p>
        {error && (
          <div className="border-l-2 border-fail bg-fail-bg px-3 py-2 mb-3 text-xs text-fail font-sans">
            {error}
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelCls}>Member ID <span className="text-coral">*</span></label>
            <input name="member_id" type="text" required className={inputCls} placeholder="EMP001" />
          </div>
          <div>
            <label className={labelCls}>Policy ID <span className="text-coral">*</span></label>
            <input name="policy_id" type="text" required className={inputCls} placeholder="PLUM_GHI_2024" />
          </div>
        </div>
      </div>

      {/* ── Claim ── */}
      <div className="px-5 py-4 section-2">
        <p className="label text-ink border-b border-border pb-1 mb-3">Claim</p>

        {/* Segmented category control */}
        <div className="mb-3">
          <label className={labelCls}>Category <span className="text-coral">*</span></label>
          <div className="flex flex-wrap gap-1 mt-1">
            {CATEGORIES.map(({ value, label, Icon }) => {
              const active = category === value;
              return (
                <button
                  key={value}
                  type="button"
                  onClick={() => setCategory(value)}
                  className={[
                    "flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium transition-colors border",
                    active
                      ? "border-aubergine bg-aubergine text-cream"
                      : "border-border bg-surface text-ink-light hover:border-ink-muted hover:text-ink",
                  ].join(" ")}
                >
                  <Icon size={11} />
                  {label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelCls}>Treatment Date <span className="text-coral">*</span></label>
            <input name="treatment_date" type="date" required className={inputCls} />
          </div>
          <div>
            <label className={labelCls}>Claimed Amount (₹) <span className="text-coral">*</span></label>
            <input name="claimed_amount" type="number" min={500} step="0.01" required
              className={inputCls} placeholder="1500.00" />
          </div>
          <div className="col-span-2">
            <label className={labelCls}>Hospital Name</label>
            <input name="hospital_name" type="text" className={inputCls}
              placeholder="Optional — triggers network discount if matched" />
          </div>
        </div>
      </div>

      {/* ── Documents ── */}
      <div className="px-5 py-4 section-3">
        <p className="label text-ink border-b border-border pb-1 mb-3">
          Documents <span className="text-coral">*</span>
        </p>

        {files.length > 0 && (
          <div className="mb-2 space-y-1">
            {files.map((f, i) => (
              <div key={i} className="flex items-center gap-2 bg-paper border border-border rounded px-2.5 py-1.5">
                <FileIcon name={f.name} />
                <span className="font-mono text-xs text-ink flex-1 truncate">{f.name}</span>
                <span className="text-[10px] text-ink-muted tabular flex-shrink-0">
                  {(f.size / 1024).toFixed(0)} KB
                </span>
                <button type="button" onClick={() => removeFile(i)}
                  className="text-ink-muted hover:text-fail transition-colors ml-0.5 flex-shrink-0">
                  <X size={11} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div
          onDragOver={e => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={e => { e.preventDefault(); setDragging(false); addFiles(e.dataTransfer.files); }}
          onClick={() => fileRef.current?.click()}
          className={[
            "flex items-center gap-2.5 px-4 py-3 border rounded cursor-pointer transition-colors text-xs font-sans",
            dragging
              ? "border-coral bg-fail-bg text-coral"
              : "border-border-strong border-dashed text-ink-muted hover:border-coral hover:text-coral",
          ].join(" ")}
        >
          <Upload size={13} className="flex-shrink-0" />
          <span>
            {files.length === 0 ? "Drop files here or click to browse — images or PDF" : "Add more documents"}
          </span>
        </div>
        <input ref={fileRef} type="file" multiple accept="image/*,application/pdf"
          className="hidden" onChange={e => addFiles(e.target.files)} />
      </div>

      {/* ── Submit ── */}
      <div className="px-5 py-4 section-4">
        <button
          type="submit"
          disabled={loading}
          className="flex items-center gap-2 px-5 py-2 rounded text-sm font-sans font-medium text-white
            transition-colors disabled:opacity-50"
          style={{ backgroundColor: loading ? "#e6293c" : "#ff4052" }}
          onMouseEnter={e => !loading && ((e.currentTarget as HTMLButtonElement).style.backgroundColor = "#e6293c")}
          onMouseLeave={e => !loading && ((e.currentTarget as HTMLButtonElement).style.backgroundColor = "#ff4052")}
        >
          {loading && <Loader2 size={13} className="animate-spin" />}
          {loading ? "Processing…" : "Submit Claim"}
        </button>
      </div>
    </form>
  );
}
