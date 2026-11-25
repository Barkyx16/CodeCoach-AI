import AxeBuilder from "@axe-core/playwright";

import { expect, setTheme, test, type Page } from "./fixtures";
import { API_URL } from "./ports";

/**
 * Kit templates come back from a backup file (Volume 20, prompt 7), against the real API: a template
 * saved (and edited, so it's at revision 2), the file downloaded through Settings, restored on a fresh
 * account through the page (its preview naming it and saying what comes back), the restored template
 * at revision 1 used to start a kit, then the restore undone: the template goes, the kit keeps what
 * it was given. axe finds nothing on the preview in either theme. Synthetic accounts only.
 */
const PASSWORD = "CorrectHorse42";

async function account(request: import("@playwright/test").APIRequestContext, tag: string) {
  const email = `${tag}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: PASSWORD, career_track: "registered-nurse" } });
  expect(reg.status()).toBe(201);
  return { email, auth: { Authorization: `Bearer ${((await reg.json()) as { access_token: string }).access_token}` } };
}

async function signIn(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
}

test("a template restored on a fresh account starts a kit, and undoing the restore leaves the kit alone", async ({ page, request }, testInfo) => {
  const a = await account(request, "kt-source");
  const made = (await (await request.post(`${API_URL}/api/v1/me/kit-templates`, { headers: a.auth, data: {
    name: "Ward interviews",
    checklist: [{ text: "Print two copies of my registration" }, { text: "Plan the bus route" }],
    questions: [{ text: "How is the preceptorship structured?", group: "training" }],
  } })).json()) as { id: string };
  expect((await request.patch(`${API_URL}/api/v1/me/kit-templates/${made.id}`, { headers: a.auth, data: { name: "Ward interviews", expected_revision: 1 } })).status()).toBe(200);

  // The file, downloaded through Settings as the learner would.
  await signIn(page, a.email);
  await page.goto("/settings");
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Download my data" }).click()]);
  const file = testInfo.outputPath("codecoach-data.json");
  await download.saveAs(file);
  await page.getByRole("region", { name: "Sign out" }).getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).not.toHaveURL(/\/settings/); // signed out

  // A fresh account restores it through the page.
  const b = await account(request, "kt-restored");
  await signIn(page, b.email);
  await page.goto("/settings/restore");
  await page.getByLabel("Backup file").setInputFiles(file);
  const pv = page.getByRole("region", { name: "2. Check what would be added" });
  const box = pv.getByRole("checkbox", { name: "Kit templates: checklist items and questions to start a kit from: 1 new" });
  await expect(box).toBeChecked();
  await expect(pv).toContainText("for example “Ward interviews”");
  await expect(pv).toContainText("Each comes back as a new template at revision 1, checked as saving one is");
  for (const theme of ["dark", "light"]) {
    await setTheme(page, theme);
    const scan = await new AxeBuilder({ page }).include(".restore-preview").analyze();
    expect(scan.violations.map((v) => v.id), theme).toEqual([]);
  }
  await expect(pv.getByRole("checkbox", { checked: true })).toHaveCount(1); // the file holds nothing else new
  await pv.getByRole("button", { name: "Restore kit templates" }).click();
  await expect(page.getByText("Restored: 1 kit templates.")).toBeVisible();
  const [restored] = (await (await request.get(`${API_URL}/api/v1/me/kit-templates`, { headers: b.auth })).json()) as { id: string; name: string; revision: number }[];
  expect([restored!.name, restored!.revision]).toEqual(["Ward interviews", 1]); // its history stays behind

  // It starts a kit, as one saved here would.
  const app = (await (await request.post(`${API_URL}/api/v1/me/applications`, { headers: b.auth, data: { employer: "Mercy General", role_title: "Ward nurse", stage: "interviewing" } })).json()) as { id: string };
  await request.post(`${API_URL}/api/v1/me/applications/${app.id}/events`, { headers: b.auth, data: { title: "Panel interview", on_date: "2026-12-08" } });
  const [ev] = ((await (await request.get(`${API_URL}/api/v1/me/applications/${app.id}`, { headers: b.auth })).json()) as { events: { id: string }[] }).events;
  const kit = `/applications/${app.id}/events/${ev!.id}/kit`;
  await page.goto(kit);
  await page.getByLabel("Start from one of your templates").selectOption({ label: "Ward interviews (3)" });
  await page.getByRole("button", { name: "Add to this kit" }).click();
  await expect(page.getByText(/Added 2 checklist items and 1 question from “Ward interviews”/)).toBeVisible();
  await page.getByRole("button", { name: "Save kit" }).click();
  await expect(page.getByText("Saved.")).toBeVisible();

  // Undo the restore: the template goes; the kit keeps its items.
  await page.goto("/settings/restore");
  page.once("dialog", (d) => void d.accept());
  await page.getByRole("button", { name: "Remove what this added" }).click();
  await expect(page.getByText(/Removed 1; kept 0 you'd changed since; 0 were already gone\./)).toBeVisible();
  expect(await (await request.get(`${API_URL}/api/v1/me/kit-templates`, { headers: b.auth })).json()).toEqual([]);
  const saved = (await (await request.get(`${API_URL}/api/v1/me${kit}`, { headers: b.auth })).json()) as { checklist: { text: string }[]; questions: { text: string }[] };
  expect(saved.checklist.map((c) => c.text)).toEqual(expect.arrayContaining(["Print two copies of my registration", "Plan the bus route"]));
  expect(saved.questions.map((q) => q.text)).toContain("How is the preceptorship structured?");
  // The source account's template is untouched.
  const theirs = (await (await request.get(`${API_URL}/api/v1/me/kit-templates/${made.id}`, { headers: a.auth })).json()) as { revision: number };
  expect(theirs.revision).toBe(2);
});
