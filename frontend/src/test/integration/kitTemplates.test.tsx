/**
 * Kit templates (Volume 11, prompt 7; docs/TEMPLATES.md). Saving one keeps only the words chosen
 * (never ticks, links, notes or the interview), after a preview, and a lost reply sent again makes
 * one. Applying one adds its items to another kit's form, unticked and unsaved, without repeating
 * what's there; the kit's own Save keeps them. Template text is plain text. A deleted template says
 * so; the list page previews, renames (revision-checked) and deletes, moving focus sensibly.
 */
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { Kit, KitTemplate, KitTemplateSummary } from "@/api/types";

import { tokenResponse, user as baseUser } from "../fixtures";
import { renderApp } from "../render";
import { API, server } from "../server";

const asUser = () => server.use(http.post(`${API}/api/v1/auth/refresh`, () => HttpResponse.json(tokenResponse({ user: { ...baseUser, career_track: "registered-nurse" } }))));
const KIT = "/applications/a1/events/e1/kit";
const now = () => new Date().toISOString();

function kit(over: Partial<Kit> = {}): Kit {
  return {
    event_id: "e1", application_id: "a1", role_title: "Ward nurse", employer: "Mercy General", event_title: "Panel interview", event_kind: "interview",
    on_date: "2026-11-12", local_time: "10:00", timezone: "Europe/London", starts_at: "2026-11-12T10:00:00Z", format: "remote", location: "Ward 7",
    meeting_link: "https://meet.example.com/secret", interviewers: [{ name: "Ms Lee", role: "Ward manager" }], notes: "Salary hopes: private",
    checklist: [
      { id: "s-0", text: "Confirm the date, time and time zone", origin: "suggested", done: true, hidden: false },
      { id: "y-1", text: "Print two copies of my registration", origin: "yours", done: true, hidden: false },
      { id: "y-2", text: "A hidden one", origin: "yours", done: false, hidden: true },
    ],
    questions: [
      { id: "y-q1", text: "How is the preceptorship structured?", group: "training", origin: "yours", excluded: false, note: null },
      { id: "y-q2", text: "What does a typical shift look like?", group: "workflow", origin: "yours", excluded: false, note: null },
    ],
    stories: [], target_title: null, saved: true, revision: 3, rescheduled_from: null, missing_stories: 0, ...over,
  };
}
const template = (over: Partial<KitTemplate> = {}): KitTemplate => ({
  id: "t1", name: "Ward interviews", revision: 1, created_at: now(), updated_at: now(), save_replay: null,
  checklist: [{ text: "Print two copies of my registration" }, { text: "Confirm the date, time and time zone" }, { text: "<img src=x onerror=alert(1)> {{employer}}" }],
  questions: [{ text: "How is the preceptorship structured?", group: "training" }],
  ...over,
});
const summary = (t: KitTemplate): KitTemplateSummary => ({ id: t.id, name: t.name, checklist_count: t.checklist.length, questions_count: t.questions.length, revision: t.revision, updated_at: t.updated_at });

describe("Saving a kit as a template", () => {
  it("keeps only the words chosen, shows them first, and a lost reply sent again makes one", async () => {
    asUser();
    const posts: Record<string, unknown>[] = [];
    let lose = true;
    server.use(
      http.get(`${API}/api/v1/me/applications/a1/events/e1/kit`, () => HttpResponse.json(kit())),
      http.post(`${API}/api/v1/me/kit-templates`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        posts.push(body);
        if (lose) { lose = false; return HttpResponse.error(); } // it was saved; the reply was lost
        return HttpResponse.json(template({ name: String(body.name) }), { status: 201 });
      }),
    );
    const { user } = renderApp(KIT, { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Save as a template…" }, { timeout: 3000 }));
    const name = screen.getByLabelText("Template name");
    expect(name).toHaveValue("Ward nurse interviews");
    await user.clear(name);
    await user.type(name, "Ward interviews");
    // The hidden item isn't offered; the second question is left out here.
    const keep = screen.getByRole("group", { name: "Checklist items to keep" });
    expect(within(keep).queryByText("A hidden one")).toBeNull();
    await user.click(within(screen.getByRole("group", { name: "Questions to keep" })).getByRole("checkbox", { name: "What does a typical shift look like?" }));
    const preview = screen.getByRole("region", { name: "What the template will hold" });
    expect(within(preview).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      "Confirm the date, time and time zone", "Print two copies of my registration", "How is the preceptorship structured? · Training and support",
    ]);
    expect(screen.getByText(/Never kept: what you've ticked, the meeting link, location, interviewers, notes, examples/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Save template" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No reply came, so it isn't known whether the template was saved. Saving again is safe: it makes one template, not two.");
    await user.click(screen.getByRole("button", { name: "Save again" }));
    expect(await screen.findByText(/Saved as “Ward interviews”\./)).toBeInTheDocument();
    expect(posts).toHaveLength(2);
    expect(posts[1]).toEqual(posts[0]); // the same create, with the same key
    expect(posts[0]).toEqual({
      name: "Ward interviews",
      checklist: [{ text: "Confirm the date, time and time zone" }, { text: "Print two copies of my registration" }],
      questions: [{ text: "How is the preceptorship structured?", group: "training" }],
      client_request_id: expect.any(String),
    });
    expect(JSON.stringify(posts[0])).not.toMatch(/done|meet\.example|Salary|Ms Lee|Ward 7|Panel interview|Mercy/);
  });
});

describe("Starting another kit from a template", () => {
  it("adds the items unticked and unsaved, skips what's there, and shows template text as text", async () => {
    asUser();
    const puts: { checklist: Kit["checklist"]; questions: Kit["questions"] }[] = [];
    const fresh = kit({ event_title: "Second interview", checklist: [{ id: "s-0", text: "Confirm the date, time and time zone", origin: "suggested", done: false, hidden: false }], questions: [], saved: false, revision: 0, meeting_link: null, notes: "" });
    server.use(
      http.get(`${API}/api/v1/me/applications/a1/events/e1/kit`, () => HttpResponse.json(fresh)),
      http.get(`${API}/api/v1/me/kit-templates`, () => HttpResponse.json([summary(template())])),
      http.get(`${API}/api/v1/me/kit-templates/t1`, () => HttpResponse.json(template())),
      http.put(`${API}/api/v1/me/applications/a1/events/e1/kit`, async ({ request }) => {
        const body = (await request.json()) as typeof puts[number];
        puts.push(body);
        return HttpResponse.json({ ...fresh, ...body, saved: true, revision: 1 });
      }),
    );
    const { user } = renderApp(KIT, { signedIn: true });
    await user.selectOptions(await screen.findByLabelText("Start from one of your templates", undefined, { timeout: 3000 }), "t1");
    const preview = await screen.findByRole("region", { name: "Preview: Ward interviews" });
    expect(preview.querySelector("img")).toBeNull();
    expect(within(preview).getByText("<img src=x onerror=alert(1)> {{employer}}")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Add to this kit" }));
    expect(screen.getByText("Added 2 checklist items and 1 question from “Ward interviews”, not ticked. They aren't saved yet: Save kit keeps them.")).toBeInTheDocument();
    const printed = screen.getByRole("checkbox", { name: "Print two copies of my registration" });
    expect(printed).not.toBeChecked();
    expect(screen.getAllByRole("checkbox", { name: "Confirm the date, time and time zone" })).toHaveLength(1); // not twice
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
    expect(puts).toEqual([]); // applying isn't saving
    expect(document.querySelector(".kit-page img")).toBeNull();

    // The same template again adds nothing more.
    await user.selectOptions(screen.getByLabelText("Start from one of your templates"), "t1");
    await user.click(await screen.findByRole("button", { name: "Add to this kit" }));
    expect(screen.getByText("Everything in “Ward interviews” is already in this kit.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Save kit" }));
    await waitFor(() => expect(puts).toHaveLength(1));
    const added = puts[0]!.checklist.filter((c) => c.id !== "s-0");
    expect(added.map((c) => [c.text, c.done, c.origin])).toEqual([
      ["Print two copies of my registration", false, "yours"],
      ["<img src=x onerror=alert(1)> {{employer}}", false, "yours"],
    ]);
    expect(new Set(added.map((c) => c.id)).size).toBe(2);
    expect(puts[0]!.questions.map((q) => [q.text, q.group, q.excluded])).toEqual([["How is the preceptorship structured?", "training", false]]);
  });

  it("says a template deleted elsewhere is gone, and offers nothing to add", async () => {
    asUser();
    server.use(
      http.get(`${API}/api/v1/me/applications/a1/events/e1/kit`, () => HttpResponse.json(kit())),
      http.get(`${API}/api/v1/me/kit-templates`, () => HttpResponse.json([summary(template())])),
      http.get(`${API}/api/v1/me/kit-templates/t1`, () => HttpResponse.json({ error: { code: "not_found", message: "Template not found", request_id: "r" } }, { status: 404 })),
    );
    const { user } = renderApp(KIT, { signedIn: true });
    await user.selectOptions(await screen.findByLabelText("Start from one of your templates", undefined, { timeout: 3000 }), "t1");
    expect(await screen.findByText("That template was deleted. Kits made from it keep their items.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add to this kit" })).toBeNull();
  });
});

describe("Your kit templates", () => {
  it("previews, renames against its revision, and deletes with focus moving on", async () => {
    asUser();
    let list = [template(), template({ id: "t2", name: "Phone screens", checklist: [{ text: "Quiet room" }], questions: [] })];
    const patches: Record<string, unknown>[] = [];
    server.use(
      http.get(`${API}/api/v1/me/kit-templates`, () => HttpResponse.json(list.map(summary))),
      http.get(`${API}/api/v1/me/kit-templates/:id`, ({ params }) => HttpResponse.json(list.find((t) => t.id === params.id))),
      http.patch(`${API}/api/v1/me/kit-templates/:id`, async ({ params, request }) => {
        const body = (await request.json()) as { name: string; expected_revision: number };
        patches.push(body);
        const t = list.find((x) => x.id === params.id)!;
        if (body.expected_revision !== t.revision) {
          return HttpResponse.json({ error: { code: "stale_revision", message: "Changed", request_id: "r", details: { current_revision: t.revision, current: t } } }, { status: 409 });
        }
        list = list.map((x) => (x.id === t.id ? { ...x, name: body.name, revision: x.revision + 1 } : x));
        return HttpResponse.json(list.find((x) => x.id === t.id));
      }),
      http.delete(`${API}/api/v1/me/kit-templates/:id`, ({ params }) => { list = list.filter((t) => t.id !== params.id); return new HttpResponse(null, { status: 204 }); }),
    );
    const { user } = renderApp("/kit-templates", { signedIn: true });
    await user.click(await screen.findByRole("button", { name: "Preview: Ward interviews" }, { timeout: 3000 }));
    expect(await screen.findByRole("region", { name: "Preview: Ward interviews" })).toHaveTextContent("Print two copies of my registration");

    await user.click(screen.getByRole("button", { name: "Rename: Ward interviews" }));
    await user.clear(screen.getByLabelText("New name"));
    await user.type(screen.getByLabelText("New name"), "Ward interviews (nights)");
    await user.click(screen.getByRole("button", { name: "Save name" }));
    expect(await screen.findByText("Renamed.")).toBeInTheDocument();
    expect(patches[0]).toEqual({ name: "Ward interviews (nights)", expected_revision: 1, client_request_id: expect.any(String) });
    // Changed elsewhere meanwhile: the page says so and shows the saved name.
    list = list.map((x) => (x.id === "t2" ? { ...x, name: "Phone screens (edited elsewhere)", revision: 2 } : x));
    await user.click(screen.getByRole("button", { name: "Rename: Phone screens" }));
    await user.clear(screen.getByLabelText("New name"));
    await user.type(screen.getByLabelText("New name"), "Mine");
    await user.click(screen.getByRole("button", { name: "Save name" }));
    expect(await screen.findByText(/It was changed somewhere else since this page loaded/)).toBeInTheDocument();
    expect(await screen.findByText("Phone screens (edited elsewhere)")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Delete: Ward interviews (nights)" }));
    const ask = screen.getByRole("group", { name: "Delete “Ward interviews (nights)”" });
    expect(ask).toHaveTextContent("Kits you made from it keep their items.");
    await user.click(within(ask).getByRole("button", { name: "Delete template" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Preview: Phone screens (edited elsewhere)" })).toHaveFocus());
    expect(screen.getByText("“Ward interviews (nights)” deleted. Kits made from it keep their items.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Delete: Phone screens (edited elsewhere)" }));
    await user.click(screen.getByRole("button", { name: "Delete template" }));
    await waitFor(() => expect(screen.getByRole("heading", { level: 1, name: "Your kit templates" })).toHaveFocus());
    expect(screen.getByText("No templates yet")).toBeInTheDocument();
  });
});
