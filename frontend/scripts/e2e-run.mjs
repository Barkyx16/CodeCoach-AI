#!/usr/bin/env node
/**
 * `npm run e2e`: runs Playwright and owns everything the run starts, so an aborted run can't leave
 * an orphaned API behind for the next run to reuse.
 *
 *   npm run e2e [-- playwright args]       e.g. npm run e2e -- e2e/notes.spec.ts --project=desktop
 *   npm run e2e -- --max-minutes 20 …      stop the whole run (servers too) after 20 minutes: exit 124
 *   npm run e2e:owned                      list e2e runs and the server process groups they started
 *   npm run e2e:stop -- <run id>           stop the servers of a run whose launcher is gone
 *
 * Ownership:
 * - Playwright and its workers run in a process group of their own.
 * - Each web server records its own group through scripts/e2e-owned.mjs.
 * On success, failure, Ctrl+C, SIGTERM or the time limit, it stops exactly those groups, and
 * never anything found by name or by port. A server that was already running and got reused
 * isn't this run's, so it's left alone (e2e/global-setup.ts checks it's the right kind of server
 * first). The exit status is Playwright's, 124 for the time limit, or 128+N for a signal.
 * Records hold names, numbers and times only: no environment, no command lines.
 *
 * Provenance (Volume 9, prompt 10): a run says which source it tested. At the start it names the
 * commit and any runtime input (the app's source, the browser tests, their configs, the backend
 * app) that differs from it; at the end it hashes those inputs again. If any changed during the
 * run, the results describe neither the commit nor the tree it started with: it says so and exits
 * 3 ("contaminated"), whatever the tests did. Results go to test-results/e2e-provenance.json. It
 * only reads: nothing is reset, cleaned or stopped to make a tree "clean". Generated files that
 * git ignores (screenshots, logs, databases) aren't inputs.
 */
import { execFileSync, spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const OWNED_DIR = resolve(process.env.E2E_OWNED_DIR ?? join(here, "..", "test-results", ".e2e-owned"));

/** Does the process group still have a running member? Zombies don't count: an exited process
 * waits for its parent to collect it, and in some containers nothing does. */
function alive(pgid) {
  try {
    process.kill(-pgid, 0);
  } catch (e) {
    if (e.code !== "EPERM") return false;
  }
  try {
    const rows = execFileSync("ps", ["-eo", "pgid=,stat="], { encoding: "utf8" }).split("\n");
    return rows.some((row) => {
      const [g, stat] = row.trim().split(/\s+/);
      return Number(g) === pgid && stat && !stat.startsWith("Z");
    });
  } catch {
    return true; // no ps: the signal check above is all there is
  }
}

function pidAlive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch (e) {
    return e.code === "EPERM";
  }
}

function records(runId) {
  if (!existsSync(OWNED_DIR)) return [];
  return readdirSync(OWNED_DIR)
    .filter((f) => f.endsWith(".json") && (!runId || f.startsWith(`${runId}.`)))
    .map((f) => {
      try {
        return { file: join(OWNED_DIR, f), ...JSON.parse(readFileSync(join(OWNED_DIR, f), "utf8")) };
      } catch {
        return null;
      }
    })
    .filter(Boolean);
}

async function stopGroup(pgid, graceMs = 5000) {
  if (!alive(pgid)) return "gone";
  try { process.kill(-pgid, "SIGTERM"); } catch { /* raced to exit */ }
  const until = Date.now() + graceMs;
  while (Date.now() < until && alive(pgid)) await new Promise((r) => setTimeout(r, 100));
  if (alive(pgid)) {
    try { process.kill(-pgid, "SIGKILL"); } catch { /* raced to exit */ }
    return "killed";
  }
  return "stopped";
}

async function stopRun(runId) {
  const owned = records(runId).filter((r) => r.name !== "launcher");
  for (const r of owned) {
    const how = await stopGroup(r.pgid);
    if (how !== "gone") console.error(`[e2e-run] ${how} ${r.name} (process group ${r.pgid})`);
    rmSync(r.file, { force: true });
  }
}

if (process.argv[2] === "--list") {
  const all = records();
  if (!all.length) console.log("No e2e runs recorded.");
  for (const r of all) {
    const state = r.name === "launcher" ? (pidAlive(r.pid) ? "running" : "gone (aborted?)") : alive(r.pgid) ? "alive" : "gone";
    console.log(`${r.run}  ${r.name.padEnd(8)} group ${String(r.pgid).padEnd(7)} ${state}  since ${r.started_at}`);
  }
  process.exit(0);
}

if (process.argv[2] === "--stop") {
  const runId = process.argv[3];
  const launcher = records(runId).find((r) => r.name === "launcher");
  if (!runId || !records(runId).length) {
    console.error("usage: npm run e2e:stop -- <run id>   (see npm run e2e:owned)");
    process.exit(2);
  }
  if (launcher && pidAlive(launcher.pid)) {
    console.error(`[e2e-run] run ${runId} is still running (launcher ${launcher.pid}): stop it with Ctrl+C instead`);
    process.exit(1);
  }
  await stopRun(runId);
  if (launcher) rmSync(launcher.file, { force: true });
  process.exit(0);
}

let args = process.argv.slice(2);
let maxMinutes = null;
const at = args.indexOf("--max-minutes");
if (at !== -1) {
  maxMinutes = Number(args[at + 1]);
  if (!(maxMinutes > 0)) {
    console.error("--max-minutes needs a positive number");
    process.exit(2);
  }
  args = [...args.slice(0, at), ...args.slice(at + 2)];
}

// Runs whose launcher died, leaving servers behind: say so (never stop them silently here).
for (const r of records().filter((x) => x.name === "launcher" && !pidAlive(x.pid))) {
  const left = records(r.run).filter((x) => x.name !== "launcher" && alive(x.pgid));
  if (left.length) {
    console.error(`[e2e-run] an aborted run (${r.run}) left ${left.map((x) => x.name).join(", ")} running: npm run e2e:stop -- ${r.run}`);
  }
}

// Which source this run tests. E2E_SOURCE_ROOT exists for the launcher's own tests.
const SOURCE_ROOT = resolve(process.env.E2E_SOURCE_ROOT ?? join(here, "..", ".."));
const RUNTIME_INPUTS = ["frontend/src", "frontend/e2e", "frontend/public", "frontend/index.html", "frontend/vite.config.ts",
  "frontend/playwright.config.ts", "frontend/package.json", "frontend/package-lock.json", "frontend/tsconfig.json",
  "backend/app", "backend/requirements.txt"];
function git(gitArgs) {
  return execFileSync("git", gitArgs, { cwd: SOURCE_ROOT, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
}
/** Every runtime input git doesn't ignore (tracked or not), with a hash of its contents; null
 * (with the reason in snapshotError) if they can't be listed. */
let snapshotError = null;
function snapshot() {
  try {
    const files = git(["ls-files", "-co", "--exclude-standard", "-z", "--", ...RUNTIME_INPUTS]).split("\0").filter(Boolean);
    const hashes = new Map();
    for (const f of files) {
      let digest = "missing";
      try { digest = createHash("sha1").update(readFileSync(join(SOURCE_ROOT, f))).digest("hex"); } catch { /* removed meanwhile */ }
      hashes.set(f, digest);
    }
    return hashes;
  } catch (e) {
    snapshotError = String(e?.message ?? e).split("\n")[0];
    return null; // not a git checkout, or git failed: provenance unknown, said below
  }
}
function changedBetween(a, b) {
  const out = [];
  for (const [f, h] of a) if (b.get(f) !== h) out.push(f);
  for (const f of b.keys()) if (!a.has(f)) out.push(f);
  return out.sort();
}
const brief = (files) => files.slice(0, 5).join(", ") + (files.length > 5 ? `, and ${files.length - 5} more` : "");
let candidate = null;
try {
  const commit = git(["rev-parse", "HEAD"]).trim();
  const differs = git(["status", "--porcelain", "--untracked-files=all", "--", ...RUNTIME_INPUTS])
    .split("\n").filter(Boolean).map((line) => line.slice(3));
  candidate = { commit, differs };
} catch { /* not a git checkout */ }
const startSnapshot = snapshot();
const startedAt = new Date().toISOString();
if (!candidate || !startSnapshot) {
  console.error("[e2e-run] candidate: unknown (not a git checkout); source changes during the run can't be detected");
} else if (candidate.differs.length) {
  console.error(`[e2e-run] candidate: ${candidate.commit.slice(0, 7)} plus ${candidate.differs.length} changed runtime file(s) (${brief(candidate.differs)}): results describe this working tree, not that commit`);
} else {
  console.error(`[e2e-run] candidate: ${candidate.commit.slice(0, 7)}, runtime inputs unchanged from the commit`);
}

const runId = `${Date.now().toString(36)}-${process.pid}`;
mkdirSync(OWNED_DIR, { recursive: true });
const launcherRecord = join(OWNED_DIR, `${runId}.launcher.json`);
writeFileSync(launcherRecord, JSON.stringify({ run: runId, name: "launcher", pid: process.pid, pgid: process.pid, started_at: new Date().toISOString() }));

// E2E_PLAYWRIGHT_CMD exists for the launcher's own tests (a stand-in for Playwright).
const [cmd, ...cmdArgs] = process.env.E2E_PLAYWRIGHT_CMD
  ? ["sh", "-c", process.env.E2E_PLAYWRIGHT_CMD]
  : ["npx", "playwright", "test", ...args];
const PROVENANCE_DIR = resolve(process.env.E2E_PROVENANCE_DIR ?? join(here, "..", "test-results"));
const RESULTS_FILE = join(PROVENANCE_DIR, `e2e-results-${runId}.json`); // Playwright's JSON report
const child = spawn(cmd, cmdArgs, {
  detached: true, // its own process group: Playwright, its workers, and anything they start
  stdio: "inherit",
  env: { ...process.env, E2E_RUN_ID: runId, E2E_OWNED_DIR: OWNED_DIR, E2E_LAUNCHER_PID: String(process.pid), E2E_RESULTS_FILE: RESULTS_FILE },
});
writeFileSync(join(OWNED_DIR, `${runId}.playwright.json`), JSON.stringify({ run: runId, name: "playwright", pid: child.pid, pgid: child.pid, started_at: new Date().toISOString() }));

let reason = null; // "timeout" | signal name
let finishing = false;
async function finish(code) {
  if (finishing) return;
  finishing = true;
  await stopRun(runId); // Playwright's own group, then every server group this run recorded
  // A server still starting may record itself a moment later: sweep once more.
  await new Promise((r) => setTimeout(r, 1500));
  await stopRun(runId);
  rmSync(launcherRecord, { force: true });
  let status = reason === "timeout" ? 124 : reason ? 128 + ({ SIGINT: 2, SIGTERM: 15, SIGHUP: 1 }[reason] ?? 15) : code;
  if (reason) console.error(`[e2e-run] ${reason === "timeout" ? `stopped after ${maxMinutes} min` : `interrupted (${reason})`}: run ${runId} incomplete, its servers stopped`);
  // What Playwright itself counted, and which tests didn't run: "passed" with three judge tests
  // skipped isn't a full real-sandbox pass, so the skipped ones are named.
  let tests = null;
  try {
    const report = JSON.parse(readFileSync(RESULTS_FILE, "utf8"));
    const skipped = [];
    const walk = (suite) => {
      for (const spec of suite.specs ?? []) for (const t of spec.tests ?? []) {
        if (t.status === "skipped") skipped.push(`[${t.projectName}] ${spec.file}:${spec.line} ${spec.title}${t.annotations?.find((a) => a.type === "skip")?.description ? ` (${t.annotations.find((a) => a.type === "skip").description})` : ""}`);
      }
      for (const child of suite.suites ?? []) walk(child);
    };
    for (const suite of report.suites ?? []) walk(suite);
    const st = report.stats ?? {};
    tests = { passed: st.expected ?? 0, failed: st.unexpected ?? 0, flaky: st.flaky ?? 0, skipped: st.skipped ?? 0, skipped_tests: skipped };
    rmSync(RESULTS_FILE, { force: true });
  } catch { /* no report (Playwright didn't get that far): the exit status is all there is */ }
  if (tests) {
    console.error(`[e2e-run] tests: ${tests.passed} passed, ${tests.failed} failed, ${tests.flaky} flaky, ${tests.skipped} skipped; real judge ${process.env.E2E_JUDGE === "1" ? "on" : "off (judge tests skip)"}`);
    for (const t of tests.skipped_tests.slice(0, 10)) console.error(`[e2e-run]   skipped: ${t}`);
    if (tests.skipped_tests.length > 10) console.error(`[e2e-run]   and ${tests.skipped_tests.length - 10} more skipped (listed in e2e-provenance.json)`);
  }
  // Did the source change while it ran?
  const endSnapshot = startSnapshot ? snapshot() : null;
  // Couldn't look again: nothing can be said about the source at the end, so it isn't "unchanged".
  const unverified = Boolean(startSnapshot && !endSnapshot);
  const changed = startSnapshot && endSnapshot ? changedBetween(startSnapshot, endSnapshot) : [];
  let outcome = reason === "timeout" ? "timed-out" : reason ? "canceled" : code === 0 ? "passed" : "failed";
  if (outcome === "passed" && tests?.skipped) outcome = `passed, ${tests.skipped} skipped`;
  if (changed.length) {
    console.error(`[e2e-run] CONTAMINATED: ${changed.length} runtime file(s) changed during the run (${brief(changed)}): these results describe neither ${candidate ? candidate.commit.slice(0, 7) : "the commit"} nor the tree the run started with`);
    if (!reason) status = 3;
    outcome = `contaminated (${outcome})`;
  } else if (unverified) {
    console.error(`[e2e-run] UNVERIFIED: the source couldn't be checked at the end (${snapshotError}): these results can't be tied to ${candidate ? candidate.commit.slice(0, 7) : "a commit"}`);
    if (!reason) status = 3;
    outcome = `unverified (${outcome})`;
  }
  console.error(`[e2e-run] outcome: ${outcome} (exit ${status})`);
  try {
    mkdirSync(PROVENANCE_DIR, { recursive: true });
    writeFileSync(join(PROVENANCE_DIR, "e2e-provenance.json"), JSON.stringify({
      run: runId, commit: candidate?.commit ?? null, differs_at_start: candidate?.differs ?? null,
      changed_during_run: startSnapshot && !unverified ? changed : null, outcome, exit: status, tests,
      real_judge: process.env.E2E_JUDGE === "1", started_at: startedAt,
      ended_at: new Date().toISOString(), playwright_args: args,
    }, null, 2));
  } catch { /* nowhere to write: the lines above still say it */ }
  process.exit(status);
}

for (const sig of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(sig, () => {
    reason ??= sig;
    void finish(1);
  });
}
if (maxMinutes) {
  setTimeout(() => {
    reason ??= "timeout";
    void finish(1);
  }, maxMinutes * 60_000).unref();
}
child.on("exit", (code, signal) => void finish(code ?? (signal ? 1 : 0)));
