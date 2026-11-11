import AxeBuilder from "@axe-core/playwright";

import { expect, setTheme, test } from "./fixtures";
import { API_URL } from "./ports";

/**
 * Archive as a presentation lifecycle (Volume 11, prompt 4) against the real API: an offer
 * comparison archived by keyboard leaves the active list and "Continue your work", stays findable
 * under Archived with its content, and is restored unchanged; an application with an interview still
 * to come asks first and keeps its stage. Axe in both themes. Synthetic account.
 */
test("archive and restore a comparison; an application with an interview coming asks first", async ({ page, request }) => {
  const email = `ar-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "registered-nurse" } });
  expect(reg.status()).toBe(201);
  const auth = { Authorization: `Bearer ${((await reg.json()) as { access_token: string }).access_token}` };
  const comp = (await (await request.post(`${API_URL}/api/v1/me/offer-comparisons`, { headers: auth, data: { example: true } })).json()) as { id: string; revision: number; doc: { title: string } };
  const app = (await (await request.post(`${API_URL}/api/v1/me/applications`, { headers: auth, data: { employer: "Northfield", role_title: "Ward nurse", stage: "interviewing" } })).json()) as { id: string };
  const soon = new Date(Date.now() + 10 * 86_400_000).toISOString().slice(0, 10);
  expect((await request.post(`${API_URL}/api/v1/me/applications/${app.id}/events`, { headers: auth, data: { title: "Panel interview", on_date: soon } })).status()).toBe(200);

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);

  await page.goto("/offers/compare");
  await expect(page.getByRole("button", { name: "Active (1)" })).toBeVisible();
  const archive = page.getByRole("button", { name: `Archive: ${comp.doc.title}` });
  await archive.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByText(/archived\. It's under Archived; nothing was deleted\./)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your comparisons" })).toBeFocused(); // the last one went
  await expect(page.getByRole("button", { name: "Archived (1)" })).toBeVisible();

  await page.goto("/dashboard");
  const recent = page.getByRole("region", { name: "Continue your work" }).getByRole("group", { name: "Saved to your account" });
  await expect(recent).toContainText("Ward nurse at Northfield");
  await expect(recent).not.toContainText(comp.doc.title); // archived: not in an active view

  await page.goto("/offers/compare?archived=1");
  await expect(page.getByRole("heading", { name: "Archived comparisons" })).toBeVisible();
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".oc-list").analyze();
    expect(scan.violations.map((v) => v.id), theme).toEqual([]);
  }
  await page.getByRole("link", { name: comp.doc.title }).click();
  await expect(page.getByText(/Archived: it's out of your active list, kept exactly as it is\./)).toBeVisible();
  await page.getByRole("button", { name: "Restore" }).click();
  await expect(page.getByText(/Archived: it's out of your active list/)).toHaveCount(0);
  const after = (await (await request.get(`${API_URL}/api/v1/me/offer-comparisons/${comp.id}`, { headers: auth })).json()) as { revision: number; archived: boolean; doc: unknown };
  expect([after.revision, after.archived]).toEqual([comp.revision, false]); // the same comparison, unchanged

  await page.goto(`/applications/${app.id}`);
  await page.getByRole("button", { name: "Archive", exact: true }).click();
  const ask = page.getByRole("group", { name: "Archive with an interview coming up" });
  await expect(ask).toContainText("It doesn't cancel the interview or change the stage");
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".application-page").analyze();
    expect(scan.violations.map((v) => v.id), `application, ${theme}`).toEqual([]);
  }
  await ask.getByRole("button", { name: "Archive anyway" }).click();
  await expect(page.getByText(/APPLICATION · ARCHIVED/)).toBeVisible();
  const archived = (await (await request.get(`${API_URL}/api/v1/me/applications/${app.id}`, { headers: auth })).json()) as { stage: string; archived: boolean };
  expect([archived.stage, archived.archived]).toEqual(["interviewing", true]);
});
