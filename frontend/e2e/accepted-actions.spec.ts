import AxeBuilder from "@axe-core/playwright";

import { expect, setTheme, test } from "./fixtures";
import { API_URL } from "./ports";

/**
 * One accepted improvement, one action (Volume 12, prompt 1) against the real API: a nurse accepts an
 * improvement from a finished round as a weekly action, a second tab shows it already accepted,
 * the plan schedules two weeks, the schedule marks the first week done, the kit's checklist adds the
 * same action, and after reloads and in the second tab every view agrees: one action, two schedule
 * entries, week one done, week two open; a second device signed in on its own agrees. Axe in both
 * themes on the plan and the kit. Synthetic data.
 */
const STRONG =
  "Last winter, while I was working nights, a patient's oxygen dropped during my 2 a.m. patient assessment. " +
  "I was responsible for five patients, so I moved fast. I checked his vital signs again and started oxygen " +
  "per protocol. I called the rapid response team and asked the charge nurse to cover my other patients. I " +
  "updated the doctor and documented everything. As a result, he was stable within 30 minutes, and I learned to escalate early.";
const WEAK = "We handled it together as a team and it was fine in the end, we all did well.";

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

test("an accepted improvement is the same action on the plan, the schedule and a kit", async ({ page, context, browser, request }) => {
  const email = `aa-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "registered-nurse" } });
  expect(reg.status()).toBe(201);
  const auth = { Authorization: `Bearer ${((await reg.json()) as { access_token: string }).access_token}` };
  const iv = ((await (await request.post(`${API_URL}/api/v1/interviews`, { headers: auth, data: { kind: "questions" } })).json()) as { id: string }).id;
  for (const [i, answer] of [STRONG, WEAK, WEAK, STRONG, WEAK].entries()) {
    const r = await request.post(`${API_URL}/api/v1/interviews/${iv}/answers`, { headers: auth, data: { question_index: i, answer, source: "typed" } });
    expect(r.status()).toBeLessThan(300);
  }
  const review = (await (await request.get(`${API_URL}/api/v1/interviews/${iv}/review`, { headers: auth })).json()) as { improvements: { title: string }[] };
  const title = review.improvements[0]!.title;
  const app = (await (await request.post(`${API_URL}/api/v1/me/applications`, { headers: auth, data: { employer: "Mercy General", role_title: "Ward nurse" } })).json()) as { id: string };
  const later = new Date(Date.now() + 10 * 86_400_000);
  const ev = ((await (await request.post(`${API_URL}/api/v1/me/applications/${app.id}/events`, {
    headers: auth, data: { title: "Panel interview", on_date: iso(later), local_time: "10:00", timezone: "Europe/London" },
  })).json()) as { events: { id: string }[] }).events[0]!;

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);

  // Accept it from the replay, as a weekly practice.
  await page.goto(`/interviews/${iv}`);
  const item = page.getByRole("listitem").filter({ has: page.getByRole("button", { name: `Accept as an action: ${title}` }) });
  await item.getByRole("checkbox", { name: "Every week" }).check();
  await item.getByRole("button", { name: `Accept as an action: ${title}` }).click();
  await expect(page.getByText(/Accepted as an action\./)).toBeVisible();
  // A second tab: already accepted, nothing to accept again.
  const second = await context.newPage();
  await second.goto(`/interviews/${iv}`);
  await expect(second.getByText(/Accepted as an action\./)).toBeVisible();
  await expect(second.getByRole("button", { name: `Accept as an action: ${title}` })).toHaveCount(0);

  // The plan schedules two weeks.
  const first = new Date(Date.now() + 86_400_000);
  await page.goto("/plan");
  const section = page.getByRole("region", { name: "Improvements you accepted (1)" });
  await expect(section.getByRole("heading", { name: new RegExp(title.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) })).toBeVisible();
  await section.getByRole("button", { name: "Add weeks to your schedule" }).click();
  await section.getByLabel("First week, on").fill(iso(first));
  await section.getByLabel("For how many weeks").selectOption("2");
  await section.getByRole("button", { name: "Add to schedule" }).click();
  await expect(section.getByRole("checkbox", { name: /^Week of/ })).toHaveCount(2);

  // The schedule marks the first week done.
  await page.goto(`/schedule?week=${iso(first)}`);
  await expect(page.getByText("Accepted improvement").first()).toBeVisible();
  await page.getByRole("button", { name: `Mark done: ${title}` }).first().click();
  await expect(page.getByRole("button", { name: `Mark not done: ${title}` }).first()).toBeVisible();

  // The kit's checklist takes the same action, by id.
  await page.goto(`/applications/${app.id}/events/${ev.id}/kit`);
  await page.getByLabel("Add an improvement you accepted").selectOption({ label: title });
  await page.getByRole("button", { name: "Add to checklist" }).click();
  await page.getByRole("button", { name: "Save kit" }).click();
  await expect(page.getByText("Saved.")).toBeVisible();
  await page.reload();
  await expect(page.getByText(`${title} · 1 of 2 weeks done`)).toBeVisible();
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include("main").analyze();
    expect(scan.violations.map((v) => v.id), `kit, ${theme}`).toEqual([]);
  }

  // The second tab, reloaded: the plan says the same.
  await second.goto("/plan");
  const weeks = second.getByRole("region", { name: "Improvements you accepted (1)" }).getByRole("checkbox", { name: /^Week of/ });
  await expect(weeks.nth(0)).toBeChecked();
  await expect(weeks.nth(1)).not.toBeChecked();
  for (const theme of ["dark", "light"]) {
    await setTheme(second, theme);
    const scan = await new AxeBuilder({ page: second }).include(".plan-page").analyze();
    expect(scan.violations.map((v) => v.id), `plan, ${theme}`).toEqual([]);
  }

  // A second device (its own browser, signed in on its own): the schedule and the kit say the same.
  const device = await browser.newContext();
  const phone = await device.newPage();
  await phone.goto("/login");
  await phone.getByLabel("Email").fill(email);
  await phone.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await phone.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(phone).not.toHaveURL(/\/login$/);
  await phone.goto(`/schedule?week=${iso(first)}`);
  await expect(phone.getByRole("button", { name: `Mark not done: ${title}` }).first()).toBeVisible();
  await phone.goto(`/applications/${app.id}/events/${ev.id}/kit`);
  await expect(phone.getByText(`${title} · 1 of 2 weeks done`)).toBeVisible();
  await device.close();

  // And the server holds one action with two occurrences.
  const actions = (await (await request.get(`${API_URL}/api/v1/me/actions`, { headers: auth })).json()) as { occurrences: { completed_at: string | null }[] }[];
  expect(actions).toHaveLength(1);
  expect(actions[0]!.occurrences.map((o) => o.completed_at !== null)).toEqual([true, false]);
});
