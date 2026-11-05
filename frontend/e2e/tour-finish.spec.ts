import { chooseJob, expect, test, type Page } from "./fixtures";

// Finish, then a reload in the same instant (the save is cancelled with the page): the real
// backend must end up with the tour completed, and the finished tour isn't offered again.

const tour = (page: Page) => page.getByRole("region", { name: "Introduction" });

test("a finish cancelled by an immediate reload is completed on the next load", async ({ page }) => {
  page.on("dialog", (d) => void d.accept());
  await page.goto("/register");
  await page.getByLabel("Email").fill(`finish-${Date.now()}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Start the tour" }).click();
  await expect(tour(page).getByRole("heading", { name: "Read the question" })).toBeFocused();
  for (let i = 0; i < 4; i++) await tour(page).getByRole("button", { name: "Next" }).click();
  await expect(tour(page).getByRole("button", { name: "Finish" })).toBeVisible();
  // Let the steps land, then make the finish's save never reach the server.
  await page.waitForLoadState("networkidle");
  await page.route("**/api/v1/me/onboarding", (route) =>
    route.request().method() === "PATCH" ? route.abort("connectionreset") : route.continue());
  await tour(page).getByRole("button", { name: "Finish" }).click();
  await expect(tour(page)).toHaveCount(0);
  await page.unroute("**/api/v1/me/onboarding");

  // The server still has the tour running (its save never arrived); before this change, the
  // dashboard offered to resume it. The next load sends "complete" again.
  const completed = page.waitForResponse((r) => r.url().endsWith("/api/v1/me/onboarding") && r.request().method() === "PATCH"
    && r.request().postDataJSON()?.tour === "complete");
  await page.goto("/dashboard");
  const reply = await completed;
  expect(reply.ok()).toBe(true);
  expect((await reply.json()).tour_status).toBe("completed");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("region", { name: "Getting started" })).toHaveCount(0);

  // And it stays finished on a further reload (nothing left to re-send).
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("region", { name: "Getting started" })).toHaveCount(0);
});
