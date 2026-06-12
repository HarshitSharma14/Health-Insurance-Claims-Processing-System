import React from "react";

interface ClaimFormProps {
  /** Called with the raw API response once the claim is submitted. */
  onDecision: (result: unknown) => void;
}

/**
 * Claim submission form.
 *
 * Fields (per data-contracts.md ClaimSubmission):
 *   - member_id
 *   - policy_id
 *   - claim_category   (select)
 *   - treatment_date
 *   - claimed_amount
 *   - hospital_name    (optional)
 *   - documents        (multi-file upload)
 *
 * On submit: POST /claims as multipart/form-data, pass response to onDecision.
 *
 * TODO (implement when backend is ready):
 *   - Real form state management
 *   - Input validation mirroring Pydantic constraints
 *   - Loading/error states
 *   - File type restriction (image/*, application/pdf)
 */
const ClaimForm: React.FC<ClaimFormProps> = ({ onDecision }) => {
  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    // Placeholder — wired to backend in next implementation step
    onDecision({ _placeholder: "not implemented" });
  };

  return (
    <section>
      <h2>Submit a Claim</h2>
      <p style={{ color: "#888" }}>
        Form fields will be wired to POST /claims once the backend is ready.
      </p>
      <form onSubmit={handleSubmit}>
        <fieldset>
          <legend>Member Details</legend>
          <label>
            Member ID <input name="member_id" type="text" required />
          </label>
          <br />
          <label>
            Policy ID <input name="policy_id" type="text" required />
          </label>
        </fieldset>

        <fieldset>
          <legend>Claim Details</legend>
          <label>
            Claim Category{" "}
            <select name="claim_category" required>
              <option value="">— select —</option>
              {[
                "CONSULTATION",
                "DIAGNOSTIC",
                "PHARMACY",
                "DENTAL",
                "VISION",
                "ALTERNATIVE_MEDICINE",
              ].map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </label>
          <br />
          <label>
            Treatment Date <input name="treatment_date" type="date" required />
          </label>
          <br />
          <label>
            Claimed Amount (₹){" "}
            <input name="claimed_amount" type="number" min={1} step="0.01" required />
          </label>
          <br />
          <label>
            Hospital Name (optional){" "}
            <input name="hospital_name" type="text" />
          </label>
        </fieldset>

        <fieldset>
          <legend>Documents</legend>
          <label>
            Upload documents (image or PDF){" "}
            <input name="files" type="file" multiple accept="image/*,application/pdf" required />
          </label>
        </fieldset>

        <button type="submit">Submit Claim</button>
      </form>
    </section>
  );
};

export default ClaimForm;
