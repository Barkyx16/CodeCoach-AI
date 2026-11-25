import { readFile } from "node:fs/promises";

import { expect, test } from "./fixtures";
import { api, newAccount, signIn } from "./preparation-journey";

/**
 * A real-interview reflection in the practice packet (Volume 14, prompt 8; docs/PACKET.md) against
 * the real API: chosen with its usual parts, a synthetic secret in what was noticed is in neither the
 * preview nor the saved file; edited after previewing, "Preview again" shows the new text while the
 * file saved before keeps the old; at 360 px a long reflection doesn't scroll sideways. Synthetic data.
 */
const SECRET = "CANARY-reflection-notes-5e1b2-not-a-real-secret";
const LONG = "Explained my handover routine step by step, ".repeat(40) + "Supercalifragilisticexpialidociousbutlongerstillwithnobreaksatall".repeat(3);

async function seed(request: Parameters<typeof newAccount>[0], prefix: string) {
  const acct = await newAccount(request, prefix);
  const app = await api<{ id: string }>(request, acct.auth, "post", "/api/v1/me/applications", { employer: "Mercy General", role_title: "Ward nurse", stage: "interviewing" });
  const ev = (await api<{ events: { id: string }[] }>(request, acct.auth, "post", `/api/v1/me/applications/${app.id}/events`, { title: "Panel interview", on_date: "2026-11-12" })).events[0]!;
  const url = `/api/v1/me/applications/${app.id}/events/${ev.id}/reflection`;
  const saved = await api<{ revision: number }>(request, acct.auth, "put", url, {
    questions: ["How would you handle a medication error?"], topics: ["patient assessment"],
    clear: "My opening about the ward", difficult: "The medication question", follow_ups: "Send my references by Friday",
    observations: [{ text: `They disliked me ${SECRET}`, kind: "interpretation" }], practice: [], story_ids: [], expected_revision: 0,
  });
  return { ...acct, url, revision: saved.revision };
}

test("a reflection goes into the packet part by part, and what was noticed stays out unless chosen", async ({ page, request }) => {
  const acct = await seed(request, "packet-reflection");
  await signIn(page, acct.email);
  await page.goto("/packet");
  await page.getByRole("checkbox", { name: /Reflection on Panel interview: Ward nurse at Mercy General/ }).check();
  await page.getByRole("button", { name: "Preview packet" }).click();
  const preview = page.getByRole("article", { name: "Packet preview" });
  await expect(preview).toContainText("My opening about the ward");
  await expect(preview).toContainText("What you noticed isn't included: choose “What you noticed” to add it.");
  await expect(preview).not.toContainText(SECRET);
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Save as a text file" }).click()]);
  const before = await readFile((await download.path())!, "utf8");
  expect(before).toContain("My opening about the ward");
  expect(before).not.toContain(SECRET);

  // Edited after previewing: Preview again shows the new words; the file already saved keeps the old.
  await api(request, acct.auth, "put", acct.url, {
    questions: ["How would you handle a medication error?"], topics: [], clear: "Explaining my handover routine", difficult: "",
    follow_ups: "", observations: [{ text: `They disliked me ${SECRET}`, kind: "interpretation" }], practice: [], story_ids: [], expected_revision: acct.revision,
  });
  await page.getByRole("button", { name: "Preview again" }).click();
  await expect(preview).toContainText("Explaining my handover routine");
  await expect(preview).not.toContainText(SECRET);
  expect(before).not.toContain("Explaining my handover routine");
  expect(before).toContain("My opening about the ward");
});

test("at 360 px a long reflection in the packet doesn't scroll sideways", async ({ page, request }) => {
  const acct = await seed(request, "packet-reflection-narrow");
  await api(request, acct.auth, "put", acct.url, {
    questions: [`How would you hand over ${"averyveryverylongwordwithoutanybreaks".repeat(5)}?`], topics: [], clear: LONG, difficult: "", follow_ups: "", observations: [], practice: [], story_ids: [], expected_revision: acct.revision,
  });
  await page.setViewportSize({ width: 360, height: 780 });
  await signIn(page, acct.email);
  await page.goto("/packet");
  await page.getByRole("checkbox", { name: /Reflection on Panel interview/ }).check();
  await page.getByRole("button", { name: "Preview packet" }).click();
  await expect(page.getByRole("article", { name: "Packet preview" })).toContainText("Explained my handover routine");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
