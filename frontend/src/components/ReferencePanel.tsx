import { useEffect } from "react";
import { X } from "lucide-react";

/**
 * Reviewer reference panel — a read-only "cheat sheet" of the values in
 * policy_terms.json, so anyone evaluating the assignment can cross-check a
 * decision without opening the JSON. DISPLAY ONLY: these constants mirror
 * policy_terms.json and drive no decision logic (the backend always reads the
 * real file). Keep in sync with policy_terms.json if that file changes.
 */

const MEMBERS: [string, string][] = [
  ["EMP001", "Rajesh Kumar"],
  ["EMP002", "Priya Singh"],
  ["EMP003", "Amit Verma"],
  ["EMP004", "Sneha Reddy"],
  ["EMP005", "Vikram Joshi"],
  ["EMP006", "Kavita Nair"],
  ["EMP007", "Suresh Patil"],
  ["EMP008", "Ravi Menon"],
  ["EMP009", "Anita Desai"],
  ["EMP010", "Deepak Shah"],
  ["DEP001", "Sunita Kumar (spouse of EMP001)"],
  ["DEP002", "Arjun Kumar (child of EMP001)"],
];

const CATEGORIES: { name: string; required: string; sublimit: string; copay: string }[] = [
  { name: "Consultation",     required: "Prescription + Hospital Bill",          sublimit: "₹2,000",  copay: "10% · 20% network discount" },
  { name: "Diagnostic",       required: "Prescription + Lab Report + Hosp. Bill", sublimit: "₹10,000", copay: "0% · 10% network discount" },
  { name: "Pharmacy",         required: "Prescription + Pharmacy Bill",          sublimit: "₹15,000", copay: "0% · 30% on branded drugs" },
  { name: "Dental",           required: "Hospital Bill",                          sublimit: "₹10,000", copay: "0%" },
  { name: "Vision",           required: "Prescription + Hospital Bill",          sublimit: "₹5,000",  copay: "0%" },
  { name: "Alt. Medicine",    required: "Prescription + Hospital Bill",          sublimit: "₹8,000",  copay: "0%" },
];

const WAITING: [string, string][] = [
  ["Initial (any claim)", "30 days from join date"],
  ["Diabetes / Hypertension / Thyroid", "90 days"],
  ["Mental health", "180 days"],
  ["Maternity", "270 days"],
  ["Obesity / Hernia / Cataract", "365 days"],
  ["Joint replacement", "730 days"],
];

const EXCLUSIONS = [
  "Obesity & weight-loss programs", "Bariatric surgery", "Cosmetic / aesthetic procedures",
  "Infertility & assisted reproduction", "Experimental treatments", "Substance-abuse treatment",
  "Self-inflicted injuries", "Health supplements & tonics",
];

const NETWORK = [
  "Apollo Hospitals", "Fortis Healthcare", "Max Healthcare", "Manipal Hospitals",
  "Narayana Health", "Medanta", "Kokilaben Dhirubhai Ambani Hospital",
  "Aster CMI Hospital", "Columbia Asia", "Sakra World Hospital",
];

const TRIGGERS: [string, string][] = [
  ["APPROVED", "Valid member, in-window date, covered treatment, amount ≤ ₹5,000 (e.g. EMP001, Consultation, ₹1,500)"],
  ["APPROVED + discount", "Same, with a network hospital (e.g. Apollo Hospitals → 20% off, then co-pay)"],
  ["PARTIAL", "Dental bill mixing covered + excluded items (e.g. Root Canal + Teeth Whitening)"],
  ["REJECTED · waiting period", "Diabetes/hypertension treatment within 90 days of join date"],
  ["REJECTED · exclusion", "Bariatric / obesity / cosmetic treatment"],
  ["REJECTED · pre-auth", "MRI / CT / PET scan over ₹10,000 with no pre-auth reference"],
  ["REJECTED · per-claim limit", "Any claimed amount over ₹5,000 (non dental/vision)"],
  ["MANUAL_REVIEW · fraud", "3+ claims on the same day for one member"],
  ["MANUAL_REVIEW · member", "Member ID not in the roster above"],
];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="px-5 py-4 border-b border-border">
      <p className="label text-ink border-b border-border pb-1 mb-3">{title}</p>
      {children}
    </div>
  );
}

export function ReferencePanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    if (open) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        className={`fixed inset-0 z-40 bg-black transition-opacity duration-200 ${
          open ? "opacity-40" : "opacity-0 pointer-events-none"
        }`}
      />
      {/* Slide-over */}
      <aside
        role="dialog"
        aria-label="Reviewer reference data"
        className={`fixed top-0 right-0 z-50 h-full w-full max-w-md bg-paper shadow-2xl
          overflow-y-auto transition-transform duration-300 ${
            open ? "translate-x-0" : "translate-x-full"
          }`}
      >
        <div className="sticky top-0 bg-aubergine px-5 py-4 flex items-center justify-between z-10">
          <div>
            <h2 className="font-serif text-xl font-semibold text-cream">Reference data</h2>
            <p className="text-[11px] font-sans" style={{ color: "#fff1e5", opacity: 0.65 }}>
              Cross-check any decision · mirrors policy_terms.json
            </p>
          </div>
          <button onClick={onClose} aria-label="Close reference panel"
            className="text-cream opacity-70 hover:opacity-100 transition-opacity">
            <X size={20} />
          </button>
        </div>

        <Section title="Policy">
          <dl className="text-xs font-sans text-ink space-y-1">
            <div className="flex justify-between"><dt className="text-ink-muted">Policy ID</dt><dd className="font-mono">PLUM_GHI_2024</dd></div>
            <div className="flex justify-between"><dt className="text-ink-muted">Active window</dt><dd>2024-04-01 → 2025-03-31</dd></div>
            <div className="flex justify-between"><dt className="text-ink-muted">Per-claim limit</dt><dd>₹5,000</dd></div>
            <div className="flex justify-between"><dt className="text-ink-muted">Annual OPD limit</dt><dd>₹50,000</dd></div>
            <div className="flex justify-between"><dt className="text-ink-muted">Filing deadline</dt><dd>30 days from treatment</dd></div>
            <div className="flex justify-between"><dt className="text-ink-muted">Min. claim amount</dt><dd>₹500</dd></div>
          </dl>
        </Section>

        <Section title="Valid members">
          <table className="w-full text-xs font-sans">
            <tbody>
              {MEMBERS.map(([id, name]) => (
                <tr key={id} className="border-b border-border/50 last:border-0">
                  <td className="py-1 font-mono text-ink pr-3 align-top">{id}</td>
                  <td className="py-1 text-ink-light">{name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>

        <Section title="Categories — required docs · limits">
          <div className="space-y-2.5">
            {CATEGORIES.map(c => (
              <div key={c.name} className="text-xs font-sans">
                <div className="flex justify-between">
                  <span className="font-semibold text-ink">{c.name}</span>
                  <span className="text-ink-light">{c.sublimit} · {c.copay}</span>
                </div>
                <p className="text-ink-muted">{c.required}</p>
              </div>
            ))}
          </div>
        </Section>

        <Section title="Waiting periods">
          <table className="w-full text-xs font-sans">
            <tbody>
              {WAITING.map(([k, v]) => (
                <tr key={k} className="border-b border-border/50 last:border-0">
                  <td className="py-1 text-ink-light pr-3 align-top">{k}</td>
                  <td className="py-1 text-ink text-right whitespace-nowrap">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>

        <Section title="Pre-authorization">
          <p className="text-xs font-sans text-ink-light">
            Required for <span className="text-ink font-medium">MRI, CT Scan, PET Scan</span> over
            <span className="text-ink font-medium"> ₹10,000</span>. No pre-auth reference → rejected.
          </p>
        </Section>

        <Section title="Global exclusions">
          <div className="flex flex-wrap gap-1.5">
            {EXCLUSIONS.map(e => (
              <span key={e} className="text-[11px] font-sans px-2 py-0.5 rounded bg-surface border border-border text-ink-light">
                {e}
              </span>
            ))}
          </div>
        </Section>

        <Section title="Fraud thresholds">
          <dl className="text-xs font-sans text-ink space-y-1">
            <div className="flex justify-between"><dt className="text-ink-muted">Same-day claims</dt><dd>max 2 → 3rd+ flagged</dd></div>
            <div className="flex justify-between"><dt className="text-ink-muted">Monthly claims</dt><dd>max 6</dd></div>
            <div className="flex justify-between"><dt className="text-ink-muted">High-value review</dt><dd>above ₹25,000</dd></div>
          </dl>
        </Section>

        <Section title="Network hospitals (20% discount)">
          <div className="flex flex-wrap gap-1.5">
            {NETWORK.map(h => (
              <span key={h} className="text-[11px] font-sans px-2 py-0.5 rounded bg-surface border border-border text-ink-light">
                {h}
              </span>
            ))}
          </div>
        </Section>

        <Section title="How to trigger each outcome">
          <div className="space-y-2">
            {TRIGGERS.map(([k, v]) => (
              <div key={k} className="text-xs font-sans">
                <span className="font-mono text-[10px] font-semibold text-aubergine">{k}</span>
                <p className="text-ink-light">{v}</p>
              </div>
            ))}
          </div>
        </Section>

        <div className="px-5 py-4">
          <p className="text-[11px] text-ink-muted font-sans">
            Tip: the dev panel under the form auto-runs all 12 test cases (TC001–TC012)
            with their expected outcomes.
          </p>
        </div>
      </aside>
    </>
  );
}
