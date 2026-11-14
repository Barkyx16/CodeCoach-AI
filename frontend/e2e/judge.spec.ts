import AxeBuilder from "@axe-core/playwright";
import { navTo, expect, test, type Page } from "./fixtures";

// Real judging: browser → API → worker → runner → Docker + gVisor. Run with E2E_JUDGE=1.
test.skip(process.env.E2E_JUDGE !== "1", "set E2E_JUDGE=1 (needs Docker + gVisor + sandbox image)");
test.setTimeout(120_000);

const CORRECT = `import java.util.HashMap;
import java.util.Map;

class Solution {
    public int[] twoSum(int[] nums, int target) {
        Map<Integer, Integer> seen = new HashMap<>();
        for (int i = 0; i < nums.length; i++) {
            Integer j = seen.get(target - nums[i]);
            if (j != null) return new int[] {j, i};
            seen.put(nums[i], i);
        }
        throw new IllegalArgumentException("no pair");
    }
}`;

const BUGGY = `class Solution {
    public int[] twoSum(int[] nums, int target) {
        return new int[] {0, 1};
    }
}`;

async function paste(page: Page, code: string) {
  await page.locator(".monaco-editor").first().click();
  await page.keyboard.press("ControlOrMeta+A");
  await page.keyboard.press("Delete");
  await page.evaluate((text) => navigator.clipboard.writeText(text), code);
  await page.keyboard.press("ControlOrMeta+V");
}

test("submissions are judged in the gVisor sandbox", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await page.getByRole("button", { name: "Start this problem" }).click(); // the optional welcome
  await expect(page).toHaveURL(/two-sum/);
  await expect(page.locator(".monaco-editor")).toBeVisible();

  // A wrong answer: real per-test feedback for public tests, counts only for hidden ones.
  await paste(page, BUGGY);
  // Run first: public tests only, in the same sandbox, and nothing is recorded as an attempt.
  await page.getByRole("button", { name: "Run", exact: true }).click();
  await expect(page.getByText("Run · public tests only")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("2/3 tests passed")).toBeVisible(); // [0, 1] is right for 2 of the 3 public tests
  await expect(page.getByText(/hidden: /)).toHaveCount(0);

  await page.getByRole("button", { name: "Submit" }).click();
  await expect(page.getByText("Some tests failed. Check the cases below.")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/hidden: \d\/4/)).toBeVisible();
  await expect(page.getByText("Failed", { exact: true })).toBeVisible();

  // Ask the coach why: grounded in the first failing public test, never in hidden ones.
  await page.getByRole("button", { name: "Explain this failure" }).click();
  const why = page.getByRole("region", { name: "Why it failed" });
  await expect(why.getByText("Wrong answer on a public test.")).toBeVisible();
  await expect(why.getByText(/Public test 2 \(nums = \[3, 2, 4\], target = 6\): expected \[1, 2\], got \[0, 1\]/)).toBeVisible();
  await page.screenshot({ path: "e2e/screenshots/10-explain-failure.png" });
  // Real judged results and the explanation card pass the same WCAG 2.1 A/AA scan as e2e/a11y.spec.ts.
  const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(axe.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);

  // The right answer passes every public and hidden test.
  await paste(page, CORRECT);
  await page.getByRole("button", { name: "Submit" }).click();
  await expect(page.getByText("All tests passed. Nice work.")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("7/7 tests passed")).toBeVisible();
  await expect(page.getByText("hidden: 4/4")).toBeVisible();
  await page.screenshot({ path: "e2e/screenshots/08-judged-pass.png" });

  // Solving shows up on the dashboard.
  await navTo(page, "Dashboard");
  const summary = page.getByRole("region", { name: "Summary" });
  await expect(summary.getByText("Solved")).toBeVisible();
  await expect(summary.getByText("1", { exact: true }).first()).toBeVisible();
});

test("the judge reports ready, and a reload while judging picks the submission back up", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await page.getByRole("button", { name: "Start this problem" }).click(); // the optional welcome
  await expect(page).toHaveURL(/two-sum/);
  await expect(page.locator(".monaco-editor")).toBeVisible();
  // A real, authenticated probe found the runner: no "unavailable" banner, Run is offered.
  await expect(page.getByRole("button", { name: "Run", exact: true })).toBeVisible();
  await expect(page.getByText(/temporarily unavailable|can't run on this server/)).toHaveCount(0);

  // An infinite loop: submit, reload straight away, and the verdict still arrives on the reloaded page.
  await paste(page, `class Solution {
    public int[] twoSum(int[] nums, int target) {
        while (true) { }
    }
}`);
  await page.getByRole("button", { name: "Submit" }).click();
  await expect(page.getByText(/Queued|Running your code/).first()).toBeVisible({ timeout: 30_000 });
  await page.reload();
  await expect(page.getByText("Your code ran too long. Look for an infinite loop or a slower-than-needed approach.")).toBeVisible({ timeout: 90_000 });
});

test("the debugging lab: the faulty starter fails on its reproduction case, and a repair of the learner's own passes", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  // The guest session exists once the welcome offers a problem; navigating sooner can abort it.
  await expect(page.getByRole("button", { name: "Start this problem" })).toBeVisible();
  await page.goto("/problems/debug-count-at-most");
  await expect(page.locator(".monaco-editor")).toBeVisible();
  await expect(page.getByRole("region", { name: "Fix the bug" })).toBeVisible();

  // The code as given: judged for real, it fails exactly where the brief says.
  await page.getByRole("button", { name: "Submit", exact: true }).click();
  const debrief = page.getByRole("region", { name: "Debugging debrief" });
  await expect(debrief.getByRole("heading", { name: /^Not fixed yet/ })).toBeVisible({ timeout: 60_000 });
  await expect(debrief).toContainText("nums = [4, 8, 3], limit = 5: still fails (got 1, expected 2)");

  // A repair that isn't the reference's text: a for-each loop.
  await paste(page, `class Solution {
    public int countAtMost(int[] nums, int limit) {
        int count = 0;
        for (int n : nums) {
            if (n <= limit) count++;
        }
        return count;
    }
}`);
  await page.getByRole("button", { name: "Submit", exact: true }).click();
  await expect(debrief.getByRole("heading", { name: "Fixed: every test passes" })).toBeVisible({ timeout: 60_000 });
  await expect(debrief).toContainText("nums = [4, 8, 3], limit = 5: now passes");
  await expect(debrief.getByRole("heading", { name: "Why it happened" })).toBeVisible();
});

test("test design: ordinary cases tell no faulty version apart; one boundary case does, judged in the sandbox", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  // The guest session exists once the welcome offers a problem; navigating sooner can abort it.
  await expect(page.getByRole("button", { name: "Start this problem" })).toBeVisible();
  await page.goto("/test-design/tests-count-in-range");
  const fill = async (i: number, nums: string, lo: string, hi: string, expected: string) => {
    await page.getByLabel(/^nums/).nth(i).fill(nums);
    await page.getByLabel(/^lo/).nth(i).fill(lo);
    await page.getByLabel(/^hi/).nth(i).fill(hi);
    await page.getByLabel("Expected output").nth(i).fill(expected);
  };
  await fill(0, "1, 5, 9", "2", "8", "1");
  await page.getByRole("button", { name: "Add a case" }).click();
  await fill(1, "3, 40", "0", "10", "1");
  await page.getByRole("button", { name: "Run my cases" }).click();
  const shows = page.getByRole("region", { name: "What your cases show" });
  await expect(shows).toContainText("Your cases tell 0 of the 4 authored faulty versions apart", { timeout: 60_000 });

  await page.getByRole("button", { name: "Remove case 2" }).click();
  await fill(0, "3, 7", "1", "7", "2");
  await page.getByRole("button", { name: "Run my cases" }).click();
  await expect(shows).toContainText("Your cases tell 2 of the 4 authored faulty versions apart", { timeout: 60_000 });
  await expect(page.getByRole("region", { name: "The faulty versions" })).toContainText("Version A: Leaves out values equal to hi. Told apart by case 1.");
});
