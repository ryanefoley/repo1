import { useState } from "react";
import { api } from "../api.js";

const pct = (x) => `${Math.round(x * 100)}%`;

function Row({ label, m }) {
  return (
    <tr>
      <th scope="row">{label}</th>
      <td>{m.n}</td>
      <td>{pct(m.breaking_yes_no_acc)}</td>
      <td>{m.size_mae_ft == null ? "–" : `${m.size_mae_ft} ft`}</td>
    </tr>
  );
}

export default function Scorecard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  async function load(e) {
    if (!e.target.open || data) return;
    try {
      setData(await api.scorecard());
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <details className="scorecard" onToggle={load}>
      <summary>How accurate has it been?</summary>
      {error && <p className="error-text">{error}</p>}
      {data && data.pairs === 0 && (
        <p>Nothing to score yet. After a session, open a spot and log what you saw.</p>
      )}
      {data && data.pairs > 0 && (
        <table>
          <thead>
            <tr>
              <th scope="col">Spot / swell</th>
              <th scope="col">Sessions</th>
              <th scope="col">Breaking right</th>
              <th scope="col">Size off by</th>
            </tr>
          </thead>
          <tbody>
            <Row label="Everything" m={data.overall} />
            {Object.entries(data.by_spot).map(([k, m]) => (
              <Row key={k} label={k} m={m} />
            ))}
            {Object.entries(data.by_swell_bucket).map(([k, m]) => (
              <Row key={k} label={`${k} swell`} m={m} />
            ))}
          </tbody>
        </table>
      )}
    </details>
  );
}
