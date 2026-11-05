import { expect, test, type Page } from "./fixtures";

// Release Readiness brief 14, against the real backend: the practice → feedback → lost reply →
// revision flow keeps working through the compatibility states. A server that stops saying it
// keeps one answer per key gets no safety claim; an answer too short to score is never shown as
// a score; signing in as someone else brings back none of the first account's work.
// Synthetic accounts only.

const TEXT = "Last winter on a busy ward I noticed a patient's breathing change during my night round. I checked his " +
  "observations, raised the bed, started oxygen as prescribed and called the doctor. Within the hour his saturation " +
  "was back to 96%, and I learned to escalate early rather than wait to be certain.";
const SHORT = "I would check the patient and call the doctor.";
const ANSWERS = "**/api/v1/careers/*/questions/*/answers";

async function newNurse(page: Page, prefix: string): Promise<string> {
  const email = `${prefix}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.getByLabel("Job you're preparing for").selectOption("registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  return email;
}

test("a server that stopped keeping keys by the lost reply gets no safety claim, and a resend is a second try", async ({ page }) => {
  await newNurse(page, "older-server");
  await page.locator(".rec-list").first().getByRole("link").first().click();
  const box = page.getByRole("textbox", { name: "Your answer" });
  await box.fill(TEXT);

  // From now on /capabilities answers as an older server would: without answer_request_keys.
  await page.route("**/api/v1/capabilities", async (route) => {
    const real = await route.fetch();
    const body = await real.json();
    delete body.answer_request_keys;
    await route.fulfill({ response: real, json: body });
  });
  let firstKey: string | undefined;
  await page.route(ANSWERS, async (route) => {
    if (route.request().method() === "POST") {
      firstKey = route.request().postDataJSON()?.client_request_id;
      expect((await route.fetch()).status()).toBe(201); // saved; its reply is lost
    }
    await route.abort("connectionreset");
  });
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByText(/look under “Your past answers” before sending it again/)).toBeVisible();
  await expect(page.getByText(/Sending it again unchanged is safe/)).toHaveCount(0);
  expect(firstKey).toBeTruthy(); // it was sent while the page still believed keys were kept
  await page.unroute(ANSWERS);

  // Resent without a key (the server no longer says it keeps them): honestly a second try.
  const resend = page.waitForResponse((r) => r.url().includes("/answers") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Get feedback" }).click();
  const reply = await resend;
  expect(reply.request().postDataJSON()?.client_request_id).toBeUndefined();
  expect(reply.status()).toBe(201);
  await expect(page.getByRole("button", { name: /^Try 2/ })).toBeVisible();
});

test("too short is never a score, a revision is linked, and another account sees none of it", async ({ page, viewport }) => {
  test.info().annotations.push({ type: "viewport", description: `${viewport?.width}x${viewport?.height}` });
  await newNurse(page, "acceptance-a");
  await page.locator(".rec-list").first().getByRole("link").first().click();
  const questionUrl = page.url();
  const box = page.getByRole("textbox", { name: "Your answer" });

  await box.fill(SHORT);
  await page.getByRole("button", { name: "Get feedback" }).click();
  const feedback = page.getByRole("region", { name: "Feedback", exact: true });
  await expect(feedback.getByLabel("Not enough to score yet")).toBeVisible();
  await expect(page.getByRole("button", { name: /^Try 1 \(first\).*Too short to score/ })).toBeVisible();
  await page.reload();
  await expect(page.getByText("Answered, too short to score")).toBeVisible();
  await expect(page.getByText(/^Best score/)).toHaveCount(0);

  // An explicit revision of that try, long enough to score: saved as try 2, linked to try 1.
  await page.getByRole("button", { name: /^Try 1 \(first\)/ }).click();
  await page.getByRole("button", { name: "Add to this answer" }).click();
  await box.fill(TEXT);
  const saved = page.waitForResponse((r) => r.url().includes("/answers") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Get feedback" }).click();
  const rev = await saved;
  expect(rev.status()).toBe(201);
  expect((await rev.json()).revises_answer_id).toBeTruthy();
  await expect(page.getByRole("button", { name: /^Try 2.*revised from try 1/ })).toBeVisible();
  await expect(page.getByText(/^Best score \d+/)).toBeVisible();

  // Another account on the same browser: no answers, no draft, no score from the first one.
  await page.locator("#primary-navigation").getByRole("button", { name: "Sign out" }).click();
  await newNurse(page, "acceptance-b");
  await page.goto(questionUrl);
  await expect(page.getByRole("textbox", { name: "Your answer" })).toHaveValue("");
  await expect(page.getByRole("button", { name: /^Try 1/ })).toHaveCount(0);
  await expect(page.getByText(/^Best score/)).toHaveCount(0);
  await expect(page.getByText("Answered, too short to score")).toHaveCount(0);
});
