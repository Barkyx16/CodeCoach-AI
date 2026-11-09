import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

import { chooseJob, expect, test, type Page, type Request } from "./fixtures";
import { E2E_DATABASE_URL } from "./ports";

// One answer followed across the system (docs/OBSERVABILITY.md): the browser's trace context goes
// with the request, the API continues it, the page reports what it showed, and an admin reads the
// whole action back by its trace id. Real browser, real backend.

const ANSWER = "Last winter a patient's oxygen dropped during my assessment. I checked his vital signs, started oxygen per protocol and called the rapid response team. As a result he was stable within 30 minutes, and I learned to escalate early.";
const TRACEPARENT = /^00-([0-9a-f]{32})-[0-9a-f]{16}-01$/;

async function signUp(page: Page, tag: string): Promise<string> {
  const email = `${tag}-${Date.now()}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("CorrectHorse42");
  await chooseJob(page, "registered-nurse");
  await page.locator("#main").getByRole("button", { name: "Create account" }).click();
  await page.getByRole("link", { name: "Do this later" }).click();
  await page.getByRole("button", { name: "Not now, take me to my dashboard" }).click(); // the optional welcome
  await expect(page).toHaveURL(/\/dashboard$/);
  return email;
}

function grantAdmin(email: string) {
  // The same command an operator runs; there is no API for it.
  execFileSync(process.env.PYTHON ?? "python", ["-m", "app.cli", "grant-admin", email], {
    cwd: resolve(process.cwd(), "../backend"),
    env: { ...process.env, DATABASE_URL: E2E_DATABASE_URL, SECRET_KEY: "e2e-secret-key-that-is-at-least-32-characters" },
  });
}

const isAnswer = (r: Request) => r.method() === "POST" && r.url().endsWith("/answers");
const traceOf = (r: Request) => TRACEPARENT.exec(r.headers()["traceparent"] ?? "")?.[1] ?? "";

test("an answer is followed from the click through the server to what the screen showed", async ({ page, browser }) => {
  await signUp(page, "trace");
  await page.goto("/interviews/questions");
  await page.getByRole("radio", { name: /Behavioral interview/ }).check();
  await page.getByRole("button", { name: "Start interview" }).click();
  await expect(page.getByText(/QUESTION 1 OF 5/)).toBeVisible();

  // A normal answer: the request carries the action's trace, and the response names the same one.
  const sent = page.waitForRequest(isAnswer);
  const answered = page.waitForResponse((r) => isAnswer(r.request()));
  await page.getByLabel("Your answer", { exact: true }).fill(ANSWER);
  await page.getByRole("button", { name: "Next question" }).click();
  const shownTrace = traceOf(await sent);
  expect(shownTrace).toMatch(/^[0-9a-f]{32}$/);
  expect((await answered).headers()["x-trace-id"]).toBe(shownTrace);
  const reply = page.getByLabel("Your reply");
  await expect(reply.or(page.getByText(/QUESTION 2 OF 5/))).toBeVisible();
  if (await reply.isVisible()) await page.getByRole("button", { name: "Skip follow-up" }).click();
  await expect(page.getByText(/QUESTION 2 OF 5/)).toBeVisible();

  // The next answer is saved by the server, but its response never reaches the browser.
  await page.route("**/api/v1/interviews/*/answers", async (route) => {
    await route.fetch();
    await route.abort("connectionreset");
  }, { times: 1 });
  const lostSent = page.waitForRequest(isAnswer);
  await page.getByLabel("Your answer", { exact: true }).fill(ANSWER);
  await page.getByRole("button", { name: "Next question" }).click();
  const lostTrace = traceOf(await lostSent);
  await expect(page.getByRole("alert")).toContainText(/can't reach/i);
  await expect(page.getByLabel("Your answer", { exact: true })).toHaveValue(ANSWER); // nothing lost
  // The page reports it (in its next small batch, to this app's own API).
  const reported = await page.waitForRequest((r) => r.url().endsWith("/api/v1/telemetry/ui") && (r.postData() ?? "").includes(lostTrace));
  expect((await reported.response())?.status()).toBe(204);
  expect(reported.postData()).not.toContain("vital signs"); // never the learner's words

  // An admin reads both actions back.
  const adminContext = await browser.newContext();
  const admin = await adminContext.newPage();
  const adminEmail = await signUp(admin, "trace-admin");
  grantAdmin(adminEmail);
  await admin.goto(`/admin/traces/${lostTrace}`);
  const onServer = admin.getByRole("region", { name: "On the server" });
  await expect(onServer).toContainText("round.action");
  await expect(onServer).toContainText(/result=(advanced|followup)/); // the server saved it…
  await expect(onServer).toContainText("evaluate");
  await expect(admin.getByRole("region", { name: "In the browser" })).toContainText("answer: network_error"); // …the browser never saw it

  await admin.getByLabel("Trace id or request id").fill(shownTrace);
  await admin.getByRole("button", { name: "Look up" }).click();
  await expect(admin).toHaveURL(new RegExp(`/admin/traces/${shownTrace}$`));
  await expect(admin.getByRole("region", { name: "In the browser" })).toContainText("answer: rendered");
  await adminContext.close();
});
