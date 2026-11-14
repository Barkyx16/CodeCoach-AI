/**
 * scripts/e2e-run.mjs owns what an e2e run starts. These run the real launcher with a stand-in for
 * Playwright (E2E_PLAYWRIGHT_CMD) that starts a "server" the way Playwright does: a detached
 * process group, wrapped by scripts/e2e-owned.mjs. Each server here is a `sleep` with a unique
 * marker, so no real ports, and nothing else on the machine, are involved.
 */
import { execFileSync, spawn, type ChildProcess } from "node:child_process";
import { mkdtempSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { afterEach, describe, expect, it } from "vitest";

const LAUNCHER = resolve(__dirname, "../../scripts/e2e-run.mjs");
const OWNED = resolve(__dirname, "../../scripts/e2e-owned.mjs");

function alive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

/** PIDs of the stand-in server itself (`sleep 300 # marker`, or the shell running it). The
 * launcher's stand-in for Playwright also mentions that command in its own arguments, so only a
 * command line that *starts* with it counts. */
function pidsWith(marker: string): number[] {
  const out = execFileSync("ps", ["-eo", "pid=,stat=,args="], { encoding: "utf8" });
  const server = new RegExp(`^(\\S*/)?(sh -c )?sleep 300 # ${marker}`);
  return out.split("\n").map((l) => l.trim().split(/\s+/)).filter(([, stat, ...args]) => stat && !stat.startsWith("Z") && server.test(args.join(" ")))
    .map(([pid]) => Number(pid));
}

async function until(check: () => boolean, ms = 10_000): Promise<void> {
  const end = Date.now() + ms;
  while (!check()) {
    if (Date.now() > end) throw new Error("timed out waiting");
    await new Promise((r) => setTimeout(r, 50));
  }
}

/** A stand-in Playwright: starts one detached "server" through the shim, like webServer does. */
function standIn(marker: string, then: string): string {
  const server = `E2E_OWNED_NAME=api E2E_OWNED_COMMAND='sleep 300 # ${marker}' node ${OWNED}`;
  // setsid-like: Node's detached spawn from a tiny script, so the server leads its own group.
  return `node -e "require('child_process').spawn('sh', ['-c', process.argv[1]], {detached: true, stdio: 'ignore'}).unref()" "${server}"; sleep 0.5; ${then}`;
}

const children: ChildProcess[] = [];
const unrelated: ChildProcess[] = [];
afterEach(() => {
  for (const c of [...children.splice(0), ...unrelated.splice(0)]) if (c.pid && alive(c.pid)) c.kill("SIGKILL");
});

function launch(dir: string, then: string, marker: string, extra: string[] = []) {
  const child = spawn("node", [LAUNCHER, ...extra], {
    env: { ...process.env, E2E_OWNED_DIR: dir, E2E_PLAYWRIGHT_CMD: standIn(marker, then) },
    stdio: ["ignore", "pipe", "pipe"],
  });
  children.push(child);
  let stderr = "";
  child.stderr?.on("data", (d) => { stderr += String(d); });
  const exited = new Promise<{ code: number | null }>((r) => child.on("exit", (code) => r({ code })));
  return { child, exited, stderr: () => stderr };
}

describe("an e2e run owns what it starts", { timeout: 30_000 }, () => {
  it.each([
    ["the tests pass", "exit 0", 0],
    ["a test fails", "exit 1", 1],
  ])("stops its servers when %s, and keeps Playwright's exit status", async (_, then, status) => {
    const dir = mkdtempSync(join(tmpdir(), "e2e-owned-"));
    const marker = `codecoach-e2e-test-${Math.random().toString(36).slice(2)}`;
    const bystander = spawn("sleep", ["300"]); // something else on the machine
    unrelated.push(bystander);
    const run = launch(dir, `sleep 1; ${then}`, marker);
    await until(() => pidsWith(marker).length > 0);
    const { code } = await run.exited;
    expect(code).toBe(status);
    await until(() => pidsWith(marker).length === 0);
    expect(alive(bystander.pid!)).toBe(true);
    expect(readdirSync(dir)).toEqual([]); // records cleaned up
  });

  it("stops its servers on Ctrl+C and says the run is incomplete (exit 130)", async () => {
    const dir = mkdtempSync(join(tmpdir(), "e2e-owned-"));
    const marker = `codecoach-e2e-test-${Math.random().toString(36).slice(2)}`;
    const run = launch(dir, "sleep 300", marker);
    await until(() => pidsWith(marker).length > 0); // starting: possibly not recorded yet
    run.child.kill("SIGINT");
    const { code } = await run.exited;
    expect(code).toBe(130);
    expect(run.stderr()).toMatch(/incomplete/);
    await until(() => pidsWith(marker).length === 0);
  });

  it("stops everything at the time limit (exit 124)", async () => {
    const dir = mkdtempSync(join(tmpdir(), "e2e-owned-"));
    const marker = `codecoach-e2e-test-${Math.random().toString(36).slice(2)}`;
    const run = launch(dir, "sleep 300", marker, ["--max-minutes", "0.03"]);
    const { code } = await run.exited;
    expect(code).toBe(124);
    await until(() => pidsWith(marker).length === 0);
  });

  it("servers stop on their own when the launcher is killed outright (the old orphan)", async () => {
    const dir = mkdtempSync(join(tmpdir(), "e2e-owned-"));
    const marker = `codecoach-e2e-test-${Math.random().toString(36).slice(2)}`;
    const run = launch(dir, "sleep 300", marker);
    await until(() => readdirSync(dir).some((f) => f.endsWith(".api.json")));
    const standIn = JSON.parse(readFileSync(join(dir, readdirSync(dir).find((f) => f.endsWith(".playwright.json"))!), "utf8"));
    run.child.kill("SIGKILL"); // no chance to clean up
    await run.exited;
    await until(() => pidsWith(marker).length === 0); // the server stopped itself
    try { process.kill(-standIn.pgid, "SIGKILL"); } catch { /* already gone */ } // the stand-in "Playwright"
  });

  it("a recorded group that outlived everything is listed, and stopped only on request", async () => {
    const dir = mkdtempSync(join(tmpdir(), "e2e-owned-"));
    const marker = `codecoach-e2e-test-${Math.random().toString(36).slice(2)}`;
    // A server whose launcher and shim both died: only its record and its process group remain.
    const orphan = spawn("sh", ["-c", `sleep 300 # ${marker}`], { detached: true, stdio: "ignore" });
    unrelated.push(orphan);
    const run = "old-run";
    writeFileSync(join(dir, `${run}.launcher.json`), JSON.stringify({ run, name: "launcher", pid: 999_999, pgid: 999_999, started_at: "x" }));
    writeFileSync(join(dir, `${run}.api.json`), JSON.stringify({ run, name: "api", pid: orphan.pid, pgid: orphan.pid, started_at: "x" }));
    const env = { ...process.env, E2E_OWNED_DIR: dir };
    const listed = execFileSync("node", [LAUNCHER, "--list"], { env, encoding: "utf8" });
    expect(listed).toMatch(/launcher .*gone/);
    expect(listed).toMatch(/api .*alive/);
    execFileSync("node", [LAUNCHER, "--stop", run], { env });
    await until(() => pidsWith(marker).length === 0);
    expect(readdirSync(dir)).toEqual([]);
  });

  it("its records hold names and numbers only: no environment, no command line", async () => {
    const dir = mkdtempSync(join(tmpdir(), "e2e-owned-"));
    const marker = `codecoach-e2e-test-${Math.random().toString(36).slice(2)}`;
    process.env.E2E_CANARY_TOKEN = "CANARY-e2e-7f3a9-not-a-real-token"; // inherited by the launcher and servers
    try {
      const run = launch(dir, "sleep 300", marker);
      await until(() => readdirSync(dir).some((f) => f.endsWith(".api.json")));
      const written = readdirSync(dir).map((f) => readFileSync(join(dir, f), "utf8")).join("\n");
      expect(written).not.toContain("CANARY-e2e");
      expect(written).not.toContain(marker); // the server's command line isn't recorded either
      run.child.kill("SIGTERM");
      await run.exited;
    } finally {
      delete process.env.E2E_CANARY_TOKEN;
    }
  });

  it("won't stop a run that's still going", async () => {
    const dir = mkdtempSync(join(tmpdir(), "e2e-owned-"));
    const marker = `codecoach-e2e-test-${Math.random().toString(36).slice(2)}`;
    const run = launch(dir, "sleep 300", marker);
    await until(() => pidsWith(marker).length > 0);
    const runId = JSON.parse(readFileSync(join(dir, readdirSync(dir).find((f) => f.endsWith(".launcher.json"))!), "utf8")).run;
    expect(() => execFileSync("node", [LAUNCHER, "--stop", runId], { env: { ...process.env, E2E_OWNED_DIR: dir }, stdio: "pipe" })).toThrow();
    expect(pidsWith(marker).length).toBeGreaterThan(0);
    run.child.kill("SIGTERM");
    await run.exited;
    await until(() => pidsWith(marker).length === 0);
  });
});

/**
 * Provenance (Volume 9, prompt 10): a run names the commit it tested and whether its runtime
 * inputs differed, and a run whose inputs changed while it ran is "contaminated" (exit 3), not a
 * pass. Each case uses a throwaway git repository as the source, so the real tree is never read
 * or touched, and a stand-in for Playwright.
 */
describe("an e2e run says which source it tested", { timeout: 30_000 }, () => {
  function repo(): string {
    const root = mkdtempSync(join(tmpdir(), "e2e-source-"));
    const run = (...a: string[]) => execFileSync("git", a, { cwd: root, stdio: "pipe" });
    execFileSync("mkdir", ["-p", join(root, "frontend/src"), join(root, "frontend/e2e/screenshots")]);
    writeFileSync(join(root, "frontend/src/app.ts"), "export const v = 1;\n");
    writeFileSync(join(root, ".gitignore"), "frontend/e2e/screenshots/\n");
    run("init", "-q");
    run("-c", "user.email=t@example.com", "-c", "user.name=t", "add", ".");
    run("-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", "synthetic");
    return root;
  }
  async function runIn(root: string, then: string) {
    const owned = mkdtempSync(join(tmpdir(), "e2e-owned-"));
    const out = mkdtempSync(join(tmpdir(), "e2e-prov-"));
    const child = spawn("node", [LAUNCHER], {
      cwd: root,
      env: { ...process.env, E2E_OWNED_DIR: owned, E2E_SOURCE_ROOT: root, E2E_PROVENANCE_DIR: out, E2E_PLAYWRIGHT_CMD: then },
      stdio: ["ignore", "pipe", "pipe"],
    });
    children.push(child);
    let stderr = "";
    child.stderr?.on("data", (d) => { stderr += String(d); });
    const code = await new Promise<number | null>((r) => child.on("exit", (c) => r(c)));
    const commit = execFileSync("git", ["rev-parse", "HEAD"], { cwd: root, encoding: "utf8" }).trim();
    return { code, stderr, commit, record: JSON.parse(readFileSync(join(out, "e2e-provenance.json"), "utf8")) };
  }

  it("names an unchanged commit, and a pass is a pass", async () => {
    const root = repo();
    const r = await runIn(root, "exit 0");
    expect(r.code).toBe(0);
    expect(r.stderr).toContain(`candidate: ${r.commit.slice(0, 7)}, runtime inputs unchanged from the commit`);
    expect(r.record).toMatchObject({ commit: r.commit, differs_at_start: [], changed_during_run: [], outcome: "passed", exit: 0 });
  });

  it("a source file changed during the run makes it contaminated (exit 3), and the change is left as it is", async () => {
    const root = repo();
    const r = await runIn(root, "sleep 0.3; echo 'export const v = 2;' > frontend/src/app.ts; exit 0");
    expect(r.code).toBe(3);
    expect(r.stderr).toMatch(/CONTAMINATED: 1 runtime file\(s\) changed during the run \(frontend\/src\/app\.ts\)/);
    expect(r.record).toMatchObject({ changed_during_run: ["frontend/src/app.ts"], outcome: "contaminated (passed)", exit: 3 });
    expect(readFileSync(join(root, "frontend/src/app.ts"), "utf8")).toBe("export const v = 2;\n"); // nothing reset
  });

  it("if the source can't be checked at the end, the run isn't reported as unchanged (exit 3)", async () => {
    const root = repo();
    const r = await runIn(root, "printf x > .git/index; exit 0"); // git can no longer list the files
    expect(r.code).toBe(3);
    expect(r.stderr).toMatch(/UNVERIFIED: the source couldn't be checked at the end \(.+\): these results can't be tied to [0-9a-f]{7}/);
    expect(r.record).toMatchObject({ changed_during_run: null, outcome: "unverified (passed)", exit: 3 });
  });

  it("an edit made before the run is named, not called contaminated, and stays", async () => {
    const root = repo();
    writeFileSync(join(root, "frontend/src/app.ts"), "export const v = 3; // work in progress\n");
    writeFileSync(join(root, "frontend/src/new.ts"), "export const w = 1;\n");
    const r = await runIn(root, "exit 1");
    expect(r.code).toBe(1);
    expect(r.stderr).toMatch(/plus 2 changed runtime file\(s\) \(frontend\/src\/app\.ts, frontend\/src\/new\.ts\): results describe this working tree, not that commit/);
    expect(r.record).toMatchObject({ differs_at_start: ["frontend/src/app.ts", "frontend/src/new.ts"], changed_during_run: [], outcome: "failed" });
    expect(readFileSync(join(root, "frontend/src/app.ts"), "utf8")).toContain("work in progress");
  });

  it("a pass with skipped tests says so and names them: three judge skips aren't a full real-sandbox pass", async () => {
    const root = repo();
    const report = JSON.stringify({
      stats: { expected: 90, unexpected: 0, flaky: 0, skipped: 1 },
      suites: [{ title: "judge.spec.ts", specs: [{ title: "a real verdict", file: "judge.spec.ts", line: 9,
        tests: [{ projectName: "desktop", status: "skipped", annotations: [{ type: "skip", description: "needs E2E_JUDGE=1" }] }] }] }],
    });
    const r = await runIn(root, `printf '%s' '${report}' > "$E2E_RESULTS_FILE"; exit 0`);
    expect(r.code).toBe(0);
    expect(r.stderr).toContain("tests: 90 passed, 0 failed, 0 flaky, 1 skipped; real judge off (judge tests skip)");
    expect(r.stderr).toContain("skipped: [desktop] judge.spec.ts:9 a real verdict (needs E2E_JUDGE=1)");
    expect(r.record).toMatchObject({ outcome: "passed, 1 skipped", exit: 0, real_judge: false, tests: { passed: 90, skipped: 1 } });
    expect(r.record.tests.skipped_tests).toEqual(["[desktop] judge.spec.ts:9 a real verdict (needs E2E_JUDGE=1)"]);
  });

  it("generated files git ignores (screenshots) don't count as source changes", async () => {
    const root = repo();
    const r = await runIn(root, "echo png > frontend/e2e/screenshots/shot.png; exit 0");
    expect(r.code).toBe(0);
    expect(r.record.changed_during_run).toEqual([]);
  });
});
