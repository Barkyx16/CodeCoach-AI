import { readFileSync } from "node:fs";

import type { Page } from "@playwright/test";

import { JUDGE_NEEDED, SE_TRACK, judgeReady, paste, submitAndJudge, verdict, type Sub } from "./engineer-journey";
import { expect, test } from "./fixtures";
import { ACCESS_LOG } from "./ports";
import { Recorder, api, newAccount, signIn } from "./preparation-journey";

/**
 * A second problem, on a phone, judged for real (Volume 17, prompt 10; docs/PREPARATION_JOURNEY.md,
 * "A second problem on a phone"). The engineer's other journeys use Two Sum; this one, in the mobile
 * project (a Pixel 7, 412 px wide), uses Valid Palindrome, offered by a target's requirement about
 * string processing. A failing solution (the reference with one line changed: it compares letters
 * with their case) fails a named public test, which the result then shows; a passing one, written
 * plainly (not the reference), passes. The requirement lists both, compared, in the same words as the
 * submission's own page. The lesson that prepares the debugging exercises is read, then the exercise
 * "Fix: Sentence Palindrome" is submitted and judged, and its result shows that help as its
 * conditions. History lists both kinds, each row opening its attempt. Every page is checked at 412
 * and at 360 px for sideways scrolling, and a canary typed into the code is never in the API's log.
 * Synthetic account and code only; the judge's verdicts are recorded as it gave them.
 */
test.skip(process.env.E2E_JUDGE !== "1", `This journey ${JUDGE_NEEDED}.`);

const PROBLEM = "valid-palindrome";
const PROBLEM_TITLE = "Valid Palindrome";
const EXERCISE = "debug-palindrome-sentence";
const EXERCISE_TITLE = "Fix: Sentence Palindrome";
const LESSON_TITLE = "Fixing code from a failing test";
const REQ_STRINGS = "Solid experience with string processing in Java";
const JD = `Software Engineer - Search
Requirements:
- ${REQ_STRINGS}
- Experience writing tests for production code
Responsibilities:
- Build and tune the query parser`;
const CANARY = "CANARY-second-problem-9d3f2-not-a-real-secret";
/** The reference solution with one line changed: letters are compared with their case. */
const FAILING = `class Solution {
    public boolean isPalindrome(String s) {
        int left = 0, right = s.length() - 1;
        while (left < right) {
            while (left < right && !Character.isLetterOrDigit(s.charAt(left))) left++;
            while (left < right && !Character.isLetterOrDigit(s.charAt(right))) right--;
            if (s.charAt(left) != s.charAt(right)) {
                return false;
            }
            left++;
            right--;
        }
        return true;
    }
}`;
/** The failing public test, by its input, as the result names it. */
const FAILED_TEST = "A man, a plan, a canal: Panama";
/** Written plainly, not the reference: keep letters and digits, lower-cased, and compare with the reverse. */
const PASSING = `class Solution {
    // Keep what counts, then read it both ways. (${CANARY})
    public boolean isPalindrome(String s) {
        StringBuilder kept = new StringBuilder();
        for (char c : s.toCharArray()) {
            if (Character.isLetterOrDigit(c)) {
                kept.append(Character.toLowerCase(c));
            }
        }
        String forward = kept.toString();
        return forward.equals(kept.reverse().toString());
    }
}`;
/** The learner's repair of the exercise (not the reference's text): compare lower-cased letters and digits. */
const REPAIR = `class Solution {
    public boolean isPalindrome(String s) {
        int i = 0;
        int j = s.length() - 1;
        while (i < j) {
            char a = Character.toLowerCase(s.charAt(i));
            char b = Character.toLowerCase(s.charAt(j));
            if (!Character.isLetterOrDigit(a)) {
                i++;
            } else if (!Character.isLetterOrDigit(b)) {
                j--;
            } else if (a != b) {
                return false;
            } else {
                i++;
                j--;
            }
        }
        return true;
    }
}`;

interface Requirement {
  id: string;
  text: string;
  comparisons: string | null;
  submissions: { submission_id: string; status: string; passed_count: number | null; total_count: number | null; outcome_text: string; compared: { comparison: { explanation: string } } | null }[];
}

/** No sideways scroll at the phone's own width (412 px) and at 360 px. */
async function fitsBothWidths(page: Page, where: string, checked: string[]): Promise<void> {
  const size = page.viewportSize()!;
  for (const width of [size.width, 360]) {
    await page.setViewportSize({ width, height: size.height });
    const fits = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
    expect(fits, `${where}: the page scrolls sideways at ${width} px`).toBe(true);
  }
  await page.setViewportSize(size);
  checked.push(where);
}

/** "Failed · 6 of 8 tests passed" and "Failed 6 of 8 tests passed" say the same words. */
const verdictWords = (text: string) => text.replace(/·/g, " ").replace(/\s+/g, " ").trim();

test("a requirement's compared code and a debugging exercise, judged for real on a phone", async ({ page, context, request }, info) => {
  test.setTimeout(300_000);
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const rec = new Recorder(info, "engineer-second-problem");
  const fitted: string[] = [];
  const phone = { made: "phone" as const, read: ["phone" as const] };
  try {
    const acct = await newAccount(request, "engineer-second", SE_TRACK);
    rec.facts.problem = PROBLEM;
    rec.facts.exercise = EXERCISE;
    rec.facts.language = "java";
    rec.facts.viewport = `${page.viewportSize()!.width}x${page.viewportSize()!.height}`;
    let targetId = "";
    let failing: Sub | null = null;
    let passing: Sub | null = null;
    let fix: Sub | null = null;
    const tab = (name: string) => page.getByRole("tab", { name, exact: true });

    await rec.step("The judge is ready", async (check) => {
      await judgeReady(request, acct, rec);
      check(`/capabilities: code execution on, the judge "ready", the coach "${rec.facts.ai_provider}"`);
    });
    await signIn(page, acct.email);

    await rec.step("A target whose requirement lists code", async (check) => {
      await page.goto("/targets");
      await page.getByRole("button", { name: "Add a target role" }).first().click();
      await page.getByLabel("Role title").fill("Search engineer");
      await page.getByLabel("Job description").fill(JD);
      await page.getByRole("button", { name: "Find requirements" }).click();
      await expect(page).toHaveURL(/\/targets\/[0-9a-f-]+$/);
      targetId = page.url().split("/").pop()!;
      rec.ids.target = targetId;
      const req = page.getByRole("article", { name: REQ_STRINGS });
      await expect(req).toContainText("Limited evidence: not practised yet");
      await expect(req.getByRole("link", { name: `Problem: ${PROBLEM_TITLE}` })).toBeVisible();
      await fitsBothWidths(page, "the target", fitted);
      check(`"${REQ_STRINGS}" offers "Problem: ${PROBLEM_TITLE}"; not practised yet; the page fits at 412 and 360 px`);
      await req.getByRole("link", { name: `Problem: ${PROBLEM_TITLE}` }).click();
      await expect(page).toHaveURL(new RegExp(`/problems/${PROBLEM}$`));
      check(`the link opens the ${PROBLEM_TITLE} workspace`);
    }, undefined, phone);

    await rec.step("A failing solution, judged for real, its failed test shown", async (check) => {
      await tab("Code").click();
      await expect(page.locator(".monaco-editor")).toBeVisible();
      await paste(page, FAILING);
      const { sub, seenMs } = await submitAndJudge(page, request, acct, "Some tests failed. Check the cases below.");
      expect(sub.status).toBe("FAILED");
      failing = sub;
      rec.ids.failing_submission = sub.id;
      rec.judged.push(verdict("A failing solution, judged for real, its failed test shown", sub, seenMs));
      const failed = page.getByRole("region", { name: "Submission results" }).locator(".case--fail").filter({ hasText: FAILED_TEST });
      await expect(failed).toContainText("expected true");
      await expect(failed).toContainText("got false");
      rec.facts.failed_test = `s = "${FAILED_TEST}": expected true, got false`;
      await fitsBothWidths(page, "the workspace with a failed result", fitted);
      check(`judged in the sandbox: ${sub.status}, ${sub.result!.passed_count}/${sub.result!.total_count}; the result names the failed test: s = "${FAILED_TEST}", expected true, got false`);
    }, ["real judge"], phone);

    await rec.step("A passing solution, written plainly, judged for real", async (check) => {
      await paste(page, PASSING);
      const { sub, seenMs } = await submitAndJudge(page, request, acct, "All tests passed. Nice work.");
      expect(sub.status).toBe("PASSED");
      expect(sub.compared?.previous.id).toBe(failing!.id);
      passing = sub;
      rec.ids.passing_submission = sub.id;
      rec.judged.push(verdict("A passing solution, written plainly, judged for real", sub, seenMs));
      check(`judged in the sandbox: ${sub.status}, ${sub.result!.passed_count}/${sub.result!.total_count}; compared with the failing one: "${sub.compared!.comparison.explanation}"`);
    }, ["real judge"], phone);

    await rec.step("The requirement lists both, compared, in the submission page's words", async (check) => {
      const t = await api<{ requirement_list: Requirement[] }>(request, acct.auth, "get", `/api/v1/targets/${targetId}`);
      const r = t.requirement_list.find((x) => x.text === REQ_STRINGS)!;
      expect(r.submissions.map((s) => s.submission_id)).toEqual([passing!.id, failing!.id]);
      const newest = r.submissions[0]!;
      expect(newest.compared?.comparison.explanation).toBe(passing!.compared!.comparison.explanation);
      rec.facts.requirement_comparisons = r.comparisons;
      await page.goto(`/targets/${targetId}`);
      const latest = page.getByRole("list", { name: `Your latest submissions for ${REQ_STRINGS}` });
      const items = latest.getByRole("listitem");
      await expect(items).toHaveCount(2);
      const onTarget: string[] = [];
      for (const [i, s] of [[0, passing!], [1, failing!]] as const) {
        const item = items.nth(i);
        // Its verdict and counts, as the requirement shows them (the badge, then "· N of M tests passed …").
        const badge = (await item.locator(".badge").first().textContent()) ?? "";
        const counts = (await item.locator(".subtle").filter({ hasText: "tests passed" }).textContent()) ?? "";
        expect(counts).toContain(`${s.result!.passed_count} of ${s.result!.total_count} tests passed`);
        onTarget.push(verdictWords(`${badge} ${counts}`));
      }
      await expect(page.getByRole("article", { name: REQ_STRINGS })).toContainText(r.comparisons!);
      await fitsBothWidths(page, "the target with both submissions", fitted);
      // The outcome links to the comparison on the passing submission's own page.
      await items.first().getByRole("link", { name: newest.outcome_text }).click();
      await expect(page).toHaveURL(new RegExp(`/history/submissions/${passing!.id}#comparison$`));
      const section = page.getByRole("region", { name: "Compared with your previous submission" });
      await expect(section).toBeVisible();
      const lines = section.getByRole("listitem");
      // Each line less its "Earlier, <time>:" or "This one:" lead (a time has a colon of its own).
      const lineWords = async (i: number) => {
        const line = lines.nth(i);
        const lead = (await line.locator(".submission-compared__when").textContent()) ?? "";
        return verdictWords(((await line.textContent()) ?? "").slice(lead.length));
      };
      const earlier = await lineWords(0);
      const thisOne = await lineWords(1);
      expect([thisOne, earlier], "the requirement's verdicts and counts are the page's, word for word").toEqual(onTarget);
      await expect(section).toContainText(passing!.compared!.comparison.explanation);
      rec.facts.requirement_says = onTarget.join(" | ");
      rec.facts.page_says = [thisOne, earlier].join(" | ");
      await fitsBothWidths(page, "the passing submission's page", fitted);
      check(`the requirement lists both, newest first: "${onTarget.join("\", \"")}" with "${newest.outcome_text}"; its line: "${r.comparisons}"`);
      check(`its outcome opens the submission's own comparison, which says "${thisOne}" and "${earlier}", word for word, and "${passing!.compared!.comparison.explanation}"`);
    }, undefined, phone);

    await rec.step("The lesson that prepares the exercise, read", async (check) => {
      await page.goto(`/problems/${EXERCISE}`);
      const learn = page.getByRole("region", { name: "Learn first" });
      await learn.getByRole("link", { name: LESSON_TITLE }).click();
      await expect(page.getByRole("heading", { name: LESSON_TITLE, level: 1 })).toBeVisible();
      await page.getByRole("button", { name: "I've read this unit" }).click();
      await expect(page.getByText(/Marked as read for version \d+\./)).toBeVisible();
      await fitsBothWidths(page, "the lesson", fitted);
      check(`"${LESSON_TITLE}", opened from the exercise's "Learn first", marked as read`);
    }, undefined, phone);

    await rec.step("The debugging exercise, submitted and judged, its conditions shown", async (check) => {
      await page.goto(`/problems/${EXERCISE}`);
      await tab("Code").click();
      await expect(page.locator(".monaco-editor")).toBeVisible();
      await paste(page, REPAIR);
      const debrief = page.getByRole("region", { name: "Debugging debrief" });
      const { sub, seenMs } = await submitAndJudge(page, request, acct, "All tests passed. Nice work.");
      expect(sub.status).toBe("PASSED");
      await expect(debrief.getByRole("heading", { name: "Fixed: every test passes" })).toBeVisible();
      fix = sub;
      rec.ids.exercise_submission = sub.id;
      rec.judged.push(verdict("The debugging exercise, submitted and judged, its conditions shown", sub, seenMs));
      expect(sub.conditions?.labels).toEqual(["Hint shown"]);
      await fitsBothWidths(page, "the exercise with its debrief", fitted);
      await page.goto(`/history/submissions/${sub.id}`);
      const conditions = page.locator(".attempt-conditions");
      await expect(conditions).toContainText("In-app help before this attempt: Hint shown");
      await expect(conditions).toContainText(`Lesson “${LESSON_TITLE}” read`);
      rec.facts.exercise_conditions = (await conditions.innerText()).split(/\s*\n+\s*/).filter(Boolean).join(" / ");
      await fitsBothWidths(page, "the exercise's submission page", fitted);
      check(`judged in the sandbox: ${sub.status}, ${sub.result!.passed_count}/${sub.result!.total_count}; "Fixed: every test passes"; its page: "${rec.facts.exercise_conditions}"`);
    }, ["real judge"], phone);

    await rec.step("History lists both kinds, each opening its attempt", async (check) => {
      await page.goto("/history");
      for (const [name, s] of [[PROBLEM_TITLE, passing!], [PROBLEM_TITLE, failing!], [EXERCISE_TITLE, fix!]] as const) {
        const link = page.locator(`a[href="/history/submissions/${s.id}"]`).filter({ hasText: name });
        await expect(link.first()).toBeVisible();
      }
      await fitsBothWidths(page, "History", fitted);
      await page.locator(`a[href="/history/submissions/${fix!.id}"]`).first().click();
      await expect(page).toHaveURL(new RegExp(`/history/submissions/${fix!.id}$`));
      await expect(page.locator(".attempt-conditions")).toContainText("Hint shown");
      await page.goBack();
      await page.locator(`a[href="/history/submissions/${failing!.id}"]`).first().click();
      await expect(page).toHaveURL(new RegExp(`/history/submissions/${failing!.id}$`));
      check(`History lists the two ${PROBLEM_TITLE} submissions and "${EXERCISE_TITLE}", each by its id; the exercise's row and the failing one's open those attempts`);
    }, undefined, phone);

    await rec.step("Nothing typed reached the API's log", async (check) => {
      expect(readFileSync(ACCESS_LOG, "utf8")).not.toContain(CANARY);
      check("the canary typed into the passing solution isn't in the API's log");
      rec.facts.fitted = fitted.join(", ");
      check(`no sideways scroll at 412 or 360 px on: ${fitted.join("; ")}`);
    });
  } finally {
    rec.write(true);
  }
});
