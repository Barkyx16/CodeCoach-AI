/**
 * The support report's schema and allowlist (Volume 7, prompt 8), asserted directly rather than
 * left to a secret scanner: exact keys at every level, values bounded, and synthetic secrets
 * seeded in every input the report must not copy (query strings, fragments, the full user
 * agent, error codes and request paths) never reach its text.
 */
import { clearFailures, maskPath, recentFailures, recordFailure } from "@/lib/supportLog";
import { startAuthGeneration } from "@/api/client";

import { buildSupportReport, CATEGORY_MEANING, coarseBrowser, MAX_DESCRIPTION, reportFilename, reportText, type ReportInput } from "./report";

const SECRET = "sk-SYNTHETIC-canary-0123456789abcdef";
const EMAIL = "canary.person@example.test";
const PRIVATE = "PRIVATE-ANSWER-MARKER";
const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15 SerialABC123";

function input(over: Partial<ReportInput> = {}): ReportInput {
  return {
    now: new Date("2026-11-08T21:05:30Z"),
    timeZone: "Europe/London",
    build: "abc123def456",
    mode: "production",
    pathname: `/problems/two-sum?token=${SECRET}&email=${EMAIL}#access_token=${SECRET}`,
    userAgent: UA,
    language: "en-GB",
    online: true,
    session: "signed_in",
    capabilities: { code_judge: "ready", code_judge_reason: "ok", ai_provider: "offline", emails_delivered: true },
    error: { action: "Saving your answer", category: "server", code: "internal_error", status: 500, request_id: "0f1e2d3c4b5a69788796a5b4c3d2e1f0" },
    failures: [],
    description: "",
    ...over,
  };
}

it("has a fixed, versioned shape: exactly these fields, in this order", () => {
  const report = buildSupportReport(input({
    failures: [{ at: "2026-11-08T21:04:00.000Z", method: "POST", path: "/api/v1/careers/answers", status: 500, code: "internal_error", request_id: "0f1e2d3c4b5a6978" }],
  }));
  expect(Object.keys(report)).toEqual([
    "format", "version", "created_at", "time_zone", "app", "page", "browser", "session", "server_said", "problem", "recent_failed_requests", "description",
  ]);
  expect(report.format).toBe("codecoach-support-report");
  expect(report.version).toBe(1);
  expect(Object.keys(report.app)).toEqual(["build", "mode"]);
  expect(Object.keys(report.page)).toEqual(["name", "path"]);
  expect(Object.keys(report.browser)).toEqual(["name", "major_version", "platform", "language", "online"]);
  expect(Object.keys(report.server_said as object)).toEqual(["code_judge", "code_judge_reason", "ai_provider", "emails_delivered"]);
  expect(Object.keys(report.problem!)).toEqual(["action", "category", "meaning", "code", "status", "request_id"]);
  expect(Object.keys(report.recent_failed_requests[0]!)).toEqual(["at", "method", "path", "status", "code", "request_id"]);
  expect(report.created_at).toBe("2026-11-08T21:05:30.000Z");
});

it("keeps the page and browser coarse: no query, fragment, full user agent or region", () => {
  const report = buildSupportReport(input());
  expect(report.page).toEqual({ name: "Coding workspace", path: "/problems/two-sum" });
  expect(report.browser).toEqual({ name: "Safari", major_version: 17, platform: "macOS", language: "en", online: true });
  const text = reportText(report);
  for (const leaked of [SECRET, EMAIL, "token=", "access_token", "SerialABC123", "AppleWebKit", "en-GB"]) expect(text).not.toContain(leaked);
});

it("never copies a secret, address or private text from any input it doesn't allow", () => {
  const report = buildSupportReport(input({
    pathname: `/notes/${EMAIL}/${SECRET}`,
    build: `${SECRET} plus more`,
    timeZone: "Europe/London",
    error: { action: "Saving your answer", category: "server", code: "internal_error", status: 500, request_id: `${SECRET}` },
    failures: [{ at: "2026-11-08T21:04:00.000Z", method: "GET", path: `/api/v1/shares/${SECRET}?key=${SECRET}`, status: 0, code: "network_error", request_id: null }],
  }));
  const text = reportText(report);
  expect(text).not.toContain(SECRET);
  expect(text).not.toContain(EMAIL);
  expect(text).not.toContain(PRIVATE);
  expect(report.page.path).toBe("/notes/:id/:id");
  expect(report.problem!.request_id).toBeNull(); // not shaped like one of ours: not reported as one
  expect(report.recent_failed_requests[0]!.path).toBe("/api/v1/shares/:id");
  expect(report.app.build).toBe("unknown"); // a build id is a commit id or a short safe label
});

it("says which states are unknown instead of guessing", () => {
  expect(buildSupportReport(input({ capabilities: "unavailable" })).server_said).toBe("unknown: the server's status couldn't be loaded");
  expect(buildSupportReport(input({ capabilities: "loading" })).server_said).toBe("not answered yet");
  const none = buildSupportReport(input({ error: null, timeZone: null, language: null, userAgent: "" }));
  expect(none.problem).toBeNull();
  expect(none.time_zone).toBeNull();
  expect(none.browser).toEqual({ name: "other", major_version: null, platform: "other", language: null, online: true });
  const offline = buildSupportReport(input({ error: { action: "The hint", category: "offline", code: "network_error", status: 0, request_id: null } }));
  expect(offline.problem!.request_id).toBeNull(); // never made up
  expect(offline.problem!.meaning).toBe(CATEGORY_MEANING.offline);
  expect(offline.problem!.meaning).not.toMatch(/outage|down/i); // no reply is not an established outage
  expect(buildSupportReport(input({ error: { action: "x", category: "toString", code: null, status: null, request_id: null } })).problem!.category).toBe("other");
});

it("bounds every value: description, action, codes and the request list", () => {
  const failures = Array.from({ length: 9 }, (_, i) => ({ at: "t", method: "GET", path: `/api/v1/x${i}`, status: 500, code: "x".repeat(200), request_id: null }));
  const report = buildSupportReport(input({ description: "d".repeat(MAX_DESCRIPTION + 300), failures,
    error: { action: "a".repeat(300), category: "server", code: "c".repeat(300), status: 500, request_id: null } }));
  expect(report.description).toHaveLength(MAX_DESCRIPTION);
  expect(report.problem!.action).toHaveLength(60);
  expect(report.problem!.code).toHaveLength(60);
  expect(report.recent_failed_requests).toHaveLength(5);
  expect(report.recent_failed_requests[0]!.path).toBe("/api/v1/x4");
  expect(reportText(report).length).toBeLessThan(4000);
});

it("writes markup in a description as JSON text, nothing more", () => {
  const markup = `<img src=x onerror="alert(1)"><script>alert(2)</script>`;
  const text = reportText(buildSupportReport(input({ description: markup })));
  expect(JSON.parse(text).description).toBe(markup);
});

it("names files predictably, in local time", () => {
  expect(reportFilename(new Date(2026, 10, 8, 21, 5, 59))).toBe("codecoach-support-report-20261108-2105.json");
});

it("reads only the browser family, major version and OS family", () => {
  expect(coarseBrowser("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.86 Safari/537.36"))
    .toEqual({ browser: "Chrome", major: 131, platform: "Windows" });
  expect(coarseBrowser("Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0")).toEqual({ browser: "Firefox", major: 133, platform: "Linux" });
  expect(coarseBrowser("Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/131.0 Mobile/15E148 Safari/604.1"))
    .toEqual({ browser: "Chrome", major: 131, platform: "iOS" });
});

describe("the failed-request log", () => {
  afterEach(() => clearFailures());

  it("keeps identifiers only, masks record ids, and holds five", () => {
    for (let i = 0; i < 7; i++) recordFailure({ method: "GET", path: `/api/v1/notes/${1000 + i}?q=${SECRET}`, status: 500, code: "internal_error", request_id: null });
    const kept = recentFailures();
    expect(kept).toHaveLength(5);
    expect(kept.every((f) => f.path === "/api/v1/notes/:id")).toBe(true);
    expect(JSON.stringify(kept)).not.toContain(SECRET);
    expect(maskPath("/api/v1/stories/3f2504e0-4f89-41d3-9a0c-0305e82c3301/versions")).toBe("/api/v1/stories/:id/versions");
  });

  it("is emptied when the session changes, so one account's failures never reach another's report", () => {
    recordFailure({ method: "POST", path: "/api/v1/careers/answers", status: 500, code: "internal_error", request_id: "0f1e2d3c4b5a6978" });
    expect(recentFailures()).toHaveLength(1);
    startAuthGeneration();
    expect(recentFailures()).toEqual([]);
  });
});
