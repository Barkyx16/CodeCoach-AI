import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Kit } from "@/api/types";
import { externalHref } from "@/lib/links";

import { hint, nurseAnswer, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

// Learner text, the coach's text (built-in or Claude) and data from the API are untrusted when
// they reach the page. These tests go through the real pages, at the point where that text is
// rendered. Detecting text addressed to the grader is a separate matter (the rubric); this is
// about what the browser does with it.

const PAYLOAD = `<img src=x onerror="window.__pwned=1"><script>window.__pwned=1</script><b>bold</b>`;
const nurse = { ...baseUser, career_track: "registered-nurse" };

declare global {
  interface Window { __pwned?: number }
}

beforeEach(() => {
  window.__pwned = undefined;
});

describe("Untrusted text renders as text", () => {
  it("feedback, its quotes and notes show markup literally", async () => {
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
      http.get(`${API}/api/v1/careers/:track/questions/:id/answers`, () => HttpResponse.json([])),
      http.post(`${API}/api/v1/careers/:track/questions/:id/answers`, () =>
        HttpResponse.json({
          ...nurseAnswer,
          summary: `Summary ${PAYLOAD}`,
          notes: [`Note ${PAYLOAD}`],
          points: [{ label: "Sets the scene: where you were and what was at stake", covered: true, advice: "a", evidence: `Quote ${PAYLOAD}` }],
        }, { status: 201 }),
      ),
    );
    const { user, container } = renderApp("/careers/registered-nurse/questions/m-pressure-0", { signedIn: true });
    await user.type(await screen.findByLabelText("Your answer"), "Last winter I handled a deteriorating patient.");
    await user.click(screen.getByRole("button", { name: "Get feedback" }));
    const feedback = await screen.findByRole("region", { name: "Feedback" });
    expect(within(feedback).getByText(/Summary <img src=x onerror/)).toBeInTheDocument();
    expect(within(feedback).getByText(/Quote <img src=x onerror/)).toBeInTheDocument();
    expect(container.querySelector("img[src='x'], script, b")).toBeNull();
    expect(window.__pwned).toBeUndefined();
  });

  it("a coaching hint shows markup literally", async () => {
    server.use(http.post(`${API}/api/v1/ai/hint`, () => HttpResponse.json({ ...hint(1), content: { ...hint(1).content, hint: `Try ${PAYLOAD}` } })));
    const { user, container } = renderApp("/problems/two-sum", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Get a hint" }));
    expect(await screen.findByText(/Try <img src=x onerror/)).toBeInTheDocument();
    expect(container.querySelector("img[src='x'], script")).toBeNull();
    expect(window.__pwned).toBeUndefined();
  });
});

describe("Links from data follow the server's rule: absolute http(s) only", () => {
  it.each([
    ["https://meet.example.com/x", "https://meet.example.com/x"],
    ["http://example.com", "http://example.com"],
    ["  https://example.com/a  ", "https://example.com/a"],
    ["javascript:alert(1)", undefined],
    ["JaVaScRiPt:alert(1)", undefined],
    [" javascript:alert(1)", undefined],
    ["data:text/html,<script>alert(1)</script>", undefined],
    ["vbscript:msgbox(1)", undefined],
    ["//evil.example.com", undefined],
    ["/relative", undefined],
    ["https://exa mple.com", undefined],
    ["", undefined],
    [null, undefined],
  ])("%s", (input, expected) => {
    expect(externalHref(input)).toBe(expected);
  });

  const kit = (meeting_link: string): Kit => ({
    event_id: "e1", application_id: "a1", role_title: "Ward nurse", employer: "Mercy General", event_title: "Panel interview",
    event_kind: "interview", on_date: "2026-11-12", local_time: "10:00", timezone: "Europe/London", starts_at: "2026-11-12T10:00:00Z",
    format: "remote", location: "", meeting_link, interviewers: [], notes: "", checklist: [], questions: [], stories: [],
    target_title: null, saved: true,
  });

  it("a meeting link that isn't http(s) is shown as text, not as a link", async () => {
    // The server only saves http(s) links; this stands for an older row or any other path that
    // didn't apply that rule. React 18 doesn't block javascript: URLs in href.
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
      http.get(`${API}/api/v1/me/applications/a1/events/e1/kit`, () => HttpResponse.json(kit("javascript:window.__pwned=1"))),
    );
    const { container } = renderApp("/applications/a1/events/e1/kit", { signedIn: true });
    expect(await screen.findByText("javascript:window.__pwned=1")).toBeInTheDocument();
    expect(container.querySelector("a[href^='javascript' i]")).toBeNull();
  });

  it("an https meeting link stays a link that opens in a new tab", async () => {
    server.use(
      http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: nurse }))),
      http.get(`${API}/api/v1/me/applications/a1/events/e1/kit`, () => HttpResponse.json(kit("https://meet.example.com/x"))),
    );
    renderApp("/applications/a1/events/e1/kit", { signedIn: true });
    const link = await screen.findByRole("link", { name: /meet\.example\.com\/x/ });
    expect(link).toHaveAttribute("href", "https://meet.example.com/x");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });
});
