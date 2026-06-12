import React from "react";

interface DecisionViewProps {
  /** Raw API response — either ClaimDecision or DocumentVerificationResult. */
  decision: unknown;
  onNewClaim: () => void;
}

/**
 * Decision and trace review view.
 *
 * Renders:
 *   - Decision badge (APPROVED / PARTIAL / REJECTED / MANUAL_REVIEW)
 *     or verification failure message.
 *   - Approved amount and confidence score.
 *   - Human-readable reason.
 *   - Full trace as a readable timeline/checklist (one row per TraceEvent),
 *     NOT a raw JSON dump — required by observability.md and grading criteria.
 *   - Financial breakdown (if present).
 *   - Line-item evaluations (if present).
 *
 * TODO (implement when backend is ready):
 *   - Parse and type-check the response against ClaimDecision schema.
 *   - Render TraceEvent list as a step-by-step timeline with status icons.
 *   - Colour-code decisions (green=APPROVED, amber=PARTIAL/MANUAL_REVIEW,
 *     red=REJECTED).
 *   - Expand/collapse individual trace events.
 */
const DecisionView: React.FC<DecisionViewProps> = ({ decision, onNewClaim }) => {
  return (
    <section>
      <h2>Claim Decision</h2>
      <p style={{ color: "#888" }}>
        Decision rendering will be implemented once the backend pipeline is complete.
      </p>

      {/* Raw JSON fallback — replace with structured UI */}
      <pre
        style={{
          background: "#f4f4f4",
          padding: 16,
          borderRadius: 6,
          overflow: "auto",
          fontSize: 13,
        }}
      >
        {JSON.stringify(decision, null, 2)}
      </pre>

      <button onClick={onNewClaim}>Submit Another Claim</button>
    </section>
  );
};

export default DecisionView;
