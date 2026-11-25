import { expect, test, type Page } from "./fixtures";
import { API_URL } from "./ports";

/**
 * The explanation shown with a reading's own result counts as seen (Volume 20, prompt 3), against the
 * real API: two readings of one lesson, with the explanation never opened on its own. The first
 * reading's help is none; its result shows the explanation; the second reading says "Solution
 * revealed: The explanation was shown with an earlier reading's result before this was sent" with the
 * first reading's time, on the reading and in the export. Synthetic account.
 */
async function reading(page: Page) {
  await page.goto("/compare/cmp-relevance");
  await page.getByRole("list", { name: "Answer A, sentence by sentence" }).getByRole("listitem").nth(1).getByRole("button", { name: "Strength" }).click();
  await page.getByLabel("Why is it a strength?").fill("Gives a rule and the reason for it.");
  const sending = page.waitForResponse((r) => r.request().method() === "POST" && r.url().endsWith("/me/comparisons/cmp-relevance/attempts"));
  await page.getByRole("button", { name: "Compare with the explanation" }).click();
  const sent = (await (await sending).json()) as { id: string; created_at: string; explanation: unknown };
  return { sent, result: page.locator("section", { has: page.locator("#cmp-result") }) };
}

test("a second reading says the explanation was seen with the first one's result, at its time", async ({ page, request }) => {
  const email = `cmp-shown-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "customer-service-representative" } });
  expect(reg.status()).toBe(201);
  const auth = { Authorization: `Bearer ${((await reg.json()) as { access_token: string }).access_token}` };
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);

  const first = await reading(page);
  await expect(first.result.locator(".attempt-conditions")).toContainText("No in-app help recorded");
  await expect(page.locator("#cmp-result")).toBeVisible(); // its result, with the explanation in it
  expect(first.sent.explanation).toBeTruthy();

  const second = await reading(page);
  const help = second.result.locator(".attempt-conditions li").filter({ hasText: "Solution revealed: The explanation was shown with an earlier reading's result before this was sent" });
  await expect(help).toHaveCount(1);
  expect(Date.parse((await help.locator("time").getAttribute("datetime"))!)).toBe(Date.parse(first.sent.created_at));

  const doc = (await (await request.get(`${API_URL}/api/v1/me/export`, { headers: auth })).json()) as { comparison_openings: { lesson: string; at: string; source: string }[] };
  expect(doc.comparison_openings.map((o) => [o.lesson, o.source, Date.parse(o.at)])).toEqual([["cmp-relevance", "with_result", Date.parse(first.sent.created_at)]]);
});
