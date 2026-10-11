import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import Controls from "./components/Controls.jsx";
import InputsPanel from "./components/InputsPanel.jsx";
import Scorecard from "./components/Scorecard.jsx";
import SpotRow from "./components/SpotRow.jsx";
import { hourLabel, isoDay } from "./format.js";

const REGIONS = {
  north_coast: "North Coast",
  westside: "Westside and town",
  eastside: "Eastside",
  south_county: "South County",
};

function initialParams() {
  const h = Math.min(Math.max(new Date().getHours(), 5), 21);
  return { date: isoDay(new Date()), start: h, end: h + 2, scope: "lane" };
}

function useElapsed(running) {
  const [s, setS] = useState(0);
  useEffect(() => {
    if (!running) return;
    setS(0);
    const t = setInterval(() => setS((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, [running]);
  return s;
}

export default function App() {
  const [params, setParams] = useState(initialParams);
  const [preview, setPreview] = useState(null); // fast: data + pre-pass, no model
  const [result, setResult] = useState(null); // full analysis
  const [phase, setPhase] = useState("idle"); // idle | fetching | thinking | done | error
  const [error, setError] = useState(null);
  const [health, setHealth] = useState(null);
  const runId = useRef(0);
  const elapsed = useElapsed(phase === "thinking");

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ ok: false }));
  }, []);

  async function run() {
    const id = ++runId.current;
    setError(null);
    setResult(null);
    setPreview(null);
    setPhase("fetching");
    try {
      // Show the data and window dials right away, then wait on the model.
      const p = await api.analyze({ ...params, dryRun: true });
      if (id !== runId.current) return;
      setPreview(p);
      setPhase("thinking");
      const r = await api.analyze(params);
      if (id !== runId.current) return;
      setResult(r);
      setPhase("done");
    } catch (err) {
      if (id !== runId.current) return;
      setError(err.message);
      setPhase("error");
    }
  }

  const shown = result || preview;
  const analysis = result?.analysis;
  const calls = Object.fromEntries((analysis?.spots || []).map((c) => [c.id, c]));
  const feats = Object.fromEntries((shown?.features || []).map((f) => [f.id, f]));
  const groups = [];
  for (const m of shown?.spots_meta || []) {
    const g = groups.at(-1);
    if (g && g.region === m.region) g.spots.push(m);
    else groups.push({ region: m.region, spots: [m] });
  }
  const req = shown?.request;

  return (
    <div className="page">
      <header className="masthead">
        <h1>What's breaking</h1>
        <p className="lede">Santa Cruz, spot by spot, and why.</p>
      </header>

      {health && !health.api_key_set && (
        <p className="notice">
          No Anthropic API key on the server. Add ANTHROPIC_API_KEY to the .env file and restart; until then you'll see the
          data and window dials but no calls.
        </p>
      )}

      <Controls value={params} onChange={setParams} onSubmit={run} busy={phase === "fetching" || phase === "thinking"} />

      {phase === "idle" && (
        <p className="empty">Pick a day and time, then check the surf. It takes a minute or two to think it through.</p>
      )}
      {phase === "fetching" && <p className="status">Reading buoys, forecasts and tides…</p>}
      {phase === "error" && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {shown && (
        <main>
          <section className="read" aria-live="polite">
            {analysis ? (
              <>
                <p className="summary">{analysis.summary}</p>
                <p className="best-call">{analysis.best_call}</p>
                <div className="reads">
                  <p>
                    <strong>Swell.</strong> {analysis.swell_read}
                  </p>
                  <p>
                    <strong>Wind and tide.</strong> {analysis.wind_tide_read}
                  </p>
                </div>
                {analysis.caveats.length > 0 && (
                  <ul className="caveats">
                    {analysis.caveats.map((c) => (
                      <li key={c}>{c}</li>
                    ))}
                  </ul>
                )}
              </>
            ) : (
              phase === "thinking" && (
                <p className="status">
                  Thinking it through for {shown.conditions.weekday}, {hourLabel(req.start_hour)} to {hourLabel(req.end_hour)}…{" "}
                  {elapsed}s
                </p>
              )
            )}
          </section>

          <ul className="legend" aria-hidden="true">
            <li><span className="key best" />Best swell window</li>
            <li><span className="key ok" />Has to wrap in</li>
            <li><span className="key arrow" />Swell that reaches</li>
            <li><span className="key arrow blocked" />Blocked or too short</li>
          </ul>

          {groups.map((g) => (
            <section key={g.region} className="region">
              {groups.length > 1 && <h2>{REGIONS[g.region]}</h2>}
              <ul className="spots">
                {g.spots.map((m) => (
                  <SpotRow
                    key={m.id}
                    meta={m}
                    feature={feats[m.id]}
                    call={calls[m.id]}
                    pending={phase === "thinking"}
                    request={req}
                    predictionId={result?.prediction_id}
                    showParent={groups.length > 1}
                  />
                ))}
              </ul>
            </section>
          ))}

          {result?.warnings?.length > 0 && <p className="warn">{result.warnings.join(" ")}</p>}
          <InputsPanel conditions={shown.conditions} usage={result?.usage} cached={result?.cached} />
        </main>
      )}

      <footer>
        <Scorecard />
      </footer>
    </div>
  );
}
