import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { AdminReportDetail, MyReport, ReportGroup } from "@/api/types";

import { contentMeta } from "../content";
import { nurseAnswer, tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const nurse = { ...baseUser, career_track: "registered-nurse" };
const asUser = (u = nurse) => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: u }))));
const now = () => new Date().toISOString();
const QUESTION = "/careers/registered-nurse/questions/m-pressure-0";

function myReport(over: Partial<MyReport> = {}): MyReport {
  return {
    id: "r1", content_type: "question", content_id: "registered-nurse/m-pressure-0", content_title: "Patient assessment under pressure",
    content_href: QUESTION, content_version: 1, category: "ambiguous_wording", context: "content", details: "Unclear.", excerpt: null,
    status: "open", resolution: null, created_at: now(), updated_at: now(), ...over,
  };
}

describe("question metadata and corrections", () => {
  it("shows what the question is and how it was made, without claiming review", async () => {
    asUser();
    const { user } = renderApp(QUESTION, { signedIn: true });
    const info = await screen.findByText(/About this question · Version 1/);
    await user.click(info);
    const details = info.closest("details")!;
    expect(within(details).getByText("Registered Nurse")).toBeInTheDocument();
    expect(within(details).getByText(/Generated from the Registered Nurse career profile/)).toBeInTheDocument();
    expect(within(details).getByText("Not reviewed by a subject-matter expert")).toBeInTheDocument();
  });

  it("tells a learner what changed since they answered, and keeps the old answer tied to its version", async () => {
    asUser();
    server.use(
      http.get(`${API}/api/v1/content/question/*`, () => HttpResponse.json(contentMeta({
        version: 2, version_label: "Version 2",
        changes: [{ version: 2, note: "The prompt now says which assessment to describe.", significant: true, at: now() }],
      }))),
      http.get(`${API}/api/v1/careers/:track/questions/:id/answers`, () => HttpResponse.json([{ ...nurseAnswer, content_version: 1 }])),
      http.get(`${API}/api/v1/careers/:track/questions/:id/versions/1`, () => HttpResponse.json({ version: 1, title: "Old title", prompt: "The old wording." })),
    );
    const { user } = renderApp(`${QUESTION}?answer=a-1`, { signedIn: true });
    const banner = await screen.findByText(/This question changed since you answered it/);
    expect(banner.closest(".banner")).toHaveTextContent("version 1 → 2");
    expect(banner.closest(".banner")).toHaveTextContent("The prompt now says which assessment to describe.");
    const older = await screen.findByText(/Answered version 1 of this question \(it's now version 2\)/);
    await user.click(older);
    expect(await screen.findByText("The old wording.")).toBeInTheDocument();
    expect(screen.getByText(/This answer and its score stay as they were/)).toBeInTheDocument();
  });

  it("a retired question is still readable but isn't graded", async () => {
    asUser();
    server.use(http.get(`${API}/api/v1/content/question/*`, () => HttpResponse.json(contentMeta({ status: "retired", retired_reason: "The scenario was misleading." }))));
    const { user } = renderApp(QUESTION, { signedIn: true });
    expect(await screen.findByText(/The scenario was misleading\./)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Your answer"), "Still drafting.");
    expect(screen.getByRole("button", { name: "Get feedback" })).toBeDisabled();
    expect(screen.getByText(/This question is retired, so it isn't graded any more/)).toBeInTheDocument();
  });
});

describe("reporting an issue", () => {
  it("sends the content id and version on screen, and an excerpt only if the learner chose and reviewed it", async () => {
    asUser();
    const sent: unknown[] = [];
    server.use(http.post(`${API}/api/v1/reports`, async ({ request }) => {
      sent.push(await request.json());
      return sent.length === 1
        ? HttpResponse.json(myReport(), { status: 201 })
        : HttpResponse.json({ error: { code: "already_reported", message: "x", request_id: "r", details: { report_id: "r1" } } }, { status: 409 });
    }));
    const { user } = renderApp(QUESTION, { signedIn: true });
    await user.type(await screen.findByLabelText("Your answer"), "My private draft about Mr. Smith.");
    const toggle = screen.getByRole("button", { name: "Report an issue" });
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    const send = screen.getByRole("button", { name: "Send report" });
    expect(send).toBeDisabled(); // a category first
    await user.click(screen.getByRole("radio", { name: "Ambiguous or unclear wording" }));
    await user.type(screen.getByLabelText(/Details/), "Which patient?");
    expect(screen.getByText(/Not sent: your other answers, recordings/)).toBeInTheDocument();
    await user.click(send);
    expect(await screen.findByText(/Thanks, it's been reported/)).toBeInTheDocument();
    expect(sent[0]).toEqual({ content_type: "question", content_id: "registered-nurse/m-pressure-0", content_version: 1,
      category: "ambiguous_wording", details: "Which patient?", context: "content", answer_id: null, excerpt: null });

    await user.click(screen.getByRole("button", { name: "Close" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Report an issue" })).toHaveFocus());
    await user.click(screen.getByRole("button", { name: "Report an issue" }));
    await user.click(screen.getByRole("radio", { name: "Ambiguous or unclear wording" }));
    await user.click(screen.getByRole("checkbox", { name: /Attach part of my answer/ }));
    const excerpt = screen.getByLabelText("Excerpt to attach");
    expect(excerpt).toHaveValue("My private draft about Mr. Smith.");
    await user.clear(excerpt);
    await user.type(excerpt, "My private draft");
    await user.click(screen.getByRole("button", { name: "Send report" }));
    expect(await screen.findByText(/You've already reported this and it's still open/)).toBeInTheDocument();
    expect(sent[1]).toMatchObject({ excerpt: "My private draft" });
  });

  it("feedback reports name the answer; the learner sees their reports and outcomes", async () => {
    asUser();
    let body: Record<string, unknown> | null = null;
    server.use(
      http.post(`${API}/api/v1/reports`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(myReport({ context: "feedback" }), { status: 201 });
      }),
      http.get(`${API}/api/v1/careers/:track/questions/:id/answers`, () => HttpResponse.json([nurseAnswer])),
    );
    const { user, unmount } = renderApp(`${QUESTION}?answer=a-1`, { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Report a problem with this feedback" }));
    await user.click(screen.getByRole("radio", { name: "Incorrect example or answer" }));
    await user.click(screen.getByRole("button", { name: "Send report" }));
    await screen.findByText(/Thanks, it's been reported/);
    expect(body).toMatchObject({ context: "feedback", answer_id: "a-1", category: "incorrect_example", excerpt: null });
    unmount();

    server.use(http.get(`${API}/api/v1/me/reports`, () => HttpResponse.json([
      myReport({ status: "resolved", resolution: "Corrected in version 2: clearer prompt.", details: "<b>bold?</b>" }),
    ])));
    renderApp("/reports", { signedIn: true });
    expect(await screen.findByText("Resolved")).toBeInTheDocument();
    expect(screen.getByText("Corrected in version 2: clearer prompt.")).toBeInTheDocument();
    expect(screen.getByText("<b>bold?</b>")).toBeInTheDocument(); // shown as text
  });
});

describe("admin triage", () => {
  const detail = (over: Partial<AdminReportDetail> = {}): AdminReportDetail => ({
    ...myReport({ details: "<img src=x onerror=alert(1)> wrong" }), reporter: "Ada", duplicate_of: null, duplicates: ["r2"], current_version: 1,
    audit: [{ action: "reported", actor: "Ada", detail: { category: "ambiguous_wording" }, internal_note: null, created_at: now() }],
    meta: contentMeta(), ...over,
  });

  it("is a plain 'not found' page for anyone who isn't an admin", async () => {
    asUser();
    renderApp("/admin/reports", { signedIn: true });
    expect(await screen.findByRole("heading", { level: 1, name: /page not found/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Triage" })).toBeNull();
  });

  it("admins see grouped reports, set a status with a public explanation, and publish a correction", async () => {
    asUser({ ...nurse, is_admin: true });
    const groups: ReportGroup[] = [{ content_type: "question", content_id: "registered-nurse/m-pressure-0", content_title: "Patient assessment under pressure", open_count: 2,
      reports: [{ ...detail(), audit: undefined, meta: undefined } as unknown as ReportGroup["reports"][number], { ...detail({ id: "r2", duplicate_of: "r1", duplicates: [] }), audit: undefined, meta: undefined } as unknown as ReportGroup["reports"][number]] }];
    const calls: unknown[] = [];
    server.use(
      http.get(`${API}/api/v1/admin/reports`, () => HttpResponse.json(groups)),
      http.get(`${API}/api/v1/admin/reports/r1`, () => HttpResponse.json(detail())),
      http.post(`${API}/api/v1/admin/reports/r1/status`, async ({ request }) => { calls.push(await request.json()); return HttpResponse.json(detail({ status: "investigating" })); }),
      http.post(`${API}/api/v1/admin/content/question/registered-nurse/m-pressure-0/corrections`, async ({ request }) => {
        calls.push(await request.json());
        return HttpResponse.json(contentMeta({ version: 2, version_label: "Version 2" }));
      }),
    );
    const { user } = renderApp("/admin/reports", { signedIn: true });
    expect(await screen.findByRole("link", { name: "Triage" })).toBeInTheDocument();
    expect(await screen.findByText("2 open · 2 in this list")).toBeInTheDocument();
    expect(screen.getByText(/likely duplicate/)).toBeInTheDocument();
    await user.click(screen.getAllByRole("link", { name: "Ambiguous or unclear wording" })[0]!);
    expect(await screen.findByText("<img src=x onerror=alert(1)> wrong")).toBeInTheDocument(); // plain text
    await user.selectOptions(screen.getByLabelText("Status"), "resolved");
    expect(screen.getByRole("button", { name: "Save status" })).toBeDisabled(); // needs the public explanation
    await user.selectOptions(screen.getByLabelText("Status"), "investigating");
    await user.type(screen.getByLabelText(/Internal note/), "Checking the profile.");
    await user.click(screen.getByRole("button", { name: "Save status" }));
    await waitFor(() => expect(calls[0]).toEqual({ status: "investigating", internal_note: "Checking the profile." }));

    const prompt = await screen.findByLabelText("Prompt");
    await user.clear(prompt);
    await user.type(prompt, "Tell me about a time you assessed a deteriorating patient.");
    await user.type(screen.getByLabelText(/What changed, in plain language/), "Says what to describe.");
    await user.click(screen.getByRole("button", { name: "Publish version 2" }));
    await waitFor(() => expect(calls[1]).toMatchObject({ prompt: "Tell me about a time you assessed a deteriorating patient.", change_note: "Says what to describe.", significant: true, report_ids: ["r1"] }));
  });
});
