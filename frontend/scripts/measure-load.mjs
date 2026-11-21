// Page-load timings of the production build (docs/PERFORMANCE.md, "Frontend"):
//   npm run build && npx vite preview --port 4174 &   then:   node scripts/measure-load.mjs
// For each page: first contentful paint, DOMContentLoaded and load, plus bytes of JavaScript
// transferred, median of RUNS cold loads (fresh browser context, no cache), with and without
// 4x CPU throttling. No backend is needed for these public pages (the session check fails fast).
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://localhost:4174";
const RUNS = Number(process.env.RUNS ?? 7);
const PAGES = ["/", "/login"];
const median = (xs) => {
  const ok = xs.filter(Number.isFinite).sort((a, b) => a - b);
  return ok.length ? ok[Math.floor(ok.length / 2)] : null;
};

const browser = await chromium.launch();
const results = [];
for (const throttle of [1, 4]) {
  for (const path of PAGES) {
    const runs = [];
    for (let i = 0; i < RUNS; i++) {
      const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
      const page = await context.newPage();
      if (throttle > 1) {
        const cdp = await context.newCDPSession(page);
        await cdp.send("Emulation.setCPUThrottlingRate", { rate: throttle });
      }
      let jsBytes = 0;
      page.on("response", async (r) => {
        if (r.request().resourceType() === "script") jsBytes += Number(r.headers()["content-length"] ?? (await r.body().catch(() => Buffer.alloc(0))).length);
      });
      await page.goto(BASE + path, { waitUntil: "load" });
      await page.getByRole("heading", { level: 1 }).first().waitFor();
      const t = await page.evaluate(() => {
        const nav = performance.getEntriesByType("navigation")[0];
        const fcp = performance.getEntriesByName("first-contentful-paint")[0];
        return { fcp: fcp?.startTime ?? NaN, dcl: nav.domContentLoadedEventEnd, load: nav.loadEventEnd };
      });
      runs.push({ ...t, jsBytes });
      await context.close();
    }
    const row = {
      path, cpuThrottle: throttle, runs: RUNS,
      fcpMs: median(runs.map((r) => r.fcp)) === null ? null : Math.round(median(runs.map((r) => r.fcp))),
      fcpMeasuredRuns: runs.filter((r) => Number.isFinite(r.fcp)).length, // headless Chrome sometimes reports none
      domContentLoadedMs: Math.round(median(runs.map((r) => r.dcl))),
      loadMs: Math.round(median(runs.map((r) => r.load))),
      jsKBUncompressed: Math.round(median(runs.map((r) => r.jsBytes)) / 1024), // vite preview doesn't compress
    };
    results.push(row);
    console.log(JSON.stringify(row));
  }
}
await browser.close();
