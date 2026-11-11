import AxeBuilder from "@axe-core/playwright";

import { expect, test } from "./fixtures";
import { API_URL } from "./ports";

/**
 * "Continue your work" (Volume 11, prompt 1) against the real API: saved records with honest times,
 * a finished interview opening its results, an earlier uncertain action checked (read-only) and
 * opened, Back returning to the dashboard, and no accessibility violations in either theme.
 * Synthetic account.
 */
test("continue a saved story, check an earlier action, and come back", async ({ page, request }) => {
  const email = `cw-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "registered-nurse" } });
  expect(reg.status()).toBe(201);
  const { access_token: token, user } = (await reg.json()) as { access_token: string; user: { id: string } };
  const auth = { Authorization: `Bearer ${token}` };
  expect((await request.post(`${API_URL}/api/v1/me/notes`, { headers: auth, data: { title: "Sepsis signs (synthetic)", body: "x" } })).status()).toBe(201);
  // A story whose reply "never came": the server made it under this key; this browser kept the record.
  const key = `cw-story-${Date.now()}`;
  const story = { title: "Night shift handover (synthetic)", situation: "A busy ward", task: "t", action: "a", result: "r", client_request_id: key };
  expect((await request.post(`${API_URL}/api/v1/me/stories`, { headers: auth, data: story })).status()).toBe(201);
  const round = await request.post(`${API_URL}/api/v1/interviews`, { headers: auth, data: { kind: "questions" } });
  const roundId = ((await round.json()) as { id: string }).id;
  expect((await request.post(`${API_URL}/api/v1/interviews/${roundId}/abandon`, { headers: auth })).status()).toBe(200);

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
  await page.evaluate(([id, k]) => {
    localStorage.setItem(`codecoach.pending.v1.${id}`, JSON.stringify({ "story:new": { v: 1, kind: "story", target: "new", key: k, fingerprint: "synthetic", sentAt: Date.now() } }));
  }, [user.id, key]);
  await page.goto("/dashboard");

  const section = page.getByRole("region", { name: "Continue your work" });
  const saved = section.getByRole("group", { name: "Saved to your account" });
  await expect(saved.getByRole("link", { name: /Sepsis signs \(synthetic\)/ })).toContainText(/Note · saved .* · Open/);
  await expect(saved.getByRole("link", { name: /question round/ })).toContainText(/ended early · finished .* · See results/);
  await expect(saved.getByRole("link", { name: /question round/ })).toHaveAttribute("href", `/interviews/${roundId}`);

  for (const theme of ["dark", "light"]) {
    await page.evaluate((t) => document.documentElement.setAttribute("data-theme", t), theme);
    const scan = await new AxeBuilder({ page }).include(".continue-card").analyze();
    expect(scan.violations.map((v) => v.id), theme).toEqual([]);
  }

  const waiting = section.getByRole("group", { name: "Waiting for a reply" });
  await waiting.getByRole("button", { name: "Check result" }).click();
  await expect(waiting).toContainText("It arrived.");
  await waiting.getByRole("link", { name: "Open the story" }).click();
  await expect(page.getByLabel("Title")).toHaveValue("Night shift handover (synthetic)");
  await page.goBack();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("region", { name: "Continue your work" })).toBeVisible();
  // Checked once: the record is done with, and nothing was sent again (still one story).
  const stories = await request.get(`${API_URL}/api/v1/me/stories`, { headers: auth });
  const list = (await stories.json()) as unknown;
  const count = Array.isArray(list) ? list.length : (list as { items: unknown[] }).items.length;
  expect(count).toBe(1);
});
