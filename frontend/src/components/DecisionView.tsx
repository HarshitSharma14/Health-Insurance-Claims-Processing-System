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
        <VerificationFailureView data={result.data as DocumentVerificationResult} />
      ) : (
        <>
          <DecisionSummary data={result.data as ClaimDecision} />
          <div className="border-t border-border pt-6">
            <TraceTimeline trace={(result.data as ClaimDecision).trace} />
          </div>
        </>
      )}

      <div className="mt-8 pt-5 border-t border-border">
        <button
          onClick={onNewClaim}
          className="text-sm text-accent hover:text-accent-hover font-medium transition-colors"
        >
          ← Submit another claim
        </button>
      </div>
    </div>
  );
}
