import { chooseJob, expect, test } from "./fixtures";

// A reply lost after the server saved the answer, against the real backend: the page can't
// confirm it (the follow-up lookup fails too), says so, and resending the unchanged answer
// returns the saved one (the same request key) instead of a second copy.

const TEXT = "Last winter on a busy ward I noticed a patient's breathing change during my night round. I checked his " +
  "observations, raised the bed, started oxygen as prescribed and called the doctor. Within the hour his saturation " +
  "was back to 96%, and I learned to escalate early rather than wait to be certain.";

test("a resend after a lost reply returns the saved answer, not a second one", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`replay-${Date.now()}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  await page.locator(".rec-list").first().getByRole("link").first().click();
  const box = page.getByRole("textbox", { name: "Your answer" });
  await box.fill(TEXT);

  // The POST reaches the server and is saved; its reply is dropped. The lookup that follows fails too.
  const ANSWERS = "**/api/v1/careers/*/questions/*/answers**";
  let firstKey: string | undefined;
  await page.route(ANSWERS, async (route) => {
    if (route.request().method() === "POST") {
      firstKey = route.request().postDataJSON()?.client_request_id;
      const saved = await route.fetch();
      expect(saved.status()).toBe(201);
      await route.abort("connectionreset");
    } else {
      await route.abort("connectionreset");
    }
  });
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByText(/Sending it again unchanged is safe/)).toBeVisible();
  await expect(box).toHaveValue(TEXT);
  expect(firstKey).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
  await page.unroute(ANSWERS);

  // The resend carries the same key; the server answers with the saved answer (200, replayed).
  const replay = page.waitForResponse((r) => r.url().includes("/answers") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Get feedback" }).click();
  const reply = await replay;
  expect(reply.request().postDataJSON()?.client_request_id).toBe(firstKey);
  expect(reply.status()).toBe(200);
  expect(reply.headers()["idempotent-replayed"]).toBe("true");
  await expect(page.getByRole("region", { name: "Feedback", exact: true })).toBeVisible();
  // One saved answer, not two.
  await expect(page.getByRole("button", { name: /^Try 1 \(first\)/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Try 2/ })).toHaveCount(0);
});
