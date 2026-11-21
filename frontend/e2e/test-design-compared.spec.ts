import AxeBuilder from "@axe-core/playwright";

import { expect, setTheme, test, type Page } from "./fixtures";
import { API_URL } from "./ports";

/**
 * Each test-design run beside the run before it, by the one contract (Volume 19, prompt 4), against
 * the real API. Judged for real (E2E_JUDGE=1: worker → runner → gVisor): an ordinary case, then a
 * boundary case — comparable, both counts shown as given; then, after the faulty versions are shown,
 * a third run that's partly comparable and says why. The runs' list, the report and History say the
 * same, History in the contract's short words, and the comparison opens the earlier run's report.
 * Without the judge, runs are saved but not run, and each says why it isn't compared. Synthetic
 * accounts.
 */
const SLUG = "tests-count-in-range";

async function signIn(page: Page, request: import("@playwright/test").APIRequestContext) {
  const email = `tdc-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "software-engineer" } });
  expect(reg.status()).toBe(201);
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
}

async function fill(page: Page, nums: string, lo: string, hi: string, expected: string) {
  await page.getByLabel(/^nums/).nth(0).fill(nums);
  await page.getByLabel(/^lo/).nth(0).fill(lo);
  await page.getByLabel(/^hi/).nth(0).fill(hi);
  await page.getByLabel("Expected output").nth(0).fill(expected);
}

async function historyRow(page: Page, text: string) {
  await page.goto("/history");
  return page.locator("a", { hasText: text }).first();
}

test("judged runs: comparable, then partly comparable after the faulty versions were shown", async ({ page, request }) => {
  test.skip(process.env.E2E_JUDGE !== "1", "set E2E_JUDGE=1 (needs Docker + gVisor + sandbox image)");
  test.setTimeout(180_000);
  await signIn(page, request);
  await page.goto(`/test-design/${SLUG}`);
  const shows = page.getByRole("region", { name: "What your cases show" });
  const report = page.locator("section", { has: page.locator("#td-result") });
  // An ordinary case: the first judged run.
  await fill(page, "1, 5, 9", "2", "8", "1");
  await page.getByRole("button", { name: "Run my cases" }).click();
  await expect(shows).toContainText("Your cases tell 0 of the 4 authored faulty versions apart", { timeout: 60_000 });
  await expect(report).toContainText("Not compared: the first judged run of this exercise.");

  // A boundary case: beside the first, comparable, both counts as given.
  await fill(page, "3, 7", "1", "7", "2");
  await page.getByRole("button", { name: "Run my cases" }).click();
  await expect(shows).toContainText("Your cases tell 2 of the 4 authored faulty versions apart", { timeout: 60_000 });
  const beside = page.getByRole("region", { name: "Compared with your previous attempt" });
  await expect(beside).toContainText(/Earlier, .*: told apart 0 of 4 faulty versions/);
  await expect(beside).toContainText("This one: told apart 2 of 4 faulty versions");
  await expect(beside).toContainText("Comparable: the same exercise and version, run against the same authored faulty versions");
  await expect(beside).toContainText("Both counts are of the faulty versions written for this exercise only, not of every possible defect.");
  await expect(beside).not.toContainText(/improv|better/i);

  // After the faulty versions are shown: partly comparable, and why.
  await page.getByRole("button", { name: "Stuck? Show what the faulty versions get wrong" }).click();
  await page.getByRole("button", { name: "Show the faulty versions" }).click();
  await expect(page.getByRole("region", { name: "The faulty versions" })).toBeVisible();
  await page.getByRole("button", { name: "Run my cases" }).click();
  await expect(beside).toContainText(/Earlier, .*: told apart 2 of 4 faulty versions/, { timeout: 60_000 });
  await expect(beside).toContainText(
    "Partly comparable: the in-app help differed: before the earlier one, none recorded; before the later one, solution revealed",
  );
  const rows = page.getByRole("region", { name: "Your earlier runs" }).getByRole("listitem");
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(0)).toContainText("told apart 2 of 4 faulty versions · version 1 · In-app help: Solution revealed · Partly comparable with the one before");
  await expect(rows.nth(1)).toContainText("told apart 2 of 4 faulty versions · version 1 · In-app help: No in-app help recorded · Comparable with the one before");
  await expect(rows.nth(2)).toContainText("· Not compared: the first judged run of this exercise");
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".submission-compared").analyze();
    expect(scan.violations.map((v) => v.id), theme).toEqual([]);
  }

  // The comparison opens the earlier run's report, which is set beside its own earlier run.
  await beside.getByRole("link", { name: "Open that run's report" }).click();
  await expect(page).toHaveURL(/\?attempt=/);
  await expect(beside).toContainText("This one: told apart 2 of 4 faulty versions");
  await expect(beside).toContainText(/Earlier, .*: told apart 0 of 4 faulty versions/);

  // History says the same, in the contract's short words, and opens that run.
  const row = await historyRow(page, "Partly comparable with the one before");
  await expect(row).toContainText("1 case · told apart 2 of 4 faulty versions · version 1 · Partly comparable with the one before");
  await expect(row).toHaveAttribute("href", new RegExp(`/test-design/${SLUG}\\?attempt=`));
  await expect(page.locator("a", { hasText: "· Comparable with the one before" }).first()).toContainText("told apart 2 of 4 faulty versions");
});

test("without the judge, runs are saved, not run, and each says why it isn't compared", async ({ page, request }) => {
  test.skip(process.env.E2E_JUDGE === "1", "the judge is on: the judged test covers it");
  await signIn(page, request);
  await page.goto(`/test-design/${SLUG}`);
  await fill(page, "3, 7", "1", "7", "2");
  const save = page.getByRole("button", { name: "Save my cases (not run)" });
  await save.click();
  const report = page.locator("section", { has: page.locator("#td-result") });
  const why = "Not compared: it wasn't run (this server can't run code), so there's no result";
  await expect(report).toContainText(`${why}.`);
  await save.click();
  const rows = page.getByRole("region", { name: "Your earlier runs" }).getByRole("listitem");
  await expect(rows).toHaveCount(2);
  for (const i of [0, 1]) await expect(rows.nth(i)).toContainText(`1 case · not run: this server can't run code · version 1 · In-app help: No in-app help recorded · ${why}`);
  await expect(page.getByRole("region", { name: "Compared with your previous attempt" })).toHaveCount(0);
  const row = await historyRow(page, "not run: this server can't run code");
  await expect(row).toContainText(`1 case · not run: this server can't run code · version 1 · ${why}`);
});
