import { expect, test, type Page } from "./fixtures";
import { API_URL } from "./ports";

/**
 * The third test-design exercise, Count Pairs (Volume 20, prompt 9), against the real API: listed
 * with the others, opened, its page saying it was drafted with an assistant, machine-checked and
 * that its review is owed. Without a judge a run is saved and says it wasn't run; with the real judge
 * (E2E_JUDGE=1, CI's sandbox job) its four witnesses are judged and the report names how many of
 * its four faulty versions they tell apart. Synthetic accounts.
 */
const SLUG = "tests-count-pairs";

async function signedIn(page: Page, request: import("@playwright/test").APIRequestContext) {
  const email = `td-pairs-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  expect((await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "software-engineer" } })).status()).toBe(201);
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
}

async function fill(page: Page, i: number, nums: string, target: string, expected: string) {
  await page.getByLabel(/^nums/).nth(i).fill(nums);
  await page.getByLabel(/^target/).nth(i).fill(target);
  await page.getByLabel("Expected output").nth(i).fill(expected);
}

async function open(page: Page) {
  await page.goto("/problems?view=test-design");
  const listed = page.getByRole("link", { name: "Test design: Count Pairs" });
  await expect(listed).toBeVisible();
  await expect(page.locator("li", { has: listed })).toContainText("4 faulty versions to tell apart.");
  await listed.click();
  await expect(page).toHaveURL(new RegExp(`/test-design/${SLUG}$`));
  await expect(page.locator("#main")).toContainText("Drafted in this repository with an AI coding assistant");
  await expect(page.locator("#main")).toContainText("Its review is owed: not yet reviewed by the project author.");
}

test("listed with the others, labelled as a draft, and a run saved without a judge", async ({ page, request }) => {
  test.skip(process.env.E2E_JUDGE === "1", "the judged test below covers this server");
  await signedIn(page, request);
  await open(page);
  await fill(page, 0, "3, 1", "6", "0");
  await page.getByRole("button", { name: "Save my cases (not run)" }).click();
  await expect(page.locator("section", { has: page.locator("#td-result") })).toContainText(/can't run code/);
});

test("its witnesses, judged in the sandbox, tell all four faulty versions apart", async ({ page, request }) => {
  test.skip(process.env.E2E_JUDGE !== "1", "set E2E_JUDGE=1 (needs Docker + gVisor + sandbox image)");
  await signedIn(page, request);
  await open(page);
  const cases: [string, string, string][] = [["3, 1", "6", "0"], ["1, 5, 2, 4", "6", "2"], ["2, 2, 2", "4", "3"], ["4, 7, 2", "6", "1"]];
  for (const [i, [nums, target, expected]] of cases.entries()) {
    if (i > 0) await page.getByRole("button", { name: "Add a case" }).click();
    await fill(page, i, nums, target, expected);
  }
  await page.getByRole("button", { name: "Run my cases" }).click();
  const shows = page.getByRole("region", { name: "What your cases show" });
  await expect(shows).toContainText("Your cases tell 4 of the 4 authored faulty versions apart", { timeout: 60_000 });
});
