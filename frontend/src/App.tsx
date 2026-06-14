import { useState } from "react";
import { Check } from "lucide-react";
import { ClaimSubmissionForm } from "./components/ClaimSubmissionForm";
import { DecisionView } from "./components/DecisionView";
import type { PipelineResponse } from "./types";
import { DEMO_APPROVED, DEMO_REJECTED, DEMO_VERIFICATION_FAILURE, DEMO_PARTIAL } from "./demo-fixtures";

function getDemoResult(): PipelineResponse | null {
  const p = new URLSearchParams(window.location.search).get("demo");
  if (p === "approved")     return DEMO_APPROVED;
  if (p === "rejected")     return DEMO_REJECTED;
  if (p === "partial")      return DEMO_PARTIAL;
  if (p === "verification") return DEMO_VERIFICATION_FAILURE;
  return null;
}

const FEATURES = [
  {
    title: "Instant document check:",
    body: "Wrong or unreadable documents are caught before processing, with a clear note on what to re-upload.",
  },
  {
    title: "Full policy evaluation against PLUM_GHI_2024 — waiting periods, exclusions, sub-limits, co-pay and network discounts.",
  },
  {
    title: "Every decision is fully explainable — see the complete trace behind APPROVED, PARTIAL, REJECTED or MANUAL_REVIEW.",
  },
  {
    title: "Graceful under failure — the pipeline never crashes, it degrades and flags for review.",
  },
];

export default function App() {
  const [result, setResult] = useState<PipelineResponse | null>(getDemoResult);

  return (
    <div className="min-h-screen bg-aubergine">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header>
        <div className="max-w-7xl mx-auto px-6 lg:px-10 py-6 flex items-center justify-between">
          <div className="flex items-baseline gap-2">
            <span
              className="font-sans font-bold text-2xl tracking-tight leading-none"
              style={{ color: "#ff4052", letterSpacing: "-0.02em" }}
            >
              plum
            </span>
            <span
              className="font-sans font-medium text-[11px] tracking-[0.2em] uppercase"
              style={{ color: "#fff1e5", opacity: 0.55 }}
            >
              claims
            </span>
          </div>

          {result && (
            <button
              onClick={() => setResult(null)}
              className="text-sm font-sans transition-opacity hover:opacity-100 opacity-70"
              style={{ color: "#fff1e5" }}
            >
              ← New claim
            </button>
          )}
        </div>
      </header>

      {/* ── Body ───────────────────────────────────────────────────────────── */}
      {result === null ? (
        // Landing split: hero left, form card right
        <main className="max-w-7xl mx-auto px-6 lg:px-10 pb-16 grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-14 items-start">
          {/* Left — hero copy */}
          <section className="pt-6 lg:pt-10 section-1">
            <h1 className="font-serif text-cream font-semibold leading-[1.05] text-5xl lg:text-6xl">
              Health Insurance Claims, Decided Instantly.
            </h1>
            <p className="mt-6 text-lg lg:text-xl font-sans leading-snug" style={{ color: "#fff1e5", opacity: 0.8 }}>
              Automated verification, extraction, and policy evaluation —
              with a full audit trail behind every decision.
            </p>

            <ul className="mt-9 border-t" style={{ borderColor: "rgba(255,241,229,0.12)" }}>
              {FEATURES.map((f, i) => (
                <li
                  key={i}
                  className="flex gap-3 py-3.5 border-b text-sm font-sans leading-relaxed"
                  style={{ borderColor: "rgba(255,241,229,0.12)", color: "#fff1e5" }}
                >
                  <Check size={16} className="flex-shrink-0 mt-0.5" style={{ color: "#ff4052" }} />
                  <span style={{ opacity: 0.85 }}>
                    {f.title && <span className="font-semibold" style={{ opacity: 1 }}>{f.title} </span>}
                    {f.body}
                  </span>
                </li>
              ))}
            </ul>

            <p className="mt-8 font-serif italic text-lg" style={{ color: "#fff1e5", opacity: 0.6 }}>
              Trusted automation for Plum's operations team.
            </p>
          </section>

          {/* Right — form card */}
          <section className="lg:pt-4 section-2">
            <div className="bg-paper rounded-lg shadow-xl overflow-hidden border" style={{ borderColor: "rgba(70,9,50,0.08)" }}>
              <div className="px-5 pt-6 pb-2">
                <h2 className="font-serif text-2xl text-ink font-semibold">
                  Submit your claim <span className="italic font-normal">with Plum</span>
                </h2>
                <p className="text-xs text-ink-muted mt-1 font-sans">
                  Enter member details and attach supporting documents.
                </p>
              </div>
              <ClaimSubmissionForm onResult={setResult} />
            </div>
          </section>
        </main>
      ) : (
        // Result view — wider, centred for the trace timeline
        <main className="max-w-4xl mx-auto px-6 lg:px-10 pb-16">
          <div className="mb-5">
            <h1 className="font-serif text-2xl font-semibold text-cream">Claim Result</h1>
            <p className="text-sm mt-1 font-sans" style={{ color: "#fff1e5", opacity: 0.7 }}>
              Decision, financial breakdown, and full processing trace.
            </p>
          </div>
          <div className="bg-paper rounded-lg shadow-xl overflow-hidden border" style={{ borderColor: "rgba(70,9,50,0.08)" }}>
            <DecisionView result={result} onNewClaim={() => setResult(null)} />
          </div>
        </main>
      )}
    </div>
  );
}
