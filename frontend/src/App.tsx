import { useState } from "react";
import { ClaimSubmissionForm } from "./components/ClaimSubmissionForm";
import { DecisionView } from "./components/DecisionView";
import type { PipelineResponse } from "./types";

export default function App() {
  const [result, setResult] = useState<PipelineResponse | null>(null);

  return (
    <div className="min-h-screen bg-bg">
      {/* Top bar */}
      <header className="border-b border-border bg-surface">
        <div className="max-w-3xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-5 h-5 bg-accent rounded-sm flex-shrink-0" />
            <span className="font-serif font-semibold text-sm tracking-wide text-text-primary">
              Plum Claims
            </span>
            <span className="text-border-strong text-xs mx-1">|</span>
            <span className="text-xs text-text-muted font-sans">Health Insurance Processing</span>
          </div>
          {result && (
            <button
              onClick={() => setResult(null)}
              className="text-xs text-text-secondary hover:text-accent transition-colors font-medium"
            >
              New claim
            </button>
          )}
        </div>
      </header>

      {/* Content */}
      <main className="max-w-3xl mx-auto px-6 py-8">
        {result === null ? (
          <div>
            <div className="mb-6">
              <h1 className="font-serif text-xl font-semibold text-text-primary">Submit a Claim</h1>
              <p className="text-sm text-text-secondary mt-1">
                Upload member details and supporting documents for automated processing.
              </p>
            </div>
            <div className="bg-surface border border-border rounded p-6">
              <ClaimSubmissionForm onResult={setResult} />
            </div>
          </div>
        ) : (
          <div>
            <div className="mb-6">
              <h1 className="font-serif text-xl font-semibold text-text-primary">Claim Result</h1>
              <p className="text-sm text-text-secondary mt-1">
                Full decision, financial breakdown, and processing trace.
              </p>
            </div>
            <div className="bg-surface border border-border rounded p-6">
              <DecisionView result={result} onNewClaim={() => setResult(null)} />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
