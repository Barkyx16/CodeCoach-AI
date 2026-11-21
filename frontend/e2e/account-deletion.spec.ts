import type { APIRequestContext, Page } from "@playwright/test";

import { expect, test } from "./fixtures";
import { API_URL } from "./ports";
import { api, newAccount, signIn } from "./preparation-journey";

/**
 * Deleting a synthetic account after reading its list (Volume 14, prompt 6; docs/LIFECYCLE.md,
 * docs/YOUR_DATA.md) against the real API: from the privacy view to the danger zone, the list comes
 * first, with the privacy view's own counts, the shared link and every signed-in device; the delete
 * is refused until the list is shown; afterwards signing in fails and the link is gone, as the
 * list said. At desktop and phone width. No email is sent: the test server's mail goes to its log.
 */
const PASSWORD = "CorrectHorse42"; // the journey helpers' synthetic password
const ANSWER = "Last winter I was the night nurse for five patients. I checked his vital signs and called the rapid response team.";

async function seed(request: APIRequestContext, prefix: string) {
  const acct = await newAccount(request, prefix);
  await api(request, acct.auth, "post", "/api/v1/me/notes", { title: "Shift notes", body: "SBAR first." });
  const answer = await api<{ id: string }>(request, acct.auth, "post", "/api/v1/careers/registered-nurse/questions/m-pressure-0/answers", { answer: ANSWER });
  const shared = await api<{ token: string }>(request, acct.auth, "post", "/api/v1/me/shares", { answer_id: answer.id, acknowledge_link_access: true, sentences: [0] });
  const opened = await request.post(`${API_URL}/api/v1/shared/open`, { data: { token: shared.token } });
  expect(opened.status(), "the link works before").toBe(200);
  return { ...acct, token: shared.token };
}

async function deleteAfterReading(page: Page, request: APIRequestContext, acct: Awaited<ReturnType<typeof seed>>) {
  await signIn(page, acct.email);
  await page.goto("/settings/data");
  // The privacy view's own count of notes, to compare with the list.
  await expect(page.getByRole("region", { name: "Saved to your account" })).toContainText("1 Notes");
  await page.getByRole("link", { name: "Delete my account" }).click();
  const form = page.getByRole("form", { name: "Delete account" });
  await form.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await form.getByLabel('Type "DELETE" to confirm').fill("DELETE");
  const submit = form.getByRole("button", { name: "Delete my account" });
  await expect(submit).toBeDisabled(); // no confirm box without the list
  await form.getByRole("button", { name: "Show what would be deleted" }).click();
  const list = form.getByRole("group", { name: "What deleting your account does" });
  await expect(list).toContainText("Notes: 1");
  await expect(list).toContainText("Answers you shared through a link, with the feedback they received: 1");
  await expect(list).toContainText("1 link you shared");
  await expect(list).toContainText("They stop working at once.");
  await expect(list).toContainText("Every device is signed out.");
  await expect(list).toContainText(/keep a copy until they age out: with the default rotation \(docs\/BACKUP\.md\), the last of them by \d{4}-\d{2}-01\./);
  await submit.click();
  await expect(page).toHaveURL(/\/$/);

  // As the list said: signing in fails, the link is gone, the old token is refused.
  const login = await request.post(`${API_URL}/api/v1/auth/login`, { data: { email: acct.email, password: PASSWORD } });
  expect(login.status()).toBe(401);
  expect((await request.post(`${API_URL}/api/v1/shared/open`, { data: { token: acct.token } })).status()).toBe(404);
  expect((await request.get(`${API_URL}/api/v1/auth/me`, { headers: acct.auth })).status()).toBe(401);
}

test("an account is deleted only after its list is read, and then it's gone as the list said", async ({ page, request }) => {
  await deleteAfterReading(page, request, await seed(request, "delete-account"));
});

test("at phone width the list reads without sideways scrolling", async ({ page, request }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const acct = await seed(request, "delete-account-phone");
  await signIn(page, acct.email);
  await page.goto("/settings#danger");
  const form = page.getByRole("form", { name: "Delete account" });
  await form.getByRole("button", { name: "Show what would be deleted" }).click();
  await expect(form.getByRole("group", { name: "What deleting your account does" })).toContainText("Notes: 1");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  await page.context().clearCookies();
  await deleteAfterReading(page, request, acct);
});
