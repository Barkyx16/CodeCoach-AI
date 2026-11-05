import { expect, test, type Page } from "./fixtures";

// Verification brief 15: this batch's changed critical flows on the supported phone configuration
// (the `mobile` project: Pixel 7 emulation in Chromium, the only engine installed here), against
// the real backend. Emulation isn't a physical phone, a screen reader or an on-screen keyboard.

const TEXT = "Last winter on a busy ward I noticed a patient's breathing change during my night round. I checked his " +
  "observations, raised the bed, started oxygen as prescribed and called the doctor. Within the hour his saturation " +
  "was back to 96%, and I learned to escalate early rather than wait to be certain.";
const ANSWERS = "**/api/v1/careers/*/questions/*/answers**";

async function newNurse(page: Page, prefix: string): Promise<void> {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`${prefix}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.getByLabel("Job you're preparing for").selectOption("registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
}

test("a keyed resend after a lost reply replays through the protected route", async ({ page }) => {
  await newNurse(page, "m-replay");
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  await page.locator(".rec-list").first().getByRole("link").first().click();
  const box = page.getByRole("textbox", { name: "Your answer" });
  await box.fill(TEXT);
  let firstUrl = "";
  await page.route(ANSWERS, async (route) => {
    if (route.request().method() === "POST") {
      firstUrl = route.request().url();
      expect((await route.fetch()).status()).toBe(201); // saved; its reply is lost
    }
    await route.abort("connectionreset");
  });
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByText(/Sending it again unchanged is safe/)).toBeVisible();
  expect(firstUrl).toMatch(/\/answers\/keyed$/);
  await page.unroute(ANSWERS);
  const resend = page.waitForResponse((r) => r.url().includes("/answers") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Get feedback" }).click();
  const reply = await resend;
  expect(reply.status()).toBe(200);
  expect(reply.headers()["idempotent-replayed"]).toBe("true");
  await expect(page.getByRole("button", { name: /^Try 1 \(first\)/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Try 2/ })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("an answer stored without grading metadata is shown as not counted (controlled list)", async ({ page }) => {
  await newNurse(page, "m-unknown");
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  await page.locator(".rec-list").first().getByRole("link").first().click();
  await expect(page.getByRole("textbox", { name: "Your answer" })).toBeVisible();
  // No code writes such a row, so the list is a controlled response: the server's real shape for
  // one (evidence_level "unknown"), as the backend tests produce it.
  await page.route(ANSWERS, async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    const qid = new URL(route.request().url()).pathname.split("/").at(-2);
    await route.fulfill({ json: [{
      id: "u-1", question_id: qid, answer: "(legacy)", score: 50, rating: "Developing", summary: "Synthetic.",
      points: [], rubric_version: "v1", evidence_level: "unknown", notes: [], outline: [], word_count: 1,
      coach: "built-in (offline)", created_at: "2026-11-01T09:00:00Z", content_version: 1, story_id: null,
      track: "registered-nurse", evaluation_status: "measured", evaluation_note: null, revises_answer_id: null,
    }] });
  });
  await page.reload();
  const entry = page.getByRole("button", { name: /not counted \(how it was graded wasn't recorded\)/ });
  await entry.click();
  await expect(page.getByText(/its score isn't counted in your best scores or averages/)).toBeVisible();
});

test("finishing the introduction survives an immediate reload", async ({ page }) => {
  page.on("dialog", (d) => void d.accept());
  await newNurse(page, "m-tour");
  const tour = page.getByRole("region", { name: "Introduction" });
  await page.getByRole("button", { name: "Start the tour" }).click();
  for (let i = 0; i < 4; i++) await tour.getByRole("button", { name: "Next" }).click();
  await page.waitForLoadState("networkidle");
  await page.route("**/api/v1/me/onboarding", (route) =>
    route.request().method() === "PATCH" ? route.abort("connectionreset") : route.continue());
  await tour.getByRole("button", { name: "Finish" }).click();
  await expect(tour).toHaveCount(0);
  await page.unroute("**/api/v1/me/onboarding");
  const saved = page.waitForResponse((r) => r.url().endsWith("/api/v1/me/onboarding") && r.request().method() === "PATCH");
  await page.reload();
  expect((await saved).status()).toBe(200);
  await expect(tour).toHaveCount(0);
});
