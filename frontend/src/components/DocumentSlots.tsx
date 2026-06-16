/**
 * Slotted document upload per claim category.
 *
 * Once a category is selected, shows one labeled slot per required document
 * type (from policy_terms.json → document_requirements) plus collapsed
 * optional slots.
 *
 * Each slot carries the user-declared document type — this is sent to the
 * backend as document_type_{i} so Stage 0 verification uses the declared
 * type rather than LLM classification.
 *
 * Category-change behaviour:
 *   - Slots that are empty: silently cleared / replaced with new slots.
 *   - Slots with an uploaded file: shown with a ⚠ "Re-check" warning.
 *     The user must explicitly keep (confirm) or remove (replace) the file.
 */
import React, { useRef, useState } from "react";
import { Upload, X, FileText, FileImage, AlertTriangle, Check, ExternalLink } from "lucide-react";

// ── Document requirements (mirrors policy_terms.json) ────────────────────────

export const DOC_REQUIREMENTS: Record<string, { required: string[]; optional: string[] }> = {
  CONSULTATION:         { required: ["PRESCRIPTION", "HOSPITAL_BILL"],          optional: ["LAB_REPORT", "DIAGNOSTIC_REPORT"] },
  DIAGNOSTIC:           { required: ["PRESCRIPTION", "LAB_REPORT", "HOSPITAL_BILL"], optional: ["DISCHARGE_SUMMARY"] },
  PHARMACY:             { required: ["PRESCRIPTION", "PHARMACY_BILL"],          optional: [] },
  DENTAL:               { required: ["HOSPITAL_BILL"],                           optional: ["PRESCRIPTION", "DENTAL_REPORT"] },
  VISION:               { required: ["PRESCRIPTION", "HOSPITAL_BILL"],          optional: [] },
  ALTERNATIVE_MEDICINE: { required: ["PRESCRIPTION", "HOSPITAL_BILL"],          optional: [] },
};

function humanType(t: string): string {
  return t.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

// ── Slot state ────────────────────────────────────────────────────────────────

export interface SlotState {
  docType: string;       // the declared document type for this slot
  required: boolean;
  file: File | null;
  // Set when a category change happened and this slot's old type ≠ new type
  staleType: string | null;
  confirmed: boolean;    // user clicked "Keep this file" after a type change
}

function FileIcon({ name }: { name: string }) {
  const ext = (name.split(".").pop() ?? "").toLowerCase();
  if (["jpg", "jpeg", "png", "gif", "webp"].includes(ext))
    return <FileImage size={11} className="flex-shrink-0 text-ink-muted" />;
  return <FileText size={11} className="flex-shrink-0 text-ink-muted" />;
}

// ── Build initial slots from category ────────────────────────────────────────

export function buildSlots(category: string, prev: SlotState[] = []): SlotState[] {
  const reqs = DOC_REQUIREMENTS[category];
  if (!reqs) return [];

  // Map old files: file's declared docType → file (only one per type)
  const prevByType = new Map<string, File>();
  for (const s of prev) {
    if (s.file) prevByType.set(s.docType, s.file);
  }

  const slots: SlotState[] = [];

  for (const dt of reqs.required) {
    const oldFile = prevByType.get(dt) ?? null;
    slots.push({ docType: dt, required: true, file: oldFile, staleType: null, confirmed: false });
  }
  for (const dt of reqs.optional) {
    const oldFile = prevByType.get(dt) ?? null;
    slots.push({ docType: dt, required: false, file: oldFile, staleType: null, confirmed: false });
  }

  return slots;
}

/**
 * Transition slots when category changes.
 * Files in slots whose docType exists in the new category's slots are silently
 * carried over. Files in slots whose docType does NOT exist in the new slots
 * get a staleType warning.
 */
export function transitionSlots(newCategory: string, prev: SlotState[]): SlotState[] {
  const reqs = DOC_REQUIREMENTS[newCategory];
  if (!reqs) return [];

  const newTypes = new Set([...reqs.required, ...reqs.optional]);

  // Collect stale files: had a file but their slot type doesn't exist in new category
  const staleFiles: Array<{ file: File; oldType: string }> = [];
  for (const s of prev) {
    if (s.file && !newTypes.has(s.docType)) {
      staleFiles.push({ file: s.file, oldType: s.docType });
    }
  }

  const slots: SlotState[] = [];
  let staleIdx = 0;

  for (const dt of reqs.required) {
    // Check if there's an existing file for this exact type from prev
    const exactMatch = prev.find(s => s.docType === dt && s.file);
    slots.push({
      docType: dt, required: true,
      file: exactMatch ? exactMatch.file : null,
      staleType: null, confirmed: false,
    });
  }

  for (const dt of reqs.optional) {
    const exactMatch = prev.find(s => s.docType === dt && s.file);
    slots.push({
      docType: dt, required: false,
      file: exactMatch ? exactMatch.file : null,
      staleType: null, confirmed: false,
    });
  }

  // Assign stale files to the first empty slots of the new category, with warnings
  for (const slot of slots) {
    if (!slot.file && staleIdx < staleFiles.length) {
      const { file, oldType } = staleFiles[staleIdx++];
      slot.file = file;
      slot.staleType = oldType; // show warning
      slot.confirmed = false;
    }
  }

  return slots;
}

// ── Single slot UI ────────────────────────────────────────────────────────────

interface SlotProps {
  slot: SlotState;
  onFile: (file: File) => void;
  onRemove: () => void;
  onConfirm: () => void;
}

function DocumentSlot({ slot, onFile, onRemove, onConfirm }: SlotProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const hasStaleWarning = slot.file && slot.staleType && !slot.confirmed;
  const hasFile = slot.file !== null;

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) onFile(f);
  };

  // Open the uploaded file (image or PDF) in a new browser tab.
  // A temporary anchor click is used rather than window.open(): browsers block
  // or silently fail window.open() on blob: URLs (especially with a "noopener"
  // features string), whereas an <a target="_blank"> click opens them reliably.
  const openFile = () => {
    if (!slot.file) return;
    const url = URL.createObjectURL(slot.file);
    const a = document.createElement("a");
    a.href = url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    document.body.appendChild(a);
    a.click();
    a.remove();
    // Release the object URL once the new tab has had time to load it.
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  };

  return (
    <div className={[
      "rounded border transition-colors",
      hasStaleWarning
        ? "border-warn bg-warn-bg"
        : hasFile
          ? "border-border bg-paper"
          : "border-border-strong border-dashed bg-surface",
    ].join(" ")}>
      {/* Slot header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border/60">
        <div className="flex items-center gap-1.5">
          <span className="font-mono text-[10px] text-ink font-medium">{humanType(slot.docType)}</span>
          {slot.required
            ? <span className="text-coral text-[10px]">required</span>
            : <span className="text-ink-muted text-[10px]">optional</span>
          }
        </div>
        {hasFile && (
          <button type="button" onClick={onRemove}
            className="text-ink-muted hover:text-fail transition-colors">
            <X size={11} />
          </button>
        )}
      </div>

      {/* Stale warning */}
      {hasStaleWarning && (
        <div className="px-3 py-2 border-b border-warn/30">
          <div className="flex items-start gap-1.5">
            <AlertTriangle size={11} className="text-warn flex-shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="text-[11px] text-warn font-sans leading-snug">
                Re-check: this file was uploaded as <span className="font-mono">{humanType(slot.staleType!)}</span>,
                now assigned to <span className="font-mono">{humanType(slot.docType)}</span>.
                Confirm this is correct or remove and re-upload.
              </p>
              <button
                type="button"
                onClick={onConfirm}
                className="mt-1.5 flex items-center gap-1 text-[10px] text-ok font-medium font-sans
                  hover:text-ok transition-colors"
              >
                <Check size={10} />
                Yes, this is my {humanType(slot.docType)}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* File or drop zone */}
      {hasFile ? (
        <div className="flex items-center gap-2 px-3 py-2">
          <FileIcon name={slot.file!.name} />
          <button
            type="button"
            onClick={openFile}
            title="Open in a new tab"
            className="font-mono text-xs text-ink flex-1 truncate text-left flex items-center gap-1
              hover:text-coral hover:underline transition-colors"
          >
            <span className="truncate">{slot.file!.name}</span>
            <ExternalLink size={10} className="flex-shrink-0 opacity-60" />
          </button>
          <span className="text-[10px] text-ink-muted tabular flex-shrink-0">
            {(slot.file!.size / 1024).toFixed(0)} KB
          </span>
        </div>
      ) : (
        <div
          onDragOver={e => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={[
            "flex items-center gap-2 px-3 py-2.5 cursor-pointer text-xs font-sans transition-colors",
            dragging ? "text-coral" : "text-ink-muted hover:text-coral",
          ].join(" ")}
        >
          <Upload size={11} className="flex-shrink-0" />
          <span>Upload {humanType(slot.docType).toLowerCase()}</span>
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept="image/*,application/pdf"
        className="hidden"
        onChange={e => { const f = e.target.files?.[0]; if (f) onFile(f); }}
      />
    </div>
  );
}

// ── Main DocumentSlots component ──────────────────────────────────────────────

interface Props {
  category: string;
  slots: SlotState[];
  onSlotsChange: (slots: SlotState[]) => void;
}

export function DocumentSlots({ category, slots, onSlotsChange }: Props) {
  const [optionalsOpen, setOptionalsOpen] = useState(false);

  const required = slots.filter(s => s.required);
  const optional = slots.filter(s => !s.required);

  const setFile = (idx: number, file: File) => {
    onSlotsChange(slots.map((s, i) =>
      i === idx ? { ...s, file, staleType: null, confirmed: false } : s
    ));
  };

  const removeFile = (idx: number) => {
    onSlotsChange(slots.map((s, i) =>
      i === idx ? { ...s, file: null, staleType: null, confirmed: false } : s
    ));
  };

  const confirm = (idx: number) => {
    onSlotsChange(slots.map((s, i) =>
      i === idx ? { ...s, staleType: null, confirmed: true } : s
    ));
  };

  const slotIndex = (slot: SlotState) => slots.indexOf(slot);

  if (!DOC_REQUIREMENTS[category]) return null;

  return (
    <div className="space-y-2">
      {/* Required slots */}
      {required.map(slot => (
        <DocumentSlot
          key={slot.docType}
          slot={slot}
          onFile={f => setFile(slotIndex(slot), f)}
          onRemove={() => removeFile(slotIndex(slot))}
          onConfirm={() => confirm(slotIndex(slot))}
        />
      ))}

      {/* Optional slots — collapsed by default */}
      {optional.length > 0 && (
        <div>
          <button
            type="button"
            onClick={() => setOptionalsOpen(o => !o)}
            className="text-[10px] font-sans text-ink-muted hover:text-ink transition-colors flex items-center gap-1 mt-1"
          >
            <span>{optionalsOpen ? "▲" : "▼"}</span>
            {optional.length} optional document{optional.length > 1 ? "s" : ""}
            {" "}({optional.map(s => humanType(s.docType)).join(", ")})
          </button>

          {optionalsOpen && (
            <div className="mt-2 space-y-2">
              {optional.map(slot => (
                <DocumentSlot
                  key={slot.docType}
                  slot={slot}
                  onFile={f => setFile(slotIndex(slot), f)}
                  onRemove={() => removeFile(slotIndex(slot))}
                  onConfirm={() => confirm(slotIndex(slot))}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
