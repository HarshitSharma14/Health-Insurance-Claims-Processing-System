import React, { useState } from "react";

interface ClaimFormProps {
  onDecision: (result: unknown) => void;
}

const CATEGORIES = [
  "CONSULTATION",
  "DIAGNOSTIC",
  "PHARMACY",
  "DENTAL",
  "VISION",
  "ALTERNATIVE_MEDICINE",
];

const ClaimForm: React.FC<ClaimFormProps> = ({ onDecision }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const form = e.currentTarget;
    const data = new FormData(form);

    try {
      const res = await fetch("/claims", { method: "POST", body: data });
      const json = await res.json();
      if (!res.ok) {
        setError(json.detail ?? `Error ${res.status}`);
        return;
      }
      onDecision(json);
    } catch {
      setError("Network error — is the backend running on port 8000?");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section style={s.section}>
      <h2 style={s.heading}>Submit a Claim</h2>
      {error && <div style={s.errorBanner}>{error}</div>}
      <form onSubmit={handleSubmit} style={s.form}>
        <fieldset style={s.fieldset}>
          <legend style={s.legend}>Member Details</legend>
          <Field label="Member ID" name="member_id" required />
          <Field label="Policy ID" name="policy_id" required />
        </fieldset>

        <fieldset style={s.fieldset}>
          <legend style={s.legend}>Claim Details</legend>
          <div style={s.fieldRow}>
            <label style={s.label}>
              Claim Category
              <select name="claim_category" required style={s.input}>
                <option value="">— select —</option>
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </label>
          </div>
          <Field label="Treatment Date" name="treatment_date" type="date" required />
          <Field label="Claimed Amount (₹)" name="claimed_amount" type="number" min={1} step="0.01" required />
          <Field label="Hospital Name (optional)" name="hospital_name" />
        </fieldset>

        <fieldset style={s.fieldset}>
          <legend style={s.legend}>Documents</legend>
          <div style={s.fieldRow}>
            <label style={s.label}>
              Upload documents (image or PDF)
              <input name="files" type="file" multiple accept="image/*,application/pdf" required style={s.fileInput} />
            </label>
          </div>
        </fieldset>

        <button type="submit" disabled={loading} style={s.button}>
          {loading ? "Processing…" : "Submit Claim"}
        </button>
      </form>
    </section>
  );
};

const Field: React.FC<{
  label: string; name: string; type?: string;
  required?: boolean; min?: number; step?: string;
}> = ({ label, name, type = "text", required, min, step }) => (
  <div style={s.fieldRow}>
    <label style={s.label}>
      {label}
      <input name={name} type={type} required={required} min={min} step={step} style={s.input} />
    </label>
  </div>
);

const s: Record<string, React.CSSProperties> = {
  section: { maxWidth: 560 },
  heading: { marginBottom: 16 },
  form: { display: "flex", flexDirection: "column", gap: 16 },
  fieldset: { border: "1px solid #ddd", borderRadius: 6, padding: "12px 16px" },
  legend: { fontWeight: 600, padding: "0 6px" },
  fieldRow: { marginBottom: 10 },
  label: { display: "flex", flexDirection: "column", gap: 4, fontWeight: 500, fontSize: 14 },
  input: { marginTop: 4, padding: "6px 10px", border: "1px solid #ccc", borderRadius: 4, fontSize: 14, width: "100%", boxSizing: "border-box" },
  fileInput: { marginTop: 4, fontSize: 14 },
  button: { padding: "10px 24px", background: "#0057ff", color: "#fff", border: "none", borderRadius: 6, fontSize: 15, fontWeight: 600, cursor: "pointer", alignSelf: "flex-start" },
  errorBanner: { background: "#fff0f0", border: "1px solid #f5c6cb", color: "#721c24", borderRadius: 4, padding: "10px 14px", marginBottom: 12, fontSize: 14 },
};

export default ClaimForm;
