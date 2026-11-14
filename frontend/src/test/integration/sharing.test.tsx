import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { vi } from "vitest";

import type { RecipientView, ShareDetail, SharedView } from "@/api/types";

import { renderApp } from "../render";
import { API, server } from "../server";

const TOKEN = "T".repeat(43);
const SENTENCES = ["I checked his vitals.", "I called the team.", "He was stable in 30 minutes."].map((text, index) => ({ index, text }));
const now = () => new Date().toISOString();
const later = () => new Date(Date.now() + 7 * 86_400_000).toISOString();
const err = (status: number, code: string, message: string) =>
  HttpResponse.json({ error: { code, message, request_id: "r", details: null } }, { status });

function viewFor(indices: number[], ai = false): SharedView {
  return {
    kind: "practice_answer", career_title: "Registered Nurse",
    question: { title: "Patient assessment under pressure", prompt: "Tell me about a time…", kind: "behavioral", difficulty: "medium" },
    excerpt: SENTENCES.filter((s) => indices.includes(s.index)), total_sentences: 3, omitted_sentences: 3 - indices.length,
    followup: null, note: "", answered_on: "2026-11-03",
    ai_feedback: ai ? { score: 92, rating: "Strong", summary: "Clear and specific.", points: [{ label: "Result", covered: true }], coach: "built-in (offline)" } : null,
    prompts: ["What was clear?", "What needs more evidence?", "One useful next step"],
  };
}

function detail(over: Partial<ShareDetail> = {}): ShareDetail {
  return {
    id: "s1", status: "active", kind: "practice_answer", career_title: "Registered Nurse", question_title: "Patient assessment under pressure",
    source_answer_id: "a-1", created_at: now(), expires_at: later(), closed_at: null, revoked_at: null, last_opened_at: null,
    feedback_count: 0, last_feedback_at: null, view: viewFor([0, 1, 2]), feedback: [], source_changed: false, source_missing: false, ...over,
  };
}

describe("sharing an answer: owner", () => {
  it("previews exactly what's chosen, needs explicit consent, and shows the link once", async () => {
    const previews: unknown[] = [];
    let created: Record<string, unknown> | null = null;
    server.use(
      http.post(`${API}/api/v1/me/shares/preview`, async ({ request }) => {
        const body = (await request.json()) as { sentences?: number[] | null; include_ai_feedback: boolean };
        previews.push(body);
        return HttpResponse.json({ source_sentences: SENTENCES, has_followup: false, view: viewFor(body.sentences ?? [0, 1, 2], body.include_ai_feedback) });
      }),
      http.post(`${API}/api/v1/me/shares`, async ({ request }) => {
        created = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ share: detail({ view: viewFor([0, 2]) }), token: TOKEN, path: `/shared#t=${TOKEN}` }, { status: 201 });
      }),
    );
    const { user } = renderApp("/share/new?answer=a-1", { signedIn: true });
    // After user-event's setup, which installs its own clipboard.
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    const preview = await screen.findByRole("region", { name: "Preview: what your reviewer sees" });
    await within(preview).findByText("I called the team.");

    await user.click(screen.getByRole("checkbox", { name: /I called the team\./ }));
    await user.click(screen.getByRole("checkbox", { name: /Include CodeCoach's automated feedback/ }));
    await waitFor(() => expect(within(preview).queryByText("I called the team.")).toBeNull());
    expect(within(preview).getByText("[…] 1 sentence not shared")).toBeInTheDocument();
    expect(within(preview).getByRole("heading", { name: "CodeCoach's automated feedback" })).toBeInTheDocument();
    expect(previews.at(-1)).toMatchObject({ answer_id: "a-1", sentences: [0, 2], include_ai_feedback: true });

    const create = screen.getByRole("button", { name: "Create link" });
    expect(create).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: /anyone who has the link/ }));
    await user.click(create);
    const link = await screen.findByRole("textbox", { name: "Private link" });
    expect(link).toHaveValue(`${window.location.origin}/shared#t=${TOKEN}`);
    expect(created).toMatchObject({ sentences: [0, 2], include_ai_feedback: true, expires_in_days: 7, acknowledge_link_access: true });
    expect(screen.getByText(/This is the only time the link is shown/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Copy link" }));
    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/shared#t=${TOKEN}`);
    expect(await screen.findByText(/Copied\./)).toBeInTheDocument();
  });

  it("shows people's feedback apart from the AI's, and can mark it useful and turn the link off", async () => {
    let share = detail({
      feedback_count: 1, view: viewFor([0, 1, 2], true),
      feedback: [{ id: "f1", reviewer: { kind: "guest", label: "Sam (guest, name not verified)" }, clear: "<b>The order</b> was clear.", needs_evidence: "", next_step: "Lead with the result.",
        comments: [{ sentence: 1, text: "Who first?", quote: "I called the team." }], created_at: now(), useful: false }],
    });
    const calls: string[] = [];
    server.use(
      http.get(`${API}/api/v1/me/shares/s1`, () => HttpResponse.json(share)),
      http.put(`${API}/api/v1/me/shares/s1/feedback/f1/useful`, async ({ request }) => {
        calls.push(`useful:${((await request.json()) as { useful: boolean }).useful}`);
        share = { ...share, feedback: share.feedback.map((f) => ({ ...f, useful: true })) };
        return HttpResponse.json(share);
      }),
      http.post(`${API}/api/v1/me/shares/s1/revoke`, () => {
        calls.push("revoke");
        share = { ...share, status: "revoked", revoked_at: now() };
        return HttpResponse.json(share);
      }),
    );
    const { user } = renderApp("/shares/s1", { signedIn: true });
    const item = await screen.findByRole("article", { name: "Feedback from Sam (guest, name not verified)" });
    expect(within(item).getByText("<b>The order</b> was clear.")).toBeInTheDocument(); // text, never HTML
    expect(within(item).getByText("Who first?")).toBeInTheDocument();
    expect(screen.getByText(/it isn't a hiring decision or professional validation/)).toBeInTheDocument();
    // The automated feedback is only inside the shared copy, labelled.
    const copy = screen.getByRole("region", { name: "What you shared" });
    expect(within(copy).getByRole("heading", { name: "CodeCoach's automated feedback" })).toBeInTheDocument();
    expect(within(item).queryByText(/92/)).toBeNull();

    await user.click(within(item).getByRole("button", { name: "Useful" }));
    await waitFor(() => expect(within(screen.getByRole("article")).getByRole("button", { name: "Useful" })).toHaveAttribute("aria-pressed", "true"));

    await user.click(screen.getByRole("button", { name: "Turn the link off" }));
    expect(screen.getByRole("alertdialog", { name: "Turn this link off for good?" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("alertdialog")).toBeNull();
    await waitFor(() => expect(screen.getByRole("button", { name: "Turn the link off" })).toHaveFocus());
    await user.click(screen.getByRole("button", { name: "Turn the link off" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Turn it off" }));
    expect(await screen.findByText("Link turned off")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Make a new link" })).toBeNull();
    expect(calls).toEqual(["useful:true", "revoke"]);
  });
});

describe("sharing an answer: the reviewer", () => {
  const open = (over: Partial<RecipientView> = {}): RecipientView => ({ status: "active", expires_at: later(), view: viewFor([0, 2]), reviewer: null, ...over });

  it("sends the secret in the body (never a URL), shows only the shared copy and takes structured feedback", async () => {
    const opened: string[] = [];
    let sent: Record<string, unknown> | null = null;
    server.use(
      http.post(`${API}/api/v1/shared/open`, async ({ request }) => {
        opened.push(request.url);
        expect(await request.json()).toEqual({ token: TOKEN });
        return HttpResponse.json(open());
      }),
      http.post(`${API}/api/v1/shared/feedback`, async ({ request }) => {
        sent = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ duplicate: false, feedback: { id: "f1", reviewer: { kind: "guest", label: "Sam (guest, name not verified)" }, clear: "Clear order.", needs_evidence: "", next_step: "", comments: [{ sentence: 2, text: "Add the number.", quote: "He was stable in 30 minutes." }], created_at: now(), useful: false } }, { status: 201 });
      }),
    );
    const { user } = renderApp(`/shared#t=${TOKEN}`);
    expect(await screen.findByRole("heading", { level: 1, name: "A practice answer to review" })).toBeInTheDocument();
    expect(opened.every((u) => !u.includes(TOKEN))).toBe(true);
    expect(document.head.querySelector('meta[name="robots"]')).toHaveAttribute("content", "noindex, nofollow");
    expect(document.head.querySelector('meta[name="referrer"]')).toHaveAttribute("content", "no-referrer");
    const copy = screen.getByRole("region", { name: "The shared answer" });
    expect(within(copy).queryByText("I called the team.")).toBeNull();
    expect(within(copy).getByText("[…] 1 sentence not shared")).toBeInTheDocument();

    const send = screen.getByRole("button", { name: "Send feedback" });
    expect(send).toBeDisabled();
    await user.type(screen.getByLabelText(/Your name/), "Sam");
    await user.type(screen.getByLabelText("What was clear?"), "Clear order.");
    await user.selectOptions(screen.getByLabelText("Sentence"), "2");
    await user.type(screen.getByLabelText("Your comment"), "Add the number.");
    await user.click(screen.getByRole("button", { name: "Add comment" }));
    await user.click(send);
    const thanks = await screen.findByRole("heading", { name: "Thanks, your feedback was sent" });
    await waitFor(() => expect(thanks).toHaveFocus());
    expect(sent).toMatchObject({ token: TOKEN, clear: "Clear order.", guest_name: "Sam", comments: [{ sentence: 2, text: "Add the number." }] });
    expect(String((sent as unknown as { client_request_id: string }).client_request_id).length).toBeGreaterThanOrEqual(8);
  });

  it("explains revoked, expired and broken links without showing anything", async () => {
    for (const [code, title] of [["share_revoked", "This link was turned off"], ["share_expired", "This link has expired"], ["share_not_found", "This link doesn't work"]] as const) {
      server.use(http.post(`${API}/api/v1/shared/open`, () => err(code === "share_not_found" ? 404 : 410, code, "x")));
      const { unmount } = renderApp(`/shared#t=${TOKEN}`);
      expect(await screen.findByRole("heading", { level: 1, name: title })).toBeInTheDocument();
      expect(screen.queryByText("I checked his vitals.")).toBeNull();
      unmount();
    }
    renderApp("/shared");
    expect(await screen.findByRole("heading", { level: 1, name: "This link doesn't work" })).toBeInTheDocument();
  });

  it("a closed share can be read but takes no feedback; a signed-in reviewer is named", async () => {
    server.use(http.post(`${API}/api/v1/shared/open`, () => HttpResponse.json(open({ status: "closed" }))));
    const { unmount } = renderApp(`/shared#t=${TOKEN}`);
    expect(await screen.findByRole("heading", { name: "Not taking feedback" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send feedback" })).toBeNull();
    unmount();
    server.use(http.post(`${API}/api/v1/shared/open`, () => HttpResponse.json(open({ reviewer: { kind: "account", label: "Bea (signed-in CodeCoach user)" } }))));
    renderApp(`/shared#t=${TOKEN}`, { signedIn: true });
    expect(await screen.findByText("Bea (signed-in CodeCoach user)")).toBeInTheDocument();
    expect(screen.queryByLabelText(/Your name/)).toBeNull();
  });
});
