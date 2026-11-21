import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

import { expect, test } from "./fixtures";
import { E2E_DATABASE_URL } from "./ports";
import { TRACK, api, newAccount, signIn } from "./preparation-journey";

/**
 * A saved item knows its version (Volume 14, prompt 7; docs/STORY_FRESHNESS.md, "Saved items and
 * collections"), against the real API: a question saved at version 1, then corrected by an admin
 * (granted from the command line), is badged "Source updated" on the saved list and in a
 * collection's practice queue; the saved list filters by it; "Mark reviewed" shows what changed,
 * records the version shown and clears the badge, and the saved item stays exactly where it was.
 * Synthetic data; a question no other spec uses, since corrections are shared.
 */
const QID = "e-tool-1"; // "Working with IV pumps"
const PROMPT_V2 = "How comfortable are you with IV pumps? Tell us how you've used one, or how you'd get up to speed safely.";

function grantAdmin(email: string) {
  execFileSync(process.env.PYTHON ?? "python", ["-m", "app.cli", "grant-admin", email], {
    cwd: resolve(process.cwd(), "../backend"),
    env: { ...process.env, DATABASE_URL: E2E_DATABASE_URL, SECRET_KEY: "e2e-secret-key-that-is-at-least-32-characters" },
  });
}

test("a corrected saved question is badged, filtered and reviewed, and stays saved as it was", async ({ page, request }) => {
  const acct = await newAccount(request, "saved-fresh");
  const item = { item_type: "question", track: TRACK, ref_id: QID };
  const [saved] = (await api<{ id: string; ref_id: string; content_version: number; created_at: string }[]>(request, acct.auth, "put", "/api/v1/me/bookmarks", item)).filter((b) => b.ref_id === QID);
  const other = { item_type: "question", track: TRACK, ref_id: "e-good-0" };
  await api(request, acct.auth, "put", "/api/v1/me/bookmarks", other);
  const c = await api<{ id: string }>(request, acct.auth, "post", "/api/v1/me/collections", { name: "IV prep" });
  await api(request, acct.auth, "post", `/api/v1/me/collections/${c.id}/items`, item);
  const meta = await api<{ version: number }>(request, acct.auth, "get", `/api/v1/content/question/${TRACK}/${QID}/meta`);
  expect(saved!.content_version).toBe(meta.version);
  const root = await newAccount(request, "saved-fresh-admin");
  grantAdmin(root.email);
  await api(request, root.auth, "post", `/api/v1/admin/content/question/${TRACK}/${QID}/corrections`, {
    prompt: PROMPT_V2, change_note: "Asks about using one safely.", significant: true,
  });
  const next = meta.version + 1;
  await signIn(page, acct.email);

  // The queue badges it too.
  await page.goto(`/saved/collections/${c.id}/practice`);
  await expect(page.locator(".queue-current")).toContainText("Source updated");

  await page.goto("/saved");
  const marks = page.getByRole("region", { name: "Bookmarks" });
  const row = marks.locator(".saved-list__item").filter({ hasText: "Working with IV pumps" });
  await expect(row).toContainText("Source updated");
  const filter = page.getByRole("checkbox", { name: "Source updated (1)" });
  await filter.click();
  await expect(page).toHaveURL(/updated=1/);
  await expect(marks.locator(".saved-list__item")).toHaveCount(1);
  await row.getByText("What changed").click();
  await expect(row).toContainText(`The question changed since you saved this item (version ${meta.version}, now ${next}).`);
  await expect(row).toContainText(PROMPT_V2);
  await expect(row).toContainText(`Version ${next}: Asks about using one safely.`);
  await row.getByRole("button", { name: `Mark reviewed (version ${next}): Working with IV pumps` }).click();
  await expect(page.getByText(`Marked reviewed at version ${next}. Nothing about the saved item changed.`)).toBeVisible();
  await expect(row).not.toContainText("Source updated");

  // Stays saved, as it was; the collection's own copy still asks (it's reviewed there).
  const stored = await api<{ id: string; ref_id: string; content_version: number; created_at: string; freshness: { state: string } }[]>(request, acct.auth, "get", "/api/v1/me/bookmarks");
  const after = stored.find((b) => b.ref_id === QID)!;
  expect([after.id, after.content_version, after.created_at, after.freshness.state]).toEqual([saved!.id, meta.version, saved!.created_at, "current"]);
  expect(stored).toHaveLength(2);
  const coll = await api<{ item_list: { ref_id: string; freshness: { state: string } }[] }>(request, acct.auth, "get", `/api/v1/me/collections/${c.id}`);
  expect(coll.item_list.map((i) => [i.ref_id, i.freshness.state])).toEqual([[QID, "needs_review"]]);
});
