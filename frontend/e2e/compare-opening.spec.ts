import AxeBuilder from "@axe-core/playwright";

import { expect, setTheme, test } from "./fixtures";
import { API_URL } from "./ports";

/**
 * When a sample-answer lesson's explanation was opened (Volume 19, prompt 5), against the real API:
 * opening it early records the opening on the account (one keyed request); a reading sent afterwards
 * says "Solution revealed" with the opening's time, not its own, on the reading, in the list and in
 * History, and the export carries the opening. axe finds nothing on the conditions in either theme.
 * Synthetic account.
 */
test("a reading sent after opening the explanation carries the opening's time", async ({ page, request }) => {
  const email = `cmp-open-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "customer-service-representative" } });
  expect(reg.status()).toBe(201);
  const auth = { Authorization: `Bearer ${((await reg.json()) as { access_token: string }).access_token}` };
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);

  await page.goto("/compare/cmp-relevance");
  await page.getByRole("button", { name: "Show the explanation now" }).click();
  const opening = page.waitForResponse((r) => r.request().method() === "POST" && r.url().endsWith("/me/comparisons/cmp-relevance/explanation"));
  await page.getByRole("button", { name: "Show the explanation", exact: true }).click();
  const opened = (await (await opening).json()) as { opened_at: string };
  const explanation = page.getByRole("region", { name: "The explanation", exact: true });
  await expect(explanation.getByRole("status")).toContainText("recorded on your account: a reading of this version you send now says the explanation was opened then.");

  await page.getByRole("list", { name: "Answer A, sentence by sentence" }).getByRole("listitem").nth(1).getByRole("button", { name: "Strength" }).click();
  await page.getByLabel("Why is it a strength?").fill("Gives a rule and the reason for it.");
  const sending = page.waitForResponse((r) => r.request().method() === "POST" && r.url().endsWith("/me/comparisons/cmp-relevance/attempts"));
  await page.getByRole("button", { name: "Compare with the explanation" }).click();
  const reading = (await (await sending).json()) as { id: string; created_at: string };
  expect(Date.parse(reading.created_at)).toBeGreaterThan(Date.parse(opened.opened_at));

  // On the reading: the opening's time, not the reading's.
  const result = page.locator("section", { has: page.locator("#cmp-result") });
  const help = result.locator(".attempt-conditions li").filter({ hasText: "Solution revealed: The explanation was opened before this was sent" });
  await expect(help).toHaveCount(1);
  expect(Date.parse((await help.locator("time").getAttribute("datetime"))!)).toBe(Date.parse(opened.opened_at));

  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".attempt-conditions").analyze();
    expect(scan.violations.map((v) => v.id), theme).toEqual([]);
  }

  // The same words in the list, History's conditions and the export.
  const mine = (await (await request.get(`${API_URL}/api/v1/me/comparisons/cmp-relevance/attempts`, { headers: auth })).json()) as { id: string; conditions: { help: { label: string; at: string }[] } }[];
  const listed = mine.find((r) => r.id === reading.id)!;
  expect(listed.conditions.help.map((h) => [h.label, Date.parse(h.at)])).toEqual([["Solution revealed", Date.parse(opened.opened_at)]]);
  await expect(page.getByRole("region", { name: "Your earlier readings" })).toContainText("In-app help: Solution revealed");
  await page.goto("/history");
  await expect(page.locator("a", { hasText: "matching the explanation" }).first()).toContainText("In-app help: Solution revealed");
  const doc = (await (await request.get(`${API_URL}/api/v1/me/export`, { headers: auth })).json()) as { comparison_openings: { lesson: string; at: string }[] };
  expect(doc.comparison_openings.map((o) => [o.lesson, Date.parse(o.at)])).toEqual([["cmp-relevance", Date.parse(opened.opened_at)]]);

});
