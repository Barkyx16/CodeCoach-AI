import { writeFileSync } from "node:fs";

import { chooseJob, expect, test, type Page } from "./fixtures";

// The interview pack as a real PDF (Chromium's own print-to-PDF, `page.pdf()`), not a print-media
// screenshot. Synthetic sentinel values stand in for private details. What this checks in the raw
// file: no clickable link annotation to a private URL and no private value in the metadata. The
// files are written to this test's output folder so their text can also be extracted and checked
// (docs/INTERVIEW_WORKFLOW.md has the command and the result). A local PDF isn't paper or every
// viewer.

const LINK = "https://meet.example.test/PRIVATE-LINK-SENTINEL";
const NAME = "Sentinel Interviewer";
const NOTE = "PRIVATE-NOTE-SENTINEL";
const QUESTION = "How is feedback given to new nurses?"; // a positive control: chosen, so it prints

async function signUpNurse(page: Page) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`pdf-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

/** Every URI in a link annotation, as written in the file (Chromium writes them uncompressed). */
function uris(pdf: Buffer): string[] {
  return [...pdf.toString("latin1").matchAll(/\/URI\s*\(([^)]*)\)/g)].map((m) => m[1]!);
}

test("the saved PDF has only what was chosen, no private link annotation, and unsaved changes print as a notice", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "page.pdf() is Chromium desktop only");
  await signUpNurse(page);
  await page.goto("/applications");
  await page.getByRole("button", { name: "Add an application" }).click();
  const form = page.getByRole("form", { name: "New application" });
  await form.getByLabel("Role title").fill("Ward nurse");
  await form.getByLabel("Employer").fill("Synthetic Hospital");
  await form.getByRole("button", { name: "Add application" }).click();
  await page.getByRole("link", { name: "Ward nurse" }).click();
  await page.getByRole("button", { name: "Add an event" }).click();
  const ev = page.getByRole("form", { name: "New event" });
  await ev.getByLabel("What").fill("Panel interview");
  await ev.getByLabel(/^Date/).fill("2026-11-12");
  await ev.getByRole("button", { name: "Add event" }).click();
  await page.getByRole("link", { name: "Interview-day kit" }).click();

  await page.getByRole("combobox", { name: /^Format/ }).selectOption("remote");
  await page.getByRole("textbox", { name: /^Meeting link/ }).fill(LINK);
  await page.getByRole("button", { name: "Add an interviewer" }).click();
  await page.getByLabel("Name", { exact: true }).fill(NAME);
  await page.getByLabel("Private notes").fill(NOTE);
  await page.getByLabel("Add your own question").fill(QUESTION);
  await page.locator("form").filter({ has: page.getByLabel("Add your own question") }).getByRole("button", { name: "Add" }).click();
  await page.getByRole("button", { name: "Save kit" }).click();
  await expect(page.getByText("Saved.")).toBeVisible();

  // 1. Saved, with the default choices: private details are off.
  const saved = await page.pdf({ format: "A4" });
  writeFileSync(testInfo.outputPath("kit-default.pdf"), saved);
  expect(uris(saved).filter((u) => u.includes("example.test"))).toEqual([]);
  const raw = saved.toString("latin1");
  for (const secret of ["PRIVATE-LINK-SENTINEL", NOTE, NAME]) expect(raw).not.toContain(secret); // not in metadata either

  // 2. Opted in: the link prints as text, never as a clickable annotation.
  await page.getByRole("checkbox", { name: "Meeting link (private)" }).check();
  await page.getByRole("checkbox", { name: "Interviewer names (private)" }).check();
  await page.getByRole("checkbox", { name: "Your notes (private)" }).check();
  const optedIn = await page.pdf({ format: "A4" });
  writeFileSync(testInfo.outputPath("kit-opted-in.pdf"), optedIn);
  expect(uris(optedIn).filter((u) => u.includes("example.test"))).toEqual([]);

  // 3. With an unsaved change: only the notice prints (checked as text below), even though the
  // browser's own print can't be disabled.
  await page.getByLabel("Private notes").fill(`${NOTE} edited`);
  await expect(page.getByRole("article", { name: "Your interview pack" })).toContainText("This kit has unsaved changes");
  writeFileSync(testInfo.outputPath("kit-unsaved.pdf"), await page.pdf({ format: "A4" }));
  await page.getByRole("button", { name: "Save kit" }).click();
  await expect(page.getByText("Saved.")).toBeVisible();

  // 4. Any other page still prints its own content (the kit's print rule used to blank them all).
  await page.goto("/applications");
  await page.emulateMedia({ media: "print" });
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: "Ward nurse" })).toBeVisible();
  writeFileSync(testInfo.outputPath("other-page.pdf"), await page.pdf({ format: "A4" }));
  await page.emulateMedia({ media: "screen" });
});
