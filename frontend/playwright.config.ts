import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests against the REAL backend (FastAPI + throwaway SQLite DB) and the real
 * frontend dev server. Run: `npm run e2e` (needs the backend's Python deps installed).
 * PYTHON can point at a specific interpreter (e.g. a virtualenv's python).
 */
const python = process.env.PYTHON ?? "python";

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
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } }, testIgnore: /mobile\.spec\.ts/ },
    { name: "mobile", use: { ...devices["Pixel 7"] }, testMatch: /mobile\.spec\.ts/ },
  ],
  webServer: [
    {
      command: `${python} -m uvicorn app.main:app --port 8000`,
      cwd: "../backend",
      url: "http://localhost:8000/health/ready",
      reuseExistingServer: !process.env.CI,
      env: {
        DATABASE_URL: "sqlite:///./e2e.db",
        SECRET_KEY: "e2e-secret-key-that-is-at-least-32-characters",
        AI_PROVIDER: "offline",
        AUTH_RATE_LIMIT_PER_MINUTE: "1000",
        LOG_LEVEL: "WARNING",
      },
      timeout: 60_000,
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
