import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

import { devices, expect, type APIRequestContext, type Browser, type Page, type TestInfo } from "./fixtures";
import { ACCESS_LOG, API_URL, E2E_DATABASE_URL } from "./ports";
import { MIDDLING, Recorder, STRONG, answerRound, api, newAccount, signIn, signInApi } from "./preparation-journey";

/**
 * One account on two devices and through a backup (Volume 15, prompt 10; docs/PREPARATION_JOURNEY.md,
 * "Two devices and a restore"): what's chosen, saved and dismissed on a desktop window reads the same
 * on a phone-sized one, by id; an answer made on the phone shows on the desktop after a reload, with
 * both open at once; then a version 2 backup, the collection and the improvement deleted, restored
 * from the file with their ids, versions and reviews, and the restore undone. Synthetic data only.
 */
const TRACK = "registered-nurse";
const ANSWERED = "e-inform-0"; // answered twice on the desktop; its reviewed follow-up is then offered
const FOLLOW_UP_TITLE = "Keeping patients' families informed";
const CORRECTED = "e-inform-3"; // "Keeping charge nurses informed": corrected by an admin, so the collection asks for a review
const CORRECTED_TITLE = "Keeping charge nurses informed";
const ROUND = ["e-good-0", "e-steps-0", "e-time-0"];
export const DESKTOP_CANARY = "CANARY-desktop-4b21e-not-a-real-secret";
export const PHONE_CANARY = "CANARY-phone-9c07d-not-a-real-secret";
const FIRST = "Every morning I tell each patient the plan for the day: tests, medicines and when the doctor will come. " +
  "When something changes I go back and explain it in plain words, check they understood by asking them to tell me " +
  `the plan, and write it on the whiteboard in the room. Patients asked fewer worried questions and complaints dropped. (${DESKTOP_CANARY})`;
const SECOND = FIRST + " I also note what each patient asked so the next shift can keep them informed the same way.";
const PHONE_ANSWER = "On a busy night shift two of my patients got worse within an hour. I told the charge nurse straight away " +
  "which patients had changed, what I had already done, what was still pending and what help I needed, using SBAR so it was " +
  "quick and clear. I repeated back the plan she gave me and wrote it on the board. When I couldn't reach her I asked the " +
  "nurse in charge of the next bay. Both patients were reviewed within twenty minutes and nothing was missed at handover. " +
  `(${PHONE_CANARY})`;
const COLLECTION = "Night shift";
const CORRECTIONS = [
  "Tell us how you keep the charge nurse up to date on a busy shift, and what you do when you can't reach them.",
  "Tell us how you keep the charge nurse informed during a busy shift, and what you do when you can't reach them.",
];

function grantAdmin(email: string) {
  execFileSync(process.env.PYTHON ?? "python", ["-m", "app.cli", "grant-admin", email], {
    cwd: resolve(process.cwd(), "../backend"),
    env: { ...process.env, DATABASE_URL: E2E_DATABASE_URL, SECRET_KEY: "e2e-secret-key-that-is-at-least-32-characters" },
  });
}

async function noSidewaysScroll(page: Page, where: string): Promise<void> {
  const fits = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
  expect(fits, `${where}: the page scrolls sideways at phone width`).toBe(true);
}

interface Item { id: string; ref_id: string; position: number; content_version: number | null; freshness: Record<string, unknown> | null }
interface Collection { id: string; name: string; item_list: Item[] }
interface Action { id: string; title: string; source: Record<string, unknown>; created_at: string }
interface QAnswer { id: string; score: number; comparison?: { previous_answer_id?: string | null } | null }
interface Dismissal { key: string; kind: string }
interface Batch { id: string; status: string; categories: string[] }

/** The parts of a collection a restore must bring back as they were, by id. */
const shape = (c: Collection) => ({
  id: c.id, name: c.name,
  items: c.item_list.map((i) => ({ id: i.id, ref_id: i.ref_id, position: i.position, content_version: i.content_version, freshness: i.freshness })),
});

export async function deviceJourney(page: Page, browser: Browser, request: APIRequestContext, info: TestInfo): Promise<Recorder> {
  const rec = new Recorder(info, "devices");
  const phoneContext = await browser.newContext({ ...devices["Pixel 7"] });
  try {
    await run(rec, page, await phoneContext.newPage(), request);
  } finally {
    rec.write(true);
    await phoneContext.close();
  }
  return rec;
}

async function run(rec: Recorder, desk: Page, phone: Page, request: APIRequestContext) {
  const acct = await newAccount(request, "devices", TRACK);
  rec.facts.phone_viewport = `${devices["Pixel 7"].viewport.width}x${devices["Pixel 7"].viewport.height}`;
  await signIn(desk, acct.email);
  let collectionId = "";
  let actionId = "";
  let before: ReturnType<typeof shape> | null = null;
  let actionBefore: Action | null = null;
  let backup = "";

  await rec.step("Two questions saved to a collection", async (check) => {
    for (const [qid, fresh] of [[ANSWERED, true], [CORRECTED, false]] as const) {
      await desk.goto(`/careers/${TRACK}/questions/${qid}`);
      const save = desk.getByRole("region", { name: "Save for later" });
      if (fresh) await save.getByLabel("New collection name").fill(COLLECTION);
      else await save.getByLabel("Add to a collection").selectOption({ label: COLLECTION });
      await save.getByRole("button", { name: "Add" }).click();
      await expect(save.getByText(`Added to “${COLLECTION}”.`)).toBeVisible();
    }
    check(`both questions added to a new collection "${COLLECTION}" from their pages`);
    const [summary] = await api<{ id: string }[]>(request, acct.auth, "get", "/api/v1/me/collections");
    collectionId = summary!.id;
    const c = await api<Collection>(request, acct.auth, "get", `/api/v1/me/collections/${collectionId}`);
    expect(c.item_list.map((i) => i.ref_id)).toEqual([ANSWERED, CORRECTED]);
    rec.ids.collection = collectionId;
    rec.ids.collection_items = c.item_list.map((i) => i.id);
    rec.facts.added_at_versions = c.item_list.map((i) => `${i.ref_id}@${i.content_version}`).join(", ");
    check(`by the API: collection ${collectionId} holds ${ANSWERED} then ${CORRECTED}, each with the version it was added at`);
  }, undefined, { made: "desktop" });

  await rec.step("Answered twice, the second compared with the first", async (check) => {
    for (const text of [FIRST, SECOND]) {
      await desk.goto(`/careers/${TRACK}/questions/${ANSWERED}`);
      await desk.getByRole("textbox", { name: "Your answer" }).fill(text);
      await desk.getByRole("button", { name: "Get feedback" }).click();
      await expect(desk.getByRole("region", { name: "Feedback", exact: true })).toBeVisible();
    }
    await desk.goto(`/careers/${TRACK}/questions/${ANSWERED}`);
    await desk.getByRole("button", { name: /^Try 2/ }).click();
    await expect(desk.getByRole("region", { name: "What next" }).locator(".answer-recap__comparison")).toContainText("Compared with try 1. ");
    check("the question page sets try 2 beside try 1 (\"Compared with try 1. …\"), by the comparison contract");
    const answers = await api<QAnswer[]>(request, acct.auth, "get", `/api/v1/careers/${TRACK}/questions/${ANSWERED}/answers`);
    expect(answers).toHaveLength(2);
    rec.ids.desktop_answers = answers.map((a) => a.id).reverse();
    rec.facts.desktop_scores = answers.map((a) => a.score).reverse().join(", ");
  }, ["built-in coach"], { made: "desktop" });

  await rec.step("A follow-up question dismissed with Not now", async (check) => {
    const card = desk.getByRole("heading", { name: "A related question" }).locator("xpath=ancestor::section[1]");
    await expect(card.getByRole("link", { name: FOLLOW_UP_TITLE })).toBeVisible();
    await card.getByRole("button", { name: "Not now" }).click();
    await expect(desk.getByRole("heading", { name: "A related question" })).toHaveCount(0);
    check(`"A related question" offered "${FOLLOW_UP_TITLE}"; Not now took it away`);
    const list = await api<{ items: Dismissal[] }>(request, acct.auth, "get", "/api/v1/me/dismissals");
    expect(list.items.map((d) => d.kind)).toEqual(["question_follow_up"]);
    rec.ids.dismissal = list.items[0]!.key;
    check(`by the API: one dismissal kept with the account, ${list.items[0]!.key}`);
  }, undefined, { made: "desktop" });

  await rec.step("An improvement accepted", async (check) => {
    const iv = await api<{ id: string }>(request, acct.auth, "post", "/api/v1/interviews", { kind: "questions", track: TRACK, question_ids: ROUND });
    await desk.goto(`/interviews/${iv.id}`);
    await answerRound(desk, [STRONG, MIDDLING, STRONG]);
    await expect(desk.getByRole("heading", { name: "Work on next" })).toBeVisible();
    const review = await api<{ improvements: { key: string; title: string }[] }>(request, acct.auth, "get", `/api/v1/interviews/${iv.id}/review`);
    expect(review.improvements.length).toBeGreaterThan(0);
    const title = review.improvements[0]!.title;
    await desk.getByRole("button", { name: `Accept as an action: ${title}` }).click();
    await expect(desk.getByText(/Accepted as an action\./).first()).toBeVisible();
    check(`a three-question round answered on the desktop; "${title}" accepted from its "Work on next"`);
    const actions = await api<Action[]>(request, acct.auth, "get", "/api/v1/me/actions");
    expect(actions).toHaveLength(1);
    actionId = actions[0]!.id;
    actionBefore = actions[0]!;
    rec.ids.interview = iv.id;
    rec.ids.action = actionId;
  }, ["built-in coach"], { made: "desktop" });

  await rec.step("The phone reads the same", async (check) => {
    await signIn(phone, acct.email);
    await phone.goto(`/saved/collections/${collectionId}`);
    const items = phone.getByRole("list", { name: "Items in order" }).getByRole("listitem");
    await expect(items).toHaveCount(2);
    await expect(items.nth(1)).toContainText(CORRECTED_TITLE);
    await noSidewaysScroll(phone, "the collection");
    check(`the phone opens collection ${collectionId} with the same two questions in the same order`);
    await phone.goto(`/careers/${TRACK}/questions/${ANSWERED}`);
    await expect(phone.getByRole("heading", { name: "Your past answers" })).toBeVisible();
    await expect(phone.getByRole("button", { name: /^Try 2/ })).toBeVisible();
    await expect(phone.getByRole("heading", { name: "A related question" })).toHaveCount(0);
    await noSidewaysScroll(phone, "the question page");
    check("the question page lists both tries, and the dismissed follow-up isn't offered there either");
    await phone.goto("/plan");
    await expect(phone.locator("#accepted-actions").getByRole("heading", { name: "Improvements you accepted (1)" })).toBeVisible();
    await noSidewaysScroll(phone, "the plan");
    check("the plan lists the one accepted improvement");
    const auth = await signInApi(request, acct.email); // the phone's own sign-in
    expect(shape(await api<Collection>(request, auth, "get", `/api/v1/me/collections/${collectionId}`)).items.map((i) => i.id)).toEqual(rec.ids.collection_items);
    expect((await api<{ items: Dismissal[] }>(request, auth, "get", "/api/v1/me/dismissals")).items.map((d) => d.key)).toEqual([rec.ids.dismissal]);
    expect((await api<Action[]>(request, auth, "get", "/api/v1/me/actions")).map((a) => a.id)).toEqual([actionId]);
    expect((await api<QAnswer[]>(request, auth, "get", `/api/v1/careers/${TRACK}/questions/${ANSWERED}/answers`)).map((a) => a.id).reverse()).toEqual(rec.ids.desktop_answers);
    check("by the API with a new token: the same collection item ids, dismissal key, improvement id and answer ids");
  }, undefined, { made: "desktop", read: ["phone"] });

  await rec.step("An answer on the phone, seen on the desktop after a reload, both open", async (check) => {
    await desk.goto(`/careers/${TRACK}/questions/${CORRECTED}`);
    await expect(desk.getByRole("textbox", { name: "Your answer" })).toBeVisible();
    await phone.goto(`/careers/${TRACK}/questions/${CORRECTED}`);
    await phone.getByRole("textbox", { name: "Your answer" }).fill(PHONE_ANSWER);
    await phone.getByRole("button", { name: "Get feedback" }).click();
    const feedback = phone.getByRole("region", { name: "Feedback", exact: true });
    await expect(feedback.getByLabel(/^Score \d+ out of 100/)).toBeVisible();
    await noSidewaysScroll(phone, "the feedback");
    const [made] = await api<QAnswer[]>(request, acct.auth, "get", `/api/v1/careers/${TRACK}/questions/${CORRECTED}/answers`);
    rec.ids.phone_answer = made!.id;
    check(`the phone answered ${CORRECTED} and got its feedback (${made!.score}/100) while the desktop had the same page open`);
    await desk.reload();
    const past = desk.locator(".card").filter({ has: desk.getByRole("heading", { name: "Your past answers" }) });
    await expect(past).toContainText(`${made!.score}/100`);
    check(`after a reload the desktop's page lists the phone's answer, ${made!.score}/100 (no new sign-in)`);
  }, ["built-in coach"], { made: "phone", read: ["desktop"] });

  await rec.step("A question in the collection corrected, and marked reviewed", async (check) => {
    const meta = await api<{ version: number }>(request, acct.auth, "get", `/api/v1/content/question/${TRACK}/${CORRECTED}/meta`);
    const root = await newAccount(request, "devices-admin");
    grantAdmin(root.email);
    // Corrections are shared content, so each run makes a real change: one of two wordings, never
    // the one the question has now (versions alternate between them).
    await api(request, root.auth, "post", `/api/v1/admin/content/question/${TRACK}/${CORRECTED}/corrections`, {
      prompt: CORRECTIONS[meta.version % 2], change_note: "Asks what you do when they can't be reached.", significant: true,
    });
    const next = meta.version + 1;
    check(`an admin (granted from the command line) corrected ${CORRECTED}: version ${meta.version} to ${next}`);
    await phone.goto(`/saved/collections/${collectionId}`);
    const row = phone.getByRole("list", { name: "Items in order" }).getByRole("listitem").filter({ hasText: CORRECTED_TITLE });
    await expect(row).toContainText("Source updated");
    await row.getByText("What changed").click();
    await row.getByRole("button", { name: `Mark reviewed (version ${next}): ${CORRECTED_TITLE}` }).click();
    await expect(row).not.toContainText("Source updated");
    await noSidewaysScroll(phone, "the collection after the review");
    check(`the phone's collection badged it "Source updated"; marked reviewed at version ${next} there`);
    await desk.goto(`/saved/collections/${collectionId}`);
    await expect(desk.getByRole("list", { name: "Items in order" }).getByRole("listitem").filter({ hasText: CORRECTED_TITLE })).not.toContainText("Source updated");
    check("the desktop's copy of the collection shows it reviewed too");
    const c = await api<Collection>(request, acct.auth, "get", `/api/v1/me/collections/${collectionId}`);
    before = shape(c);
    rec.facts.reviewed_version = next;
  }, undefined, { made: "phone", read: ["desktop"] });

  await rec.step("A version 2 backup downloaded", async (check) => {
    await desk.goto("/settings");
    await desk.getByRole("checkbox", { name: /Include links between records \(format version 2\)/ }).check();
    const [download] = await Promise.all([desk.waitForEvent("download"), desk.getByRole("button", { name: "Download my data" }).click()]);
    backup = join(tmpdir(), `devices-${Date.now()}-${Math.floor(Math.random() * 1e6)}.json`);
    writeFileSync(backup, readFileSync((await download.path())!));
    const doc = JSON.parse(readFileSync(backup, "utf8")) as { export_version: number; collections?: { id: string }[]; accepted_actions?: { id: string }[] };
    expect(doc.export_version).toBe(2);
    expect((doc.collections ?? []).map((c) => c.id)).toEqual([collectionId]);
    expect((doc.accepted_actions ?? []).map((a) => a.id)).toEqual([actionId]);
    check(`the file is format version 2 and carries collection ${collectionId} and improvement ${actionId} by id`);
  }, undefined, { made: "desktop" });

  await rec.step("The collection and the improvement deleted", async (check) => {
    await phone.goto(`/saved/collections/${collectionId}`);
    await phone.getByRole("button", { name: "Delete", exact: true }).click();
    await phone.getByRole("alertdialog").getByRole("button", { name: "Delete collection" }).click();
    await expect(phone).toHaveURL(/\/saved$/);
    check("the phone deleted the collection (after its confirmation)");
    await phone.goto("/plan");
    const section = phone.locator("#accepted-actions");
    await section.getByRole("button", { name: `Delete: ${actionBefore!.title}` }).click();
    await section.getByRole("group", { name: "What this will do" }).getByRole("button", { name: "Delete this improvement" }).click();
    await expect(section.getByRole("status")).toContainText(`Deleted ${actionBefore!.title}.`);
    await noSidewaysScroll(phone, "the plan after the delete");
    check("the phone deleted the improvement, as its preview said");
    await desk.goto(`/saved/collections/${collectionId}`);
    await expect(desk.getByText("Collection not found")).toBeVisible();
    check("the desktop, after a reload, finds the collection gone");
    expect((await request.get(`${API_URL}/api/v1/me/actions/${actionId}`, { headers: acct.auth })).status()).toBe(404);
  }, undefined, { made: "phone", read: ["desktop"] });

  await rec.step("Restored from the file", async (check) => {
    await desk.goto("/settings/restore");
    await desk.getByLabel("Backup file").setInputFiles(backup);
    const pv = desk.getByRole("region", { name: "2. Check what would be added" });
    await expect(pv.getByRole("checkbox", { name: "Collections, with their items in order (version 2 files): 1 new" })).toBeChecked();
    await expect(pv.getByRole("checkbox", { name: "Accepted improvements, with their occurrences (version 2 files): 1 new" })).toBeChecked();
    await expect(pv.getByRole("checkbox", { name: "Notes: 0 new" })).toBeDisabled();
    check('the preview offers "Collections, with their items in order (version 2 files): 1 new" and "Accepted improvements, with their occurrences (version 2 files): 1 new", and nothing else new');
    await pv.getByRole("button", { name: /^Restore / }).click();
    const done = desk.getByRole("status").filter({ hasText: /^Restored: / });
    await expect(done).toHaveText("Restored: 1 accepted improvements, 1 collections.");
    check(`it says "${await done.innerText()}"`);
    const [batch, ...rest] = await api<Batch[]>(request, acct.auth, "get", "/api/v1/me/restore/batches");
    expect(rest).toEqual([]);
    expect(batch!.status).toBe("applied");
    expect(batch!.categories.sort()).toEqual(["accepted_actions", "collections"]);
    rec.ids.restore_batch = batch!.id;
    check(`restore batch ${batch!.id}: applied, collections and accepted improvements`);
    const c = await api<Collection>(request, acct.auth, "get", `/api/v1/me/collections/${collectionId}`);
    expect(shape(c)).toEqual(before);
    const a = await api<Action>(request, acct.auth, "get", `/api/v1/me/actions/${actionId}`);
    expect([a.id, a.title, a.source]).toEqual([actionBefore!.id, actionBefore!.title, actionBefore!.source]);
    check(`by the API: collection ${collectionId} is back with the same item ids, order, added-at versions and review (version ${rec.facts.reviewed_version}), and improvement ${actionId} with the same source`);
    await phone.goto(`/saved/collections/${collectionId}`);
    await expect(phone.getByRole("list", { name: "Items in order" }).getByRole("listitem")).toHaveCount(2);
    await expect(phone.getByRole("list", { name: "Items in order" }).getByRole("listitem").filter({ hasText: CORRECTED_TITLE })).not.toContainText("Source updated");
    await phone.goto("/plan");
    await expect(phone.locator("#accepted-actions").getByRole("heading", { name: "Improvements you accepted (1)" })).toBeVisible();
    check("the phone, after a reload, has the collection (still reviewed) and the improvement again");
  }, undefined, { made: "desktop", read: ["phone"] });

  await rec.step("The restore undone", async (check) => {
    await desk.goto("/settings/restore");
    let asked = "";
    desk.once("dialog", (d) => { asked = d.message(); void d.accept(); });
    await desk.getByRole("button", { name: "Remove what this added" }).click();
    await expect(desk.getByText(/^Removed \d+; kept 0 you'd changed since/)).toBeVisible();
    expect(asked).not.toBe("");
    check(`"Remove what this added" asked first ("${asked}"), then removed the restored records and kept none (nothing was changed since)`);
    const [batch] = await api<Batch[]>(request, acct.auth, "get", "/api/v1/me/restore/batches");
    expect([batch!.id, batch!.status]).toEqual([rec.ids.restore_batch, "removed"]);
    check(`restore batch ${batch!.id} is recorded as removed`);
    expect((await request.get(`${API_URL}/api/v1/me/collections/${collectionId}`, { headers: acct.auth })).status()).toBe(404);
    expect((await request.get(`${API_URL}/api/v1/me/actions/${actionId}`, { headers: acct.auth })).status()).toBe(404);
    check(`by the API: collection ${collectionId} and improvement ${actionId} are gone again`);
    await phone.goto(`/saved/collections/${collectionId}`);
    await expect(phone.getByText("Collection not found")).toBeVisible();
    await noSidewaysScroll(phone, "the missing collection");
    check("the phone, after a reload, finds the collection gone");
    // What the undo leaves: the answers and the dismissal, which the restore never touched.
    expect((await api<{ items: Dismissal[] }>(request, acct.auth, "get", "/api/v1/me/dismissals")).items.map((d) => d.key)).toEqual([rec.ids.dismissal]);
    check("the dismissal still holds (the restore and its undo don't touch it)");
  }, undefined, { made: "desktop", read: ["phone"] });

  await rec.step("No secret in the logs", async (check) => {
    const log = readFileSync(ACCESS_LOG, "utf8");
    expect(log.length).toBeGreaterThan(0);
    expect(log).not.toContain(DESKTOP_CANARY);
    expect(log).not.toContain(PHONE_CANARY);
    check("the API's access log for this run contains neither the canary typed on the desktop nor the one typed on the phone");
  });
}
