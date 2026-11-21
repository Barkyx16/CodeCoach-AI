import { chooseJob, expect, test } from "./fixtures";

/**
 * Two devices edit one application's private notes from the same start (Volume 8, prompt 5),
 * against the real API, in two browser contexts signed in to the same account. Before, the later
 * save silently replaced the earlier one. Now the second save is refused with the saved notes
 * shown beside its own, and nothing is overwritten until the learner chooses.
 */
test("two devices editing private application notes: one saves, the other compares both", async ({ browser }, testInfo) => {
  const phone = await (await browser.newContext()).newPage();
  const email = `notes-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.com`;
  await phone.goto("/register");
  await phone.getByLabel("Email").fill(email);
  await phone.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(phone, "registered-nurse");
  await phone.locator("#main").getByRole("button", { name: "Create account" }).click();
  await expect(phone).not.toHaveURL(/\/register$/);
  await phone.goto("/applications");
  await phone.getByRole("button", { name: "Add an application" }).click();
  const form = phone.getByRole("form", { name: "New application" });
  await form.getByLabel("Role title").fill("Ward nurse");
  await form.getByLabel("Employer").fill("Mercy General");
  await form.getByRole("button", { name: "Add application" }).click();
  await phone.getByRole("link", { name: "Ward nurse" }).first().click();
  await expect(phone).toHaveURL(/\/applications\/[0-9a-f-]{36}$/);
  const url = phone.url();

  // The laptop: another browser context, signed in to the same account, on the same application.
  const laptop = await (await browser.newContext()).newPage();
  await laptop.goto("/login");
  await laptop.getByLabel("Email").fill(email);
  await laptop.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await laptop.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(laptop).not.toHaveURL(/\/login$/);
  await laptop.goto(url);
  const notesOn = (p: typeof phone) => p.getByLabel(/Notes \(private\)/);
  await expect(notesOn(laptop)).toHaveValue("");

  // Both start from the same (empty) notes. The phone saves first.
  await notesOn(phone).fill("Recruiter: Sam. Panel on Tuesday.");
  await phone.getByRole("button", { name: "Save details" }).click();
  await expect(phone.getByText("Saved.")).toBeVisible();
  await notesOn(laptop).fill("Bring two references.");
  await laptop.getByRole("button", { name: "Save details" }).click();

  // The laptop's save is refused: both versions are shown, the phone's is still the saved one.
  const conflict = laptop.getByRole("region", { name: "Edit conflict" });
  await expect(conflict.getByText("Recruiter: Sam. Panel on Tuesday.")).toBeVisible();
  await expect(conflict.getByText("Bring two references.")).toBeVisible();
  await laptop.screenshot({ path: "e2e/screenshots/application-notes-conflict.png", fullPage: true });
  await testInfo.attach("application-notes-conflict", { path: "e2e/screenshots/application-notes-conflict.png", contentType: "image/png" });
  await phone.reload();
  await expect(notesOn(phone)).toHaveValue("Recruiter: Sam. Panel on Tuesday.");

  // The learner merges by hand on the laptop and keeps theirs, knowingly, over version 2.
  await notesOn(laptop).fill("Recruiter: Sam. Panel on Tuesday. Bring two references.");
  await conflict.getByRole("button", { name: /Keep my notes/ }).click();
  await expect(conflict).toHaveCount(0);
  await phone.reload();
  await expect(notesOn(phone)).toHaveValue("Recruiter: Sam. Panel on Tuesday. Bring two references.");
});
