import AxeBuilder from "@axe-core/playwright";

import { expect, setTheme, test, type Page } from "./fixtures";
import { API_URL } from "./ports";

/**
 * Know the effects before you choose (Volume 12, prompt 9; docs/LIFECYCLE.md), against the real
 * API: deleting an application lists every item it reaches from the plan that deletes it; another
 * tab adding an event meanwhile shows the new list and does nothing; the delete does what was
 * listed (the comparison keeps its figures and opens, the schedule entry stays as no longer
 * available, the story stays); archiving a note says it unpins and erases nothing. Synthetic data.
 */
async function scan(page: Page, what: string) {
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const r = await new AxeBuilder({ page }).include("main").withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    expect(r.violations.map((v) => v.id), `${what}, ${theme}`).toEqual([]);
  }
}

const offer = (id: string, applicationId: string | null) => ({
  id, label: `Offer ${id.toUpperCase()}`, application_id: applicationId, source_note: "", terms_as_of: null, currency: null, pay_amount: null,
  pay_period: null, months_paid: null, hours_per_week: null, weeks_per_year: null, guaranteed_extra: null, guaranteed_note: "",
  bonus_amount: null, bonus_note: "", equity_note: "", benefits_note: "",
});

test("deleting an application and archiving a note: the preview is what happens", async ({ page, request }) => {
  const email = `life-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "registered-nurse" } });
  expect(reg.status()).toBe(201);
  const auth = { Authorization: `Bearer ${((await reg.json()) as { access_token: string }).access_token}` };
  const post = async <T,>(path: string, data: unknown, method: "post" | "put" = "post") => {
    const r = await request[method](`${API_URL}${path}`, { headers: auth, data });
    expect(r.ok(), `${path}: ${await r.text()}`).toBe(true);
    return (await r.json()) as T;
  };
  const story = await post<{ id: string }>("/api/v1/me/stories", { title: "Two call lights", situation: "A busy night shift." });
  const app = await post<{ id: string }>("/api/v1/me/applications", { employer: "Synthetic Hospital", role_title: "ED nurse", stage: "interviewing", story_ids: [story.id] });
  const apps = `/api/v1/me/applications/${app.id}`;
  const panel = (await post<{ events: { id: string; title: string }[] }>(`${apps}/events`, { title: "Panel interview", on_date: "2030-01-10" })).events[0]!;
  await post(`${apps}/events/${panel.id}/kit`, { story_ids: [story.id] }, "put");
  const prep = await post<{ id: string; title: string }>("/api/v1/me/schedule", {
    kind: "application_event", ref: panel.id, on_date: "2030-01-09", local_time: "18:30", timezone: "Europe/London", duration_min: 60,
  });
  const comp = await post<{ id: string; revision: number }>("/api/v1/me/offer-comparisons", { title: "Two offers" });
  await post(`/api/v1/me/offer-comparisons/${comp.id}`, {
    doc: { title: "Two offers", offers: [offer("a", app.id), offer("b", null)], factors: [], conversions: [], weights_on: false, show_in: null },
    expected_revision: comp.revision,
  }, "put");
  const note = await post<{ id: string }>("/api/v1/me/notes", { title: "Handover phrases", body: "SBAR first." });
  await request.patch(`${API_URL}/api/v1/me/notes/${note.id}`, { headers: auth, data: { pinned: true } });

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);

  // The preview: every item, by what happens to it; focus on the list; nothing sent yet.
  await page.goto(`/applications/${app.id}`);
  await page.getByRole("button", { name: "Delete…" }).click();
  const group = page.getByRole("group", { name: "What this will do" });
  await expect(group.getByRole("heading", { name: "What this will do" })).toBeFocused();
  await expect(group.getByRole("heading", { name: "Deleted (3)" })).toBeVisible();
  await expect(group).toContainText("Interview event: Panel interview (10 January 2030)");
  await expect(group).toContainText("Interview-day kit: Kit for Panel interview");
  await expect(group).toContainText("Story: Two call lights Stays in your story bank.");
  await expect(group).toContainText(`Schedule entry: ${prep.title} Stays on your schedule, marked no longer available.`);
  await expect(group).toContainText("Offer comparison: Two offers Keeps the figures you entered for this offer");
  await expect(group).toContainText("This can't be undone.");
  await scan(page, "delete preview");

  // Another tab adds an event: the scope changed, so nothing is done and the new list shows.
  await post(`${apps}/events`, { title: "Final interview", on_date: "2030-01-20" });
  await group.getByRole("button", { name: "Delete this application, its 1 event and 1 kit" }).click();
  await expect(group).toContainText("What this affects changed since you looked. Nothing was done: check the list again.");
  await expect(group).toContainText("Interview event: Final interview (20 January 2030)");
  expect((await request.get(`${API_URL}${apps}`, { headers: auth })).status()).toBe(200);

  await group.getByRole("button", { name: "Delete this application, its 2 events and 1 kit" }).click();
  await expect(page).toHaveURL(/\/applications$/);
  const done = page.getByRole("status").filter({ hasText: "Deleted ED nurse at Synthetic Hospital." });
  await expect(done).toContainText("With it went its 2 events and 1 kit. Everything listed as kept or unlinked is where it was.");
  await expect(done).toBeFocused();

  // Done as listed.
  expect((await request.get(`${API_URL}${apps}`, { headers: auth })).status()).toBe(404);
  expect((await request.get(`${API_URL}/api/v1/me/stories/${story.id}`, { headers: auth })).status()).toBe(200);
  const opened = await request.get(`${API_URL}/api/v1/me/offer-comparisons/${comp.id}`, { headers: auth });
  expect(opened.status()).toBe(200);
  expect(((await opened.json()) as { doc: { offers: { application_id: string | null }[] } }).doc.offers.map((o) => o.application_id)).toEqual([null, null]);
  const entries = (await (await request.get(`${API_URL}/api/v1/me/schedule?from=2030-01-01&to=2030-01-31`, { headers: auth })).json()) as { id: string; available: boolean }[];
  expect(entries.find((e) => e.id === prep.id)?.available).toBe(false);
  const exported = (await (await request.get(`${API_URL}/api/v1/me/export`, { headers: auth })).json()) as { applications: unknown[]; interview_kits: unknown[]; stories: unknown[] };
  expect([exported.applications.length, exported.interview_kits.length, exported.stories.length]).toEqual([0, 0, 1]);

  // Archiving a note: hides and unpins, erases nothing; focus on the outcome.
  await page.goto(`/notes/${note.id}`);
  await page.getByRole("button", { name: "Archive…" }).click();
  const archive = page.getByRole("group", { name: "What this will do" });
  await expect(archive.getByRole("heading", { name: "Archived (you can undo this) (1)" })).toBeVisible();
  await expect(archive).toContainText("Pin: Pinned to the top of your notes Unarchiving won't pin it again.");
  await expect(archive).toContainText("Archiving isn't deleting");
  await scan(page, "archive preview");
  await archive.getByRole("button", { name: "Archive this note" }).click();
  const archived = page.getByRole("status").filter({ hasText: "Archived Handover phrases." });
  await expect(archived).toContainText("nothing is erased. Unarchive brings it back.");
  await expect(archived).toBeFocused();
  await expect(page.getByRole("button", { name: "Unarchive" })).toBeVisible();
  const kept = (await (await request.get(`${API_URL}/api/v1/me/notes/${note.id}`, { headers: auth })).json()) as { archived: boolean; pinned: boolean; body: string };
  expect([kept.archived, kept.pinned, kept.body]).toEqual([true, false, "SBAR first."]);
});
