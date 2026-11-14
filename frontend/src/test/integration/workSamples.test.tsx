/**
 * Work samples (Volume 10, prompt 5; docs/WORK_SAMPLES.md): the brief and the editor together, the
 * practice scope said before any input, a preview that shows text as text, a draft kept on this
 * device through a reload, feedback that quotes the learner's own sentences and names details the
 * facts don't support, one good approach only when asked, and a revision sent as a new attempt.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { WorkSampleAttempt, WorkSampleBrief, WorkSampleDraft, WorkSampleFeedback } from "@/api/types";

import { user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const ID = "ws-incident-update";
const brief: WorkSampleBrief = {
  id: ID, version: 1, title: "Checkout errors: the first status update", format: "incident_update", format_label: "Incident status update",
  careers: ["software-engineer"], scenario: "You're the on-call engineer at Larkfield Books.", audience: "Colleagues outside engineering.",
  purpose: "Say what's happening and when the next update comes.",
  facts: ["Card payments at checkout began failing at 09:12 UTC.", "About 30% of checkout attempts fail.", "The next update will be posted at 10:30 UTC."],
  required: ["What is happening", "Who is affected, and how much", "When the next update comes"],
  sections: [{ id: "happening", label: "What's happening", hint: "One or two sentences." }, { id: "next", label: "Next update", hint: "When." }],
  min_words: 10, max_words: 180, review_status: "Fictional practice brief.", scope_note: "Everything here is made up for practice. Don't paste real employer material.",
};
const emptyDraft: WorkSampleDraft = { brief_id: ID, sections: { happening: "", next: "" }, revision: 0, updated_at: null };
const feedback: WorkSampleFeedback = {
  rules_version: 1, covered: 2, total: 3, revision: "Change “fixed”: Nothing in the brief says it's fixed.", method: "Fixed checks against this brief, not AI.",
  checks: [{ id: "sections", ok: true, text: "All 2 sections have text." }, { id: "length", ok: true, text: "24 words (the brief asks for 10 to 180)." }],
  points: [
    { id: "what", label: "What is happening", covered: true, quote: "Card payments at checkout are failing since 09:12 UTC.", guidance: "" },
    { id: "who", label: "Who is affected, and how much", covered: false, quote: null, guidance: "Give the size from the brief (about 30% of checkout attempts)." },
    { id: "next", label: "When the next update comes", covered: true, quote: "Next update at 10:30 UTC.", guidance: "" },
  ],
  unsupported: [{ text: "14:00", sentence: "It started again at 14:00.", why: "This detail isn't in the brief." }],
  claims: [{ phrase: "fixed", sentence: "It is fixed now.", why: "Nothing in the brief says it's fixed." }],
  jargon: [], long_sentences: [],
};
const attempt = (over: Partial<WorkSampleAttempt> = {}): WorkSampleAttempt => ({
  id: "att-1", brief_id: ID, brief_version: 1, current_version: 1, title: brief.title, format_label: brief.format_label,
  sections: { happening: "Card payments at checkout are failing since 09:12 UTC.", next: "Next update at 10:30 UTC." },
  section_labels: { happening: "What's happening", next: "Next update" }, feedback: feedback as unknown as WorkSampleAttempt["feedback"],
  reference: { happening: "Since 09:12 UTC, some card payments at checkout have been failing.", next: "Next update at 10:30 UTC." },
  revision_of: null, created_at: "2026-11-09T10:00:00Z", ...over,
});

let sends: { sections: Record<string, string>; revision_of?: string | null }[] = [];
let listed: { id: string; brief_version: number; covered: number; total: number; revision_of: string | null; created_at: string }[] = [];
function serve(draft: WorkSampleDraft = emptyDraft) {
  sends = [];
  listed = [];
  let current = draft;
  server.use(
    http.get(`${API}/api/v1/work-samples`, () => HttpResponse.json([{ id: ID, title: brief.title, format_label: brief.format_label, careers: brief.careers }])),
    http.get(`${API}/api/v1/work-samples/${ID}`, () => HttpResponse.json(brief)),
    http.get(`${API}/api/v1/me/work-samples/${ID}/draft`, () => HttpResponse.json(current)),
    http.put(`${API}/api/v1/me/work-samples/${ID}/draft`, async ({ request }) => {
      const body = (await request.json()) as { sections: Record<string, string>; expected_revision: number };
      if (body.expected_revision !== current.revision) {
        return HttpResponse.json({ error: { code: "stale_revision", message: "Saved elsewhere.", details: { current_revision: current.revision, current } } }, { status: 409 });
      }
      current = { ...current, sections: body.sections, revision: current.revision + 1, updated_at: "2026-11-09T10:00:00Z" };
      return HttpResponse.json(current);
    }),
    http.post(`${API}/api/v1/me/work-samples/${ID}/attempts`, async ({ request }) => {
      const body = (await request.json()) as (typeof sends)[number];
      sends.push(body);
      const made = attempt({ id: `att-${sends.length}`, sections: body.sections, revision_of: body.revision_of ?? null });
      listed = [{ id: made.id, brief_version: 1, covered: 2, total: 3, revision_of: made.revision_of, created_at: made.created_at }, ...listed];
      return HttpResponse.json(made, { status: 201 });
    }),
    http.get(`${API}/api/v1/me/work-samples/${ID}/attempts`, () => HttpResponse.json(listed)),
    http.get(`${API}/api/v1/me/work-samples/attempts/:id`, ({ params }) => HttpResponse.json(attempt({ id: String(params.id) }))),
  );
}

describe("work samples", () => {
  it("lists briefs for your career first and opens one with the brief beside the editor; the scope comes before any input", async () => {
    serve();
    const { user } = renderApp("/work-samples", { signedIn: true });
    const mine = await screen.findByRole("region", { name: "For your career" });
    await user.click(within(mine).getByRole("link", { name: brief.title }));
    const briefRegion = await screen.findByRole("region", { name: "The brief" });
    expect(briefRegion).toHaveTextContent("About 30% of checkout attempts fail.");
    expect(screen.getByRole("note")).toHaveTextContent("Everything here is made up for practice.");
    expect(screen.getByRole("note")).toHaveTextContent("practice evidence, not a credential");
    expect(screen.getByLabelText(/^What's happening/)).toBeInTheDocument();
  });

  it("counts words, previews the text as text, and keeps an unsaved draft on this device through a reload", async () => {
    serve();
    const first = renderApp(`/work-samples/${ID}`, { signedIn: true });
    const hostile = "<img src=x onerror=\"window.__pwned=1\"> Payments are failing.";
    await first.user.type(await screen.findByLabelText(/^What's happening/), hostile);
    expect(screen.getByText(/^\d+ words \(the brief asks for 10 to 180\)\.$/)).toBeInTheDocument();
    await first.user.click(screen.getByRole("button", { name: "Preview" }));
    const preview = screen.getByRole("article", { name: "Preview" });
    expect(preview).toHaveTextContent(hostile);
    expect(preview.querySelector("img")).toBeNull();
    expect((window as { __pwned?: number }).__pwned).toBeUndefined();
    expect(within(preview).getByRole("button", { name: "Copy as text" })).toBeInTheDocument();
    expect(localStorage.getItem(`work-sample-draft:${baseUser.id}:${ID}`)).toContain("Payments are failing.");
    first.unmount();

    serve();
    const second = renderApp(`/work-samples/${ID}`, { signedIn: true });
    await second.user.click(within(await screen.findByRole("region", { name: "Unsaved changes" })).getByRole("button", { name: "Restore them" }));
    expect(screen.getByLabelText(/^What's happening/)).toHaveValue(hostile);
    await second.user.click(screen.getByRole("button", { name: "Save draft" }));
    expect(await screen.findByText("Saved to your account.")).toBeInTheDocument();
  });

  it("feedback quotes the learner's sentences, names what the brief doesn't support, and keeps one good approach until asked", async () => {
    serve();
    const { user } = renderApp(`/work-samples/${ID}`, { signedIn: true });
    await user.type(await screen.findByLabelText(/^What's happening/), "Card payments at checkout are failing since 09:12 UTC.");
    await user.type(screen.getByLabelText(/^Next update/), "Next update at 10:30 UTC.");
    await user.click(screen.getByRole("button", { name: "Get feedback" }));
    const heading = await screen.findByRole("heading", { name: /^Feedback on/ });
    await waitFor(() => expect(heading).toHaveFocus());
    expect(sends).toEqual([{ sections: { happening: "Card payments at checkout are failing since 09:12 UTC.", next: "Next update at 10:30 UTC." }, revision_of: null }]);
    expect(screen.getByRole("region", { name: "What you covered" })).toHaveTextContent("What is happening: Card payments at checkout are failing since 09:12 UTC.");
    expect(screen.getByRole("region", { name: "Missing" })).toHaveTextContent("Give the size from the brief (about 30% of checkout attempts).");
    const flags = screen.getByRole("region", { name: "Not supported by the brief" });
    expect(flags).toHaveTextContent("“fixed” in It is fixed now.");
    expect(flags).toHaveTextContent("“14:00” in It started again at 14:00.");
    expect(screen.getByRole("region", { name: "One revision to try" })).toHaveTextContent("Change “fixed”");
    expect(screen.queryByRole("region", { name: "One good approach" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show one good approach" }));
    expect(screen.getByRole("region", { name: "One good approach" })).toHaveTextContent("Your wording, order and style don't need to match");
  });

  it("a second send is a revision of the first, and the first stays as it was", async () => {
    serve();
    const { user } = renderApp(`/work-samples/${ID}`, { signedIn: true });
    await user.type(await screen.findByLabelText(/^What's happening/), "Card payments at checkout are failing since 09:12 UTC.");
    await user.click(screen.getByRole("button", { name: "Get feedback" }));
    await screen.findByRole("heading", { name: /^Feedback on/ });
    await user.type(screen.getByLabelText(/^Next update/), "Next update at 10:30 UTC.");
    await user.click(await screen.findByRole("button", { name: "Send the revision for feedback" }));
    await waitFor(() => expect(sends).toHaveLength(2));
    expect(sends[1]!.revision_of).toBe("att-1");
    expect(await screen.findByText("Sent as a revision. Your earlier attempt is kept as it was.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: /\(a revision\)$/ })).toBeInTheDocument();
  });

  it("a save refused because another tab saved first shows both versions", async () => {
    serve({ ...emptyDraft, revision: 2, sections: { happening: "From the other tab.", next: "" } });
    const { user } = renderApp(`/work-samples/${ID}`, { signedIn: true });
    await screen.findByLabelText(/^What's happening/);
    serve({ ...emptyDraft, revision: 3, sections: { happening: "Newer, from the other tab.", next: "" } });
    await user.type(screen.getByLabelText(/^Next update/), "At 10:30 UTC.");
    await user.click(screen.getByRole("button", { name: "Save draft" }));
    expect(await screen.findByRole("region", { name: "Edit conflict" })).toHaveTextContent("Newer, from the other tab.");
    expect(screen.getByLabelText(/^Next update/)).toHaveValue("At 10:30 UTC.");
  });
});
