import { chooseJob, expect, test, type Page } from "./fixtures";

// Pages that load their code on first use: they load, and when their code can't be downloaded
// (offline, or replaced by an update) the page says so inside the normal layout and offers a
// reload, instead of React Router's raw error screen.

async function signUp(page: Page) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`lazy-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

// The settings page's own code: a dev-server module or a hashed production chunk.
const SETTINGS_CODE = /\/(src\/features\/settings\/SettingsPage\.tsx|assets\/SettingsPage-[^/]+\.js)(\?|$)/;

test("a page whose code can't load says so and recovers on reload", async ({ page }) => {
  await signUp(page);
  await page.route(SETTINGS_CODE, (route) => route.abort());
  await page.goto("/settings");
  const alert = page.getByRole("alert").filter({ hasText: "This page couldn't load" });
  await expect(alert).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible(); // still inside the layout
  await expect(page.getByText("Unexpected Application Error")).toHaveCount(0);

  await page.unroute(SETTINGS_CODE);
  await alert.getByRole("button", { name: "Reload the page" }).click();
  await expect(page.getByRole("heading", { level: 1, name: /Settings/ })).toBeVisible();
});

test("pages that load on first use open from the navigation", async ({ page }) => {
  await signUp(page);
  for (const [path, heading] of [["/applications", /applications/i], ["/stories", /stor/i], ["/schedule", /schedule/i], ["/settings", /Settings/]] as const) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
  }
});
