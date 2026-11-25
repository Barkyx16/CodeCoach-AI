import { expect, test, type Page, type Route } from "./fixtures";

/**
 * A save whose reply was lost (Volume 8, prompt 3), against the real API. The save reaches the
 * server and is accepted; only the reply is lost. Pressing Save again sends the same save with
 * the same key: the page is told its save went through, instead of meeting its own new version
 * as a conflict. If another tab saved after it, both versions are shown and nothing is replaced.
 */
async function newStory(page: Page): Promise<string> {
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await expect(page).toHaveURL(/\/welcome$/);
  await page.goto("/stories/new");
  await page.getByLabel("Title").fill("Covering a short-staffed ward");
  await page.getByLabel("Situation").fill("Two nurses called in sick on a night shift.");
  await page.getByRole("button", { name: "Save story" }).click();
  await expect(page).toHaveURL(/\/stories\/[0-9a-f-]{36}$/);
  // The address changes a moment before the saved story's editor replaces the new-story one;
  // typing into the outgoing editor is lost with it. Only the saved story's says "Save changes".
  await expect(page.getByRole("button", { name: "Save changes" })).toBeVisible();
  return page.url();
}

/** Let the first PATCH reach the server, then lose its reply; record every PATCH's key. */
function loseFirstSaveReply(page: Page) {
  const keys: string[] = [];
  let lost = false;
  void page.route("**/api/v1/me/stories/*", async (route: Route) => {
    if (route.request().method() !== "PATCH") return route.continue();
    keys.push((route.request().postDataJSON() as { client_request_id: string }).client_request_id);
    if (lost) return route.continue();
    lost = true;
    await route.fetch(); // the server saves it...
    await route.abort("connectionreset"); // ...and the page never hears back
  });
  return keys;
}

test("a lost save, sent again, is the learner's own success", async ({ page }) => {
  await newStory(page);
  const keys = loseFirstSaveReply(page);
  await page.getByLabel("Result").fill("Both patients were seen within ten minutes.");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.locator(".inline-error")).toBeVisible();
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Your earlier save went through as version 2.")).toBeVisible();
  await expect(page.getByRole("region", { name: "Edit conflict" })).toHaveCount(0);
  expect(keys).toHaveLength(2);
  expect(keys[1]).toBe(keys[0]);
});

test("a lost save recovered after another tab saved over it: both shown, the newer work kept", async ({ page }, testInfo) => {
  const url = await newStory(page);
  loseFirstSaveReply(page);
  await page.getByLabel("Result").fill("Mine: both patients seen within ten minutes.");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.locator(".inline-error")).toBeVisible();

  // Another tab (the same account) loads the story, now at version 2, and saves version 3.
  const other = await page.context().newPage();
  await other.goto(url);
  await expect(other.getByLabel("Result")).toHaveValue("Mine: both patients seen within ten minutes.");
  await other.getByLabel("Result").fill("Newer, from the other tab: seen within eight minutes.");
  await other.getByRole("button", { name: "Save changes" }).click();
  await expect(other.getByText("Saved as version 3.")).toBeVisible();
  await other.close();

  await page.getByRole("button", { name: "Save changes" }).click();
  const conflict = page.getByRole("region", { name: "Edit conflict" });
  await expect(conflict.getByText(/Your save went through as version 2\. This story was changed after that/)).toBeVisible();
  await expect(conflict.getByText("Newer, from the other tab: seen within eight minutes.")).toBeVisible();
  await expect(conflict.getByText("Mine: both patients seen within ten minutes.")).toBeVisible();
  await expect(page.getByLabel("Result")).toHaveValue("Mine: both patients seen within ten minutes.");
  const shot = await page.screenshot({ path: "e2e/screenshots/lost-save-recovered.png", fullPage: true });
  await testInfo.attach("lost-save-recovered-with-newer-work", { body: shot, contentType: "image/png" });

  // Nothing was overwritten on the server: reloading shows version 3, the other tab's.
  await page.goto(url);
  await expect(page.getByLabel("Result")).toHaveValue("Newer, from the other tab: seen within eight minutes.");
});
