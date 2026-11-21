import { writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import AxeBuilder from "@axe-core/playwright";

import { expect, setTheme, test } from "./fixtures";
import { API_URL } from "./ports";

/**
 * Which questions were saved for review comes back from a backup file, each starting afresh (Volume
 * 20, prompt 1), against the real API: one account saves two questions; its real backup file, edited
 * as a file could be to claim each ladder well along (step 4, 7 reviews, a perfect score), is restored
 * on a fresh account through the page, whose preview says what isn't restored; the queue then lists
 * both as new (first due a day from now), and removing the restore takes them away again. axe finds
 * nothing on the preview in either theme. Synthetic accounts only.
 */
type QueueItem = { id: string; title: string; due_at: string; due: boolean; interval_days: number; reviews: number; last_score: number | null };
type Queue = { due: QueueItem[]; upcoming: QueueItem[]; disputed: QueueItem[] };
const listed = (q: Queue) => [...q.due, ...q.upcoming, ...q.disputed];

async function account(request: import("@playwright/test").APIRequestContext, tag: string) {
  const email = `${tag}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "registered-nurse" } });
  expect(reg.status()).toBe(201);
  return { email, auth: { Authorization: `Bearer ${((await reg.json()) as { access_token: string }).access_token}` } };
}

test("saved questions restored on a fresh account start afresh, and the restore can be removed", async ({ page, request }) => {
  const a = await account(request, "rq-source");
  const qs = ((await (await request.get(`${API_URL}/api/v1/careers/registered-nurse/questions?page_size=2`, { headers: a.auth })).json()) as { items: { id: string; title: string }[] }).items;
  for (const q of qs) {
    expect((await request.post(`${API_URL}/api/v1/me/reviews`, { headers: a.auth, data: { track: "registered-nurse", question_id: q.id } })).status()).toBeLessThan(300);
  }
  // The source account's file, as its Settings would download it.
  const file = join(tmpdir(), `review-queue-${Date.now()}.json`);
  const exported = (await (await request.get(`${API_URL}/api/v1/me/export`, { headers: a.auth })).json()) as { review_queue: { question: string; step: number }[] };
  expect(exported.review_queue.map((r) => r.question).sort()).toEqual(qs.map((q) => q.id).sort());
  // Edited as a file could be: a ladder well along. The restore must take none of it.
  for (const r of exported.review_queue) Object.assign(r, { step: 4, reviews: 7, last_score: 100, due_at: "2026-01-01T00:00:00+00:00" });
  writeFileSync(file, JSON.stringify(exported));

  const b = await account(request, "rq-restored");
  await page.goto("/login");
  await page.getByLabel("Email").fill(b.email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
  await page.goto("/settings/restore");
  await page.getByLabel("Backup file").setInputFiles(file);
  const pv = page.getByRole("region", { name: "2. Check what would be added" });
  const box = pv.getByRole("checkbox", { name: "Questions saved for review, each starting afresh: 2 new" });
  await expect(box).toBeChecked();
  await expect(pv).toContainText("Ladders, due dates, scores, review counts and the points each was saved for aren't restored");
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".restore-preview").analyze();
    expect(scan.violations.map((v) => v.id), theme).toEqual([]);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await expect(pv.getByRole("checkbox", { checked: true })).toHaveCount(1); // the file holds nothing else new
  await pv.getByRole("button", { name: "Restore questions saved for review" }).click();
  await expect(page.getByText("Restored: 2 questions saved for review.")).toBeVisible();

  // The queue: both, each new.
  const queue = (await (await request.get(`${API_URL}/api/v1/me/reviews`, { headers: b.auth })).json()) as Queue;
  const items = listed(queue);
  expect(items.map((i) => i.title).sort()).toEqual(qs.map((q) => q.title).sort());
  const tomorrow = Date.now() + 24 * 3600 * 1000;
  for (const i of items) {
    // The ladder's first rung, no reviews and no score: none of what the edited file claimed.
    expect({ interval: i.interval_days, reviews: i.reviews, score: i.last_score }).toEqual({ interval: 1, reviews: 0, score: null });
    expect(i.due).toBe(false);
    expect(Math.abs(new Date(i.due_at).getTime() - tomorrow)).toBeLessThan(10 * 60 * 1000); // first rung: a day from now
  }
  await page.goto("/reviews");
  for (const q of qs) await expect(page.getByRole("listitem", { name: q.title })).toBeVisible();

  // Removing the restore takes both away (neither changed since).
  await page.goto("/settings/restore");
  page.once("dialog", (d) => void d.accept());
  await page.getByRole("button", { name: "Remove what this added" }).click();
  await expect(page.getByText(/Removed 2; kept 0 you'd changed since; 0 were already gone\./)).toBeVisible();
  expect(listed((await (await request.get(`${API_URL}/api/v1/me/reviews`, { headers: b.auth })).json()) as Queue)).toEqual([]);
});
