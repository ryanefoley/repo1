import { useState } from "react";
import { api } from "../api.js";

// Quick "what actually broke" report; feeds the scorecard.
export default function LogForm({ spotId, request, predictionId, onDone }) {
  const [breaking, setBreaking] = useState("yes");
  const [size, setSize] = useState("");
  const [notes, setNotes] = useState("");
  const [state, setState] = useState({ status: "idle" });

  async function save(e) {
    e.preventDefault();
    setState({ status: "saving" });
    try {
      await api.logSession({
        date: request.date,
        spot_id: spotId,
        breaking,
        size_ft: size === "" ? null : Number(size),
        start_hour: request.start_hour,
        end_hour: request.end_hour,
        notes,
        prediction_id: predictionId || null,
      });
      setState({ status: "saved" });
      onDone?.();
    } catch (err) {
      setState({ status: "error", message: err.message });
    }
  }

  if (state.status === "saved") return <p className="log-saved">Logged. It'll count toward the scorecard.</p>;

  return (
    <form className="log-form" onSubmit={save}>
      <div className="segmented small" role="radiogroup" aria-label="What did you see">
        {[
          ["yes", "Breaking"],
          ["marginal", "Marginal"],
          ["no", "Not breaking"],
        ].map(([v, label]) => (
          <button
            type="button"
            key={v}
            role="radio"
            aria-checked={breaking === v}
            className={breaking === v ? "on" : ""}
            onClick={() => setBreaking(v)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="log-fields">
        <label className="field narrow">
          <span>Face height, ft</span>
          <input type="number" inputMode="decimal" min="0" step="0.5" value={size} onChange={(e) => setSize(e.target.value)} />
        </label>
        <label className="field">
          <span>Notes</span>
          <input type="text" value={notes} placeholder="e.g. sets all on the main peak" onChange={(e) => setNotes(e.target.value)} />
        </label>
      </div>
      <button className="secondary" type="submit" disabled={state.status === "saving"}>
        {state.status === "saving" ? "Saving…" : "Log session"}
      </button>
      {state.status === "error" && <p className="error-text">{state.message}</p>}
    </form>
  );
}
