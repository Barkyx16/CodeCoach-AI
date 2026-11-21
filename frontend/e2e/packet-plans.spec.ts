import { readFile } from "node:fs/promises";

import { expect, test } from "./fixtures";
import { STRONG, api, newAccount, signIn } from "./preparation-journey";

/**
 * Accepted improvements and one interview's kit in the practice packet (Volume 13, prompt 7;
 * docs/PACKET.md), against the real API: the improvement says the weeks marked done as the plan page
 * does, and a new preview after marking another one done says so; the kit's checklist names the
 * improvement read now; its meeting link and a synthetic secret in its private notes are left out
 * and said; the saved file is the preview; the page has no sideways scroll at phone width.
 * Synthetic data.
 */
const SECRET = "CANARY-kit-notes-7f3a9-not-a-real-secret";
const LINK = "https://meet.example.com/abc-defg-hij";

test("an improvement and a kit go in the packet, read live, with the kit's private parts left out", async ({ page, request }) => {
  const acct = await newAccount(request, "packet-plans");
  const { auth } = acct;
  const iv = await api<{ id: string }>(request, auth, "post", "/api/v1/interviews", { kind: "questions", question_ids: ["e-accuracy-0"], duration_minutes: 15 });
  await api(request, auth, "post", `/api/v1/interviews/${iv.id}/answers`, { question_index: 0, answer: STRONG, source: "typed" });
  const review = await api<{ improvements: { key: string }[] }>(request, auth, "get", `/api/v1/interviews/${iv.id}/review`);
  const action = await api<{ id: string; title: string }>(request, auth, "post", "/api/v1/me/actions", { source: { interview_id: iv.id, key: review.improvements[0]!.key }, recurrence: "weekly" });
  const occ = (await api<{ occurrences: { id: string }[] }>(request, auth, "post", `/api/v1/me/actions/${action.id}/occurrences`, { on_date: "2026-11-16", weeks: 3 })).occurrences;
  await api(request, auth, "post", `/api/v1/me/actions/${action.id}/occurrences/${occ[0]!.id}/complete`);
  const app = await api<{ id: string }>(request, auth, "post", "/api/v1/me/applications", { employer: "Synthetic Hospital", role_title: "Ward nurse" });
  const ev = (await api<{ events: { id: string }[] }>(request, auth, "post", `/api/v1/me/applications/${app.id}/events`, { title: "Panel interview", on_date: "2030-01-10" })).events[0]!;
  await api(request, auth, "put", `/api/v1/me/applications/${app.id}/events/${ev.id}/kit`, {
    checklist: [{ id: "c1", text: "Bring my ID badge", origin: "yours" }, { id: "act-1", origin: "action", action_id: action.id, text: "" }],
    questions: [{ id: "q1", text: "How is handover done on the ward?", group: "team", origin: "yours" }],
    meeting_link: LINK, notes: `Parking code ${SECRET}`, interviewers: [{ name: "Dana Synthetic", role: "Ward manager" }],
  });
  await signIn(page, acct.email);

  await page.goto("/packet");
  await page.getByRole("checkbox", { name: new RegExp(`^${action.title.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`) }).check();
  const kits = page.getByRole("group", { name: "One interview's kit" });
  await expect(kits).toContainText("Has a meeting link, interviewers' names and private notes: left out unless you choose them.");
  await kits.getByRole("checkbox", { name: /^Panel interview: Ward nurse at Synthetic Hospital/ }).check();
  await page.getByRole("button", { name: "Preview packet" }).click();

  const view = page.getByRole("article", { name: "Packet preview" });
  await expect(view).toContainText("weekly, 1 of 3 weeks marked done");
  await expect(view).toContainText("A plan you made, not a measure of improvement.");
  await expect(view).toContainText(`[ ] ${action.title} (accepted improvement, weekly: 1 of 3 marked done)`);
  await expect(view).toContainText("The meeting link isn't included: choose “Meeting link” to add it.");
  await expect(view).not.toContainText(LINK);
  await expect(view).not.toContainText(SECRET);
  await expect(view).not.toContainText("Dana Synthetic");

  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Save as a text file" }).click()]);
  const text = await readFile((await download.path())!, "utf8");
  expect(text).toContain("weekly, 1 of 3 weeks marked done");
  expect(text).toContain(`## Checklist [Yours]`);
  expect(text).not.toContain(SECRET);
  expect(text).not.toContain(LINK);

  // Another week marked done on the plan page: a new preview reads it; the saved file doesn't change.
  await api(request, auth, "post", `/api/v1/me/actions/${action.id}/occurrences/${occ[1]!.id}/complete`);
  await page.getByRole("button", { name: "Preview again" }).click();
  await expect(view).toContainText("weekly, 2 of 3 weeks marked done");
  expect(text).not.toContain("2 of 3");

  // Phone width: nothing scrolls sideways, the long link-free kit and plan text included.
  await page.setViewportSize({ width: 360, height: 780 });
  await expect(view).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
