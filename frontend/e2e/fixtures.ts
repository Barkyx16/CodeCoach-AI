/**
 * Playwright with failure diagnostics. Specs import `test` and `expect` from here instead of
 * "@playwright/test" (everything else is re-exported unchanged).
 *
 * On a failed test, an automatic fixture writes a text summary to stdout (lines start with
 * "[diag]"), which the CI reporter prints in full in the job log, and attaches it to the result
 * (artifacts aren't always reachable):
 * - API calls: method, path (no query string), status, time to response, X-Request-ID;
 * - failed requests (including JS modules), console errors and warnings, page errors;
 * - the app's own breadcrumbs (src/lib/diagnostics.ts): round actions and views, auth refreshes;
 * - what the page showed: URL, headings, alerts and status messages, busy or disabled buttons.
 * It never records request or response bodies, form field values, cookies or headers.
 */
import { test as base, type Page, type Request } from "@playwright/test";

export * from "@playwright/test";

const MAX_LINES = 120;

function pathOf(url: string): string {
  try {
    const u = new URL(url);
    return u.pathname;
  } catch {
    return url.slice(0, 120);
  }
}

function isInteresting(url: string): boolean {
  const path = pathOf(url);
  return path.startsWith("/api/") || path.startsWith("/src/") || path.startsWith("/node_modules/") || path.endsWith(".js");
}

async function pageState(page: Page): Promise<string[]> {
  try {
    return await page.evaluate(() => {
      const text = (el: Element) => (el.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 140);
      const lines = [`url: ${location.pathname}${location.search ? "?…" : ""}`];
      for (const h of document.querySelectorAll("h1, h2")) lines.push(`${h.tagName.toLowerCase()}: ${text(h)}`);
      for (const a of document.querySelectorAll("[role=alert], .inline-error")) if (text(a)) lines.push(`alert: ${text(a)}`);
      for (const s of document.querySelectorAll("[role=status]")) if (text(s)) lines.push(`status: ${text(s)}`);
      for (const b of document.querySelectorAll("button[disabled], button[aria-busy=true]")) lines.push(`button (${b.hasAttribute("disabled") ? "disabled" : "busy"}): ${text(b)}`);
      return lines.slice(0, 40);
    });
  } catch (error) {
    return [`(page state unavailable: ${String(error).slice(0, 120)})`];
  }
}

async function appEvents(page: Page): Promise<string[]> {
  try {
    const events = await page.evaluate(() => (window as unknown as { __ccDiag?: Record<string, unknown>[] }).__ccDiag ?? []);
    return events.slice(-80).map((e) => JSON.stringify(e));
  } catch (error) {
    return [`(app breadcrumbs unavailable: ${String(error).slice(0, 120)})`];
  }
}

export const test = base.extend<{ failureDiagnostics: void }>({
  failureDiagnostics: [
    async ({ page, context }, use, testInfo) => {
      const started = Date.now();
      const at = () => `+${((Date.now() - started) / 1000).toFixed(1)}s`;
      const lines: string[] = [];
      const push = (line: string) => {
        lines.push(`${at()} ${line}`);
        if (lines.length > MAX_LINES * 2) lines.splice(0, lines.length - MAX_LINES);
      };
      const sent = new Map<Request, number>();
      const pages: Page[] = [];
      // Every tab of the test's browser context; lines from a second tab start with "[tab 2]".
      const watch = (p: Page) => {
        pages.push(p);
        const tab = pages.length === 1 ? "" : `[tab ${pages.length}] `;
        p.on("request", (r) => { if (isInteresting(r.url())) sent.set(r, Date.now()); });
        p.on("requestfinished", (r) => { sent.delete(r); });
        p.on("response", (r) => {
          const req = r.request();
          if (!pathOf(r.url()).startsWith("/api/")) return;
          const t0 = sent.get(req);
          push(`${tab}${req.method()} ${pathOf(r.url())} -> ${r.status()} in ${t0 ? Date.now() - t0 : "?"}ms rid=${r.headers()["x-request-id"] ?? "-"}`);
        });
        p.on("requestfailed", (r) => {
          sent.delete(r);
          if (isInteresting(r.url())) push(`${tab}FAILED ${r.method()} ${pathOf(r.url())}: ${r.failure()?.errorText ?? "unknown"}`);
        });
        p.on("console", (m) => {
          if (m.type() === "error" || m.type() === "warning") push(`${tab}console.${m.type()}: ${m.text().replace(/\s+/g, " ").slice(0, 200)}`);
        });
        p.on("pageerror", (e) => push(`${tab}pageerror: ${e.message.slice(0, 200)}`));
        p.on("framenavigated", (f) => { if (f === p.mainFrame()) push(`${tab}navigated: ${pathOf(f.url())}`); });
      };
      watch(page);
      context.on("page", watch);

      await use();

      if (testInfo.status === testInfo.expectedStatus) return;
      const pending = [...sent.entries()].map(([r, t0]) => `${r.method()} ${pathOf(r.url())} (waiting ${Date.now() - t0}ms)`);
      const body = [
        "== network and console (last lines) ==", ...lines.slice(-MAX_LINES),
        "== requests still waiting ==", ...(pending.length ? pending : ["(none)"]),
      ];
      for (const [i, p] of pages.entries()) {
        const tab = pages.length === 1 ? "" : ` (tab ${i + 1}${p.isClosed() ? ", closed" : ""})`;
        if (p.isClosed()) continue;
        body.push(`== app breadcrumbs${tab} (last 80) ==`, ...(await appEvents(p)), `== page${tab} ==`, ...(await pageState(p)));
      }
      const text = body.join("\n");
      await testInfo.attach("failure-diagnostics", { body: text, contentType: "text/plain" });
      // Reporters show only the start of an attachment; stdout is printed in full in the CI log.
      process.stdout.write(`\n[diag] ${testInfo.title}\n${text.split("\n").map((l) => `[diag] ${l}`).join("\n")}\n`);
    },
    { auto: true },
  ],
});

/** Choose a job in the job search box (CareerSelect) as a person does: type part of its name,
 * then click it in the matches. `slug` identifies the job; its words are what gets typed. */
export async function chooseJob(
  scope: import("@playwright/test").Page | import("@playwright/test").Locator,
  slug: string,
  label: string | RegExp = "Job you're preparing for",
): Promise<void> {
  await scope.getByRole("combobox", { name: label }).fill(slug.replace(/-/g, " "));
  await scope.locator(`[role="option"][data-value="${slug}"]`).click();
}
