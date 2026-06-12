import React, { useState } from "react";
import ClaimForm from "./components/ClaimForm";
import DecisionView from "./components/DecisionView";

/**
 * Root application component.
 *
 * Two views:
 *   "form"     — ClaimForm: member details, treatment type, claimed amount,
 *                file upload.
 *   "decision" — DecisionView: decision, approved amount, confidence score,
 *                full trace rendered as a readable timeline/checklist.
 *
 * State management is minimal for scaffold; wire up real API calls when
 * the backend endpoints are implemented.
 */
const App: React.FC = () => {
  const [view, setView] = useState<"form" | "decision">("form");
  // decision holds the raw API response (ClaimDecision | DocumentVerificationResult)
  const [decision, setDecision] = useState<unknown>(null);

  const handleDecisionReceived = (result: unknown) => {
    setDecision(result);
    setView("decision");
  };

  const handleNewClaim = () => {
    setDecision(null);
    setView("form");
  };

  return (
    <main style={{ fontFamily: "sans-serif", maxWidth: 800, margin: "0 auto", padding: 24 }}>
      <h1>Plum Health Insurance Claims</h1>
      {view === "form" ? (
        <ClaimForm onDecision={handleDecisionReceived} />
      ) : (
        <DecisionView decision={decision} onNewClaim={handleNewClaim} />
      )}
    </main>
  );
};

export default App;
