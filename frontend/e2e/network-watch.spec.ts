import { createServer, type ServerResponse } from "node:http";
import type { AddressInfo } from "node:net";

import { expect, test } from "./fixtures";
import { NetworkWatch } from "./network-watch";

/**
 * Forced examples for the network diagnostics (Volume 13, prompt 8; docs/NAVIGATION.md, "Requests
 * that never reach the API"): each explanation a waiting request can match, made to happen on purpose
 * against a small local server, produces the line that names it, in under a second.
 */
async function forcedServer() {
  const held: ServerResponse[] = [];
  const srv = createServer((req, res) => {
    const path = new URL(req.url ?? "/", "http://local").pathname;
    if (path === "/") {
      res.writeHead(200, { "content-type": "text/html" });
      res.end("<!doctype html><title>Forced network examples</title><p>Forced network examples</p>");
    } else if (path === "/hold") {
      held.push(res); // never answered until the test ends: it holds a connection
    } else if (path === "/drop") {
      req.socket.destroy(); // the server closes the connection as the request arrives
    } else if (path === "/preflight" && req.method === "OPTIONS") {
      held.push(res); // a CORS preflight held unanswered: the page gives up on its request meanwhile
    } else if (path === "/slow") {
      setTimeout(() => res.end("slow"), 300);
    } else {
      res.end("ok");
    }
  });
  await new Promise<void>((resolve) => srv.listen(0, "127.0.0.1", resolve));
  const origin = `http://127.0.0.1:${(srv.address() as AddressInfo).port}`;
  return {
    origin,
    close: () => { for (const r of held) r.destroy(); srv.closeAllConnections(); srv.close(); },
  };
}

test.describe("which explanation a waiting request matches", () => {
  test("six held connections: the seventh request is queued in the browser (H1)", async ({ page }) => {
    const s = await forcedServer();
    try {
      await page.goto(`${s.origin}/`);
      const w = (await NetworkWatch.attach(page, Date.now()))!;
      await page.evaluate(() => {
        for (let i = 0; i < 6; i++) void fetch(`/hold?i=${i}`);
        void fetch("/ok?late");
      });
      await expect.poll(() => [...w.entries.values()].filter((e) => e.path === "/hold" && e.onNetwork).length).toBe(6);
      await expect.poll(() => [...w.entries.values()].some((e) => e.path === "/ok")).toBe(true);
      const { waiting, ms } = await w.report(null, 0);
      expect(waiting.find((l) => l.startsWith("GET /ok"))).toMatch(
        /^GET \/ok \[Fetch\] waiting \d+\.\ds \(\+\d+\.\ds\): H1 queued in the browser: 6 requests to http:\/\/127\.0\.0\.1:\d+ were already open \(Chrome sends at most 6 at once to one server\): GET \/hold/,
      );
      expect(waiting.filter((l) => l.startsWith("GET /hold")).every((l) => /sent to http:\/\/127\.0\.0\.1:\d+, no answer yet$/.test(l))).toBe(true);
      expect(ms + w.setupMs).toBeLessThan(1000);
    } finally {
      s.close();
    }
  });

  test("a server-closed keep-alive socket: the request fails with the connection closed under it (H2)", async ({ page }) => {
    const s = await forcedServer();
    try {
      await page.goto(`${s.origin}/`);
      const w = (await NetworkWatch.attach(page, Date.now()))!;
      await page.evaluate(async () => {
        await (await fetch("/ok?first")).text(); // leaves a kept-alive connection
        await fetch("/drop").catch(() => undefined); // reuses it; the server closes it
      });
      const { slow, ms } = await w.report(null, 0);
      expect(slow.find((l) => l.startsWith("GET /drop"))).toMatch(
        /H2 the server closed the connection under it \(net::ERR_(EMPTY_RESPONSE|CONNECTION_RESET|CONNECTION_CLOSED)\); the last answer from http:\/\/127\.0\.0\.1:\d+ came \d+\.\ds earlier/,
      );
      expect(ms + w.setupMs).toBeLessThan(1000);
    } finally {
      s.close();
    }
  });

  test("a page replaced while its request was open: the request went with that page (H6)", async ({ page }) => {
    const s = await forcedServer();
    try {
      await page.goto(`${s.origin}/`);
      const w = (await NetworkWatch.attach(page, Date.now()))!;
      const heard: string[] = []; // what Playwright's own events say about it (the old waiting list used them)
      page.on("requestfinished", (r) => { if (r.url().includes("/hold")) heard.push("finished"); });
      page.on("requestfailed", (r) => { if (r.url().includes("/hold")) heard.push("failed"); });
      await page.evaluate(() => { void fetch("/hold?orphan"); });
      await expect.poll(() => [...w.entries.values()].some((e) => e.path === "/hold" && e.onNetwork)).toBe(true);
      await page.goto(`${s.origin}/?next`);
      const { waiting, slow, ms } = await w.report(null, 0);
      const line = [...waiting, ...slow].find((l) => l.startsWith("GET /hold"));
      expect(line).toMatch(/^GET \/hold \[Fetch\] waiting \d+\.\ds \(\+\d+\.\ds\): H6 from an earlier page: asked for \d+\.\ds before the page was replaced \(\+\d+\.\ds\); its outcome went with that page, so this isn't a stall$/);
      // Neither Chrome nor Playwright ever says it ended: a list of "waiting" requests keeps it forever
      // (CI run 315's six). Nothing about it is wrong.
      await page.waitForTimeout(300);
      expect(heard).toEqual([]);
      expect(ms + w.setupMs).toBeLessThan(1000);
    } finally {
      s.close();
    }
  });

  test("a request canceled during its CORS preflight: the preflight ends with it, not left waiting", async ({ page }) => {
    const s = await forcedServer();
    try {
      await page.goto(`${s.origin}/`);
      const w = (await NetworkWatch.attach(page, Date.now()))!;
      const other = s.origin.replace("127.0.0.1", "localhost"); // another origin: a custom header needs a preflight
      await page.evaluate(async (url) => {
        const ctl = new AbortController();
        const sent = fetch(url, { headers: { "x-forced": "1" }, signal: ctl.signal }).catch(() => undefined);
        setTimeout(() => ctl.abort(), 250);
        await sent;
      }, `${other}/preflight`);
      const main = () => [...w.entries.values()].find((e) => e.method === "GET" && e.path === "/preflight");
      // What Chrome itself reports: the cancel on the request (just after the page hears it), and
      // nothing at all on its preflight.
      await expect.poll(() => main()?.canceled).toBe(true);
      const preflight = [...w.entries.values()].find((e) => e.method === "OPTIONS");
      await page.waitForTimeout(300);
      expect(preflight?.preflightFor).toBe(main()?.id);
      expect(preflight?.endAt).toBeUndefined();
      const { waiting, slow, ms } = await w.report(null, 0);
      expect(waiting).toEqual([]);
      expect(slow.find((l) => l.startsWith("OPTIONS /preflight"))).toMatch(
        /^OPTIONS \/preflight \[Other\] took \d+\.\ds \(\+\d+\.\ds\): a CORS preflight for GET \/preflight, which failed \(net::ERR_ABORTED, canceled by the page\) \d+\.\ds after the preflight was sent: Chrome reports no end for a preflight whose request ended first, so it ended then and this isn't a stall$/,
      );
      expect(ms + w.setupMs).toBeLessThan(1000);
    } finally {
      s.close();
    }
  });

  test("a blocked main thread: nothing it asked for is heard back (H5)", async ({ page }) => {
    const s = await forcedServer();
    try {
      await page.goto(`${s.origin}/`);
      const w = (await NetworkWatch.attach(page, Date.now()))!;
      await page.evaluate(() => { void fetch("/hold?h5"); });
      await expect.poll(() => [...w.entries.values()].some((e) => e.path === "/hold" && e.onNetwork)).toBe(true);
      // The page busy for 2.5 s inside an evaluation that isn't awaited: the probe's own evaluation
      // waits behind it. Nothing else may touch the page meanwhile: with tracing on (as in CI), every
      // Playwright page call, page.waitForTimeout included, first snapshots the page and so waits for
      // it to be free; CI runs 322 and 323 probed only after the busy loop ended. So the pause is
      // Node's own timer.
      const busy = page.evaluate(() => { const t = Date.now(); while (Date.now() - t < 2500) { /* the page is busy */ } }).catch(() => undefined);
      await new Promise((resolve) => setTimeout(resolve, 100));
      const { waiting, ms } = await w.report(null, 0);
      expect(waiting.find((l) => l.startsWith("GET /hold"))).toMatch(/H5 the page's main thread is blocked \(it didn't answer in 500 ms\)/);
      expect(waiting).toContain("(the page's main thread didn't answer in 500 ms)");
      expect(ms + w.setupMs).toBeLessThan(1000);
      await busy; // let the page finish before it closes
    } finally {
      s.close();
    }
  });
});
