/**
 * Where this e2e run's servers listen. E2E_PORT_OFFSET (0–999, default 0) moves every port, so
 * two runs on one machine never share an API, a database or a dev server:
 *   E2E_PORT_OFFSET=10 npm run e2e   → API :8010, runner :8110, web :5183, preview :4183
 * Specs and the config import these instead of writing ports out.
 */
const raw = process.env.E2E_PORT_OFFSET ?? "0";
const offset = Number(raw);
if (!Number.isInteger(offset) || offset < 0 || offset > 999) {
  throw new Error(`E2E_PORT_OFFSET must be a whole number from 0 to 999, got "${raw}"`);
}

export const PORT_OFFSET = offset;
export const PORTS = { api: 8000 + offset, runner: 8100 + offset, web: 5173 + offset, preview: 4173 + offset };
export const API_URL = `http://localhost:${PORTS.api}`;
export const RUNNER_URL = `http://localhost:${PORTS.runner}`;
export const WEB_URL = `http://localhost:${PORTS.web}`;
export const PREVIEW_URL = `http://localhost:${PORTS.preview}`;
/** The label this suite's API answers with (X-CodeCoach-Instance). Anything else isn't ours. */
export const INSTANCE_LABEL = "e2e";
/** The suite API's access log (start and finish of each request), read by the failure diagnostics
 * to tell a read that never reached the server from one the server never finished. Relative to
 * frontend/; the API writes it from backend/. */
export const ACCESS_LOG = `../backend/e2e-access${offset ? `-${offset}` : ""}.log`;
