import { readFile } from "node:fs/promises";

import AxeBuilder from "@axe-core/playwright";

import { expect, setTheme, test } from "./fixtures";
import { API_URL } from "./ports";

/**
 * A practice packet (Volume 11, prompt 8) against the real API: a bookmarked question with your
 * answer and its automated feedback, a note holding a phone number, an email and markup, and a
 * story, in the order chosen; the saved text file is what the preview showed (contact details
 * removed, markup as text); a note edited after previewing doesn't change the file until it's
 * previewed again. Axe in both themes. Synthetic account.
 */
test("choose, order, preview and save a packet that matches the preview", async ({ page, request }) => {
  const email = `pk-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "registered-nurse" } });
  expect(reg.status()).toBe(201);
  const auth = { Authorization: `Bearer ${((await reg.json()) as { access_token: string }).access_token}` };
  const q = ((await (await request.get(`${API_URL}/api/v1/careers/registered-nurse/questions?page_size=1`, { headers: auth })).json()) as { items: { id: string; title: string }[] }).items[0]!;
  await request.put(`${API_URL}/api/v1/me/bookmarks`, { headers: auth, data: { item_type: "question", track: "registered-nurse", ref_id: q.id } });
  const answered = await request.post(`${API_URL}/api/v1/careers/registered-nurse/questions/${q.id}/answers`, { headers: auth, data: {
    answer: "In my last role I owned patient assessment for five patients. I checked vital signs, escalated early to the charge nurse and documented everything, and as a result the patient was stable within an hour.",
  } });
  expect(answered.status()).toBe(201);
  const note = (await (await request.post(`${API_URL}/api/v1/me/notes`, { headers: auth, data: {
    title: "Handover notes", body: "Call 07700 900123 or mail ward7@example.com.\n<script>alert(1)</script> Use SBAR.",
  } })).json()) as { id: string; revision: number };
  await request.post(`${API_URL}/api/v1/me/stories`, { headers: auth, data: { title: "Two call lights", situation: "A busy night shift.", task: "Decide who to see first.", action: "I checked who was at higher risk.", result: "Both seen within five minutes." } });

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
  await page.goto("/packet");

  await page.getByRole("checkbox", { name: q.title }).check();
  await page.getByRole("checkbox", { name: "Handover notes" }).check();
  await page.getByRole("checkbox", { name: "Two call lights" }).check();
  await page.getByRole("button", { name: "Move up: Two call lights" }).click();
  const qParts = page.getByRole("group", { name: `Parts of ${q.title}` });
  await qParts.getByRole("checkbox", { name: "Your latest answer" }).check();
  await qParts.getByRole("checkbox", { name: "Automated feedback on it" }).check();
  await page.getByRole("button", { name: "Preview packet" }).click();

  const view = page.getByRole("article", { name: "Packet preview" });
  await expect(view).toContainText("Handover notes");
  await expect(view.getByRole("heading", { level: 3 })).toHaveText([`${q.title} (Question)`, "Two call lights (Your story)", "Handover notes (Your note)"]);
  await expect(view).toContainText("Not a grade from a person");
  await expect(view).not.toContainText("07700");
  await expect(view).not.toContainText("ward7@example.com");
  await expect(view).toContainText("<script>alert(1)</script> Use SBAR.");
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".packet-page").analyze();
    expect(scan.violations.map((v) => v.id), `packet, ${theme}`).toEqual([]);
  }

  // Edited after previewing: the file is still what was previewed.
  const edit = await request.patch(`${API_URL}/api/v1/me/notes/${note.id}`, { headers: auth, data: { body: "Edited after the preview.", base_revision: note.revision } });
  expect(edit.status()).toBe(200);
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Save as a text file" }).click()]);
  const text = await readFile((await download.path())!, "utf8");
  expect(download.suggestedFilename()).toMatch(/^my-practice-packet-\d{4}-\d{2}-\d{2}\.txt$/);
  expect(text).toContain("Use SBAR.");
  expect(text).not.toContain("Edited after the preview.");
  expect(text).not.toMatch(/07700|ward7@example\.com/);
  expect(text.indexOf(`1. ${q.title} (Question)`)).toBeLessThan(text.indexOf("2. Two call lights (Your story)"));
  expect(text).toContain("[Automated feedback]");
  // Previewing again picks up the edit, with a new fingerprint.
  const before = await view.getByText(/fingerprint/).textContent();
  await page.getByRole("button", { name: "Preview again" }).click();
  await expect(view).toContainText("Edited after the preview.");
  expect(await view.getByText(/fingerprint/).textContent()).not.toBe(before);
});
