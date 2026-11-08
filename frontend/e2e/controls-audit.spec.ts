import { expect, test, type Page } from "./fixtures";

// Audit: use every visible control on every page (fresh load each time) and check it does
// something: navigation, a dialog, a request, a DOM change, a changed value, or a focus move.
// Fails if any control does nothing or causes a console error or failed request. Slow (~15 min),
// so it's opt-in:  AUDIT=1 E2E_JUDGE=1 npx playwright test e2e/controls-audit.spec.ts --project=desktop
// Writes test-results/controls-audit.json.
test.skip(process.env.AUDIT !== "1", "set AUDIT=1");
test.setTimeout(30 * 60_000);
// A control that's gone should fail in seconds, not wait out the 30 minutes.
test.use({ actionTimeout: 15_000 });

type Row = { page: string; control: string; effect: string[]; errors: string[] };

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
    if ((await page.locator(CONTROLS).count()) <= i) break;
    const d = await describe(page, i);
    if (d.disabled) { rows.push({ page: url, control: d.label, effect: ["(disabled)"], errors: [] }); continue; }
    if (skip.test(d.label)) { rows.push({ page: url, control: d.label, effect: ["(skipped: destructive)"], errors: [] }); continue; }
    if (d.href && /^https?:/.test(d.href)) { rows.push({ page: url, control: d.label, effect: [`external ${d.href}`], errors: [] }); continue; }
    if (d.active) { rows.push({ page: url, control: d.label, effect: ["(already active)"], errors: [] }); continue; }

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
    page.off("console", onConsole); page.off("pageerror", onPageError); page.off("response", onResponse);
    page.off("request", onRequest); page.off("dialog", onDialog);

    const effect: string[] = [...valueEffect];
    if (after.url !== before.url) effect.push(`navigated ${after.url.replace(/^https?:\/\/[^/]+/, "")}`);
    if (dialog) effect.push(`dialog "${dialog.slice(0, 50)}"`);
    if (requests) effect.push(`${requests} request(s)`);
    if (muts > baseline + 2) effect.push(`dom +${muts} (baseline ${baseline})`);
    if (after.focus !== before.focus) effect.push("focus moved");
    rows.push({ page: url, control: d.label, effect: effect.length ? effect : ["NOTHING"], errors });
  }
  const fs = await import("node:fs");
  fs.writeFileSync("test-results/controls-audit.json", JSON.stringify(rows, null, 2)); // partial results survive
}

test("every control does something", async ({ page, context }) => {
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
  console.log(`AUDIT ${rows.length} controls, ${dead.length} with no visible effect, ${broken.length} with errors`);
  expect(dead.map((r) => `${r.page} ${r.control}`), "controls that did nothing").toEqual([]);
  expect(broken.map((r) => `${r.page} ${r.control}: ${r.errors.join("; ")}`), "controls that caused errors").toEqual([]);
});
