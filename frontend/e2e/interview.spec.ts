import { expect, test } from "@playwright/test";

const ANSWERS = [
  "Can the array contain duplicates, and is there always exactly one valid pair?",
  "I'd use a hash map from value to index and make a single pass, checking for target minus the current number before inserting it.",
  "Done. One pass with a HashMap, and I check the complement before storing the current value.",
  "Time complexity is O(n) because each element is visited once, and space is O(n) for the map.",
  "I'd test the given example, duplicates like [3,3], negative numbers and the smallest input of two elements.",
];

const CODE = `class Solution {
    public int[] twoSum(int[] nums, int target) {
        Map<Integer, Integer> seen = new HashMap<>();
        for (int i = 0; i < nums.length; i++) {
            Integer j = seen.get(target - nums[i]);
            if (j != null) return new int[] {j, i};
            seen.put(nums[i], i);
        }
        return new int[0];
    }
}`;

test("mock interview: five phases, real editor, rubric feedback, history", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await expect(page).toHaveURL(/two-sum/);

  await page.getByRole("link", { name: "Interview" }).click();
  await page.getByLabel("Problem").selectOption("two-sum");
  await page.getByText("15 min").click();
  await page.getByRole("button", { name: "Start interview" }).click();
  await expect(page).toHaveURL(/\/interviews\/[0-9a-f-]+$/);
  await expect(page.getByText(/we'll work on "Two Sum"/)).toBeVisible();
  await expect(page.getByRole("timer")).toHaveText(/^1[45]:\d\d$/);
  await expect(page.locator(".monaco-editor")).toBeVisible();

  const box = page.getByLabel("Your answer");
  for (const [i, answer] of ANSWERS.entries()) {
    if (i === 2) {
      // Write the solution in the real Monaco editor before telling the interviewer it's done.
      await page.locator(".monaco-editor").first().click();
      await page.keyboard.press("ControlOrMeta+A");
      await page.keyboard.press("Delete");
      await page.evaluate((text) => navigator.clipboard.writeText(text), CODE);
      await page.keyboard.press("ControlOrMeta+V");
    }
    await box.fill(answer);
    await page.getByRole("button", { name: "Send" }).click();
    await expect(page.getByText(answer)).toBeVisible();
    await expect(page.getByLabel("Interviewer is typing")).toHaveCount(0);
  }
  await expect(page.getByText(/Click Finish to see your feedback/).first()).toBeVisible();
  await page.screenshot({ path: "e2e/screenshots/06-interview-live.png" });

  await page.getByRole("button", { name: "Finish & get feedback" }).click();
  await expect(page.getByRole("heading", { name: "Interview feedback" })).toBeVisible();
  const rubric = page.getByRole("list", { name: /rubric scores/i });
  await expect(rubric.getByRole("listitem")).toHaveCount(5);
  await expect(rubric.getByText("Complexity analysis")).toBeVisible();
  await page.screenshot({ path: "e2e/screenshots/07-interview-feedback.png", fullPage: true });

  await page.getByRole("link", { name: "History" }).click();
  await page.getByRole("tab", { name: "Interviews" }).click();
  await expect(page.getByRole("link", { name: /Two Sum/ })).toBeVisible();
});
