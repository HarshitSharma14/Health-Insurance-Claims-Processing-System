import React, { useState, useRef, useCallback } from "react";
import {
  Upload, X, Loader2, FileText, FileImage,
  Stethoscope, FlaskConical, Pill, Smile, Eye, Leaf,
  CheckCircle2, Building2,
} from "lucide-react";
import type { PipelineResponse } from "../types";
import { TEST_CASES, TC_DESCRIPTIONS } from "../test-cases";
import { LoadingStages } from "./LoadingStages";

// ── Constants ─────────────────────────────────────────────────────────────────

const NETWORK_HOSPITALS = [
  "Apollo Hospitals",
  "Fortis Healthcare",
  "Max Healthcare",
  "Manipal Hospitals",
  "Narayana Health",
  "Medanta",
  "Kokilaben Dhirubhai Ambani Hospital",
  "Aster CMI Hospital",
  "Columbia Asia",
  "Sakra World Hospital",
];

const CATEGORIES = [
  { value: "CONSULTATION",         label: "Consultation",   Icon: Stethoscope },
  { value: "DIAGNOSTIC",           label: "Diagnostic",     Icon: FlaskConical },
  { value: "PHARMACY",             label: "Pharmacy",       Icon: Pill },
  { value: "DENTAL",               label: "Dental",         Icon: Smile },
  { value: "VISION",               label: "Vision",         Icon: Eye },
  { value: "ALTERNATIVE_MEDICINE", label: "Alt. Medicine",  Icon: Leaf },
] as const;

type CategoryValue = typeof CATEGORIES[number]["value"];

// ── Minimal 1×1 JPEG used as placeholder for TC001-TC003 document slots ───────
// We need real bytes for the multipart endpoint; this is a valid 1×1 white JPEG.
const PLACEHOLDER_JPEG_B64 =
  "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEQMRAD8AJQAB/9k=";

function b64toBlob(b64: string, type = "image/jpeg"): Blob {
  const binary = atob(b64);
  const arr = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) arr[i] = binary.charCodeAt(i);
  return new Blob([arr], { type });
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function FileIcon({ name }: { name: string }) {
  const ext = (name.split(".").pop() ?? "").toLowerCase();
  if (["jpg", "jpeg", "png", "gif", "webp"].includes(ext))
    return <FileImage size={12} className="flex-shrink-0 text-ink-muted" />;
  return <FileText size={12} className="flex-shrink-0 text-ink-muted" />;
}

const inputCls =
  "w-full bg-surface border border-border rounded px-2.5 py-1.5 text-sm text-ink " +
  "font-sans placeholder-ink-muted focus:outline-none transition-colors";

const labelCls = "label block mb-1";

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <p className="label text-ink border-b border-border pb-1 mb-3">{children}</p>
  );
}

// ── Build ExtractedDocumentData from a TC doc with content ────────────────────

function buildExtracted(doc: { file_id: string; actual_type: string; content?: Record<string, unknown> }) {
  const c = doc.content ?? {};
  const lineItems = (c.line_items as Array<{ description: string; amount: number }> | undefined)
    ?.map(li => ({ description: li.description, amount: li.amount })) ?? [];
  return {
    file_id:             doc.file_id,
    document_type:       doc.actual_type,
    patient_name:        (c.patient_name as string) ?? null,
    diagnosis:           (c.diagnosis as string) ?? null,
    treatment:           (c.treatment as string) ?? null,
    doctor_name:         (c.doctor_name as string) ?? null,
    doctor_registration: (c.doctor_registration as string) ?? null,
    hospital_name:       (c.hospital_name as string) ?? null,
    date:                (c.date as string) ?? null,
    line_items:          lineItems,
    total:               (c.total as number) ?? null,
    tests_ordered:       (c.tests_ordered as string[]) ?? [],
    field_confidence:    {},
    overall_confidence:  0.92,
    is_partial:          false,
    extraction_notes:    null,
  };
}

// ── Main form component ───────────────────────────────────────────────────────

interface Props {
  onResult: (result: PipelineResponse) => void;
}

export function ClaimSubmissionForm({ onResult }: Props) {
  const [loading,       setLoading]       = useState(false);
  const [files,         setFiles]         = useState<File[]>([]);
  const [category,      setCategory]      = useState<CategoryValue | "">("");
  const [dragging,      setDragging]      = useState(false);
  const [hospitalInput, setHospitalInput] = useState("");
  const [hospitalOpen,  setHospitalOpen]  = useState(false);
  const [amountError,   setAmountError]   = useState<string | null>(null);
  const [dateError,     setDateError]     = useState<string | null>(null);
  const [submitError,   setSubmitError]   = useState<string | null>(null);
  const [catError,      setCatError]      = useState<string | null>(null);
  const [docError,      setDocError]      = useState<string | null>(null);

  const fileRef        = useRef<HTMLInputElement>(null);
  const hospitalRef    = useRef<HTMLInputElement>(null);

  // ── Hospital typeahead ──────────────────────────────────────────────────────

  const hospitalMatches = hospitalInput.length > 0
    ? NETWORK_HOSPITALS.filter(h => h.toLowerCase().includes(hospitalInput.toLowerCase()))
    : [];
  const isNetworkMatch = NETWORK_HOSPITALS.some(
    h => h.toLowerCase() === hospitalInput.toLowerCase()
  );
  const hasInput        = hospitalInput.length > 0;

  // ── File handling ──────────────────────────────────────────────────────────

  const addFiles = useCallback((incoming: FileList | File[] | null) => {
    if (!incoming) return;
    setFiles(prev => {
      const existing = new Set(prev.map(f => f.name + f.size));
      const arr = Array.from(incoming);
      return [...prev, ...arr.filter(f => !existing.has(f.name + f.size))];
    });
    setDocError(null);
  }, []);

  const removeFile = (i: number) => setFiles(prev => prev.filter((_, j) => j !== i));

  // ── Amount validation on blur ──────────────────────────────────────────────

  const handleAmountBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    const v = parseFloat(e.target.value);
    if (!isNaN(v) && v < 500) setAmountError("Minimum claimable amount is ₹500");
    else setAmountError(null);
  };

  // ── Date validation on blur ────────────────────────────────────────────────

  const handleDateBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    const v = e.target.value;
    if (v && new Date(v) > new Date()) setDateError("Treatment date cannot be in the future");
    else setDateError(null);
  };

  // ── Category keyboard nav ──────────────────────────────────────────────────

  const handleCatKeyDown = (e: React.KeyboardEvent, idx: number) => {
    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      const next = (idx + 1) % CATEGORIES.length;
      (e.currentTarget.parentElement?.children[next] as HTMLElement)?.focus();
    }
    if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      const prev = (idx - 1 + CATEGORIES.length) % CATEGORIES.length;
      (e.currentTarget.parentElement?.children[prev] as HTMLElement)?.focus();
    }
  };

  // ── Submit (real form) ─────────────────────────────────────────────────────

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    let hasError = false;
    if (!category)          { setCatError("Select a claim category."); hasError = true; } else setCatError(null);
    if (files.length === 0) { setDocError("Upload at least one document."); hasError = true; } else setDocError(null);
    if (hasError) return;
    setSubmitError(null);
    setLoading(true);

    const form = e.currentTarget;
    const fd   = new FormData();
    const get  = (n: string) => (form.elements.namedItem(n) as HTMLInputElement).value;
    fd.append("member_id",      get("member_id"));
    fd.append("policy_id",      get("policy_id"));
    fd.append("claim_category", category);
    fd.append("treatment_date", get("treatment_date"));
    fd.append("claimed_amount", get("claimed_amount"));
    if (hospitalInput) fd.append("hospital_name", hospitalInput);
    files.forEach(f => fd.append("files", f));

    try {
      const res  = await fetch("/claims", { method: "POST", body: fd });
      const json = await res.json();
      if (!res.ok) { setSubmitError(json.detail ?? `Error ${res.status}`); setLoading(false); return; }
      onResult(json as PipelineResponse);
    } catch {
      setSubmitError("Network error — is the backend running on port 8000?");
      setLoading(false);
    }
  };

  // ── TC quick-loader ────────────────────────────────────────────────────────

  const runTestCase = async (caseId: string) => {
    const tc = TEST_CASES[caseId];
    if (!tc) return;
    setLoading(true);
    setSubmitError(null);

    const hasContent = tc.documents.some(d => d.content);

    try {
      let res: Response;

      if (hasContent) {
        // POST /claims/json with pre_extracted_documents
        const body = {
          member_id:                tc.member_id,
          policy_id:                tc.policy_id,
          claim_category:           tc.claim_category,
          treatment_date:           tc.treatment_date,
          submission_date:          tc.treatment_date,
          claimed_amount:           tc.claimed_amount,
          hospital_name:            tc.hospital_name ?? null,
          ytd_claims_amount:        tc.ytd_claims_amount ?? null,
          claims_history:           (tc.claims_history ?? []).map(h => ({
            claim_id: h.claim_id, date: h.date, amount: h.amount, provider: h.provider ?? null,
          })),
          simulate_component_failure: tc.simulate_component_failure ?? false,
          documents:                tc.documents.map(d => ({
            file_id:           d.file_id,
            actual_type:       d.actual_type,
            file_name:         d.file_name ?? null,
            patient_name_on_doc: d.patient_name_on_doc ?? null,
          })),
          pre_extracted_documents:  tc.documents.map(buildExtracted),
        };
        res = await fetch("/claims/json", {
          method:  "POST",
          headers: { "Content-Type": "application/json" },
          body:    JSON.stringify(body),
        });
      } else {
        // POST /claims multipart — attach placeholder images per document
        const fd = new FormData();
        fd.append("member_id",      tc.member_id);
        fd.append("policy_id",      tc.policy_id);
        fd.append("claim_category", tc.claim_category);
        fd.append("treatment_date", tc.treatment_date);
        fd.append("claimed_amount", String(tc.claimed_amount));
        if (tc.hospital_name) fd.append("hospital_name", tc.hospital_name);
        // Attach one placeholder JPEG per document, named to hint at document type
        for (const doc of tc.documents) {
          const blob = b64toBlob(PLACEHOLDER_JPEG_B64);
          const name = doc.file_name ?? `${doc.actual_type.toLowerCase()}.jpg`;
          const file = new File([blob], name, { type: "image/jpeg" });
          fd.append("files", file);
        }
        res = await fetch("/claims", { method: "POST", body: fd });
      }

      const json = await res.json();
      if (!res.ok) { setSubmitError(json.detail ?? `Error ${res.status}`); setLoading(false); return; }
      onResult(json as PipelineResponse);
    } catch {
      setSubmitError("Network error — is the backend running on port 8000?");
      setLoading(false);
    }
  };

  // ── Loading state ──────────────────────────────────────────────────────────

  if (loading) return <LoadingStages />;

  // ── Form ───────────────────────────────────────────────────────────────────

  return (
    <form onSubmit={handleSubmit} className="divide-y divide-border">

      {/* Member */}
      <div className="px-5 py-4 section-1">
        <SectionHeader>Member</SectionHeader>
        {submitError && (
          <div className="border-l-2 border-fail bg-fail-bg px-3 py-2 mb-3 text-xs text-fail font-sans">
            {submitError}
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelCls}>Member ID <span className="text-coral">*</span></label>
            <input name="member_id" type="text" required className={inputCls} placeholder="EMP001" />
          </div>
          <div>
            <label className={labelCls}>
              Policy ID <span className="text-coral">*</span>
              <span className="ml-1 normal-case font-normal text-ink-muted" style={{ fontSize: "9px", letterSpacing: 0 }}>
                (only valid value for this demo)
              </span>
            </label>
            <input name="policy_id" type="text" required className={inputCls}
              defaultValue="PLUM_GHI_2024" placeholder="PLUM_GHI_2024" />
          </div>
        </div>
      </div>

      {/* Claim */}
      <div className="px-5 py-4 section-2">
        <SectionHeader>Claim</SectionHeader>

        {/* Category segmented control */}
        <div className="mb-3">
          <label className={labelCls}>Category <span className="text-coral">*</span></label>
          <div
            role="group"
            aria-label="Claim category"
            className="flex flex-wrap gap-1 mt-1"
          >
            {CATEGORIES.map(({ value, label, Icon }, idx) => {
              const active = category === value;
              return (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  tabIndex={active || (category === "" && idx === 0) ? 0 : -1}
                  onClick={() => { setCategory(value); setCatError(null); }}
                  onKeyDown={e => handleCatKeyDown(e, idx)}
                  className={[
                    "flex items-center gap-1.5 px-2 py-1.5 rounded text-xs font-medium transition-colors border",
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
          {catError && <p className="text-[11px] text-fail mt-1 font-sans">{catError}</p>}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelCls}>Treatment Date <span className="text-coral">*</span></label>
            <input name="treatment_date" type="date" required className={inputCls}
              onBlur={handleDateBlur}
              max={new Date().toISOString().split("T")[0]}
            />
            {dateError && <p className="text-[11px] text-fail mt-1 font-sans">{dateError}</p>}
          </div>
          <div>
            <label className={labelCls}>Claimed Amount (₹) <span className="text-coral">*</span></label>
            <input name="claimed_amount" type="number" min={500} step="0.01" required
              className={inputCls} placeholder="1500.00"
              onBlur={handleAmountBlur}
            />
            {amountError && <p className="text-[11px] text-fail mt-1 font-sans">{amountError}</p>}
          </div>

          {/* Hospital name with typeahead */}
          <div className="col-span-2 relative">
            <label className={labelCls}>Hospital Name</label>
            <div className="relative">
              <Building2 size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-muted pointer-events-none" />
              <input
                ref={hospitalRef}
                name="hospital_name"
                type="text"
                className={inputCls + " pl-7"}
                placeholder="Optional — triggers network discount if matched"
                value={hospitalInput}
                onChange={e => { setHospitalInput(e.target.value); setHospitalOpen(true); }}
                onFocus={() => setHospitalOpen(true)}
                onBlur={() => setTimeout(() => setHospitalOpen(false), 150)}
                autoComplete="off"
              />
            </div>

            {/* Dropdown */}
            {hospitalOpen && hospitalMatches.length > 0 && (
              <div className="absolute z-10 w-full mt-0.5 bg-surface border border-border rounded shadow-sm">
                {hospitalMatches.map(h => (
                  <button
                    key={h}
                    type="button"
                    className="w-full text-left px-3 py-1.5 text-xs font-sans text-ink hover:bg-paper transition-colors flex items-center gap-2"
                    onMouseDown={() => { setHospitalInput(h); setHospitalOpen(false); }}
                  >
                    <CheckCircle2 size={11} className="text-ok flex-shrink-0" />
                    {h}
                  </button>
                ))}
              </div>
            )}

            {/* Match indicator */}
            {hasInput && (
              <p className={`text-[11px] mt-1 font-sans flex items-center gap-1 ${isNetworkMatch ? "text-ok" : "text-ink-muted"}`}>
                {isNetworkMatch
                  ? <><CheckCircle2 size={11} /> Network hospital — 20% discount applies</>
                  : "No network discount for this hospital"
                }
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Documents */}
      <div className="px-5 py-4 section-3">
        <SectionHeader>Documents <span className="text-coral">*</span></SectionHeader>

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
        {docError && <p className="text-[11px] text-fail mt-1 font-sans">{docError}</p>}
        <input ref={fileRef} type="file" multiple accept="image/*,application/pdf"
          className="hidden" onChange={e => addFiles(e.target.files)} />
      </div>

      {/* Submit */}
      <div className="px-5 py-4 section-4">
        <button
          type="submit"
          disabled={loading || !!amountError || !!dateError}
          className="flex items-center gap-2 px-5 py-2 rounded text-sm font-sans font-medium text-white transition-colors disabled:opacity-50"
          style={{ backgroundColor: "#ff4052" }}
          onMouseEnter={e => { if (!loading) (e.currentTarget as HTMLButtonElement).style.backgroundColor = "#e6293c"; }}
          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = "#ff4052"; }}
        >
          {loading && <Loader2 size={13} className="animate-spin" />}
          {loading ? "Processing…" : "Submit Claim"}
        </button>
      </div>

      {/* ── Dev tools panel ── */}
      <DevPanel onRun={runTestCase} />
    </form>
  );
}

// ── Dev quick-loader panel ────────────────────────────────────────────────────

function DevPanel({ onRun }: { onRun: (id: string) => void }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="px-5 py-3 border-t border-dashed border-border-strong">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="label text-ink-muted hover:text-ink transition-colors flex items-center gap-1.5"
      >
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-ink-muted opacity-50" />
        DEVELOPMENT TOOLS
        <span className="ml-1 text-[9px] font-mono opacity-50">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="mt-3">
          <p className="text-[10px] text-ink-muted font-sans mb-2">
            Load a test case and auto-submit. TC001-TC003 use placeholder images;
            TC004-TC012 use pre-extracted content (no LLM calls).
          </p>
          <div className="flex flex-wrap gap-1.5">
            {Object.keys(TEST_CASES).map(id => (
              <button
                key={id}
                type="button"
                onClick={() => onRun(id)}
                title={TC_DESCRIPTIONS[id]}
                className="font-mono text-[10px] px-2 py-1 rounded border border-border-strong
                  text-ink-muted bg-paper hover:border-aubergine hover:text-ink transition-colors"
              >
                {id}
              </button>
            ))}
          </div>
          <div className="mt-2 space-y-0.5">
            {Object.entries(TC_DESCRIPTIONS).map(([id, desc]) => (
              <p key={id} className="text-[10px] text-ink-muted font-sans">
                <span className="font-mono">{id}</span> — {desc}
              </p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
