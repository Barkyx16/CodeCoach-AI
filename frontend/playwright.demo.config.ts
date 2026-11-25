import { defineConfig, devices } from "@playwright/test";
import { fileURLToPath } from "node:url";

/**
 * The portfolio demo, run from a fresh disposable database (Volume 7, prompt 10; docs/DEMO.md):
 *
 *   npm run e2e -- --config playwright.demo.config.ts
 *
 * Its own API and web server, on their own ports (E2E_PORT_OFFSET, default 50), with DEMO_MODE on.
 * Before the API starts, the demo database is created and reset twice; if the two starting-state
 * fingerprints differ, the API never starts and the run fails. Email goes to a local folder the
 * specs check stays empty. No judge, and the built-in coach: the unavailable states a reviewer
 * without a Linux sandbox or an AI key sees.
 */
const python = process.env.PYTHON ?? "python";
const offset = Number(process.env.E2E_PORT_OFFSET ?? "50");
if (!Number.isInteger(offset) || offset < 0 || offset > 999) throw new Error("E2E_PORT_OFFSET must be 0–999");
export const DEMO_PORTS = { api: 8000 + offset, web: 5173 + offset };
const API_URL = `http://localhost:${DEMO_PORTS.api}`;
const WEB_URL = `http://localhost:${DEMO_PORTS.web}`;
const owned = `node ${fileURLToPath(new URL("./scripts/e2e-owned.mjs", import.meta.url))}`;
const db = `e2e-demo-${offset}.db`;
const reset = `${python} -m app.cli demo-reset --confirm ${db} | tail -n 1`;

export default defineConfig({
  testDir: "./e2e-demo",
  timeout: 90_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: process.env.CI ? "github" : "list",
  globalSetup: "./e2e-demo/global-setup.ts",
  use: { baseURL: WEB_URL, trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      command: owned,
      cwd: "../backend",
      url: `${API_URL}/health/ready`,
      reuseExistingServer: false,
      env: {
        E2E_OWNED_NAME: "demo-api",
        // A fresh database, reset twice: the same fingerprint, or no server.
        E2E_OWNED_COMMAND:
          `rm -f ${db} && rm -rf e2e-demo-outbox-${offset} && A=$(${reset}) && B=$(${reset}) && ` +
          `echo "first reset: $A" && echo "second reset: $B" && ` +
          `case "$A" in "Starting-state fingerprint: "*) ;; *) exit 1;; esac && [ "$A" = "$B" ] && ` +
          `echo "$A" > e2e-demo-fingerprint-${offset}.txt && ` +
          `${python} -m uvicorn app.main:app --port ${DEMO_PORTS.api}`,
        INSTANCE_LABEL: "e2e-demo",
        DEMO_MODE: "true",
        DATABASE_URL: `sqlite:///./${db}`,
        CORS_ORIGINS: WEB_URL,
        SECRET_KEY: "e2e-demo-secret-key-that-is-at-least-32-characters",
        AI_PROVIDER: "offline",
        EMAIL_BACKEND: "file",
        EMAIL_FILE_DIR: `./e2e-demo-outbox-${offset}`,
        AUTH_RATE_LIMIT_PER_MINUTE: "1000",
        REFRESH_RATE_LIMIT_PER_MINUTE: "10000",
        LOG_LEVEL: "WARNING",
      },
      timeout: 90_000,
    },
    {
      command: owned,
      url: WEB_URL,
      reuseExistingServer: false,
      env: {
        E2E_OWNED_NAME: "demo-web",
        E2E_OWNED_COMMAND: `npx vite --port ${DEMO_PORTS.web} --strictPort`,
        VITE_API_BASE_URL: API_URL,
      },
      timeout: 60_000,
    },
  ],
});
