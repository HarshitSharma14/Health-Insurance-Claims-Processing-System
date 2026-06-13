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
        <div className="px-5 py-5 section-1">
          <VerificationFailureView data={result.data as DocumentVerificationResult} />
        </div>
      ) : (
        <>
          <div className="px-5 py-5 section-1">
            <DecisionSummary data={result.data as ClaimDecision} />
          </div>
          <div className="border-t border-border px-5 py-5 section-2">
            <TraceTimeline trace={(result.data as ClaimDecision).trace} />
          </div>
        </>
      )}

      <div className="border-t border-border px-5 py-4 section-3">
        <button
          onClick={onNewClaim}
          className="px-4 py-2 rounded text-sm font-sans font-medium text-white transition-colors"
          style={{ backgroundColor: "#ff4052" }}
          onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = "#e6293c"; }}
          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = "#ff4052"; }}
        >
          Submit Another Claim
        </button>
      </div>
    </div>
  );
}
