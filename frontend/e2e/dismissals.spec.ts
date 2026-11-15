import { expect, test } from "./fixtures";
import { api, newAccount, signIn } from "./preparation-journey";

/**
 * "Not now" kept with the account (Volume 15, prompt 2; docs/FOLLOW_UPS.md, "Not now"), against the
 * real API with two signed-in browser contexts (two devices): a follow-up question dismissed on one
 * isn't offered on the other, Settings on the other lists it in plain words, and "Offer it again"
 * there brings it back on both. Synthetic data.
 */
const FIRST = "Every morning I tell each patient the plan for the day: tests, medicines and when the doctor will come. " +
  "When something changes I go back and explain it in plain words, check they understood by asking them to tell me " +
  "the plan, and write it on the whiteboard in the room. Patients asked fewer worried questions and complaints dropped.";
const SECOND = FIRST + " I also note what each patient asked so the next shift can keep them informed the same way.";
const URL = "/careers/registered-nurse/questions/e-inform-0";
const RELATED = "A related question";

test("a dismissal on one device holds on another, and Offer it again brings it back on both", async ({ page, browser, request }) => {
  const acct = await newAccount(request, "dismissals", "registered-nurse");
  for (const answer of [FIRST, SECOND]) {
    await api(request, acct.auth, "post", "/api/v1/careers/registered-nurse/questions/e-inform-0/answers", { answer });
  }
  await signIn(page, acct.email);
  await page.goto(URL);
  const card = page.getByRole("heading", { name: RELATED }).locator("xpath=ancestor::section[1]");
  await expect(card.getByRole("link", { name: "Keeping patients' families informed" })).toBeVisible();
  await card.getByRole("button", { name: "Not now" }).click();
  await expect(page.getByRole("heading", { name: RELATED })).toHaveCount(0);

  // The other device: not offered there either.
  const other = await browser.newContext();
  const phone = await other.newPage();
  await signIn(phone, acct.email);
  await phone.goto(URL);
  await expect(phone.getByRole("heading", { name: "Your past answers" })).toBeVisible();
  await expect(phone.getByRole("heading", { name: RELATED })).toHaveCount(0);

  // Settings there lists it in plain words, and offers it again.
  await phone.goto("/settings#suggestions");
  const list = phone.getByRole("list", { name: "Suggestions you dismissed" });
  await expect(list).toContainText("A related question: Keeping patients' families informed");
  await list.getByRole("button", { name: /^Offer it again: A related question/ }).click();
  await expect(phone.getByText("Nothing dismissed.")).toBeVisible();

  // Back on both.
  await phone.goto(URL);
  await expect(phone.getByRole("link", { name: "Keeping patients' families informed" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("link", { name: "Keeping patients' families informed" })).toBeVisible();
  await other.close();
});
