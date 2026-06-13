import { useState } from "react";
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

export default function App() {
  const [result, setResult] = useState<PipelineResponse | null>(getDemoResult);

  return (
    <div className="min-h-screen bg-paper">
      {/* Aubergine header — Plum brand dark surface */}
      <header className="bg-aubergine">
        <div className="max-w-3xl mx-auto px-6 py-3 flex items-center justify-between">
          {/* Logotype: "plum" in coral + "claims" in cream small-caps */}
          <div className="flex items-center gap-2">
            <span
              className="font-sans font-semibold text-base tracking-tight leading-none"
              style={{ color: "#ff4052", letterSpacing: "-0.01em" }}
            >
              plum
            </span>
            <span
              className="font-sans font-medium text-[11px] tracking-[0.18em] uppercase"
              style={{ color: "#fff1e5", opacity: 0.7 }}
            >
              claims
            </span>
          </div>

          {result && (
            <button
              onClick={() => setResult(null)}
              className="text-xs font-sans transition-opacity hover:opacity-100 opacity-60"
              style={{ color: "#fff1e5" }}
            >
              ← New claim
            </button>
          )}
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-7">
        {result === null ? (
          <>
            <div className="mb-5 section-1">
              <h1 className="font-serif text-xl font-semibold text-ink">Submit a Claim</h1>
              <p className="text-xs text-ink-muted mt-0.5 font-sans">
                Enter member details and attach supporting documents for automated processing.
              </p>
            </div>
            <div className="bg-surface border border-border rounded section-2">
              <ClaimSubmissionForm onResult={setResult} />
            </div>
          </>
        ) : (
          <>
            <div className="mb-5 section-1">
              <h1 className="font-serif text-xl font-semibold text-ink">Claim Result</h1>
              <p className="text-xs text-ink-muted mt-0.5 font-sans">
                Decision, financial breakdown, and full processing trace.
              </p>
            </div>
            <div className="bg-surface border border-border rounded section-2">
              <DecisionView result={result} onNewClaim={() => setResult(null)} />
            </div>
          </>
        )}
      </main>
    </div>
  );
}
