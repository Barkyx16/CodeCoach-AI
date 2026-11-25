import AxeBuilder from "@axe-core/playwright";

import { expect, setTheme, test } from "./fixtures";
import { API_URL } from "./ports";

/**
 * Kit templates (Volume 11, prompt 7) against the real API: the first interview's kit, with items
 * ticked, a meeting link and notes, is saved as a template (one question left out); the second
 * interview's kit starts from it, unticked, and is saved; the template is renamed and deleted; the
 * first kit's ticks, link and notes and the second kit's items are unchanged throughout. Axe in
 * both themes. Synthetic account.
 */
test("reuse one interview's kit for the next without its ticks, link or notes", async ({ page, request }) => {
  const email = `kt-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "registered-nurse" } });
  expect(reg.status()).toBe(201);
  const auth = { Authorization: `Bearer ${((await reg.json()) as { access_token: string }).access_token}` };
  const app = (await (await request.post(`${API_URL}/api/v1/me/applications`, { headers: auth, data: { employer: "Mercy General", role_title: "Ward nurse", stage: "interviewing" } })).json()) as { id: string };
  for (const [title, on] of [["Phone screen", "2026-12-01"], ["Panel interview", "2026-12-08"]]) {
    await request.post(`${API_URL}/api/v1/me/applications/${app.id}/events`, { headers: auth, data: { title, on_date: on } });
  }
  const events = ((await (await request.get(`${API_URL}/api/v1/me/applications/${app.id}`, { headers: auth })).json()) as { events: { id: string; title: string }[] }).events;
  const first = `/api/v1/me/applications/${app.id}/events/${events.find((e) => e.title === "Phone screen")!.id}/kit`;
  const second = `/api/v1/me/applications/${app.id}/events/${events.find((e) => e.title === "Panel interview")!.id}/kit`;
  // The first interview's kit: two of its own items (one ticked), a question, a private link and notes.
  const base = (await (await request.get(`${API_URL}${first}`, { headers: auth })).json()) as { revision: number; questions: unknown[] };
  const firstSaved = await request.put(`${API_URL}${first}`, { headers: auth, data: {
    checklist: [
      { id: "y1", text: "Print two copies of my registration", origin: "yours", done: true },
      { id: "y2", text: "Plan the bus route", origin: "yours", done: false },
    ],
    questions: [
      { id: "q1", text: "How is the preceptorship structured?", group: "training", origin: "yours" },
      { id: "q2", text: "Who would I report to?", group: "team", origin: "yours" },
    ],
    meeting_link: "https://meet.example.com/abc", notes: "My private notes", expected_revision: base.revision,
  } });
  expect(firstSaved.status()).toBe(200);
  const before = await firstSaved.json();

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);

  // Save it as a template, leaving one question out.
  await page.goto(first.replace("/api/v1/me", ""));
  await page.getByRole("button", { name: "Save as a template…" }).click();
  await page.getByLabel("Template name").fill("Ward interviews");
  await page.getByRole("group", { name: "Questions to keep" }).getByRole("checkbox", { name: "Who would I report to?" }).uncheck();
  await expect(page.getByRole("region", { name: "What the template will hold" })).toContainText("Plan the bus route");
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".kit-templates").analyze();
    expect(scan.violations.map((v) => v.id), `kit templates, ${theme}`).toEqual([]);
  }
  await page.getByRole("button", { name: "Save template" }).click();
  await expect(page.getByText(/Saved as “Ward interviews”\./)).toBeVisible();
  const saved = (await (await request.get(`${API_URL}/api/v1/me/kit-templates`, { headers: auth })).json()) as { id: string }[];
  const template = await (await request.get(`${API_URL}/api/v1/me/kit-templates/${saved[0]!.id}`, { headers: auth })).text();
  expect(template).not.toMatch(/meet\.example|private notes|Who would I report|done|Phone screen/);

  // The next interview starts from it: unticked, saved only with the kit's own Save.
  await page.goto(second.replace("/api/v1/me", ""));
  await page.getByLabel("Start from one of your templates").selectOption({ label: "Ward interviews (3)" });
  await page.getByRole("button", { name: "Add to this kit" }).click();
  await expect(page.getByText(/Added 2 checklist items and 1 question from “Ward interviews”/)).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "Print two copies of my registration" })).not.toBeChecked();
  await page.getByRole("button", { name: "Save kit" }).click();
  await expect(page.getByText("Saved.")).toBeVisible();

  // Rename and delete the template: neither kit changes.
  await page.goto("/kit-templates");
  await page.getByRole("button", { name: "Rename: Ward interviews" }).click();
  await page.getByLabel("New name").fill("Ward interviews (nights)");
  await page.getByRole("button", { name: "Save name" }).click();
  await expect(page.getByText("Renamed.")).toBeVisible();
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".kit-templates-page").analyze();
    expect(scan.violations.map((v) => v.id), `templates page, ${theme}`).toEqual([]);
  }
  await page.getByRole("button", { name: "Delete: Ward interviews (nights)" }).click();
  await page.getByRole("button", { name: "Delete template" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Your kit templates" })).toBeFocused();

  const firstNow = await (await request.get(`${API_URL}${first}`, { headers: auth })).json();
  expect(firstNow.checklist).toEqual(before.checklist); // its tick, untouched
  expect([firstNow.meeting_link, firstNow.notes, firstNow.revision]).toEqual([before.meeting_link, before.notes, before.revision]);
  const secondNow = (await (await request.get(`${API_URL}${second}`, { headers: auth })).json()) as { checklist: { text: string; done: boolean; origin: string }[]; questions: { text: string }[]; meeting_link: string | null; notes: string };
  const mine = secondNow.checklist.filter((c) => c.origin === "yours");
  expect(mine.map((c) => [c.text, c.done])).toEqual([["Print two copies of my registration", false], ["Plan the bus route", false]]);
  expect(secondNow.questions.map((q) => q.text)).toContain("How is the preceptorship structured?");
  expect([secondNow.meeting_link, secondNow.notes]).toEqual([null, ""]);
});
