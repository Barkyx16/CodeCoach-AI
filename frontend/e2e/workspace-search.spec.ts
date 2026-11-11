import AxeBuilder from "@axe-core/playwright";

import { expect, test, setTheme } from "./fixtures";
import { API_URL } from "./ports";

/**
 * Search your saved work (Volume 11, prompt 3) in a real browser against the real API: Ada finds
 * her saved story and private note while Bea's note with the same words stays invisible in results,
 * counts and snippets; the words never appear in an address; keyboard only; Back from a result
 * restores the search; no accessibility violations in either theme. Synthetic accounts.
 */
test("find a saved story and a private note; another account's matching text stays invisible", async ({ page, request }) => {
  const stamp = `${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
  const account = async (who: string) => {
    const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email: `ws-${who}-${stamp}@example.com`, password: "CorrectHorse42", career_track: "registered-nurse" } });
    expect(reg.status()).toBe(201);
    return { Authorization: `Bearer ${((await reg.json()) as { access_token: string }).access_token}` };
  };
  const ada = await account("ada");
  const bea = await account("bea");
  expect((await request.post(`${API_URL}/api/v1/me/stories`, { headers: ada, data: { title: "Handover under pressure", situation: "A night shift with a sepsis alert", task: "t", action: "a", result: "r" } })).status()).toBe(201);
  expect((await request.post(`${API_URL}/api/v1/me/notes`, { headers: ada, data: { title: "Ward notes", body: "Sepsis bundle: lactate, cultures, antibiotics within the hour." } })).status()).toBe(201);
  expect((await request.post(`${API_URL}/api/v1/me/notes`, { headers: bea, data: { title: "BEA-ONLY sepsis note", body: "sepsis BEA-PRIVATE-4417" } })).status()).toBe(201);

  await page.goto("/login");
  await page.getByLabel("Email").fill(`ws-ada-${stamp}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
  const sent: string[] = [];
  page.on("request", (r) => { if (r.url().startsWith(API_URL)) sent.push(`${r.method()} ${r.url()}`); });
  await page.goto("/search");

  const box = page.getByLabel("Words to find");
  await box.focus();
  await page.keyboard.type("sepsis");
  const results = page.getByRole("region", { name: "Results" });
  await expect(results.getByRole("status")).toHaveText("2 found: 1 note, 1 story.");
  await expect(results.getByRole("link")).toHaveCount(2);
  await expect(results).not.toContainText("BEA");
  await expect(results.locator("mark").first()).toHaveText(/sepsis/i);
  expect(sent.filter((s) => s.includes("sepsis"))).toEqual([]); // the words are never in an address
  expect(page.url()).not.toContain("sepsis");

  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".workspace-search").analyze();
    expect(scan.violations.map((v) => v.id), theme).toEqual([]);
  }

  // Bea's exact words find nothing for Ada.
  await box.fill("BEA-PRIVATE-4417");
  await expect(results.getByRole("status")).toHaveText("Nothing saved to your account matches those words.");

  // Keyboard: open the story, then come back to the same search.
  await box.fill("sepsis handover");
  await expect(results.getByRole("link")).toHaveCount(1);
  await results.getByRole("link", { name: /Handover under pressure/ }).focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/stories\/[0-9a-f-]{36}$/);
  await expect(page.getByLabel("Title")).toHaveValue("Handover under pressure");
  await page.goBack();
  await expect(page).toHaveURL(/\/search$/);
  await expect(page.getByLabel("Words to find")).toHaveValue("sepsis handover");
  await expect(page.getByRole("region", { name: "Results" }).getByRole("link", { name: /Handover under pressure/ })).toBeVisible();
});
