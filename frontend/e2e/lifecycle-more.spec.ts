import { expect, test } from "./fixtures";
import { JD, TRACK, api, newAccount, signIn } from "./preparation-journey";

/**
 * More previews before archive and delete (Volume 13, prompt 5; docs/LIFECYCLE.md), against the real
 * API: deleting a story chosen by a kit lists the kit as kept and the application as unlinked, and the
 * kit then keeps what it prepared; deleting a pinned note says how long Undo lasts, and Undo brings it
 * back pinned; archiving the active target lists what it keeps, and it stops being active.
 * Synthetic data.
 */
test("story delete, note delete and target archive: each preview is what happens", async ({ page, request }) => {
  const acct = await newAccount(request, "life-more");
  const { auth } = acct;
  const story = await api<{ id: string }>(request, auth, "post", "/api/v1/me/stories", { title: "Two call lights", situation: "A busy night shift." });
  const app = await api<{ id: string }>(request, auth, "post", "/api/v1/me/applications", {
    employer: "Synthetic Hospital", role_title: "Ward nurse", stage: "interviewing", story_ids: [story.id],
  });
  const ev = (await api<{ events: { id: string }[] }>(request, auth, "post", `/api/v1/me/applications/${app.id}/events`, { title: "Panel interview", on_date: "2030-01-10" })).events[0]!;
  await api(request, auth, "put", `/api/v1/me/applications/${app.id}/events/${ev.id}/kit`, { story_ids: [story.id] });
  const note = await api<{ id: string }>(request, auth, "post", "/api/v1/me/notes", { title: "Handover phrases", body: "SBAR first." });
  await api(request, auth, "patch", `/api/v1/me/notes/${note.id}`, { pinned: true });
  const target = await api<{ id: string; selected: boolean }>(request, auth, "post", "/api/v1/targets", { title: "Ward Nurse", employer: "Synthetic Hospital", description: JD, track: TRACK });
  expect(target.selected).toBe(true);
  await signIn(page, acct.email);

  // A story: the kit that chose it is kept, the application is unlinked; nothing goes until asked.
  await page.goto(`/stories/${story.id}`);
  await page.getByRole("button", { name: "Delete…" }).click();
  const storyPlan = page.getByRole("group", { name: "What this will do" });
  await expect(storyPlan).toContainText("Story: Two call lights");
  await expect(storyPlan).toContainText("Interview-day kit: Kit for Panel interview Keeps what it prepared from this story");
  await expect(storyPlan).toContainText("Application: Ward nurse at Synthetic Hospital Stays in your applications; it no longer lists this story.");
  await storyPlan.getByRole("button", { name: "Delete this story, its revisions" }).click();
  await expect(page).toHaveURL(/\/stories$/);
  const kit = await api<{ stories: { id: string }[]; kept_stories: { id: string; title: string }[] }>(request, auth, "get", `/api/v1/me/applications/${app.id}/events/${ev.id}/kit`);
  expect(kit.stories.map((s) => s.id)).not.toContain(story.id);
  expect(kit.kept_stories.map((s) => s.title)).toEqual(["Two call lights"]); // as listed
  const after = await api<{ stories: { id: string }[] }>(request, auth, "get", `/api/v1/me/applications/${app.id}`);
  expect(after.stories).toEqual([]);

  // A pinned note: the preview says how long Undo lasts; Undo brings it back exactly, pinned.
  await page.goto(`/notes/${note.id}`);
  await page.getByRole("button", { name: "Delete…" }).click();
  const notePlan = page.getByRole("group", { name: "What this will do" });
  await expect(notePlan).toContainText("Restorable for 10 minutes after you delete it (Undo), exactly as it is now");
  await expect(notePlan).toContainText("Pin: Pinned to the top of your notes Restoring it brings it back pinned.");
  await notePlan.getByRole("button", { name: "Delete this note (you can undo it for 10 minutes)" }).click();
  await expect(page.getByText(/Deleted “Handover phrases”\. You can undo this until \d{1,2}:\d{2}/)).toBeVisible();
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByRole("link", { name: "Handover phrases" })).toBeVisible();
  const restored = await api<{ pinned: boolean; body: string }>(request, auth, "get", `/api/v1/me/notes/${note.id}`);
  expect([restored.pinned, restored.body]).toEqual([true, "SBAR first."]);

  // The active target: archiving says it stops being active and keeps its requirements; it does that.
  await page.goto(`/targets/${target.id}`);
  await page.getByRole("button", { name: "Archive…" }).click();
  const targetPlan = page.getByRole("group", { name: "What this will do" });
  await expect(targetPlan).toContainText("Target: Ward Nurse");
  await expect(targetPlan).toContainText("Active target: Your active target It stops being your active target");
  await expect(targetPlan.getByText(/^Requirement:/).first()).toBeVisible();
  await targetPlan.getByRole("button", { name: "Archive this target" }).click();
  await expect(page.getByText(/^Archived Ward Nurse\. Unarchive it any time\./)).toBeFocused();
  await expect(page.getByRole("button", { name: "Unarchive" })).toBeVisible();
  const archived = await api<{ archived: boolean; selected: boolean; requirement_list: unknown[] }>(request, auth, "get", `/api/v1/targets/${target.id}`);
  expect([archived.archived, archived.selected]).toEqual([true, false]);
  expect(archived.requirement_list.length).toBeGreaterThan(0);
});
