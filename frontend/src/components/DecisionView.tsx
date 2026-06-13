import type { PipelineResponse, ClaimDecision, DocumentVerificationResult } from "../types";
import { DecisionSummary } from "./DecisionSummary";
import { TraceTimeline } from "./TraceTimeline";
import { VerificationFailureView } from "./VerificationFailureView";

interface Props {
  result: PipelineResponse;
  onNewClaim: () => void;
}

export function DecisionView({ result, onNewClaim }: Props) {
  return (
    <div>
      {result.type === "verification_failure" ? (
        <div className="px-5 py-5">
          <VerificationFailureView data={result.data as DocumentVerificationResult} />
        </div>
      ) : (
        <>
          <div className="px-5 py-5">
            <DecisionSummary data={result.data as ClaimDecision} />
          </div>
          <div className="border-t border-border px-5 py-5">
            <TraceTimeline trace={(result.data as ClaimDecision).trace} />
          </div>
        </>
      )}

      <div className="border-t border-border px-5 py-3">
        <button
          onClick={onNewClaim}
          className="text-xs text-text-secondary hover:text-accent font-medium transition-colors"
        >
          ← Submit another claim
        </button>
      </div>
    </div>
  );
}
