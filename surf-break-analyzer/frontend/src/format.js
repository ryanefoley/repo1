const COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];

export const compass = (deg) => (deg == null ? "" : COMPASS[Math.round((((deg % 360) + 360) % 360) / 22.5) % 16]);

export function hourLabel(h) {
  if (h === 0 || h === 24) return "midnight";
  if (h === 12) return "noon";
  return h < 12 ? `${h}am` : `${h - 12}pm`;
}

export function sizeLabel(lo, hi) {
  if (!hi) return "Flat";
  const f = (n) => (Number.isInteger(n) ? n : n.toFixed(1));
  return lo === hi ? `${f(hi)} ft` : `${f(lo)}–${f(hi)} ft`;
}

export const QUALITY = ["", "Poor", "Fair", "Good", "Very good", "Epic"];

export const VERDICT = { yes: "Breaking", marginal: "Marginal", no: "Not breaking" };

// Local date as YYYY-MM-DD (not UTC).
export function isoDay(d) {
  const z = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`;
}

export function dayOptions() {
  const out = [];
  const now = new Date();
  for (let i = 0; i < 8; i++) {
    const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() + i);
    const label =
      i === 0 ? "Today" : i === 1 ? "Tomorrow" : d.toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" });
    out.push({ value: isoDay(d), label });
  }
  return out;
}

export function partitionLabel(p) {
  return `${p.height_ft} ft @ ${Number(p.period_s).toFixed(0)} s ${compass(p.dir_deg)}`;
}
