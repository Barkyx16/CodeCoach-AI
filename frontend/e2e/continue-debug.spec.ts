import AxeBuilder from "@axe-core/playwright";

import { expect, setTheme, test } from "./fixtures";
import { API_URL } from "./ports";

/**
 * A debugging exercise tried and not fixed, and a scenario run at its last step, in Continue your
 * work (Volume 20, prompt 6), against the real API without a judge: an attempt saved on "Fix: Count
 * Within a Limit" is listed as a "Debugging exercise" in the very words its page's debrief used
 * ("Saved, not checked"), "tried" at its time; a scenario run left after a step says "last step". The
 * card fits 360 and 412 pixels wide with axe finding nothing in either theme; loading it sends
 * nothing; Resume opens the exercise. Synthetic account.
 */
const LAB = "debug-count-at-most";

test("Resume opens a debugging exercise not fixed yet, listed in its page's words", async ({ page, request }) => {
  const email = `cont-debug-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "software-engineer" } });
  expect(reg.status()).toBe(201);
  const auth = { Authorization: `Bearer ${((await reg.json()) as { access_token: string }).access_token}` };
  // A scenario run left after a step.
  const run = (await (await request.post(`${API_URL}/api/v1/me/scenarios/rn-two-patients/attempts`, { headers: auth, data: {} })).json()) as { id: string; current: { id: string } };
  const stepped = await request.post(`${API_URL}/api/v1/me/scenario-attempts/${run.id}/steps`, { headers: auth, data: { node_id: run.current.id } });
  expect(stepped.status()).toBe(200);

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login$/);

  // An attempt saved on the exercise's page (no judge here): its debrief's words.
  await page.goto(`/problems/${LAB}`);
  await page.getByRole("button", { name: /^Save attempt/ }).click();
  const heading = page.getByRole("region", { name: "Debugging debrief" }).getByRole("heading", { level: 3 });
  await expect(heading).toHaveText("Saved, not checked");
  const words = (await heading.textContent())!;

  const sent: string[] = [];
  page.on("request", (r) => { if (r.method() !== "GET" && !r.url().endsWith("/auth/refresh")) sent.push(`${r.method()} ${r.url()}`); });
  await page.goto("/dashboard");
  const card = page.getByRole("region", { name: "Continue your work" });
  const saved = card.getByRole("group", { name: "Saved to your account" });
  const exercise = saved.getByRole("link", { name: /Fix: Count Within a Limit/ });
  await expect(exercise).toContainText(new RegExp(`Debugging exercise · ${words} · tried .* · Resume`)); // the page's words
  await expect(exercise).toHaveCount(1); // listed once, not again as the last unsolved problem
  await expect(saved).not.toContainText("Coding problem");
  await expect(saved.getByRole("link", { name: /Two call lights at once/ })).toContainText(/Scenario run · last step .* · Resume/);
  expect(sent).toEqual([]); // loading the section starts and sends nothing

  for (const width of [360, 412]) {
    await page.setViewportSize({ width, height: 800 });
    await expect(exercise).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `${width}px`).toBe(true);
    const box = await exercise.boundingBox();
    expect(box && box.x >= 0 && box.x + box.width <= width, `${width}px`).toBe(true);
    for (const theme of ["dark", "light"]) {
      await setTheme(page, theme);
      const scan = await new AxeBuilder({ page }).include(".continue-card").analyze();
      expect(scan.violations.map((v) => v.id), `${width}px, ${theme}`).toEqual([]);
    }
  }

  await exercise.click();
  await expect(page).toHaveURL(new RegExp(`/problems/${LAB}$`));
  await expect(page.getByRole("region", { name: "Fix the bug" })).toBeVisible();
});
