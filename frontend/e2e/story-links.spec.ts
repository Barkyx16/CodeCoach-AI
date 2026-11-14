import AxeBuilder from "@axe-core/playwright";

import { expect, setTheme, test } from "./fixtures";
import { API_URL } from "./ports";

/**
 * Where a story is used (Volume 11, prompt 6) against the real API: a story linked to an
 * application by keyboard, chosen in that interview's kit; from the story, "Where it's used" finds
 * the kit, opens it, and "Back to your story" returns. Nothing is copied: there's still one story.
 * Axe in both themes on both pages. Synthetic account.
 */
test("find which interview kit uses a story, open it, and come back", async ({ page, request }) => {
  const email = `sl-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "registered-nurse" } });
  expect(reg.status()).toBe(201);
  const auth = { Authorization: `Bearer ${((await reg.json()) as { access_token: string }).access_token}` };
  const story = (await (await request.post(`${API_URL}/api/v1/me/stories`, { headers: auth, data: { title: "Two call lights at once", situation: "A busy night shift." } })).json()) as { id: string };
  await request.post(`${API_URL}/api/v1/me/stories`, { headers: auth, data: { title: "Night handover" } });
  const app = (await (await request.post(`${API_URL}/api/v1/me/applications`, { headers: auth, data: { employer: "Mercy General", role_title: "Ward nurse", stage: "interviewing" } })).json()) as { id: string };
  const withEvent = (await (await request.post(`${API_URL}/api/v1/me/applications/${app.id}/events`, { headers: auth, data: { title: "Panel interview", on_date: "2026-12-03" } })).json()) as { events: { id: string }[] };
  const eventId = withEvent.events[0]!.id;

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);

  // Link it from the application, by keyboard.
  await page.goto(`/applications/${app.id}`);
  const box = page.getByRole("checkbox", { name: /Two call lights at once/ });
  await box.focus();
  await page.keyboard.press("Space");
  await expect(page.getByText(/Linked \(1\):/)).toBeVisible();
  await expect(box).toBeChecked();
  await expect(box).toBeFocused();
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".application-page").analyze();
    expect(scan.violations.map((v) => v.id), `application, ${theme}`).toEqual([]);
  }

  // Choose it in the interview's kit (as the kit page saves it).
  const kit = await request.put(`${API_URL}/api/v1/me/applications/${app.id}/events/${eventId}/kit`, { headers: auth, data: { story_ids: [story.id] } });
  expect(kit.status()).toBe(200);

  // From the story: where it's used.
  await page.goto(`/stories/${story.id}`);
  const kits = page.getByRole("region", { name: "Interview kits (1)" });
  await expect(kits).toContainText("Panel interview");
  await expect(page.getByRole("region", { name: "Applications (1)" })).toContainText("Ward nurse at Mercy General");
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".used-in").analyze();
    expect(scan.violations.map((v) => v.id), `story, ${theme}`).toEqual([]);
  }
  await kits.getByRole("link", { name: "Panel interview" }).click();
  await expect(page).toHaveURL(new RegExp(`/applications/${app.id}/events/${eventId}/kit$`));
  await expect(page.getByRole("link", { name: "Two call lights at once" })).toBeVisible(); // the kit shows the story
  await page.getByRole("link", { name: "Back to your story" }).click();
  await expect(page).toHaveURL(new RegExp(`/stories/${story.id}$`));
  await expect(page.getByRole("heading", { name: "Where it's used" })).toBeVisible();

  // Nothing was copied: still two stories, and the application lists this one once.
  const stories = (await (await request.get(`${API_URL}/api/v1/me/stories`, { headers: auth })).json()) as unknown[];
  expect(stories).toHaveLength(2);
  const linked = (await (await request.get(`${API_URL}/api/v1/me/applications/${app.id}`, { headers: auth })).json()) as { stories: { id: string }[] };
  expect(linked.stories.map((s) => s.id)).toEqual([story.id]);
});
