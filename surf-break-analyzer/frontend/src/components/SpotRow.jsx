import { useState } from "react";
import Dial from "./Dial.jsx";
import LogForm from "./LogForm.jsx";
import { QUALITY, VERDICT, sizeLabel } from "../format.js";

export default function SpotRow({ meta, feature, call, pending, request, predictionId, showParent }) {
  const [open, setOpen] = useState(false);
  const [logging, setLogging] = useState(false);
  const parts = feature?.forecast_partitions?.length ? feature.forecast_partitions : feature?.observed_partitions || [];
  const verdict = call?.breaking;

  return (
    <li className={`spot ${verdict ? `v-${verdict}` : "v-pending"}`}>
      <button className="spot-head" onClick={() => setOpen(!open)} aria-expanded={open} disabled={!call}>
        <Dial window={meta.swell_window} partitions={parts} label={meta.name} />
        <div className="spot-text">
          <h3>
            {meta.name}
            {showParent && meta.parent && <span className="parent"> {meta.parent}</span>}
          </h3>
          {call ? (
            <p className="verdict">
              <span className="verdict-mark" aria-hidden="true" />
              <strong>{VERDICT[verdict]}</strong>
              {verdict !== "no" && <span>, {sizeLabel(call.size_ft_low, call.size_ft_high)}, {QUALITY[call.quality]?.toLowerCase()}</span>}
            </p>
          ) : (
            <p className="verdict muted">{pending ? "Waiting on the read" : "No call"}</p>
          )}
          {call && !open && <p className="why-preview">{call.why}</p>}
        </div>
      </button>

      {call && open && (
        <div className="spot-detail">
          <p className="why">{call.why}</p>
          <dl className="facts">
            <div>
              <dt>Best time</dt>
              <dd>{call.best_time}</dd>
            </div>
            <div>
              <dt>Based on</dt>
              <dd>{call.key_inputs.join("; ")}</dd>
            </div>
            <div>
              <dt>Confidence</dt>
              <dd>
                {call.confidence}
                {meta.kb_confidence === "low" && " (spot notes not yet verified)"}
              </dd>
            </div>
          </dl>
          {logging ? (
            <LogForm spotId={meta.id} request={request} predictionId={predictionId} />
          ) : (
            <button className="link" onClick={() => setLogging(true)}>
              Log what you saw here
            </button>
          )}
        </div>
      )}
    </li>
  );
}
