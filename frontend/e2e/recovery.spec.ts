import { expect, test, type Page, type Route } from "./fixtures";

/**
 * An answer that never comes back (Volume 7, prompt 6), against the real API. The request
 * reaches the server and is done; only the reply is lost on the way back to the page (Playwright
 * lets the request through, then drops the response). Pressing the button again must not do it
 * twice:
 * - the submission sent again comes back as the same submission (one record, not two);
 * - the hint asked again comes back as the same hint, and today's AI budget is used once.
 */
async function startAsGuest(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await expect(page).toHaveURL(/\/welcome$/);
  await page.goto("/problems/two-sum");
  await expect(page.getByRole("heading", { name: "Two Sum", level: 1 })).toBeVisible();
}

/** Let the first matching request reach the server, keep its answer, and lose it on the way back. */
function loseFirstReply(page: Page, pattern: string): Promise<unknown> {
  return new Promise((resolve) => {
    let lost = false;
    void page.route(pattern, async (route: Route) => {
      if (lost || route.request().method() !== "POST") return route.continue();
      lost = true;
      const reply = await route.fetch(); // the server does the work...
      resolve(await reply.json());
      await route.abort("connectionreset"); // ...and the page never hears back
    });
  });
}

test("a submission and a hint whose replies were lost aren't done twice", async ({ page }) => {
  await startAsGuest(page);
  const editor = page.getByTestId("code-editor");
  await expect(editor).toContainText("write your solution here");

  // Submit: the server records it, the page loses the reply.
  const firstSubmission = loseFirstReply(page, "**/api/v1/submissions");
  const submit = page.getByRole("button", { name: /^(Submit|Save attempt)/ });
  await submit.click();
  const { id: recordedId } = (await firstSubmission) as { id: string };
  await expect(page.getByText(/We couldn't confirm your submission because the connection dropped/)).toBeVisible();
  await expect(editor).toContainText("write your solution here"); // the code is still there

  // Pressing Submit again (not only "Try again") sends the same request: the same submission back.
  const second = page.waitForResponse((r) => r.url().endsWith("/api/v1/submissions") && r.request().method() === "POST");
  await submit.click();
  const again = await (await second).json();
  expect(again.id).toBe(recordedId);
  await expect(page.getByText(/We couldn't confirm/)).toHaveCount(0);

  // A hint: the same, and the budget counter moves by one.
  const coach = page.getByRole("region", { name: "AI coach" });
  const left = coach.getByText(/\d+\/\d+ left/);
  await expect(left).toBeVisible();
  const before = Number((await left.innerText()).split("/")[0]);
  const firstHint = loseFirstReply(page, "**/api/v1/ai/hint");
  await coach.getByRole("button", { name: "Get a hint" }).click();
  const lostHint = (await firstHint) as { content: { hint: string } };
  await expect(coach.getByRole("alert")).toContainText("No reply came back, so we can't tell whether it arrived. Trying again is safe");
  await coach.getByRole("button", { name: "Try again" }).click();
  await expect(coach.getByText(lostHint.content.hint)).toBeVisible(); // the answer the server already gave
  await expect(left).toHaveText(new RegExp(`^${before - 1}/`)); // one use of the budget, not two
});
