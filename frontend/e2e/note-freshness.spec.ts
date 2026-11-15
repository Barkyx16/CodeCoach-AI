import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

import { expect, test } from "./fixtures";
import { E2E_DATABASE_URL } from "./ports";
import { TRACK, api, newAccount, signIn } from "./preparation-journey";

/**
 * A note knows where it came from (Volume 13, prompt 6; docs/STORY_FRESHNESS.md, "Notes"), against
 * the real API: a note captured from a question records its version; a correction published by an
 * admin (granted from the command line) makes the note say so, side by side, above its snapshot, and
 * the notebook marks it "Source updated"; "Mark reviewed" clears the notice and leaves the note's
 * text exactly as it was. Synthetic data; a question no other spec uses, since corrections are shared.
 */
const QID = "e-learn-0"; // "Getting better at patient assessment"
const PROMPT_V2 = "If you had three months to get noticeably better at assessing patients on your ward, what would you do first?";

function grantAdmin(email: string) {
  execFileSync(process.env.PYTHON ?? "python", ["-m", "app.cli", "grant-admin", email], {
    cwd: resolve(process.cwd(), "../backend"),
    env: { ...process.env, DATABASE_URL: E2E_DATABASE_URL, SECRET_KEY: "e2e-secret-key-that-is-at-least-32-characters" },
  });
}

test("a corrected question is said on the note, and Mark reviewed leaves the note as it was", async ({ page, request }) => {
  const acct = await newAccount(request, "note-fresh");
  const note = await api<{ id: string; body: string; revision: number; updated_at: string; source: { version: string } }>(request, acct.auth, "post", "/api/v1/me/notes", {
    title: "Assessment plan", body: "Shadow the charge nurse; practise head-to-toe checks.",
    source: { type: "question", id: QID, track: TRACK }, excerpt: "If you wanted to get noticeably better at patient assessment…", excerpt_kind: "quote",
  });
  expect(note.source.version).toBe("1");
  const root = await newAccount(request, "note-fresh-admin");
  grantAdmin(root.email);
  const meta = await api<{ version: number }>(request, root.auth, "get", `/api/v1/content/question/${TRACK}/${QID}/meta`);
  await api(request, root.auth, "post", `/api/v1/admin/content/question/${TRACK}/${QID}/corrections`, {
    prompt: PROMPT_V2, change_note: "Asks what you'd do first.", significant: true,
  });
  await signIn(page, acct.email);

  await page.goto("/notes");
  const row = page.locator(".notes-list__item").filter({ hasText: "Assessment plan" });
  await expect(row).toContainText("Source updated");
  const filter = page.getByRole("checkbox", { name: "Source updated" });
  await filter.click(); // the filter lives in the URL, so it shows as checked once the URL changes
  await expect(page).toHaveURL(/updated=1/);
  await expect(filter).toBeChecked();
  await expect(page.locator(".notes-list__item")).toHaveCount(1);
  await row.getByRole("link", { name: "Assessment plan" }).click();

  const notice = page.getByRole("region", { name: "Source updated" });
  const next = meta.version + 1;
  await expect(notice).toContainText(`The question changed since you captured this note (version 1, now ${next}).`);
  await expect(notice).toContainText(PROMPT_V2);
  await expect(notice).toContainText(`Version ${next}: Asks what you'd do first.`);
  await notice.getByRole("button", { name: `Mark reviewed (version ${next})` }).click();
  await expect(page.getByText(/^You marked it reviewed at version \d+ on .+ Your note wasn't changed\.$/)).toBeFocused();
  await expect(notice).toHaveCount(0);

  const after = await api<{ body: string; revision: number; updated_at: string; source_updated: boolean; freshness: { state: string } }>(request, acct.auth, "get", `/api/v1/me/notes/${note.id}`);
  expect([after.body, after.revision, after.updated_at]).toEqual([note.body, note.revision, note.updated_at]);
  expect([after.source_updated, after.freshness.state]).toEqual([false, "current"]);
  await page.goto("/notes");
  await expect(page.locator(".notes-list__item").filter({ hasText: "Assessment plan" })).not.toContainText("Source updated");
});
