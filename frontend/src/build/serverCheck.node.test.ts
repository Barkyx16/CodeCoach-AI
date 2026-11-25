import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { afterEach, describe, expect, it } from "vitest";

import { apiProblems } from "./serverCheck";

/** A stand-in API: what it says about itself is all the check can see. */
function fakeApi(opts: { label?: string; caps?: () => object }): Promise<{ base: string; server: Server }> {
  const server = createServer((req, res) => {
    if (opts.label) res.setHeader("X-CodeCoach-Instance", opts.label);
    res.setHeader("Content-Type", "application/json");
    if (req.url === "/health") return res.end(JSON.stringify({ status: "ok" }));
    if (req.url === "/api/v1/capabilities") return res.end(JSON.stringify(opts.caps?.() ?? {}));
    res.statusCode = 404;
    res.end("{}");
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () =>
    resolve({ base: `http://127.0.0.1:${(server.address() as AddressInfo).port}`, server })));
}

const servers: Server[] = [];
afterEach(() => { servers.splice(0).forEach((s) => s.close()); });
async function start(opts: Parameters<typeof fakeApi>[0]) {
  const { base, server } = await fakeApi(opts);
  servers.push(server);
  return base;
}

const off = { execution_enabled: false, execution: { state: "not_configured", reason: "disabled" } };
const ready = { execution_enabled: true, execution: { state: "ready", reason: "ok" } };

describe("which server an e2e run will use", () => {
  it("accepts its own test server with the expected judge setting", async () => {
    expect(await apiProblems(await start({ label: "e2e", caps: () => off }), { label: "e2e", judge: false })).toEqual([]);
    expect(await apiProblems(await start({ label: "e2e", caps: () => ready }), { label: "e2e", judge: true })).toEqual([]);
  });

  it("refuses a developer's server: no test label, possibly real data", async () => {
    const [problem] = await apiProblems(await start({ caps: () => off }), { label: "e2e", judge: false });
    expect(problem).toMatch(/isn't a test server.*real data/);
  });

  it("refuses a server labelled for something else", async () => {
    const [problem] = await apiProblems(await start({ label: "staging", caps: () => off }), { label: "e2e", judge: false });
    expect(problem).toMatch(/says it's "staging"/);
  });

  it("refuses the orphan that broke the judge tests: a test API with code execution off", async () => {
    const [problem] = await apiProblems(await start({ label: "e2e", caps: () => off }), { label: "e2e", judge: true });
    expect(problem).toMatch(/code execution is off.*needs the judge/);
  });

  it("waits for a judge that's starting, then says plainly when the runner never comes up", async () => {
    let calls = 0;
    const base = await start({ label: "e2e", caps: () => (++calls < 3
      ? { execution_enabled: true, execution: { state: "unavailable", reason: "runner_unreachable" } }
      : ready) });
    expect(await apiProblems(base, { label: "e2e", judge: true }, { waitMs: 5000, pollMs: 10 })).toEqual([]);
    expect(calls).toBe(3);

    const stuck = await start({ label: "e2e", caps: () => ({ execution_enabled: true, execution: { state: "unavailable", reason: "runner_unreachable" } }) });
    const [problem] = await apiProblems(stuck, { label: "e2e", judge: true }, { waitMs: 50, pollMs: 10 });
    expect(problem).toMatch(/isn't ready.*runner_unreachable.*runner up/);
  });

  it("refuses a judge-enabled server for a run that expects none", async () => {
    const [problem] = await apiProblems(await start({ label: "e2e", caps: () => ready }), { label: "e2e", judge: false });
    expect(problem).toMatch(/code execution is on/);
  });

  it("reports nothing listening instead of hanging", async () => {
    const [problem] = await apiProblems("http://127.0.0.1:9", { label: "e2e", judge: false });
    expect(problem).toMatch(/nothing usable answered/);
  });
});
