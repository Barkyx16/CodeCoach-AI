/**
 * Before an e2e run uses a server, check it's the one this run needs. Locally, Playwright reuses
 * whatever already answers on a port. That once ran the judge tests against an orphaned API with
 * code execution off, left by an aborted run. It could equally run them against a developer's own
 * server and its database. This looks at what the server says about itself, through public,
 * non-secret signals only:
 * - the X-CodeCoach-Instance header (INSTANCE_LABEL, which only test servers set);
 * - /api/v1/capabilities: whether code execution is on, and the judge's state.
 */

export interface Expected {
  label: string;
  judge: boolean;
}

interface Capabilities {
  execution_enabled?: boolean;
  execution?: { state?: string; reason?: string };
}

type Fetch = (url: string, init?: { signal?: AbortSignal }) => Promise<Response>;

async function get(fetchImpl: Fetch, url: string): Promise<Response | string> {
  try {
    return await fetchImpl(url, { signal: AbortSignal.timeout(5000) });
  } catch (e) {
    return `nothing usable answered at ${url} (${(e as Error).name})`;
  }
}

/** What's wrong with the API at `base` for this run; empty when it's the right server. With
 * `judge`, waits up to `waitMs` for the judge to report ready (the runner can start later). */
export async function apiProblems(
  base: string,
  expected: Expected,
  { waitMs = 0, fetchImpl = fetch as Fetch, pollMs = 1000 }: { waitMs?: number; fetchImpl?: Fetch; pollMs?: number } = {},
): Promise<string[]> {
  const health = await get(fetchImpl, `${base}/health`);
  if (typeof health === "string") return [health];
  const label = health.headers.get("x-codecoach-instance");
  if (label !== expected.label) {
    return [
      label
        ? `the server at ${base} says it's "${label}", not this suite's "${expected.label}" test server`
        : `the server at ${base} isn't a test server (no X-CodeCoach-Instance header): it may be a development server with real data`,
    ];
  }
  const deadline = Date.now() + waitMs;
  for (;;) {
    const res = await get(fetchImpl, `${base}/api/v1/capabilities`);
    if (typeof res === "string") return [res];
    const caps = (await res.json()) as Capabilities;
    const state = caps.execution?.state ?? "unknown";
    if (!expected.judge) {
      return caps.execution_enabled
        ? [`code execution is on at ${base}, but this run expects it off (unset E2E_JUDGE, or stop that server)`]
        : [];
    }
    if (!caps.execution_enabled || state === "not_configured") {
      return [
        `code execution is off at ${base} (state: ${state}), but this run needs the judge (E2E_JUDGE=1). ` +
          "It's likely a server left by a run without the judge",
      ];
    }
    if (state === "ready") return [];
    if (Date.now() >= deadline) {
      return [`the judge at ${base} isn't ready after ${Math.round(waitMs / 1000)} s (state: ${state}, reason: ${caps.execution?.reason ?? "unknown"}): is the runner up?`];
    }
    await new Promise((r) => setTimeout(r, pollMs));
  }
}
