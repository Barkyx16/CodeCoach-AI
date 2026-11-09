import { defineConfig, devices } from "@playwright/test";
import { fileURLToPath } from "node:url";

import { API_URL, E2E_DATABASE_URL, INSTANCE_LABEL, PORT_OFFSET, PORTS, PREVIEW_URL, RUNNER_URL, WEB_URL } from "./e2e/ports";

/**
 * End-to-end tests against the REAL backend (FastAPI + throwaway SQLite DB) and the real
 * frontend dev server. Run: `npm run e2e` (needs the backend's Python deps installed).
 * PYTHON can point at a specific interpreter (e.g. a virtualenv's python).
 */
const python = process.env.PYTHON ?? "python";
// E2E_JUDGE=1 also starts the isolated runner and enables code execution (needs Docker + gVisor
// + the codecoach-java-sandbox:21 image). Only e2e/judge.spec.ts depends on it.
const judge = process.env.E2E_JUDGE === "1";
const runnerToken = "e2e-runner-token-0123456789abcdef0123456789";
// Each server runs through scripts/e2e-owned.mjs, which records its process group for the run
// that started it (scripts/e2e-run.mjs), so an aborted run's servers can be stopped precisely.
const owned = `node ${fileURLToPath(new URL("./scripts/e2e-owned.mjs", import.meta.url))}`;
const suffix = PORT_OFFSET ? `-${PORT_OFFSET}` : "";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  // The launcher (scripts/e2e-run.mjs) also asks for Playwright's own results as JSON, to say how
  // many passed, failed and were skipped, and which, next to the source the run tested.
  reporter: [
    [process.env.CI ? "github" : "list"],
    ...(process.env.E2E_RESULTS_FILE ? [["json", { outputFile: process.env.E2E_RESULTS_FILE }] as [string, unknown]] : []),
  ],
  // Refuses to run against an API that isn't this suite's test server (e2e/global-setup.ts).
  globalSetup: "./e2e/global-setup.ts",
  use: {
    baseURL: WEB_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } }, testIgnore: /(mobile|offline)\.spec\.ts/ },
    { name: "mobile", use: { ...devices["Pixel 7"] }, testMatch: /(mobile|a11y)\.spec\.ts/ },
    // The installable app and offline mode need the production build (service workers aren't
    // registered by the dev server), served by `vite preview`.
    { name: "pwa", use: { ...devices["Desktop Chrome"], baseURL: PREVIEW_URL }, testMatch: /offline\.spec\.ts/ },
    { name: "pwa-mobile", use: { ...devices["Pixel 7"], baseURL: PREVIEW_URL }, testMatch: /offline\.spec\.ts/, grep: /@mobile/ },
  ],
  webServer: [
    ...(judge
      ? [{
          command: owned,
          cwd: "../runner",
          url: `${RUNNER_URL}/health`,
          reuseExistingServer: !process.env.CI,
          env: {
            E2E_OWNED_NAME: "runner",
            E2E_OWNED_COMMAND: `${python} -m uvicorn app.main:app_factory --factory --port ${PORTS.runner}`,
            RUNNER_TOKEN: runnerToken, MAX_CONCURRENCY: "2",
          },
          timeout: 60_000,
        }]
      : []),
    {
      // Start from an empty database every run: a reused e2e.db keeps old schema and old users.
      command: owned,
      cwd: "../backend",
      url: `${API_URL}/health/ready`,
      reuseExistingServer: !process.env.CI,
      env: {
        E2E_OWNED_NAME: "api",
        E2E_OWNED_COMMAND: `${python} -c "import pathlib, shutil; pathlib.Path('e2e${suffix}.db').unlink(missing_ok=True); pathlib.Path('e2e-access${suffix}.log').unlink(missing_ok=True); shutil.rmtree('e2e-outbox${suffix}', ignore_errors=True)" && ${python} -m uvicorn app.main:app --port ${PORTS.api}`,
        // Tells e2e/global-setup.ts this is the suite's own server (never a developer's).
        INSTANCE_LABEL,
        DATABASE_URL: E2E_DATABASE_URL,
        CORS_ORIGINS: `${WEB_URL},http://127.0.0.1:${PORTS.web},${PREVIEW_URL}`,
        // Links in emails (password reset) point at this run's web server, not the default port.
        APP_BASE_URL: WEB_URL,
        SECRET_KEY: "e2e-secret-key-that-is-at-least-32-characters",
        AI_PROVIDER: "offline",
        // Password-reset emails are written here; e2e/password-reset.spec.ts reads the link.
        EMAIL_BACKEND: "file",
        EMAIL_FILE_DIR: `./e2e-outbox${suffix}`,
        AUTH_RATE_LIMIT_PER_MINUTE: "1000",
        // Every test runs from 127.0.0.1 and every page load refreshes the session.
        REFRESH_RATE_LIMIT_PER_MINUTE: "10000",
        LOG_LEVEL: "WARNING",
        // Each request's start and finish, for the failure diagnostics (Volume 9, prompt 9).
        ACCESS_LOG_FILE: `./e2e-access${suffix}.log`,
        ...(judge
          ? { EXECUTION_ENABLED: "true", EMBEDDED_WORKER: "true", RUNNER_URL,
              RUNNER_TOKEN: runnerToken, WORKER_POLL_INTERVAL_S: "0.2" }
          : {}),
      },
      timeout: 60_000,
    },
    {
      command: owned,
      url: PREVIEW_URL,
      reuseExistingServer: !process.env.CI,
      env: {
        E2E_OWNED_NAME: "preview",
        E2E_OWNED_COMMAND: `npm run build && npx vite preview --port ${PORTS.preview} --strictPort`,
        VITE_API_BASE_URL: API_URL,
      },
      timeout: 120_000,
    },
    {
      command: owned,
      url: WEB_URL,
      reuseExistingServer: !process.env.CI,
      env: {
        E2E_OWNED_NAME: "web",
        E2E_OWNED_COMMAND: `npx vite --port ${PORTS.web} --strictPort`,
        VITE_API_BASE_URL: API_URL,
      },
      timeout: 60_000,
    },
  ],
});
