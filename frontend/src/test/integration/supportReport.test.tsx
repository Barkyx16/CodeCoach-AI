/**
 * A private support report the learner reads before keeping it (Volume 7, prompt 8):
 * - reports for a failed save, an unavailable judge, a blocked AI request and a page that can't
 *   load offline, each opened in place so the learner's typed work stays on the page;
 * - the preview is exactly what's copied and downloaded; copy denial and a download that can't
 *   start both leave the report selected to copy by hand; the temporary file address is revoked;
 * - synthetic secrets seeded where the report must not look (the URL, the error message, the
 *   typed answer, browser storage and cookies) never reach the preview or the file;
 * - a description is bounded, and markup in it is only ever text.
 */
import { act, cleanup, screen, waitFor, within } from "@testing-library/react";
import { onlineManager } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";

import { executionStatus } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const SECRET = "sk-SYNTHETIC-canary-0123456789abcdef";
const PRIVATE = "PRIVATE-ANSWER-MARKER";
const EMAIL = "canary.person@example.test";

const previewOf = (scope: HTMLElement = document.body) =>
  within(scope).getByRole("textbox", { name: "The report" }) as HTMLTextAreaElement;
const reportIn = (scope?: HTMLElement) => JSON.parse(previewOf(scope).value) as Record<string, unknown> & {
  problem: Record<string, unknown> | null; server_said: unknown; browser: Record<string, unknown>; page: Record<string, unknown>;
  recent_failed_requests: Record<string, unknown>[]; description: string; session: string;
};
const capabilities = (state: "ready" | "unavailable") => server.use(http.get(`${API}/api/v1/capabilities`, () => HttpResponse.json({
  execution_enabled: true, ai_provider: "offline", execution: executionStatus(state), guest_retention_days: 30, emails_delivered: true,
})));
const failure = (code: string, status: number, requestId: string | null, headers: Record<string, string> = {}) =>
  HttpResponse.json({ error: { code, message: `Server said ${SECRET} about ${EMAIL}`, request_id: requestId } }, { status, headers });

function expectNothingPrivate(text: string) {
  for (const leaked of [SECRET, PRIVATE, EMAIL, "Server said", "token", "Bearer", "cookie"]) expect(text).not.toContain(leaked);
}

beforeEach(() => {
  localStorage.setItem("codecoach.canary", SECRET);
  document.cookie = `canary=${SECRET}`;
});
afterEach(() => {
  cleanup(); // unmount first: coming back online would make a still-mounted page refetch into the next test
  localStorage.clear();
  document.cookie = "canary=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  Object.defineProperty(navigator, "onLine", { configurable: true, get: () => true });
  onlineManager.setOnline(true); // unmounted, the query library no longer hears the "online" event
  vi.restoreAllMocks();
});

it("a failed save: the report names the action, its kind and reference, never the answer or the message", async () => {
  server.use(
    http.get(`${API}/api/v1/careers/:track/questions/:id/answers`, () => HttpResponse.json([])),
    http.post(`${API}/api/v1/careers/:track/questions/:id/answers`, () => failure("internal_error", 500, "0f1e2d3c4b5a69788796a5b4c3d2e1f0")),
  );
  const { user } = renderApp(`/careers/registered-nurse/questions/m-pressure-0?ref=${SECRET}`, { signedIn: true });
  const box = await screen.findByLabelText("Your answer");
  await user.type(box, `My answer ${PRIVATE}`);
  await user.click(screen.getByRole("button", { name: "Get feedback" }));
  const help = await screen.findByRole("button", { name: "Get help with this" });
  expect(help).toHaveAttribute("aria-expanded", "false");
  await user.click(help);
  expect(help).toHaveAttribute("aria-expanded", "true");
  const region = screen.getByRole("region", { name: "Support report" });
  expect(help).toHaveAttribute("aria-controls", region.parentElement!.id);
  const report = reportIn(region);
  expect(report.problem).toEqual({
    action: "Saving your answer", category: "server", meaning: "The server replied with a fault on its side.",
    code: "internal_error", status: 500, request_id: "0f1e2d3c4b5a69788796a5b4c3d2e1f0",
  });
  expect(report.page).toEqual({ name: "Interview question", path: "/careers/registered-nurse/questions/m-pressure-0" });
  expect(report.session).toBe("signed_in");
  expect(report.recent_failed_requests).toContainEqual(expect.objectContaining({
    method: "POST", path: "/api/v1/careers/registered-nurse/questions/m-pressure-0/answers", status: 500, code: "internal_error",
  }));
  expectNothingPrivate(previewOf(region).value);
  expect(box).toHaveValue(`My answer ${PRIVATE}`); // the work stays where it was
});

it("an unavailable judge: what the server said about it, and the refused submission", async () => {
  capabilities("unavailable");
  server.use(http.post(`${API}/api/v1/submissions`, () => failure("judge_unavailable", 503, "aa11bb22cc33dd44")));
  const { user } = renderApp("/problems/two-sum", { signedIn: true });
  await user.click(await screen.findByRole("button", { name: /^Submit/ }, { timeout: 3000 }));
  await user.click(await screen.findByRole("button", { name: "Get help with this" }));
  const report = reportIn();
  expect(report.server_said).toEqual({ code_judge: "unavailable", code_judge_reason: "judge_unreachable", ai_provider: "offline", emails_delivered: true });
  expect(report.problem).toMatchObject({ action: "Your submission", category: "unavailable", code: "judge_unavailable", status: 503, request_id: "aa11bb22cc33dd44" });
  expect(report.page).toEqual({ name: "Coding workspace", path: "/problems/two-sum" });
  expectNothingPrivate(previewOf().value);
});

it("a blocked AI request: the wait is the server's, and the report says so without guessing more", async () => {
  capabilities("ready");
  server.use(http.post(`${API}/api/v1/ai/hint`, () => failure("rate_limited", 429, "ee55ff66aa77bb88", { "Retry-After": "3600" })));
  const { user } = renderApp("/problems/two-sum", { signedIn: true });
  await user.click(await screen.findByRole("button", { name: "Get a hint" }, { timeout: 3000 }));
  await user.click(await screen.findByRole("button", { name: "Get help with this" }));
  const report = reportIn();
  expect(report.problem).toEqual({
    action: "The hint", category: "busy", meaning: "The server asked for a wait before trying again.",
    code: "rate_limited", status: 429, request_id: "ee55ff66aa77bb88",
  });
  expectNothingPrivate(previewOf().value);
});

it("a page that can't load offline: no reply is reported as no reply, with no made-up reference", async () => {
  server.use(
    http.get(`${API}/api/v1/capabilities`, () => HttpResponse.error()),
    http.get(`${API}/api/v1/me/activity`, () => HttpResponse.error()),
  );
  const { user } = renderApp("/history", { signedIn: true });
  const help = await screen.findByRole("button", { name: "Get help with this" }, { timeout: 3000 });
  Object.defineProperty(navigator, "onLine", { configurable: true, get: () => false }); // the connection is gone
  act(() => { window.dispatchEvent(new Event("offline")); });
  await user.click(help);
  const report = reportIn();
  expect(report.problem).toEqual({
    action: "Loading this page", category: "offline", meaning: "No reply came back. The connection or the server; this report can't tell which.",
    code: "network_error", status: 0, request_id: null,
  });
  expect(report.browser.online).toBe(false);
  await waitFor(() => expect(reportIn().server_said).toBe("unknown: the server's status couldn't be loaded"));
  expectNothingPrivate(previewOf().value);
});

describe("the report page", () => {
  it("works signed out, says what's in it, and what's copied is exactly the preview", async () => {
    const { user } = renderApp("/help/report");
    expect(await screen.findByRole("heading", { name: "Support report", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "What's never in it" })).toBeInTheDocument();
    await waitFor(() => expect(reportIn().session).toBe("signed_out"));
    await waitFor(() => expect(reportIn().server_said).not.toBe("not answered yet"));
    expect(reportIn().problem).toBeNull();
    // The refused session check on load is how "signed out" is learned, not a failed request.
    expect(reportIn().recent_failed_requests).toEqual([]);
    const writeText = vi.spyOn(navigator.clipboard, "writeText"); // user-event's clipboard stand-in
    await user.click(screen.getByRole("button", { name: "Copy the report" }));
    expect(writeText).toHaveBeenCalledWith(previewOf().value);
    expect(await navigator.clipboard.readText()).toBe(previewOf().value);
    expect(screen.getByRole("status")).toHaveTextContent("Copied the report.");
    expectNothingPrivate(previewOf().value);
  });

  it("when copying is denied, the report is selected to copy by hand", async () => {
    const { user } = renderApp("/help/report");
    vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(new DOMException("denied", "NotAllowedError"));
    const preview = await screen.findByRole("textbox", { name: "The report" }) as HTMLTextAreaElement;
    await user.click(screen.getByRole("button", { name: "Copy the report" }));
    expect(await screen.findByRole("status")).toHaveTextContent("This browser didn't allow copying. The report is selected above");
    expect(preview).toHaveFocus();
    expect(preview.selectionStart).toBe(0);
    expect(preview.selectionEnd).toBe(preview.value.length);
  });

  it("downloads exactly the preview as a dated .json file and then revokes its address", async () => {
    let blob: Blob | null = null;
    const create = vi.fn((b: Blob) => { blob = b; return "blob:report-1"; });
    const revoke = vi.fn();
    Object.assign(URL, { createObjectURL: create, revokeObjectURL: revoke });
    const clicked: HTMLAnchorElement[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) { clicked.push(this); });
    const { user } = renderApp("/help/report");
    await screen.findByRole("textbox", { name: "The report" });
    await user.click(screen.getByRole("button", { name: /^Download codecoach-support-report-\d{8}-\d{4}\.json$/ }));
    expect(clicked).toHaveLength(1);
    expect(clicked[0]!.download).toMatch(/^codecoach-support-report-\d{8}-\d{4}\.json$/);
    expect(clicked[0]!.isConnected).toBe(false); // the temporary link is removed
    expect(await blob!.text()).toBe(previewOf().value);
    expect(blob!.type).toBe("application/json");
    expect(screen.getByRole("status")).toHaveTextContent("Nothing has been sent anywhere");
    await waitFor(() => expect(revoke).toHaveBeenCalledWith("blob:report-1"), { timeout: 3000 });
  });

  it("when the browser can't save a file, it falls back to selecting the report", async () => {
    Object.assign(URL, { createObjectURL: vi.fn(() => { throw new Error("blocked"); }), revokeObjectURL: vi.fn() });
    const { user } = renderApp("/help/report");
    const preview = await screen.findByRole("textbox", { name: "The report" });
    await user.click(screen.getByRole("button", { name: /^Download/ }));
    expect(screen.getByRole("status")).toHaveTextContent("This browser didn't save the file. The report is selected above");
    expect(preview).toHaveFocus();
  });

  it("bounds the description and keeps markup as text", async () => {
    const { user } = renderApp("/help/report");
    const description = await screen.findByLabelText(/What happened\?/);
    expect(description).toHaveAccessibleDescription(/Don't include passwords, codes from emails, or anything private/);
    const markup = `<img src=x onerror="window.__pwned=1"><b>bold</b>`;
    await user.click(description);
    await user.paste(markup);
    expect(reportIn().description).toBe(markup);
    expect(document.querySelector("img[src='x']")).toBeNull();
    expect((window as unknown as { __pwned?: number }).__pwned).toBeUndefined();
    await user.paste("x".repeat(700));
    expect(reportIn().description).toHaveLength(500);
    expect(screen.getByText(/500 of 500 characters/)).toBeInTheDocument();
  });
});

it("signing out empties the failed-request log, so the next session's report doesn't carry it", async () => {
  server.use(http.get(`${API}/api/v1/me/activity`, () => failure("internal_error", 500, "1234abcd5678ef90")));
  const { user, router } = renderApp("/history", { signedIn: true });
  await user.click(await screen.findByRole("button", { name: "Get help with this" }, { timeout: 3000 }));
  expect(reportIn().recent_failed_requests).toContainEqual(expect.objectContaining({ request_id: "1234abcd5678ef90" }));
  await user.click(screen.getByRole("button", { name: "Sign out" }));
  await screen.findByRole("link", { name: "Sign in" });
  await act(() => router.navigate("/help/report"));
  await screen.findByRole("textbox", { name: "The report" });
  expect(reportIn().session).toBe("signed_out");
  expect(reportIn().recent_failed_requests.some((f) => f.request_id === "1234abcd5678ef90")).toBe(false);
});
