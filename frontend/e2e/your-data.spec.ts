import AxeBuilder from "@axe-core/playwright";

import { expect, test, setTheme } from "./fixtures";
import { API_URL } from "./ports";

/**
 * "Your data" (Volume 10, prompt 10) against the real API: a story saved to the account and an
 * answer kept only on this device are told apart; removing the device copy leaves the saved story,
 * the sign-in and the device settings; counts come from the server; no accessibility violations in
 * either theme. Synthetic account.
 */
test("a device-only draft is told from an account save and removed without losing the save", async ({ page, request }) => {
  const email = `yd-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "registered-nurse" } });
  expect(reg.status()).toBe(201);
  const { access_token: token, user } = (await reg.json()) as { access_token: string; user: { id: string } };
  const story = { title: "Night shift handover (synthetic)", situation: "A busy ward", task: "Hand over", action: "Used a checklist", result: "Nothing missed" };
  expect((await request.post(`${API_URL}/api/v1/me/stories`, { data: story, headers: { Authorization: `Bearer ${token}` } })).status()).toBe(201);

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
  await page.evaluate((id) => {
    localStorage.setItem(`codecoach.answer.${id}.registered-nurse.m-walk-0`, "An unsent answer kept only in this browser");
    localStorage.setItem("codecoach.display.v1", JSON.stringify({ theme: "dark" }));
  }, user.id);

  await page.goto("/settings");
  await page.getByRole("link", { name: "See your data" }).click();
  await expect(page).toHaveURL(/\/settings\/data$/);
  const device = page.getByRole("region", { name: "On this device" });
  await expect(device.getByRole("heading", { name: "Not sent yet: only on this device" })).toBeVisible();
  await expect(device).toContainText("Written answer, not sent");
  const account = page.getByRole("region", { name: "Saved to your account" });
  await expect(account).toContainText("Stories, with their earlier versions");

  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".yd-page").analyze();
    expect(scan.violations.map((v) => v.id), theme).toEqual([]);
  }

  await device.getByRole("checkbox", { name: /Written answer, not sent/ }).check();
  await page.getByRole("button", { name: "Review removal (1)" }).click();
  await expect(page.getByRole("region", { name: "Before you remove this" })).toContainText("it was never sent");
  await page.getByRole("button", { name: "Remove it from this device" }).click();
  await expect(page.getByText("Removed 1 item from this browser. Everything saved to your account is unchanged.")).toBeFocused();
  await expect(device).toContainText("Nothing of this account's is waiting on this device.");
  expect(await page.evaluate(() => localStorage.getItem("codecoach.display.v1"))).toContain("dark");

  await page.reload(); // still signed in, and the saved story is still there
  await expect(page.getByRole("heading", { name: "Your data" })).toBeVisible();
  await page.goto("/stories");
  await expect(page.getByText("Night shift handover (synthetic)")).toBeVisible();
});

test("removed in one tab, an answer still open in another isn't kept again until that page is opened again", async ({ page, request }) => {
  const email = `yd-t-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "registered-nurse" } });
  const { user } = (await reg.json()) as { user: { id: string } };
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
  const key = `codecoach.answer.${user.id}.registered-nurse.m-walk-0`;
  const stored = () => page.evaluate((k) => localStorage.getItem(k), key);

  await page.goto("/careers/registered-nurse/questions/m-walk-0");
  const answer = page.locator("#answer-text");
  await answer.fill("First I checked his observations");
  await expect.poll(stored).toBe("First I checked his observations");

  const other = await page.context().newPage(); // a second tab of the same browser
  await other.goto("/settings/data");
  await other.getByRole("checkbox", { name: /Written answer, not sent/ }).check();
  await other.getByRole("button", { name: "Review removal (1)" }).click();
  await other.getByRole("button", { name: "Remove it from this device" }).click();
  await expect(other.getByText(/Removed 1 item from this browser/)).toBeVisible();
  expect(await stored()).toBeNull();

  await answer.pressSequentially(" and called the team");
  await expect(answer).toHaveValue("First I checked his observations and called the team"); // still on the page
  expect(await stored()).toBeNull(); // the open page didn't put the copy back

  // Leaving now asks first: the text isn't kept anywhere else.
  const warned = new Promise<string>((resolve) => page.once("dialog", (d) => { resolve(d.type()); void d.accept(); }));
  await page.reload(); // opened again: a new copy can be kept
  expect(await warned).toBe("beforeunload");
  await page.locator("#answer-text").fill("A fresh start");
  await expect.poll(stored).toBe("A fresh start");
  await other.close();
});
