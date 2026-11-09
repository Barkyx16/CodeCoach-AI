import { expect, test, type Page, type Route } from "./fixtures";

/**
 * An answer lost on the way back, then a reload (Volume 8, prompt 1), against the real API. The
 * request reaches the server and is done; only the reply is lost. After a reload the page asks
 * the server what the earlier key made, shows it, and nothing is made or charged twice.
 */
async function startAsGuest(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await expect(page).toHaveURL(/\/welcome$/);
  await page.goto("/problems/two-sum");
  await expect(page.getByRole("heading", { name: "Two Sum", level: 1 })).toBeVisible();
}

/** Let the first matching POST reach the server, then lose its reply; count every POST. */
function loseFirstReply(page: Page, pattern: string) {
  const sent: string[] = [];
  let lost = false;
  void page.route(pattern, async (route: Route) => {
    if (route.request().method() !== "POST") return route.continue();
    sent.push((route.request().postDataJSON() as { client_request_id: string }).client_request_id);
    if (lost) return route.continue();
    lost = true;
    await route.fetch(); // the server does the work...
    await route.abort("connectionreset"); // ...and the page never hears back
  });
  return sent;
}

test("a submission and a hint whose replies were lost are found after a reload, not done twice", async ({ page }) => {
  await startAsGuest(page);

  const submissions = loseFirstReply(page, "**/api/v1/submissions");
  await page.getByRole("button", { name: /^(Submit|Save attempt)/ }).click();
  await expect(page.getByText(/We couldn't confirm your submission/)).toBeVisible();
  await page.reload();
  await expect(page.getByText(/Your submission from .* arrived\./)).toBeVisible();
  await expect(page.getByText(/Saved, but not run yet|Execution results/).first()).toBeVisible();
  expect(submissions).toHaveLength(1);

  const coach = page.getByRole("region", { name: "AI coach" });
  const left = coach.getByText(/\d+\/\d+ left/);
  await expect(left).toBeVisible();
  const before = Number((await left.innerText()).split("/")[0]);
  const hints = loseFirstReply(page, "**/api/v1/ai/hint");
  await coach.getByRole("button", { name: "Get a hint" }).click();
  await expect(coach.getByText(/The hint didn't go through/)).toBeVisible();
  await page.reload();
  const coachAgain = page.getByRole("region", { name: "AI coach" });
  await expect(coachAgain.getByText(/Your hint request from .* arrived\./)).toBeVisible();
  await expect(coachAgain.getByText(/Level 1 · Nudge/)).toBeVisible();
  await expect(coachAgain.getByText(new RegExp(`^${before - 1}/\\d+ left$`))).toBeVisible(); // charged once
  expect(hints).toHaveLength(1);

  // A second reload asks nothing: the earlier actions are resolved.
  await page.reload();
  await expect(page.getByRole("heading", { name: "Two Sum", level: 1 })).toBeVisible();
  await expect(page.getByText(/arrived\./)).toHaveCount(0);
});
