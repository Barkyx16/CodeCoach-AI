import AxeBuilder from "@axe-core/playwright";
import { chooseJob, expect, test, type Page } from "./fixtures";

// Communication drills against the real API: every drill type typed, the voice path with a
// stand-in for the browser's speech recognition (Chromium's needs a network service), an
// editable transcript, repeats compared under the same rubric, saving and scheduling, and
// narrow, dark and light screens.

async function axe(page: Page, where: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => ({ id: v.id, targets: v.nodes.slice(0, 3).map((n) => n.target.join(" ")) })), where).toEqual([]);
}

async function signUpNurse(page: Page) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`drill-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

/** A stand-in for webkitSpeechRecognition that "hears" the given phrases when started. */
async function fakeSpeech(page: Page, phrases: string[]) {
  await page.addInitScript((said: string[]) => {
    class Fake {
      continuous = false; interimResults = false; lang = "";
      onresult: ((e: unknown) => void) | null = null;
      onerror: ((e: unknown) => void) | null = null;
      onend: (() => void) | null = null;
      start() {
        setTimeout(() => {
          const results = said.map((t) => Object.assign([{ transcript: t }], { isFinal: true }));
          this.onresult?.({ resultIndex: 0, results });
        }, 50);
      }
      stop() { setTimeout(() => this.onend?.(), 20); }
      abort() { this.onend?.(); }
    }
    // Chromium has the unprefixed constructor too, and the app prefers it.
    Object.assign(window, { SpeechRecognition: Fake, webkitSpeechRecognition: Fake });
  }, phrases);
}

const TYPED: Record<string, string> = {
  "Introduce yourself briefly": "I'm a registered nurse with three years on a medical ward. I've led handovers and trained new staff, which is why I want this role.",
  "Answer with a concrete example": "Last month when I was on nights, a patient's assessment showed falling blood pressure. I called the doctor, so we started fluids and he recovered.",
  "Explain it to a non-specialist": "Patient assessment means checking how someone is doing. It's like a mechanic listening to an engine before deciding what to fix.",
  "Ask a clarifying question": "Which ward would this be on, and how many patients would I have? That changes how I'd plan, because priorities depend on the mix.",
  "Respond to a follow-up": "First I checked his airway and oxygen, then I called the rapid response team, because his breathing was getting worse.",
};

test("every drill type in text mode, with a repeat compared under the same rubric", async ({ page }) => {
  await signUpNurse(page);
  await page.getByRole("navigation", { name: "More ways to practice" }).getByRole("link", { name: "Communication drills" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Communication drills" })).toBeVisible();
  await expect(page.getByText("There are no streaks, rankings or speed scores.", { exact: false })).toBeVisible();
  for (const [title, words] of Object.entries(TYPED)) {
    await page.goto("/drills");
    await page.getByRole("link", { name: title }).click();
    await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
    await expect(page.locator(".drill-prompt")).toContainText(/nurse|patient|ward|handover|shift/i);
    await page.getByLabel(/Answer \(check and edit/).fill(words);
    await page.getByRole("button", { name: "Get feedback" }).click();
    const fb = page.getByRole("region", { name: /Feedback on your attempt/ });
    await expect(fb).toBeVisible();
    await expect(fb).toContainText("Spoken time: not measured (typed answer)");
    await expect(fb).toContainText("an estimate, not a measurement");
  }
  await axe(page, "drill with feedback");

  // Repeat the example drill more vaguely: the comparison names what's missing, and the first stays.
  await page.goto("/drills");
  await page.getByRole("link", { name: "Answer with a concrete example" }).click();
  await page.getByLabel(/Answer \(check and edit/).fill("I'm a hard worker and a team player and I always do my best for patients.");
  await page.getByRole("button", { name: "Get feedback" }).click();
  const fb = page.getByRole("region", { name: /Feedback on your attempt/ });
  await expect(fb).toContainText("Not there this time: gives one specific situation.");
  await expect(fb).toContainText("“hard worker”");
  await expect(page.locator(".drill-history li")).toHaveCount(2);
  await page.locator(".drill-history li").nth(1).getByRole("button").click();
  await expect(page).toHaveURL(/attempt=/);
  await expect(fb).toContainText("Last month when I was on nights");
  await page.reload();
  await expect(page.getByRole("region", { name: /Feedback on your attempt/ })).toContainText("Last month when I was on nights");
});

test("voice: an editable transcript, measured time only from the recording, and fillers never marked down", async ({ page }) => {
  await fakeSpeech(page, ["um I'm a registered nurse on a medical ward uh and I've trained new staff which is why I want this role"]);
  await signUpNurse(page);
  await page.goto("/drills/intro");
  await page.getByRole("button", { name: "Speak your answer" }).click();
  await expect(page.getByRole("button", { name: "Stop speaking" })).toBeVisible();
  const box = page.getByLabel(/Answer \(check and edit/);
  await expect(box).toHaveValue(/registered nurse on a medical ward/);
  await page.waitForTimeout(1100); // let at least a second of "speaking" pass
  await page.getByRole("button", { name: "Stop speaking" }).click();
  await expect(page.getByRole("button", { name: "Speak your answer" })).toBeVisible();
  await box.press("End");
  await box.pressSequentially(" Thank you.");
  await page.getByRole("button", { name: "Get feedback" }).click();
  const fb = page.getByRole("region", { name: /Feedback on your attempt/ });
  await expect(fb).toContainText(/You spoke for \d+ seconds \(timed while the microphone was on\)/);
  await expect(fb).toContainText("2 filler sounds from speech recognition were left out of the counts. They aren't marked down.");
  await expect(fb).toContainText("Thank you.");

  // Turn delivery measurements off: no spoken time and no target length.
  await page.getByRole("checkbox", { name: /Show delivery measurements/ }).uncheck();
  await expect(fb).not.toContainText("You spoke for");
  await expect(page.getByText("There's no time limit, and speed isn't scored.")).toBeVisible();
});

test("save a drill, put it in a collection and on the schedule; works at 320px light and in dark", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("codecoach.display.v1", JSON.stringify({ theme: "dark" })));
  await signUpNurse(page);
  await page.goto("/drills/clarify");
  await page.getByRole("button", { name: "Bookmark", exact: true }).click();
  await expect(page.getByRole("button", { name: "Bookmarked" })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("combobox", { name: /^Add to a collection/ }).selectOption({ label: "New collection…" });
  await page.getByLabel("New collection name").fill("Between interviews");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await expect(page.getByRole("link", { name: "Between interviews" })).toBeVisible();
  await axe(page, "drill page, dark");
  await page.goto("/saved");
  await expect(page.getByRole("link", { name: "Drill: Ask a clarifying question" })).toBeVisible();
  await expect(page.getByText("Communication drill", { exact: false }).first()).toBeVisible();
  await page.goto("/drills/clarify");
  await page.getByRole("link", { name: "Add this drill to my schedule" }).click();
  await expect(page).toHaveURL(/\/schedule\?kind=drill&ref=clarify/);

  await page.evaluate(() => localStorage.setItem("codecoach.display.v1", JSON.stringify({ theme: "light" })));
  await page.setViewportSize({ width: 320, height: 700 });
  await page.goto("/drills/followup");
  await page.getByLabel(/Answer \(check and edit/).fill(TYPED["Respond to a follow-up"]!);
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByRole("region", { name: /Feedback on your attempt/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await axe(page, "drill at 320px, light");
});
