import { expect, test, type Page } from "./fixtures";

// Audit: use every visible control on every page (fresh load each time) and check it does
// something: navigation, a dialog, a request, a DOM change, a changed value, or a focus move.
// Fails if any control does nothing or causes a console error or failed request. Slow (~15 min),
// so it's opt-in:  AUDIT=1 E2E_JUDGE=1 npx playwright test e2e/controls-audit.spec.ts --project=desktop
// Writes test-results/controls-audit.json.
// A control that's gone should fail in seconds, not wait out the whole run.
test.use({ actionTimeout: 15_000 });

type Row = { page: string; control: string; effect: string[]; errors: string[]; ms?: number; auth?: "signed in" | "signed out" };

/** Who the page thinks is signed in: the refresh cookie, and the Sign out control (present in the
 * DOM even inside a closed menu). A "signed-out" phase that's secretly signed in, as the first
 * corrected run found, fails here instead of auditing the wrong pages. */
async function authState(page: Page): Promise<"signed in" | "signed out"> {
  const cookie = (await page.context().cookies()).some((c) => c.name === "cc_refresh");
  const signOut = (await page.locator('button:has-text("Sign out"), a:has-text("Sign out")').count()) > 0;
  return cookie || signOut ? "signed in" : "signed out";
}

async function expectAuth(page: Page, want: "signed in" | "signed out"): Promise<void> {
  const got = await authState(page);
  if (got !== want) throw new Error(`the audit expected to be ${want} on ${page.url()}, but it's ${got}: its results would describe the wrong pages`);
}

const CONTROLS = "button:visible, a[href]:visible, [role=tab]:visible, select:visible, input[type=checkbox]:visible, input[type=radio]:visible, summary:visible";

async function describe(page: Page, i: number) {
  return page.locator(CONTROLS).nth(i).evaluate((el) => {
    const labelled = el.id ? document.querySelector(`label[for="${el.id}"]`)?.textContent : null;
    const name = (el.getAttribute("aria-label") || labelled || el.closest("label")?.textContent || el.textContent
      || el.getAttribute("title") || "").replace(/\s+/g, " ").trim();
    return {
      label: `${el.tagName.toLowerCase()}${el.getAttribute("role") ? `[${el.getAttribute("role")}]` : ""} "${name.slice(0, 60)}"`,
      disabled: (el as HTMLButtonElement).disabled || el.getAttribute("aria-disabled") === "true",
      href: el.getAttribute("href"),
      // Already where this control would take you: the current page's nav link, the selected tab.
      active: el.getAttribute("aria-current") === "page" || el.getAttribute("aria-selected") === "true"
        || (el.tagName === "A" && new URL((el as HTMLAnchorElement).href, location.href).href === location.href),
      skipLink: el.classList.contains("skip-link"),
    };
  });
}

async function settle(page: Page) {
  await page.waitForLoadState("networkidle").catch(() => {});
  await expect(page.locator(".spinner")).toHaveCount(0, { timeout: 15_000 }).catch(() => {});
  await page.waitForTimeout(300);
}

/** Use one control and record what visibly happened: navigation, a dialog, a request, a DOM
 * change beyond the page's own idle churn, a changed value, or a focus move. Errors: console
 * errors, page errors, failed requests, a click that couldn't happen. */
async function probe(page: Page, i: number, d: Awaited<ReturnType<typeof describe>>, url: string): Promise<Row> {
  const errors: string[] = [];
  const onConsole = (m: { type(): string; text(): string }) => { if (m.type() === "error") errors.push(m.text().slice(0, 160)); };
  const onPageError = (e: Error) => errors.push(`pageerror ${e.message.slice(0, 160)}`);
  const onResponse = (r: { status(): number; url(): string; request(): { method(): string } }) => {
    if (r.status() >= 400) errors.push(`${r.status()} ${r.request().method()} ${r.url().replace(/^https?:\/\/[^/]+/, "")}`);
  };
  let requests = 0;
  const onRequest = () => { requests++; };
  let dialog = "";
  const onDialog = async (dlg: { message(): string; dismiss(): Promise<void> }) => { dialog = dlg.message(); await dlg.dismiss(); };
  page.on("console", onConsole); page.on("pageerror", onPageError); page.on("response", onResponse);
  page.on("dialog", onDialog);

  // Baseline: DOM changes with nobody touching anything (clocks, polling) over the same window.
  await page.evaluate(() => {
    (window as unknown as { __m: number }).__m = 0;
    const o = new MutationObserver((ms) => { (window as unknown as { __m: number }).__m += ms.length; });
    o.observe(document.body, { subtree: true, childList: true, attributes: true, characterData: true });
  });
  await page.waitForTimeout(500);
  const baseline = await page.evaluate(() => (window as unknown as { __m: number }).__m);
  await page.evaluate(() => { (window as unknown as { __m: number }).__m = 0; });
  const before = { url: page.url(), focus: await page.evaluate(() => document.activeElement?.outerHTML.slice(0, 80) ?? "") };
  page.on("request", onRequest);

  const el = page.locator(CONTROLS).nth(i);
  // Clicking a control focuses it, so focus landing on the control itself isn't an effect: the
  // audit's self-test showed a do-nothing button "passing" that way. Marked to tell it apart.
  await el.evaluate((node) => node.setAttribute("data-audit-target", ""));
  const tag = await el.evaluate((e) => e.tagName.toLowerCase());
  const valueEffect: string[] = [];
  try {
    const type = await el.getAttribute("type");
    if (tag === "select") {
      const options = await el.locator("option").evaluateAll((os) => os.map((o) => (o as HTMLOptionElement).value));
      const current = await el.inputValue();
      const next = options.find((v) => v !== current);
      if (next !== undefined) {
        await el.selectOption(next);
        if ((await el.inputValue()) === next) valueEffect.push(`value -> ${next}`);
      }
    } else if (tag === "input" && (type === "checkbox" || type === "radio")) {
      const was = await el.isChecked();
      // Styled radios/checkboxes are visually replaced by their label, which is what people click.
      await el.evaluate((node) => ((node as HTMLInputElement).labels?.[0] ?? (node as HTMLElement)).click());
      if ((await el.isChecked()) !== was || type === "radio") valueEffect.push(`checked ${await el.isChecked()}`);
    } else if (d.skipLink) {
      await page.keyboard.press("Tab"); // keyboard-only by design: it appears when focused
      await page.keyboard.press("Enter");
    } else {
      await el.click({ timeout: 5000 });
    }
  } catch (e) {
    errors.push(`click failed: ${((e as Error).message.split("\n")[0] ?? "").slice(0, 120)}`);
  }
  await page.waitForTimeout(500);
  await page.waitForLoadState("networkidle").catch(() => {});
  const muts = await page.evaluate(() => (window as unknown as { __m: number }).__m);
  const after = { url: page.url(), focus: await page.evaluate(() => document.activeElement?.outerHTML.slice(0, 80) ?? "") };
  const focusOnItself = await page.evaluate(() => document.activeElement?.hasAttribute("data-audit-target") ?? false);
  await el.evaluate((node) => node.removeAttribute("data-audit-target")).catch(() => {}); // may be gone
  page.off("console", onConsole); page.off("pageerror", onPageError); page.off("response", onResponse);
  page.off("request", onRequest); page.off("dialog", onDialog);

  const effect: string[] = [...valueEffect];
  if (after.url !== before.url) effect.push(`navigated ${after.url.replace(/^https?:\/\/[^/]+/, "")}`);
  if (dialog) effect.push(`dialog "${dialog.slice(0, 50)}"`);
  if (requests) effect.push(`${requests} request(s)`);
  if (muts > baseline + 2) effect.push(`dom +${muts} (baseline ${baseline})`);
  if (after.focus !== before.focus && !focusOnItself) effect.push("focus moved");
  return { page: url, control: d.label, effect: effect.length ? effect : ["NOTHING"], errors };
}

async function audit(page: Page, url: string, rows: Row[], skip: RegExp, signedOut = false) {
  await page.goto(url);
  await settle(page);
  const total = await page.locator(CONTROLS).count();
  for (let i = 0; i < total; i++) {
    // Signed out means no session at all: storage AND the refresh cookie, which a "Try it now"
    // or sign-up click on an earlier control would otherwise leave behind.
    if (signedOut) {
      await page.context().clearCookies();
      await page.evaluate(() => { localStorage.clear(); sessionStorage.clear(); });
    }
    await page.goto(url);
    await settle(page);
    await expectAuth(page, signedOut ? "signed out" : "signed in");
    if ((await page.locator(CONTROLS).count()) <= i) break;
    const d = await describe(page, i);
    if (d.disabled) { rows.push({ page: url, control: d.label, effect: ["(disabled)"], errors: [] }); continue; }
    if (skip.test(d.label)) { rows.push({ page: url, control: d.label, effect: ["(skipped: destructive)"], errors: [] }); continue; }
    if (d.href && /^https?:/.test(d.href)) { rows.push({ page: url, control: d.label, effect: [`external ${d.href}`], errors: [] }); continue; }
    if (d.active) { rows.push({ page: url, control: d.label, effect: ["(already active)"], errors: [] }); continue; }

    const t0 = Date.now();
    const row = await probe(page, i, d, url);
    rows.push({ ...row, ms: Date.now() - t0, auth: signedOut ? "signed out" : "signed in" });
  }
  const fs = await import("node:fs");
  fs.writeFileSync("test-results/controls-audit.json", JSON.stringify(rows, null, 2)); // partial results survive
}

// The audit's own checks: a broken control and a broken setup must show up as findings, or a
// clean audit means nothing. Fast, so they run in every e2e run.
test("the audit flags a control that does nothing, and one that throws", async ({ page }) => {
  await page.goto("/");
  await settle(page);
  await page.evaluate(() => {
    const dead = document.createElement("button");
    dead.textContent = "Audit self-test: does nothing";
    const throws = document.createElement("button");
    throws.textContent = "Audit self-test: throws";
    throws.addEventListener("click", () => { throw new Error("audit self-test"); });
    document.body.prepend(dead, throws);
  });
  const at = async (name: string) =>
    (await page.locator(CONTROLS).evaluateAll((els, n) => els.findIndex((e) => e.textContent === n), name));
  const dead = await probe(page, await at("Audit self-test: does nothing"), await describe(page, await at("Audit self-test: does nothing")), "/");
  expect(dead.effect).toEqual(["NOTHING"]);
  const throws = await probe(page, await at("Audit self-test: throws"), await describe(page, await at("Audit self-test: throws")), "/");
  expect(throws.errors.join(" ")).toContain("pageerror audit self-test");
});

test("a signed-out pass that's secretly signed in is caught, not audited", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click(); // a guest session, as an audited click would make
  await page.waitForURL(/\/welcome|\/problems/);
  await page.evaluate(() => { localStorage.clear(); sessionStorage.clear(); }); // what the first audit did
  await page.goto("/");
  await settle(page);
  await expect(expectAuth(page, "signed out")).rejects.toThrow(/expected to be signed out.*signed in/);
  await page.context().clearCookies(); // what it does now
  await page.goto("/");
  await settle(page);
  await expectAuth(page, "signed out");
});

test("every control does something", async ({ page, context, browserName }, testInfo) => {
  test.skip(process.env.AUDIT !== "1", "the full audit is opt-in (~18 min): AUDIT=1");
  test.setTimeout(30 * 60_000);
  const started = Date.now();
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const rows: Row[] = [];
  // Public pages first, signed out.
  for (const url of ["/", "/login", "/register", "/problems", "/problems/two-sum", "/no-such-page"]) {
    await audit(page, url, rows, /Sign out|Delete/i, true);
  }
  await page.context().clearCookies();
  await page.evaluate(() => { localStorage.clear(); sessionStorage.clear(); });

  // Sign in as a guest and create real activity so every page has content.
  await page.goto("/");
  await page.getByRole("button", { name: /try it now/i }).click();
  await page.getByRole("button", { name: "Start this problem" }).click(); // the optional welcome
  await expect(page).toHaveURL(/two-sum/);
  await page.getByRole("button", { name: "Get a hint" }).click();
  await expect(page.getByText(/level 1/i).first()).toBeVisible();
  await page.getByRole("tab", { name: "Code review" }).click();
  await page.getByRole("button", { name: /review my code/i }).click();
  await expect(page.getByText(/AI feedback can be wrong/)).toBeVisible();
  await page.getByRole("button", { name: /^(Submit|Save attempt)$/ }).click(); // "Save attempt" when no judge is configured
  await expect(page.getByText(/Some tests failed|Your code didn't compile|All tests passed|Saved, but not run/)).toBeVisible({ timeout: 60_000 });
  // A finished interview (for history and results pages) and a live one.
  await page.goto("/interviews");
  await page.getByRole("button", { name: "Start interview" }).click();
  await expect(page).toHaveURL(/\/interviews\/[0-9a-f-]+$/);
  const finishedUrl = page.url().replace(/^https?:\/\/[^/]+/, "");
  await page.getByLabel("Your answer").fill("Can the array be empty?");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByLabel("Interviewer is typing")).toHaveCount(0);
  await page.getByRole("button", { name: "Finish & get feedback" }).click();
  await expect(page.getByRole("heading", { name: "Interview feedback" })).toBeVisible();

  for (const url of ["/", "/problems", "/problems/two-sum", "/problems/coin-change", "/dashboard", "/analytics",
    "/history", "/history?type=interview", "/interviews", finishedUrl, "/settings"]) {
    await audit(page, url, rows, /Sign out|Delete my account|Delete account/i);
  }
  // A live interview last (its controls can end it).
  await page.goto("/interviews");
  await settle(page);
  // The audit of /interviews may already have started one (one interview at a time): then the
  // page offers "Resume it" and Start is disabled, rather than a Start that can only fail.
  const resume = page.getByRole("link", { name: "Resume it" });
  if (await resume.isVisible()) await resume.click();
  else await page.getByRole("button", { name: "Start interview" }).click();
  await expect(page).toHaveURL(/\/interviews\/[0-9a-f-]+$/);
  await audit(page, page.url().replace(/^https?:\/\/[^/]+/, ""), rows, /Sign out|Delete|End early/i);

  const fs = await import("node:fs");
  fs.writeFileSync("test-results/controls-audit.json", JSON.stringify(rows, null, 2));
  const dead = rows.filter((r) => r.effect[0] === "NOTHING");
  const broken = rows.filter((r) => r.errors.length);
  const kind = (r: Row) => (r.effect[0]?.startsWith("(") ? r.effect[0] : r.effect[0]?.startsWith("external") ? "(external link)" : "used");
  const counts: Record<string, number> = {};
  for (const r of rows) counts[kind(r)] = (counts[kind(r)] ?? 0) + 1;
  const { execSync } = await import("node:child_process");
  let sha = process.env.GITHUB_SHA ?? "";
  try { sha ||= execSync("git rev-parse HEAD", { encoding: "utf8" }).trim(); } catch { sha ||= "unknown"; }
  let dirty = false;
  try { dirty = execSync("git status --porcelain", { encoding: "utf8" }).trim().length > 0; } catch { /* no git */ }
  // The report says what was tested and what wasn't, so a clean result can't overstate itself.
  fs.writeFileSync("test-results/controls-audit-summary.json", JSON.stringify({
    finished: true,
    commit: sha,
    uncommitted_changes: dirty,
    browser: `${browserName} ${context.browser()?.version() ?? ""}`.trim(),
    viewport: testInfo.project.use.viewport ?? null,
    judge: process.env.E2E_JUDGE === "1",
    minutes: Math.round((Date.now() - started) / 6000) / 10,
    controls: rows.length,
    unique_controls: new Set(rows.map((r) => r.control)).size,
    pages: [...new Set(rows.map((r) => r.page))],
    outcomes: counts,
    no_visible_effect: dead.map((r) => `${r.page} ${r.control}`),
    errors: broken.map((r) => `${r.page} ${r.control}: ${r.errors.join("; ")}`),
    not_covered: [
      "destructive controls (Sign out, Delete my account, End early) are recorded as skipped, not used",
      "external links are recorded, not followed",
      "one browser and one viewport per run; keyboard use only for the skip link",
      "effects are visible changes, not proof that the action did the right thing (the functional e2e specs check that)",
    ],
  }, null, 2));
  console.log(`AUDIT ${rows.length} controls (${new Set(rows.map((r) => r.control)).size} unique), ${dead.length} with no visible effect, ${broken.length} with errors`);
  expect(dead.map((r) => `${r.page} ${r.control}`), "controls that did nothing").toEqual([]);
  expect(broken.map((r) => `${r.page} ${r.control}: ${r.errors.join("; ")}`), "controls that caused errors").toEqual([]);
});
