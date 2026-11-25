import AxeBuilder from "@axe-core/playwright";

import { expect, setTheme, test } from "./fixtures";
import { TRACK, api, newAccount, signIn, signInApi } from "./preparation-journey";

/**
 * New practice updates the plan when the learner asks (Volume 13, prompt 1; docs/PLAN_UPDATES.md),
 * against the real API: practice outside the plan is named in one line on Today and the plan page;
 * not updating keeps the version through a reload, a second tab and a fresh sign-in; two tabs pressing
 * "Update my plan" make one version and the second is told and shown it. Practice the planner doesn't
 * use offers nothing. Synthetic data.
 */
const WEAK =
  "Patient assessment is something every nurse does on the ward. It is part of the job and it is " +
  "important to do it well because patients depend on nurses. I do it on my shifts like everyone else " +
  "on the team and I think it is a key skill to have in this job.";
const OUTSIDE = "e-good-0"; // not in a new nurse's first plan
const RETRY = "Retry: What good patient assessment looks like";
const LINE = /^1 answer since this plan, below 70\. Your plan stays as it is until you update it\.$/;

type PlanBody = { version: number; news: { text: string } | null };

test("new practice is named, the plan waits until asked, and two tabs updating make one version", async ({ page, context, browser, request }) => {
  const acct = await newAccount(request, "plan-upd");
  await signIn(page, acct.email);
  await page.goto("/dashboard");
  const today = page.getByRole("region", { name: "Today's practice" });
  await expect(today.getByRole("article", { name: "Baseline check: 3 short questions" })).toBeVisible(); // version 1
  const weak = await api<{ score: number }>(request, acct.auth, "post", `/api/v1/careers/${TRACK}/questions/${OUTSIDE}/answers`, { answer: WEAK });
  expect(weak.score).toBeLessThan(70);

  // Said on Today and the plan page, with one button; nothing updates by itself.
  await page.reload();
  await expect(today.getByRole("region", { name: LINE }).getByRole("button", { name: "Update my plan" })).toBeVisible();
  await page.goto("/plan");
  await expect(page.getByText(/^Version 1\./)).toBeVisible();
  const news = page.getByRole("region", { name: LINE });
  await news.getByText("What's new (1)").click();
  await expect(news.getByRole("link", { name: "Answer: What good patient assessment looks like" })).toBeVisible();
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const result = await new AxeBuilder({ page }).include("main").withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    expect(result.violations.map((v) => v.id), theme).toEqual([]);
  }

  // Not updating: a reload, a second tab and a fresh sign-in elsewhere show the same version.
  await page.reload();
  await expect(page.getByText(/^Version 1\./)).toBeVisible();
  const tab = await context.newPage();
  await tab.goto("/plan");
  await expect(tab.getByText(/^Version 1\./)).toBeVisible();
  await expect(tab.getByRole("region", { name: LINE })).toBeVisible();
  const elsewhere = await browser.newContext();
  const device = await elsewhere.newPage();
  await signIn(device, acct.email);
  await device.goto("/plan");
  await expect(device.getByText(/^Version 1\./)).toBeVisible();
  await elsewhere.close();
  expect((await api<PlanBody>(request, await signInApi(request, acct.email), "get", "/api/v1/me/plan")).version).toBe(1);

  // The second tab updates first: the retry is there and the notes say why.
  await tab.getByRole("region", { name: LINE }).getByRole("button", { name: "Update my plan" }).click();
  await expect(tab.getByText("Your plan is now version 2. What changed is listed with it.")).toBeFocused();
  await expect(tab.getByText(/^Version 2\./)).toBeVisible();
  await expect(tab.getByRole("article", { name: RETRY }).first()).toBeVisible();
  await expect(tab.getByText("Updated when you asked: 1 answer since version 1, below 70.")).toBeVisible();

  // This tab still shows version 1: pressing tells it, and shows version 2. One version was made.
  await news.getByRole("button", { name: "Update my plan" }).click();
  await expect(page.getByText("Your plan was already updated, in another tab or on another device: this is version 2.")).toBeVisible();
  await expect(page.getByText(/^Version 2\./)).toBeVisible();
  await expect(page.getByRole("button", { name: "Update my plan" })).toHaveCount(0);
  const after = await api<PlanBody>(request, acct.auth, "get", "/api/v1/me/plan");
  expect(after.version).toBe(2);
  expect(after.news).toBeNull();
});

test("practice the planner doesn't use offers no update", async ({ page, request }) => {
  const acct = await newAccount(request, "plan-unused");
  await signIn(page, acct.email);
  await page.goto("/dashboard");
  await expect(page.getByRole("region", { name: "Today's practice" }).getByRole("article", { name: "Baseline check: 3 short questions" })).toBeVisible();
  // Too short to score, on one question; weak but disputed as a whole, on another.
  await api(request, acct.auth, "post", `/api/v1/careers/${TRACK}/questions/e-good-1/answers`, { answer: "I would check it again." });
  const disputed = await api<{ id: string; score: number }>(request, acct.auth, "post", `/api/v1/careers/${TRACK}/questions/${OUTSIDE}/answers`, { answer: WEAK });
  expect(disputed.score).toBeLessThan(70);
  await api(request, acct.auth, "post", `/api/v1/me/answers/${disputed.id}/flags`, { criterion: "Overall", kind: "disagree" });

  await page.goto("/plan");
  await expect(page.getByText(/^Version 1\./)).toBeVisible();
  await expect(page.getByRole("button", { name: "Update my plan" })).toHaveCount(0);
  await page.goto("/dashboard");
  await expect(page.getByRole("region", { name: "Today's practice" }).getByText(/Session estimate/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Update my plan" })).toHaveCount(0);
});
