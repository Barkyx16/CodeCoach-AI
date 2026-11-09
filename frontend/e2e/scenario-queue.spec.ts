import AxeBuilder from "@axe-core/playwright";

import { expect, test, type APIRequestContext, type Page } from "./fixtures";
import { API_URL } from "./ports";

/**
 * Work queues (Volume 10, prompt 7) against the real API: an IT support queue ordered by keyboard,
 * a debrief naming the strategy followed and the others, a second approach kept apart from the
 * first, and a dispatch queue where a broken dependency is named and the graph decides what
 * follows, with the re-plan judged on the new information. No accessibility violations in either
 * theme. Synthetic accounts.
 */
const PASSWORD = "CorrectHorse42";

async function signedIn(page: Page, request: APIRequestContext, track: string): Promise<void> {
  const email = `queue-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const r = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: PASSWORD, career_track: track } });
  expect(r.status()).toBe(201);
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
}

const order = (page: Page) => page.getByRole("list", { name: "Your order" }).getByRole("heading", { level: 3 }).allTextContents();

test("an IT support queue by keyboard, two defensible strategies, and a second approach kept apart", async ({ page, request }) => {
  await signedIn(page, request, "it-support-specialist");
  await page.goto("/scenarios");
  await expect(page.getByText("Work queue: order several tasks")).toBeVisible();
  await page.getByRole("link", { name: "The 08:45 support queue" }).click();
  await page.getByRole("button", { name: "Start the scenario" }).click();
  await expect(page.getByRole("list", { name: "Your order" })).toBeVisible();

  // Keyboard only: the VPN task down twice, so the fixed times come first.
  await page.getByRole("button", { name: "Move down: Remote staff can't connect" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: "Move down: Remote staff can't connect" })).toBeFocused();
  await page.keyboard.press("Enter");
  expect(await order(page)).toEqual(["New starter's account", "Boardroom screen", "Remote staff can't connect", "Locked-out account", "Second-floor printer jam"]);
  await page.getByLabel("What you'd do first, and why").fill("Priya's account first so it's ready at 09:30, then the screen before the 10:00 board meeting; I'd tell the remote staff when to expect the VPN.");
  for (const theme of ["dark", "light"]) {
    await page.evaluate((t) => document.documentElement.setAttribute("data-theme", t), theme);
    const scan = await new AxeBuilder({ page }).include(".scenario-attempt").analyze();
    expect(scan.violations.map((v) => v.id), theme).toEqual([]);
  }
  await page.getByRole("button", { name: "Submit this order" }).click();
  const plans = page.getByRole("region", { name: "Your plans" });
  await expect(plans).toContainText("Your order follows “Fixed times first”.");
  await expect(plans).toContainText("Most people blocked first:");
  await expect(plans).toContainText("This order meets every hard constraint");
  await expect(plans).toContainText("08:45–09:00 New starter's account (by 09:30: on time)");
  await expect(page.getByText("Queue cleared by 09:50 (simulated)")).toBeVisible();

  // Another approach is a separate attempt; this one stays as it was.
  const first = page.url();
  await page.getByRole("button", { name: "Try another approach" }).click();
  await expect(page.getByText("Exploration: a separate attempt; your original is kept")).toBeVisible();
  expect(await order(page)).toEqual(["Remote staff can't connect", "New starter's account", "Boardroom screen", "Locked-out account", "Second-floor printer jam"]);
  await page.getByLabel("What you'd do first, and why").fill("The VPN first because three people can't work; I'd message Priya's manager about 09:30.");
  await page.getByRole("button", { name: "Submit this order" }).click();
  await expect(page.getByRole("region", { name: "Your plans" })).toContainText("Your order follows “Most people blocked first”.");
  await page.goto(first);
  await expect(page.getByRole("region", { name: "Your plans" })).toContainText("Your order follows “Fixed times first”.");
});

test("a dispatch queue: a broken dependency is named, and the re-plan is judged on the new information", async ({ page, request }) => {
  await signedIn(page, request, "logistics-coordinator");
  await page.goto("/scenarios/logistics-dispatch-queue");
  await page.getByRole("button", { name: "Start the scenario" }).click();
  // Labels before the pick list: the labels need it first.
  await page.getByRole("combobox", { name: "Position of “Print the shipping labels”" }).selectOption("1");
  expect((await order(page)).slice(0, 2)).toEqual(["Print the shipping labels", "Make the pick list"]);
  await page.getByLabel("What you'd do first, and why").fill("Labels first since they're quick, then the pick list, then I call the carrier.");
  await page.getByRole("button", { name: "Submit this order" }).click();
  const history = page.getByRole("list", { name: "What has happened so far" });
  await expect(history).toContainText("This order breaks a hard constraint");
  await expect(history).toContainText("the label system reads the box count from the pick list");
  await expect(page.getByRole("heading", { level: 2, name: "The plan doesn't hold" })).toBeVisible();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("heading", { level: 2, name: "08:10: new information" })).toBeVisible();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("heading", { level: 2, name: "08:10: re-plan with what you know now" })).toBeVisible();
  // The case's order is already valid here; the courier comes after the labels.
  expect(await order(page)).toEqual([
    "Make the pick list (the 10 urgent boxes first)", "Print the shipping labels", "Book the courier for the 10 urgent boxes",
    "Confirm the 11:00 truck", "Clear the returns pallet from dock 2", "Reply to a supplier",
  ]);
  await page.getByLabel("What you'd do first, and why").fill("The urgent chain first for the 10:00 sports day, then I call the carrier before 09:00 so the slot isn't released.");
  await page.getByRole("button", { name: "Submit this order" }).click();
  await expect(page.getByText("Everything ships (simulated)")).toBeVisible();
  const plans = page.getByRole("region", { name: "Your plans" });
  await expect(plans).toContainText("Judged on what you knew at 08:00, before any new information.");
  await expect(plans).toContainText("Judged on what you knew at 08:10, after: The plan doesn't hold; 08:10: new information.");
  await expect(plans).toContainText("Your order follows “The urgent chain first”.");
});
