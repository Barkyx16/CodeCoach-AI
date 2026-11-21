#!/usr/bin/env node
/**
 * The web image's Content-Security-Policy, checked from a real browser (Chromium), not from the
 * header's text.
 *
 *   node scripts/check-csp.mjs WEB_URL API_URL
 *
 * WEB_URL serves the built image (nginx); the image was built with VITE_API_BASE_URL=API_URL, and
 * that API is running. Checks, each reported; exit 1 if any fails:
 * - Every kind of response carries the policy, with connect-src exactly 'self' + the API origin:
 *   the app shell, a deep link, a built asset, the service worker, the manifest. (nginx drops
 *   inherited headers in a location that sets its own.)
 * - Real flows run with no violation:
 *   - the landing page and sign-in;
 *   - a client-routed deep link;
 *   - the code editor, which needs its blob: worker;
 *   - an authenticated cross-origin API call (Try it now creates a guest, then pages load
 *     signed in).
 * - What the policy exists for is still refused, and reported as a CSP violation (not confused
 *   with CORS, DNS or TLS):
 *   - a fetch to an origin that isn't the API;
 *   - an external script;
 *   - an inline script.
 * Synthetic data only: the guest account is disposable.
 */
import { chromium } from "playwright";

const [web, api] = process.argv.slice(2);
if (!web || !api) {
  console.error("usage: node scripts/check-csp.mjs WEB_URL API_URL");
  process.exit(2);
}
const apiOrigin = new URL(api).origin;
const elsewhere = "http://127.0.0.1:9"; // not the API: nothing needs to listen, the policy stops it first
const results = [];
const check = (name, ok, detail = "") => results.push({ name, ok: Boolean(ok), detail });

// 1. Headers on every kind of response.
const shell = await fetch(web + "/");
const html = await shell.text();
const asset = html.match(/\/assets\/[^"']+\.js/)?.[0];
for (const path of ["/", "/dashboard", asset, "/sw.js", "/manifest.webmanifest"].filter(Boolean)) {
  const res = await fetch(web + path);
  const csp = res.headers.get("content-security-policy") ?? "";
  const connect = csp.match(/connect-src ([^;]+)/)?.[1]?.trim();
  check(`policy on ${path}`, res.ok && connect === `'self' ${apiOrigin}`, connect ?? "(no policy)");
}

// 2. Real flows in a browser, collecting every violation the page reports.
const browser = await chromium.launch();
const page = await (await browser.newContext()).newPage();
await page.addInitScript(() => {
  window.__csp = [];
  document.addEventListener("securitypolicyviolation", (e) =>
    window.__csp.push({ directive: e.effectiveDirective, blocked: e.blockedURI, sample: e.sample }));
});
const violations = async () => page.evaluate(() => window.__csp.splice(0));

await page.goto(web + "/");
await page.getByRole("button", { name: /try it now/i }).waitFor();
check("landing page: no violation", (await violations()).length === 0);

await page.goto(web + "/login");
await page.getByRole("heading").first().waitFor();
check("sign-in page: no violation", (await violations()).length === 0);

await page.goto(web + "/");
const guest = page.waitForResponse((r) => r.url() === `${apiOrigin}/api/v1/auth/guest` && r.request().method() === "POST");
await page.getByRole("button", { name: /try it now/i }).click();
const created = await guest;
await page.waitForURL(/\/welcome|\/problems|\/dashboard/);
check("authenticated cross-origin API call (guest sign-in) allowed", created.ok(), `${created.status()} ${new URL(created.url()).pathname}`);
check("signed in: no violation", (await violations()).length === 0);

await page.goto(web + "/dashboard");
await page.getByRole("heading").first().waitFor();
check("deep link /dashboard, signed in: no violation", (await violations()).length === 0);

await page.goto(web + "/problems/two-sum");
await page.locator(".monaco-editor").first().waitFor({ timeout: 30_000 });
await page.waitForTimeout(1500); // the editor's worker starts after it renders
const editor = await violations();
check("code editor and its worker: no violation", editor.length === 0, JSON.stringify(editor));

// 3. What the policy is for.
const fetched = await page.evaluate(async (url) => {
  try {
    await fetch(url);
    return "allowed";
  } catch (e) {
    return String(e);
  }
}, elsewhere + "/exfiltrate");
await page.waitForTimeout(300);
const blockedFetch = await violations();
check("a fetch to another origin is refused by connect-src", fetched !== "allowed" && blockedFetch.some((v) => v.directive === "connect-src"), JSON.stringify(blockedFetch));

await page.evaluate((url) => {
  const s = document.createElement("script");
  s.src = url;
  document.head.append(s);
}, elsewhere + "/evil.js");
await page.waitForTimeout(300);
const blockedScript = await violations();
check("an external script is refused by script-src", blockedScript.some((v) => v.directive.startsWith("script-src")), JSON.stringify(blockedScript));

await page.evaluate(() => {
  const s = document.createElement("script");
  s.textContent = "window.__inlineRan = true";
  document.head.append(s);
});
await page.waitForTimeout(300);
const blockedInline = await violations();
const ran = await page.evaluate(() => window.__inlineRan === true);
check("an inline script is refused (no 'unsafe-inline')", !ran && blockedInline.some((v) => v.directive.startsWith("script-src")), JSON.stringify(blockedInline));

await browser.close();
for (const r of results) console.log(`${r.ok ? "ok  " : "FAIL"} ${r.name}${r.detail ? `  (${r.detail})` : ""}`);
const failed = results.filter((r) => !r.ok).length;
console.log(`${results.length - failed}/${results.length} CSP checks passed (web ${web}, API ${apiOrigin})`);
process.exit(failed ? 1 : 0);
