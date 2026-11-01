import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

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
  await page.getByRole("link", { name: "Dashboard" }).click();
  const summary = page.getByRole("region", { name: "Summary" });
  await expect(summary.getByText("Solved")).toBeVisible();
  await expect(summary.getByText("1", { exact: true }).first()).toBeVisible();
});
