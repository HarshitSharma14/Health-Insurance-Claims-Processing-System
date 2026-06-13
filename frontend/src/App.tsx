import { useState } from "react";
import { ClaimSubmissionForm } from "./components/ClaimSubmissionForm";
import { DecisionView } from "./components/DecisionView";
import type { PipelineResponse } from "./types";
import { DEMO_APPROVED, DEMO_REJECTED, DEMO_VERIFICATION_FAILURE } from "./demo-fixtures";

function getDemoResult(): PipelineResponse | null {
  const p = new URLSearchParams(window.location.search).get("demo");
  if (p === "approved")     return DEMO_APPROVED;
  if (p === "rejected")     return DEMO_REJECTED;
  if (p === "verification") return DEMO_VERIFICATION_FAILURE;
  return null;
}

export default function App() {
  const [result, setResult] = useState<PipelineResponse | null>(getDemoResult);

  return (
    <div className="min-h-screen bg-bg">
      {/* Dark ink header */}
      <header className="bg-ink">
        <div className="max-w-3xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-4 h-4 bg-accent flex-shrink-0"
              style={{ clipPath: "polygon(0 0,100% 0,100% 75%,75% 100%,0 100%)" }} />
            <span className="font-serif font-semibold text-sm tracking-wide text-white">
              Plum Claims
            </span>
            <span className="text-ink-muted text-xs mx-0.5">|</span>
            <span className="text-xs text-ink-muted font-sans">Health Insurance Processing</span>
          </div>
          {result && (
            <button
              onClick={() => setResult(null)}
              className="text-xs text-ink-muted hover:text-white transition-colors font-medium"
            >
              ← New claim
            </button>
          )}
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-7">
        {result === null ? (
          <div>
            <div className="mb-5 section-1">
              <h1 className="font-serif text-lg font-semibold text-text-primary">Submit a Claim</h1>
              <p className="text-xs text-text-secondary mt-0.5">
                Enter member details and attach supporting documents for automated processing.
              </p>
            </div>
            <div className="bg-surface border border-border rounded section-2">
              <ClaimSubmissionForm onResult={setResult} />
            </div>
          </div>
        ) : (
          <div>
            <div className="mb-5 section-1">
              <h1 className="font-serif text-lg font-semibold text-text-primary">Claim Result</h1>
              <p className="text-xs text-text-secondary mt-0.5">
                Decision, financial breakdown, and full processing trace.
              </p>
            </div>
            <div className="bg-surface border border-border rounded section-2">
              <DecisionView result={result} onNewClaim={() => setResult(null)} />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
