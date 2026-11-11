import AxeBuilder from "@axe-core/playwright";

import { expect, test } from "./fixtures";
import { API_URL } from "./ports";

/**
 * Home shortcuts (Volume 11, prompt 2) in a real browser against the real API: the defaults, add
 * and reorder by keyboard with focus kept, a reload keeping the order, a shortcut opening its page
 * and Back coming home, nothing sent to the account by arranging them, a career change leaving a
 * page understandable instead of a dead link, and no accessibility violations in either theme.
 * Synthetic account.
 */
test("arrange shortcuts by keyboard, keep them through a reload, and open one", async ({ page, request }) => {
  const email = `sc-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "software-engineer" } });
  expect(reg.status()).toBe(201);
  const { access_token: token } = (await reg.json()) as { access_token: string };
  const auth = { Authorization: `Bearer ${token}` };

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
  await page.goto("/dashboard");

  const card = page.getByRole("region", { name: "Your shortcuts" });
  const labels = () => card.locator(".shortcut__label, .shortcut-edit__name strong").allTextContents();
  await expect(card.getByRole("link")).toHaveCount(5);
  expect(await labels()).toEqual(["Coding problems", "Notes", "Stories", "Applications", "My plan"]);

  // From here on, nothing but reads may reach the API.
  const sent: string[] = [];
  page.on("request", (r) => {
    if (r.url().startsWith(API_URL) && r.method() !== "GET" && !r.url().endsWith("/auth/refresh")) sent.push(`${r.method()} ${r.url()}`);
  });

  await card.getByRole("button", { name: "Edit shortcuts" }).focus();
  await page.keyboard.press("Enter");
  await card.getByLabel("Add a shortcut").selectOption({ label: "Whiteboard: explain a design" });
  await card.getByRole("button", { name: "Add" }).focus();
  await page.keyboard.press("Enter");
  await expect(card.getByRole("status")).toHaveText("Whiteboard: explain a design added as shortcut 6 of 6.");
  const up = card.getByRole("button", { name: "Move up: Whiteboard: explain a design" });
  await up.focus();
  for (let i = 0; i < 4; i += 1) await page.keyboard.press("Enter");
  await expect(card.getByRole("status")).toHaveText("Whiteboard: explain a design moved to position 2 of 6.");
  await expect(up).toBeFocused();

  for (const theme of ["dark", "light"]) {
    await page.evaluate((t) => document.documentElement.setAttribute("data-theme", t), theme);
    const scan = await new AxeBuilder({ page }).include(".shortcuts").analyze();
    expect(scan.violations.map((v) => v.id), `editing, ${theme}`).toEqual([]);
  }
  await card.getByRole("button", { name: "Done" }).click();
  await expect(card.getByRole("button", { name: "Edit shortcuts" })).toBeFocused();

  await page.reload();
  await expect(card.getByRole("link")).toHaveCount(6);
  expect(await labels()).toEqual(["Coding problems", "Whiteboard: explain a design", "Notes", "Stories", "Applications", "My plan"]);
  for (const theme of ["dark", "light"]) {
    await page.evaluate((t) => document.documentElement.setAttribute("data-theme", t), theme);
    const scan = await new AxeBuilder({ page }).include(".shortcuts").analyze();
    expect(scan.violations.map((v) => v.id), `list, ${theme}`).toEqual([]);
  }

  await card.getByRole("link", { name: /Notes/ }).click();
  await expect(page).toHaveURL(/\/notes$/);
  await page.goBack();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("region", { name: "Your shortcuts" })).toBeVisible();
  expect(sent).toEqual([]); // arranging and opening shortcuts sent nothing

  // The career changes (here through the API, as Settings would): the whiteboard isn't part of it.
  expect((await request.patch(`${API_URL}/api/v1/auth/me`, { headers: auth, data: { career_track: "registered-nurse" } })).status()).toBe(200);
  await page.reload();
  await expect(card).toContainText("Not part of Registered Nurse practice.");
  await expect(card.getByRole("link", { name: /Whiteboard/ })).toHaveCount(0);
  await expect(card.getByRole("link", { name: /Interview questions/ })).toHaveAttribute("href", "/problems");
  const me = (await (await request.get(`${API_URL}/api/v1/auth/me`, { headers: auth })).json()) as { career_track: string };
  expect(me.career_track).toBe("registered-nurse"); // only the change made on purpose
});
