import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

async function signUpNurse(page: Page, tag: string) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`${tag}-${Date.now()}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.getByLabel("Job you're preparing for").selectOption("registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

const list = (page: Page) => page.getByRole("region", { name: "Question list" });

test("filtered list → question → Back keeps the filters and scroll, even after a reload", async ({ page }) => {
  await signUpNurse(page, "explore");
  await page.goto("/problems?view=questions");
  await expect(page.getByRole("heading", { name: "Registered Nurse interview questions" })).toBeVisible();
  await page.getByRole("tablist", { name: "Difficulty" }).getByRole("tab", { name: /Medium/ }).click();
  await expect(page.getByRole("combobox", { name: "Format" }).getByRole("option", { name: "Scenario (60)" })).toBeAttached();
  await page.getByRole("combobox", { name: "Format" }).selectOption("situational");
  await expect(page).toHaveURL(/kind=situational/);
  await expect(page.getByRole("tablist", { name: "Difficulty" }).getByRole("tab", { name: "Medium 60" })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "Format: Scenario" })).toBeVisible();
  // Show more so the page scrolls, then open a question far down the list.
  for (let i = 0; i < 2; i++) await list(page).getByRole("button", { name: "View more" }).click();
  await expect(page).toHaveURL(/shown=25/);
  await expect(list(page).getByRole("listitem")).toHaveCount(25);
  const target = list(page).getByRole("listitem").nth(20).getByRole("link");
  const title = (await target.locator(".problem-row__title").innerText()).replace(/^\d+/, "").trim();
  await target.scrollIntoViewIfNeeded();
  const scrolled = await page.evaluate(() => window.scrollY);
  expect(scrolled).toBeGreaterThan(300);
  await target.click();
  await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();

  // Reload the question page, then go Back: same filters, same 25 rows, same place on the page.
  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
  await page.getByRole("link", { name: "Back to results" }).click();
  await expect(page).toHaveURL(/difficulty=medium/);
  await expect(page).toHaveURL(/kind=situational/);
  await expect(page).toHaveURL(/shown=25/);
  await expect(list(page).getByRole("listitem")).toHaveCount(25);
  await expect(page.getByRole("combobox", { name: "Format" })).toHaveValue("situational");
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(scrolled - 120);

  // Removing the filter from its chip widens the list again.
  await page.getByRole("button", { name: "Remove Format: Scenario" }).click();
  await expect(page).not.toHaveURL(/kind=/);
  await expect(list(page).getByRole("listitem")).toHaveCount(5);
});

test("bookmarks, a collection practiced as a queue, and a second account that sees none of it", async ({ page, browser }) => {
  await signUpNurse(page, "collect");
  await page.goto("/problems?view=questions");
  await expect(page.getByRole("heading", { name: "Registered Nurse interview questions" })).toBeVisible();
  const first = list(page).getByRole("listitem").first();
  const title = (await first.locator(".problem-row__title").innerText()).replace(/^\d+/, "").trim();
  const star = first.getByRole("button", { name: `Bookmark “${title}”` });
  await star.click();
  await expect(star).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("combobox", { name: "Your practice" }).selectOption("bookmarked");
  await expect(list(page).getByRole("listitem")).toHaveCount(1);

  // Add two questions to a new collection from their pages; a duplicate is refused.
  await list(page).getByRole("link").first().click();
  const save = page.getByRole("region", { name: "Save for later" });
  await save.getByLabel("New collection name").fill("Week 1");
  await save.getByRole("button", { name: "Add" }).click();
  await expect(save.getByText("Added to “Week 1”.")).toBeVisible();
  await expect(save.getByRole("option", { name: "Week 1 (already added)" })).toHaveAttribute("disabled", "");
  await page.goBack();
  await page.getByRole("combobox", { name: "Your practice" }).selectOption("");
  await list(page).getByRole("link").nth(1).click();
  const save2 = page.getByRole("region", { name: "Save for later" });
  await expect(save2.getByRole("option", { name: "Week 1" })).toBeAttached();
  await save2.getByLabel("Add to a collection").selectOption({ label: "Week 1" });
  await save2.getByRole("button", { name: "Add" }).click();
  await expect(save2.getByText("Added to “Week 1”.")).toBeVisible();

  // Reorder, and the order survives a reload.
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Saved" }).click();
  await page.getByRole("link", { name: "Week 1" }).click();
  const items = page.getByRole("list", { name: "Items in order" }).getByRole("listitem");
  await expect(items).toHaveCount(2);
  const secondTitle = (await items.nth(1).locator("a").innerText()).trim();
  await page.getByRole("button", { name: `Move “${secondTitle}” up` }).click();
  await expect(items.first()).toContainText(secondTitle);
  await page.reload();
  await expect(items.first()).toContainText(secondTitle);
  const collectionUrl = page.url();

  // Practice it as a queue: open, mark done and go to the next.
  await page.getByRole("button", { name: "Start this collection" }).click();
  await expect(page.getByText("Item 1 of 2")).toBeVisible();
  await page.getByRole("link", { name: "Answer this question" }).click();
  await expect(page).toHaveURL(/queue=/);
  const bar = page.getByRole("region", { name: "Practice queue" });
  await expect(bar).toContainText("item 1 of 2");
  await bar.getByRole("button", { name: "Mark done and go to next" }).click();
  await expect(page.getByRole("region", { name: "Practice queue" })).toContainText("item 2 of 2");
  await page.getByRole("region", { name: "Practice queue" }).getByRole("link", { name: "Back to the queue" }).click();
  await expect(page.getByRole("region", { name: "Queue progress" })).toContainText("1 of 2 marked done");
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => v.id), "queue page").toEqual([]);

  // A different account in a separate browser context can't see or open any of it.
  const other = await browser.newContext();
  const page2 = await other.newPage();
  await signUpNurse(page2, "other");
  await page2.goto(collectionUrl);
  await expect(page2.getByText("Collection not found")).toBeVisible();
  await page2.goto("/saved");
  await expect(page2.getByText(/No collections yet/)).toBeVisible();
  await expect(page2.getByText("No bookmarks yet")).toBeVisible();
  await other.close();

  // Deleting the collection asks first and keeps the bookmark.
  await page.goto(collectionUrl);
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Delete collection" }).click();
  await expect(page).toHaveURL(/\/saved$/);
  await expect(page.getByText(/No collections yet/)).toBeVisible();
  await expect(page.getByRole("link", { name: title })).toBeVisible();
  await page.screenshot({ path: "e2e/screenshots/saved.png", fullPage: true });
});
