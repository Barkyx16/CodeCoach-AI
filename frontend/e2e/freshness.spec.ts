import AxeBuilder from "@axe-core/playwright";

import { expect, setTheme, test } from "./fixtures";
import { API_URL } from "./ports";

/**
 * Records changed in another tab (Volume 11, prompt 9) against the real API, three tabs of one
 * synthetic account: tab A shows the story list (clean), tab B has the story open with unsaved
 * text, tab C renames and saves it. Tab A's list shows the new name without being touched; tab B
 * keeps its text and offers the real saved version to compare. Then tab C deletes it: tab B keeps
 * the text and offers Copy or a new story. Axe in both themes on tab B.
 */
test("a clean list updates at once while a dirty editor keeps its text and offers the saved version", async ({ page, context, request }) => {
  const email = `fr-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "registered-nurse" } });
  expect(reg.status()).toBe(201);
  const auth = { Authorization: `Bearer ${((await reg.json()) as { access_token: string }).access_token}` };
  const story = (await (await request.post(`${API_URL}/api/v1/me/stories`, { headers: auth, data: { title: "Two call lights", situation: "A busy night shift.", task: "Decide who to see first.", action: "I checked who was at higher risk.", result: "Both seen within five minutes." } })).json()) as { id: string };

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);

  const list = page;
  await list.goto("/stories");
  await expect(list.getByRole("link", { name: "Two call lights" })).toBeVisible();
  const dirty = await context.newPage();
  await dirty.goto(`/stories/${story.id}`);
  const situation = dirty.getByLabel("Situation");
  await situation.fill("My own words, not saved yet.");
  const other = await context.newPage();
  await other.goto(`/stories/${story.id}`);
  await other.getByLabel("Title").fill("Two call lights at once");
  await other.getByRole("button", { name: "Save changes" }).click();
  await expect(other.getByText("Saved as version 2.")).toBeVisible();

  // The clean list: the new name, without focus or a reload.
  await expect(list.getByRole("link", { name: "Two call lights at once" })).toBeVisible();
  // The dirty editor: its text kept, the real saved version offered.
  await expect(dirty.getByText(/This story was saved somewhere else \(version 2\) since you opened it\./)).toBeVisible();
  await expect(situation).toHaveValue("My own words, not saved yet.");
  await dirty.getByRole("button", { name: "Compare with the saved version" }).click();
  await expect(dirty.getByText("Two call lights at once")).toBeVisible();
  for (const theme of ["dark", "light"]) {
    await setTheme(dirty, theme);
    const scan = await new AxeBuilder({ page: dirty }).include(".story-editor").analyze();
    expect(scan.violations.map((v) => v.id), `editor, ${theme}`).toEqual([]);
  }

  // Deleted in the other tab: the text stays, with Copy or a new story; nothing recreates the old one.
  other.on("dialog", (d) => void d.accept());
  await other.getByRole("button", { name: "Delete…" }).click();
  await expect(other).toHaveURL(/\/stories$/);
  const alert = dirty.getByRole("alert").filter({ hasText: "This story was deleted" });
  await expect(alert).toBeVisible();
  await expect(dirty.getByRole("button", { name: "Keep mine as the newest version" })).toHaveCount(0); // the comparison is withdrawn
  await expect(situation).toHaveValue("My own words, not saved yet.");
  await expect(dirty.getByRole("button", { name: "Save changes" })).toBeDisabled();
  await expect(list.getByRole("link", { name: "Two call lights at once" })).toHaveCount(0);
  const gone = await request.get(`${API_URL}/api/v1/me/stories/${story.id}`, { headers: auth });
  expect(gone.status()).toBe(404);
  await alert.getByRole("button", { name: "Save it as a new story" }).click();
  await expect(dirty).not.toHaveURL(new RegExp(`/stories/${story.id}$`));
  const stories = (await (await request.get(`${API_URL}/api/v1/me/stories`, { headers: auth })).json()) as { id: string; title: string }[];
  expect(stories.map((s) => s.id)).not.toContain(story.id); // a new story, not the old one revived
  expect(stories).toHaveLength(1);
});
