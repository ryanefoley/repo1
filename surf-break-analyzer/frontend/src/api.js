async function request(path, options) {
  const res = await fetch(path, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return body;
}

function analyzeParams({ date, start, end, scope, dryRun, refresh }) {
  const p = new URLSearchParams({ date, start, end, scope });
  if (dryRun) p.set("dry_run", "true");
  if (refresh) p.set("refresh", "true");
  return p;
}

export const api = {
  health: () => request("/api/health"),
  analyze: (args) => request(`/api/analyze?${analyzeParams(args)}`),
  logSession: (body) =>
    request("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  scorecard: () => request("/api/scorecard"),
};
