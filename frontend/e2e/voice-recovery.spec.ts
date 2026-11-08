import AxeBuilder from "@axe-core/playwright";

import { chooseJob, expect, navTo, test, type Page } from "./fixtures";

/**
 * Voice practice that recovers (Volume 7, prompt 9), in Chromium against the real API. Chromium's
 * own speech recognition needs Google's network service, so a stand-in replaces it; the test
 * drives it through `window.__speech` like a browser would: results by index, an error, an end.
 *
 * The demonstration: mid-answer the microphone is lost. The words already recognised stay, the
 * unconfirmed ones are offered back, the learner speaks again on the same question and sends;
 * the interview goes on to question 2 without a restart. Screenshots of both moments are saved
 * under e2e/screenshots/voice-*.png.
 */
async function fakeSpeech(page: Page) {
  await page.addInitScript(() => {
    type Result = [string, boolean];
    class Fake {
      continuous = false; interimResults = false; lang = "";
      onresult: ((e: unknown) => void) | null = null;
      onerror: ((e: unknown) => void) | null = null;
      onend: (() => void) | null = null;
      finals: string[] = [];
      start() { (window as unknown as { __speech: { latest: Fake } }).__speech.latest = this; }
      stop() { setTimeout(() => this.onend?.(), 20); }
      abort() { /* aborted: no more events */ }
      emit(...results: Result[]) {
        const resultIndex = this.finals.length;
        const list = [...this.finals.map((t) => [t, true] as Result), ...results]
          .map(([t, isFinal]) => Object.assign([{ transcript: t }], { isFinal }));
        for (const [t, isFinal] of results) if (isFinal) this.finals.push(t);
        this.onresult?.({ resultIndex, results: list });
      }
    }
    Object.assign(window, { SpeechRecognition: Fake, webkitSpeechRecognition: Fake, __speech: { latest: null } });
  });
}
const speech = {
  emit: (page: Page, ...results: [string, boolean][]) =>
    page.evaluate((r) => (window as unknown as { __speech: { latest: { emit(...x: unknown[]): void } } }).__speech.latest.emit(...r), results),
  fail: (page: Page, error: string) =>
    page.evaluate((e) => (window as unknown as { __speech: { latest: { onerror(x: unknown): void } } }).__speech.latest.onerror({ error: e }), error),
};

async function signUpNurse(page: Page) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`voice-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

test("a microphone lost mid-answer: the words stay, the interview goes on", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await fakeSpeech(page);
  await signUpNurse(page);
  await navTo(page, "Mock interview");
  await page.getByRole("button", { name: "Start interview" }).click();
  await expect(page.getByText(/QUESTION 1 OF 5/)).toBeVisible();
  const box = page.getByLabel("Your answer", { exact: true });

  // Keyboard only: focus Speak answer and press Enter. Nothing listened before that.
  expect(await page.evaluate(() => (window as unknown as { __speech: { latest: unknown } }).__speech.latest)).toBeNull();
  await page.getByRole("button", { name: "Speak answer" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("status").filter({ hasText: "Listening. Microphone on" })).toBeVisible();
  await expect(page.locator(".voice-elapsed")).toHaveText(/^0:0\d$/);
  // Reduced motion: the "microphone on" dot doesn't pulse.
  expect(await page.locator(".voice-status__dot").evaluate((el) => getComputedStyle(el).animationName)).toBe("none");

  await speech.emit(page, ["I check the patient's airway and breathing first", true], ["then the monitor", false]);
  await expect(box).toHaveValue("I check the patient's airway and breathing first");
  await speech.fail(page, "audio-capture"); // unplugged
  await expect(page.getByRole("alert").filter({ hasText: "The microphone isn't available" })).toBeVisible();
  const offered = page.getByRole("group", { name: "Words that weren't confirmed" });
  await expect(offered).toContainText("then the monitor");
  await expect(box).toHaveValue("I check the patient's airway and breathing first");
  const results = await new AxeBuilder({ page }).include(".voice-composer").withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => v.id)).toEqual([]);
  await page.locator(".voice-composer").screenshot({ path: "e2e/screenshots/voice-mic-lost.png" });

  // Recover on the same question: keep the offered words, speak again, stop with Esc, send.
  await offered.getByRole("button", { name: "Add them to my answer" }).click();
  await page.getByRole("button", { name: "Speak answer" }).click();
  await speech.emit(page, ["and I escalate early because his oxygen was dropping, so he was stable within thirty minutes.", true]);
  await box.focus();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("status").filter({ hasText: "Ready" })).toBeVisible();
  await expect(box).toHaveValue(
    "I check the patient's airway and breathing first then the monitor and I escalate early because his oxygen was dropping, so he was stable within thirty minutes.",
  );
  await page.getByRole("button", { name: "Next question" }).click();
  await expect(page.getByText(/QUESTION 2 OF 5/)).toBeVisible();
  await page.screenshot({ path: "e2e/screenshots/voice-recovered.png" });
});

test("the coding editor's Ctrl/⌘+Enter doesn't send while the microphone is on", async ({ page }) => {
  await fakeSpeech(page);
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await page.getByRole("button", { name: "Start this problem" }).click();
  await expect(page).toHaveURL(/two-sum/);
  await navTo(page, "Mock interview");
  await page.getByLabel("Problem").selectOption("two-sum");
  await page.getByRole("button", { name: "Start interview" }).click();
  await expect(page).toHaveURL(/\/interviews\/[0-9a-f-]+$/);
  await expect(page.locator(".monaco-editor")).toBeVisible();

  const sent: string[] = [];
  page.on("request", (r) => { if (r.method() === "POST" && /\/messages$/.test(r.url())) sent.push(r.url()); });
  await page.getByRole("button", { name: "Speak answer" }).click();
  await speech.emit(page, ["Can the array contain duplicates", true]);
  await page.locator(".monaco-editor").first().click();
  await page.keyboard.press("ControlOrMeta+Enter");
  await page.waitForTimeout(300);
  expect(sent).toHaveLength(0); // the microphone is on: review first
  await page.getByRole("button", { name: "Stop listening" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Ready" })).toBeVisible();
  const reply = page.waitForResponse((r) => r.request().method() === "POST" && /\/messages$/.test(r.url()));
  await page.locator(".monaco-editor").first().click();
  await page.keyboard.press("ControlOrMeta+Enter");
  const body = (await reply).request().postDataJSON() as { message: string; source: string };
  expect(body).toMatchObject({ message: "Can the array contain duplicates", source: "voice" });
});
