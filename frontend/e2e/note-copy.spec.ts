import { expect, test, type Page, type Route } from "./fixtures";

/**
 * Keep both after a note conflict, with the reply lost (Volume 8, prompt 4), against the real API.
 * The copy reaches the server and is made; only the reply is lost. The page offers Check copy and
 * Retry same copy instead of another create; retrying returns the copy already made, so there's
 * one copy, and the source note keeps the other tab's version.
 */
async function noteInTwoTabs(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await expect(page).toHaveURL(/\/welcome$/);
  await page.goto("/notes/new");
  await page.getByLabel("Title").fill("Handover plan");
  await page.getByLabel("Note", { exact: true }).fill("First draft");
  await expect(page).toHaveURL(/\/notes\/[0-9a-f-]{36}$/, { timeout: 10_000 });
  await expect(page.locator(".note-status")).toHaveText("Saved");
  const other = await page.context().newPage();
  await other.goto(page.url());
  await expect(other.getByLabel("Note", { exact: true })).toHaveValue("First draft");
  return other;
}

test("Keep both with a lost reply makes one copy, and the source keeps the other tab's version", async ({ page }) => {
  const other = await noteInTwoTabs(page);
  await page.getByLabel("Note", { exact: true }).fill("Tab A's version");
  await expect(page.locator(".note-status")).toHaveText("Saved");
  await other.getByLabel("Note", { exact: true }).fill("Tab B's version");
  const conflict = other.getByRole("region", { name: "Edit conflict" });
  await expect(conflict).toContainText("Tab A's version");

  const keys: string[] = [];
  let lost = false;
  await other.route("**/api/v1/me/notes", async (route: Route) => {
    const body = route.request().postDataJSON() as { copy_of?: string; client_request_id?: string } | null;
    if (route.request().method() !== "POST" || !body?.copy_of) return route.continue();
    keys.push(body.client_request_id ?? "");
    if (lost) return route.continue();
    lost = true;
    await route.fetch(); // the copy is made...
    await route.abort("connectionreset"); // ...and the reply is lost
  });
  await conflict.getByRole("button", { name: "Keep both" }).click();
  await expect(conflict.getByText(/We couldn't confirm the copy of your version/)).toBeVisible();
  await expect(conflict.getByRole("button", { name: "Keep both" })).toHaveCount(0);
  await conflict.getByRole("button", { name: "Retry same copy" }).click();
  await expect(other.getByText(/Your version was saved as a separate note/)).toBeVisible();
  expect(keys).toHaveLength(2);
  expect(keys[1]).toBe(keys[0]);

  // One copy, holding tab B's version; the source note holds tab A's.
  await other.goto("/notes");
  await expect(other.getByRole("link", { name: /Handover plan \(my version\)/ })).toHaveCount(1);
  await other.getByRole("link", { name: /Handover plan \(my version\)/ }).click();
  await expect(other.getByLabel("Note", { exact: true })).toHaveValue("Tab B's version");
  await page.reload();
  await expect(page.getByLabel("Note", { exact: true })).toHaveValue("Tab A's version");
});
