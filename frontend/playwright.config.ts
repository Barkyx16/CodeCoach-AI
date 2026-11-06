import { defineConfig, devices } from "@playwright/test";

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

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } }, testIgnore: /(mobile|offline)\.spec\.ts/ },
    { name: "mobile", use: { ...devices["Pixel 7"] }, testMatch: /(mobile|a11y)\.spec\.ts/ },
    // The installable app and offline mode need the production build (service workers aren't
    // registered by the dev server), served by `vite preview`.
    { name: "pwa", use: { ...devices["Desktop Chrome"], baseURL: "http://localhost:4173" }, testMatch: /offline\.spec\.ts/ },
    { name: "pwa-mobile", use: { ...devices["Pixel 7"], baseURL: "http://localhost:4173" }, testMatch: /offline\.spec\.ts/, grep: /@mobile/ },
  ],
  webServer: [
    ...(judge
      ? [{
          command: `${python} -m uvicorn app.main:app_factory --factory --port 8100`,
          cwd: "../runner",
          url: "http://localhost:8100/health",
          reuseExistingServer: !process.env.CI,
          env: { RUNNER_TOKEN: runnerToken, MAX_CONCURRENCY: "2" },
          timeout: 60_000,
        }]
      : []),
    {
      // Start from an empty database every run: a reused e2e.db keeps old schema and old users.
      command: `${python} -c "import pathlib, shutil; pathlib.Path('e2e.db').unlink(missing_ok=True); shutil.rmtree('e2e-outbox', ignore_errors=True)" && ${python} -m uvicorn app.main:app --port 8000`,
      cwd: "../backend",
      url: "http://localhost:8000/health/ready",
      reuseExistingServer: !process.env.CI,
      env: {
        DATABASE_URL: "sqlite:///./e2e.db",
        CORS_ORIGINS: "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173",
        SECRET_KEY: "e2e-secret-key-that-is-at-least-32-characters",
        AI_PROVIDER: "offline",
        // Password-reset emails are written here; e2e/password-reset.spec.ts reads the link.
        EMAIL_BACKEND: "file",
        EMAIL_FILE_DIR: "./e2e-outbox",
        AUTH_RATE_LIMIT_PER_MINUTE: "1000",
        // Every test runs from 127.0.0.1 and every page load refreshes the session.
        REFRESH_RATE_LIMIT_PER_MINUTE: "10000",
        LOG_LEVEL: "WARNING",
        ...(judge
          ? { EXECUTION_ENABLED: "true", EMBEDDED_WORKER: "true", RUNNER_URL: "http://localhost:8100",
              RUNNER_TOKEN: runnerToken, WORKER_POLL_INTERVAL_S: "0.2" }
          : {}),
      },
      timeout: 60_000,
    },
    {
      command: "npm run build && npx vite preview --port 4173 --strictPort",
      url: "http://localhost:4173",
      reuseExistingServer: !process.env.CI,
      env: { VITE_API_BASE_URL: "http://localhost:8000" },
      timeout: 120_000,
    },
    {
      command: "npm run dev",
      url: "http://localhost:5173",
      reuseExistingServer: !process.env.CI,
      env: { VITE_API_BASE_URL: "http://localhost:8000" },
      timeout: 60_000,
    },
  ],
});
