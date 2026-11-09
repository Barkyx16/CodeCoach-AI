import { expect, test } from "./fixtures";
import { API_URL } from "./ports";

/** Work queues on a phone (Volume 10, prompt 7): task cards fit without sideways scrolling, a
 * task moves by its position list, the order and reasoning come back after a reload, and the
 * debrief arrives. */
test("on a phone: the queue fits, reorders by position, survives a reload and debriefs", async ({ page, request }) => {
  const email = `queue-m-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  expect((await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "it-support-specialist" } })).status()).toBe(201);
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).tap();
  await expect(page).not.toHaveURL(/\/login$/);

  await page.goto("/scenarios/it-morning-queue");
  await page.getByRole("button", { name: "Start the scenario" }).tap();
  const list = page.getByRole("list", { name: "Your order" });
  await expect(list).toBeVisible();
  const noSideways = () => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  expect(await noSideways()).toBe(true);
  await page.getByRole("combobox", { name: "Position of “Locked-out account”" }).selectOption("0");
  await expect(list.getByRole("heading", { level: 3 }).first()).toHaveText("Locked-out account");
  await page.getByLabel("What you'd do first, and why").fill("Unlock Tom first, five minutes, then the VPN for the three remote people.");
  await page.reload();
  await expect(page.getByText("Your order and reasoning were restored from this device.")).toBeVisible();
  await expect(list.getByRole("heading", { level: 3 }).first()).toHaveText("Locked-out account");
  await expect(page.getByLabel("What you'd do first, and why")).toHaveValue("Unlock Tom first, five minutes, then the VPN for the three remote people.");
  await page.getByRole("button", { name: "Submit this order" }).tap();
  await expect(page.getByRole("region", { name: "Your plans" })).toContainText("A five-minute unblock first");
  expect(await noSideways()).toBe(true);
});
