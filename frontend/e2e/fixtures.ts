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
 * - what the page showed: URL, headings, alerts and status messages, busy or disabled buttons;
 * - each request still waiting, and why it waited (e2e/network-watch.ts: which of the explanations in
 *   docs/NAVIGATION.md, "Requests that never reach the API", it matches), with the servers' open
 *   connections.
 * Any request slower than 5 s is recorded for every test, passed or not ("[slow]" lines, and a
 * "slow-requests" attachment). It never records request or response bodies, form field values,
 * cookies, headers or query strings.
 */
import { readFileSync } from "node:fs";

import { test as base, type Page, type Request } from "@playwright/test";

import { NetworkWatch, ServerLog, SLOW_MS, openConnections } from "./network-watch";
import { ACCESS_LOG, API_URL, PORTS } from "./ports";

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

/**
 * From the suite API's access log: requests it started during this test (since `since`) and never
 * finished, so a browser request still waiting can be told apart: never reached the server, or
 * reached it and stuck there (Volume 9, prompt 9). Method, path and request id only.
 */
function serverOpen(since: number): string[] {
  let text: string;
  try {
    text = readFileSync(ACCESS_LOG, "utf8");
  } catch {
    return ["(the API's access log isn't available)"];
  }
  const started = new Map<string, { at: number; line: string }>();
  for (const raw of text.split("\n")) {
    let entry: { msg?: string; request_id?: string; method?: string; path?: string; at?: number };
    try { entry = JSON.parse(raw); } catch { continue; }
    if (!entry.request_id || typeof entry.at !== "number" || entry.at * 1000 < since) continue;
    if (entry.msg === "request_started") {
      started.set(entry.request_id, { at: entry.at, line: `${entry.method} ${entry.path} (started +${((entry.at * 1000 - since) / 1000).toFixed(1)}s, rid=${entry.request_id})` });
    } else if (entry.msg === "request") {
      started.delete(entry.request_id);
    }
  }
  const open = [...started.values()].map((v) => v.line);
  return open.length ? open : ["(none: every request that reached the server was answered)"];
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
      const watches: { tab: string; w: NetworkWatch | null }[] = [];
      const attaching: Promise<void>[] = [];
      let offlineOnce = false; // set once the context goes offline (below)
      // Every tab of the test's browser context; lines from a second tab start with "[tab 2]".
      const watch = (p: Page) => {
        pages.push(p);
        const tab = pages.length === 1 ? "" : `[tab ${pages.length}] `;
        attaching.push((offlineOnce ? Promise.resolve(null) : NetworkWatch.attach(p, started)).then((w) => { watches.push({ tab, w }); }));
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
      await Promise.all(attaching);
      // Offline emulation and a watch's own DevTools session don't mix (NetworkWatch.detach): before
      // the context first goes offline, the watches stop, and none start for the rest of the test.
      const setOffline = context.setOffline.bind(context);
      context.setOffline = async (offline: boolean) => {
        if (offline && !offlineOnce) {
          offlineOnce = true;
          await Promise.all(attaching);
          await Promise.all(watches.map(({ w }) => w?.detach()));
        }
        await setOffline(offline);
      };

      await use();

      // Why requests waited (docs/NAVIGATION.md): every test records any slower than SLOW_MS.
      const t0 = Date.now();
      await Promise.all(attaching);
      const failed = testInfo.status !== testInfo.expectedStatus;
      const live = watches.filter((x): x is { tab: string; w: NetworkWatch } => x.w !== null && !x.w.detached);
      const slowOnes = live.some(({ w }) => [...w.entries.values()].some((e) => (w.endOf(e) ?? Date.now()) - e.sentAt >= SLOW_MS));
      const reports = failed || slowOnes
        ? await Promise.all(live.map(async ({ tab, w }) => ({ tab, r: await w.report(new ServerLog(ACCESS_LOG, API_URL, started)) })))
        : [];
      const slow = reports.flatMap(({ tab, r }) => r.slow.map((l) => `${tab}${l}`));
      if (slow.length) {
        const text = [...slow, openConnections({ api: PORTS.api, web: PORTS.web })].join("\n");
        await testInfo.attach("slow-requests", { body: text, contentType: "text/plain" });
        process.stdout.write(`\n[slow] ${testInfo.title}\n${text.split("\n").map((l) => `[slow] ${l}`).join("\n")}\n`);
      }
      const cost = Date.now() - t0 + Math.max(0, ...live.map(({ w }) => w.setupMs));
      if (!failed) return;
      const pending = live.length
        ? reports.flatMap(({ tab, r }) => r.waiting.map((l) => `${tab}${l}`))
        : [...sent.entries()].map(([r, at]) => `${r.method()} ${pathOf(r.url())} (waiting ${Date.now() - at}ms)`);
      const body = [
        "== network and console (last lines) ==", ...lines.slice(-MAX_LINES),
        "== requests still waiting, and why (docs/NAVIGATION.md, \"Requests that never reach the API\") ==",
        ...(offlineOnce ? ["(this test went offline, so Chrome's network events weren't watched: the list is Playwright's own, without explanations)"] : []),
        ...(pending.length ? pending : ["(none)"]),
        openConnections({ api: PORTS.api, web: PORTS.web }),
        "== API requests the server started during this test and hasn't finished ==", ...serverOpen(started),
        `(network diagnostics took ${cost} ms)`,
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

/** Go to a page through the main navigation as a person does: open the heading its link sits under
 * (a panel), then click the link. In the narrow-screen menu every section is already listed. */
export async function navTo(page: import("@playwright/test").Page, name: string): Promise<void> {
  const nav = page.getByRole("navigation", { name: "Main", exact: true });
  const link = nav.getByRole("link", { name, exact: true });
  if (!(await link.isVisible())) {
    const title = page.locator(".nav-item__title").filter({ hasText: new RegExp(`^${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`) });
    await nav.locator(".nav-group").filter({ has: title }).getByRole("button").click();
  }
  await link.click();
}

/**
 * Switch the colour theme the way a scan expects to see it: set it, then wait for the colour
 * transitions it started (buttons fade their background over 120 ms while their text changes at
 * once) so an accessibility scan never samples a half-faded background under the new text colour.
 * Only CSS transitions are awaited: a spinner's endless animation would never finish.
 */
export async function setTheme(page: import("@playwright/test").Page, theme: string): Promise<void> {
  await page.evaluate(async (t) => {
    document.documentElement.setAttribute("data-theme", t);
    void getComputedStyle(document.documentElement).color; // apply the new styles now, starting their transitions
    const fading = document.getAnimations().filter((a) => typeof CSSTransition !== "undefined" && a instanceof CSSTransition);
    await Promise.all(fading.map((a) => a.finished.catch(() => undefined)));
  }, theme);
}
