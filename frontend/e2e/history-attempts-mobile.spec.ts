import { expect, test } from "./fixtures";
import { API_URL } from "./ports";

/**
 * History on a phone (Volume 17, prompt 2) against the real API: a scenario run, a code review and a
 * sample-answer comparison, each made through the API on a fresh account, are rows in History; at
 * 412 and 360 pixels wide the rows wrap and the page doesn't scroll sideways; each row's link opens
 * that one attempt (its own page, or the lesson's page showing that reading). Synthetic account.
 */
test("scenario runs, code reviews and comparisons are History rows that open their attempt, at phone widths", async ({ page, request }) => {
  const email = `hist-m-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, { data: { email, password: "CorrectHorse42", career_track: "registered-nurse" } });
  expect(reg.status()).toBe(201);
  const auth = { Authorization: `Bearer ${((await reg.json()) as { access_token: string }).access_token}` };

  const run = await request.post(`${API_URL}/api/v1/me/scenarios/rn-two-patients/attempts`, { headers: auth, data: {} });
  expect(run.status()).toBe(200);
  const runId = ((await run.json()) as { id: string }).id;
  const review = await request.post(`${API_URL}/api/v1/me/code-reviews/review-second-largest/attempts`, {
    headers: auth,
    data: { findings: [{ id: "d", start_line: 9, end_line: 10, problem: "duplicates of the max slip in", consequence: "", repair: "" }], summary: "" },
  });
  expect([200, 201]).toContain(review.status());
  const reviewId = ((await review.json()) as { id: string }).id;
  const lesson = (await (await request.get(`${API_URL}/api/v1/comparisons/cmp-specific-evidence`)).json()) as { kind: string; samples: { id: string; sentences: { id: string }[] }[] };
  const sample = lesson.samples[0]!;
  const reading = await request.post(`${API_URL}/api/v1/me/comparisons/cmp-specific-evidence/attempts`, {
    headers: auth,
    data: { selections: [{ sample: sample.id, sentence: sample.sentences[0]!.id, kind: "strength", reason: "It names a real action taken." }], choice: lesson.kind === "clear" ? sample.id : null, revealed_early: false },
  });
  expect([200, 201]).toContain(reading.status());
  const readingId = ((await reading.json()) as { id: string }).id;

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await page.locator("#main").getByRole("button", { name: "Sign in" }).tap();
  await expect(page).not.toHaveURL(/\/login$/);

  const noSideways = () => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  const rowFor = (href: string) => page.locator(`a.activity-row[href="${href}"]`);
  const rows = {
    scenario: `/scenarios/attempts/${runId}`,
    review: `/code-reviews/attempts/${reviewId}`,
    reading: `/compare/cmp-specific-evidence?attempt=${readingId}`,
  };
  for (const width of [412, 360]) {
    await page.setViewportSize({ width, height: 800 });
    await page.goto("/history");
    await expect(page.getByRole("heading", { level: 1, name: "History" })).toBeVisible();
    await expect(rowFor(rows.scenario)).toContainText("In progress");
    // Compared since Volume 20, prompt 2: one in progress says why it isn't yet.
    await expect(rowFor(rows.scenario)).toContainText("Not compared: it isn't finished, so there's no result yet");
    await expect(rowFor(rows.review)).toContainText("points at");
    await expect(rowFor(rows.reading)).toContainText("matching the explanation");
    expect(await noSideways(), `no sideways scroll at ${width} px`).toBe(true);
  }

  // Each link opens that attempt.
  await rowFor(rows.scenario).tap();
  await expect(page).toHaveURL(new RegExp(`/scenarios/attempts/${runId}$`));
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  expect(await noSideways()).toBe(true);
  await page.goBack();
  await rowFor(rows.review).tap();
  await expect(page).toHaveURL(new RegExp(`/code-reviews/attempts/${reviewId}$`));
  await expect(page.getByRole("heading", { name: "The code you reviewed" })).toBeVisible();
  expect(await noSideways()).toBe(true);
  await page.goBack();
  await rowFor(rows.reading).tap();
  await expect(page).toHaveURL(new RegExp(`attempt=${readingId}$`));
  await expect(page.getByRole("heading", { name: "Your reading and the explanation" })).toBeVisible();
  expect(await noSideways()).toBe(true);
});
