import { compass, partitionLabel } from "../format.js";

function time(iso) {
  return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

// Everything the call was based on, so a bad call can be traced to bad data or bad reasoning.
export default function InputsPanel({ conditions, usage, cached }) {
  const buoy = conditions.buoys?.["46042"];
  const spec = buoy?.spectral_latest;
  const forecasts = Object.entries(conditions.forecast || {});
  return (
    <details className="inputs">
      <summary>What this is based on</summary>

      {buoy?.latest && (
        <section>
          <h4>Monterey buoy, {time(buoy.latest.time)}</h4>
          <p>
            {buoy.latest.wave_height_ft} ft @ {buoy.latest.dominant_period_s} s from {compass(buoy.latest.mean_wave_dir_deg)} (
            {buoy.latest.mean_wave_dir_deg}°)
            {spec && (
              <>
                . Split: swell {spec.swell_height_ft} ft @ {spec.swell_period_s} s {spec.swell_dir}, wind waves{" "}
                {spec.windwave_height_ft} ft @ {spec.windwave_period_s} s {spec.windwave_dir}
              </>
            )}
            .
          </p>
          {buoy.spectral_warning && <p className="warn">{buoy.spectral_warning}</p>}
        </section>
      )}

      {forecasts.map(([id, f]) => {
        const hour = f.window_hours?.[Math.floor((f.window_hours.length || 1) / 2)];
        const wind = f.wind_window_hours?.[0];
        return (
          <section key={id}>
            <h4>Forecast, {f.name}</h4>
            {hour ? <p>{hour.partitions.map(partitionLabel).join("; ")}</p> : <p className="warn">No swell forecast.</p>}
            {wind && (
              <p>
                Wind {wind.wind_kt} kt from {compass(wind.wind_dir_deg)}, gusting {wind.gust_kt}
              </p>
            )}
          </section>
        );
      })}

      {conditions.tide && (
        <section>
          <h4>Tide, Santa Cruz</h4>
          <p>
            {conditions.tide.extremes.map((e) => `${e.type} ${e.height_ft} ft at ${time(e.time)}`).join(", ")}
          </p>
        </section>
      )}

      <section>
        <h4>Sources</h4>
        <ul className="sources">
          {conditions.sources.map((s) => (
            <li key={s.name} className={s.status}>
              {s.name}: {s.status}
              {s.detail && s.status !== "ok" ? ` (${s.detail})` : ""}
            </li>
          ))}
        </ul>
      </section>

      {usage && (
        <p className="usage">
          {usage.model}, {usage.effort} effort: {(usage.input_tokens + usage.cache_read_input_tokens).toLocaleString()} tokens in,{" "}
          {usage.output_tokens.toLocaleString()} out, {usage.seconds}s, about ${usage.cost_usd.toFixed(2)}
          {cached && ". Reused a result from the last 45 minutes"}.
        </p>
      )}
    </details>
  );
}
