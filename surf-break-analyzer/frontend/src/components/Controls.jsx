import { dayOptions, hourLabel } from "../format.js";

const PRESETS = [
  { label: "Dawn", start: 6, end: 9 },
  { label: "Morning", start: 7, end: 11 },
  { label: "Midday", start: 11, end: 14 },
  { label: "Afternoon", start: 14, end: 18 },
  { label: "Evening", start: 16, end: 19 },
];

const HOURS = Array.from({ length: 19 }, (_, i) => i + 5); // 5am - 11pm

export default function Controls({ value, onChange, onSubmit, busy }) {
  const set = (patch) => onChange({ ...value, ...patch });
  return (
    <form
      className="controls"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <div className="when">
        <label className="field day">
          <span>Day</span>
          <select value={value.date} onChange={(e) => set({ date: e.target.value })}>
            {dayOptions().map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field narrow">
          <span>From</span>
          <select
            value={value.start}
            onChange={(e) => {
              const start = Number(e.target.value);
              set({ start, end: Math.max(value.end, start + 1) });
            }}
          >
            {HOURS.slice(0, -1).map((h) => (
              <option key={h} value={h}>
                {hourLabel(h)}
              </option>
            ))}
          </select>
        </label>
        <label className="field narrow">
          <span>To</span>
          <select value={value.end} onChange={(e) => set({ end: Number(e.target.value) })}>
            {HOURS.filter((h) => h > value.start).map((h) => (
              <option key={h} value={h}>
                {hourLabel(h)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="presets" role="group" aria-label="Time of day">
        {PRESETS.map((p) => (
          <button
            type="button"
            key={p.label}
            className={value.start === p.start && value.end === p.end ? "chip on" : "chip"}
            aria-pressed={value.start === p.start && value.end === p.end}
            onClick={() => set({ start: p.start, end: p.end })}
          >
            {p.label}
          </button>
        ))}
      </div>

      <div className="control-row bottom">
        <div className="segmented" role="radiogroup" aria-label="Which spots">
          {[
            ["lane", "Steamer Lane"],
            ["county", "Whole county"],
          ].map(([v, label]) => (
            <button
              type="button"
              key={v}
              role="radio"
              aria-checked={value.scope === v}
              className={value.scope === v ? "on" : ""}
              onClick={() => set({ scope: v })}
            >
              {label}
            </button>
          ))}
        </div>
        <button className="go" type="submit" disabled={busy}>
          {busy ? "Checking…" : "Check the surf"}
        </button>
      </div>
    </form>
  );
}
