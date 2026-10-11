import { compass, partitionLabel } from "../format.js";

// Compass dial: the spot's swell window as arcs on the ring (kelp = best,
// sandstone = needs to wrap), with each swell partition drawn as an arrow
// coming in from the direction it arrives from. Arrow length ~ height.
// Solid arrows reach the spot; dashed ones are blocked or too short-period to wrap.

const R = 38;

function pt(r, deg) {
  const a = (deg * Math.PI) / 180;
  return [r * Math.sin(a), -r * Math.cos(a)];
}

function arcPath(r, lo, hi) {
  const span = (((hi - lo) % 360) + 360) % 360;
  const [x0, y0] = pt(r, lo);
  const [x1, y1] = pt(r, hi);
  return `M ${x0.toFixed(2)} ${y0.toFixed(2)} A ${r} ${r} 0 ${span > 180 ? 1 : 0} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
}

function Arrow({ part, maxHeight }) {
  const reaches = part.window_position !== "outside" && part.wraps_in;
  const isWind = part.kind.includes("wind");
  const len = 10 + 26 * Math.min(1, part.height_ft / Math.max(maxHeight, 1));
  const start = 47;
  const end = start - len;
  const [x0, y0] = pt(start, part.dir_deg);
  const [x1, y1] = pt(end, part.dir_deg);
  // Arrowhead pointing toward the center.
  const [bx, by] = pt(end + 7, part.dir_deg);
  const [lx, ly] = pt(end + 8, part.dir_deg - 13);
  const [rx, ry] = pt(end + 8, part.dir_deg + 13);
  const cls = `dial-arrow ${reaches ? "reaches" : "blocked"} ${isWind ? "wind" : ""}`;
  return (
    <g className={cls}>
      <line x1={x0} y1={y0} x2={bx} y2={by} />
      <polygon points={`${x1},${y1} ${lx},${ly} ${rx},${ry}`} />
    </g>
  );
}

export default function Dial({ window, partitions = [], size = 88, label }) {
  const maxHeight = Math.max(...partitions.map((p) => p.height_ft), 1);
  const desc =
    `${label ? label + ": " : ""}best swell from ${window.best_dir_deg.map(Math.round).join("° to ")}° ` +
    `(${compass(window.best_dir_deg[0])} to ${compass(window.best_dir_deg[1])}). ` +
    partitions
      .map((p) => `${partitionLabel(p)} ${p.window_position === "outside" ? "blocked" : p.wraps_in ? "reaches" : "too short to wrap"}`)
      .join("; ");
  return (
    <svg className="dial" viewBox="-50 -50 100 100" width={size} height={size} role="img" aria-label={desc}>
      <circle className="dial-ring" r={R} />
      <path className="dial-ok" d={arcPath(R, ...window.ok_dir_deg)} />
      <path className="dial-best" d={arcPath(R, ...window.best_dir_deg)} />
      <text className="dial-n" x="0" y={-R + 9} textAnchor="middle">N</text>
      {partitions.map((p, i) => (
        <Arrow key={i} part={p} maxHeight={maxHeight} />
      ))}
      <circle className="dial-center" r="2.4" />
    </svg>
  );
}
