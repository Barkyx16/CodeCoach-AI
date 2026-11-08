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
 */
import { execFileSync, spawn } from "node:child_process";
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

const runId = `${Date.now().toString(36)}-${process.pid}`;
mkdirSync(OWNED_DIR, { recursive: true });
const launcherRecord = join(OWNED_DIR, `${runId}.launcher.json`);
writeFileSync(launcherRecord, JSON.stringify({ run: runId, name: "launcher", pid: process.pid, pgid: process.pid, started_at: new Date().toISOString() }));

// E2E_PLAYWRIGHT_CMD exists for the launcher's own tests (a stand-in for Playwright).
const [cmd, ...cmdArgs] = process.env.E2E_PLAYWRIGHT_CMD
  ? ["sh", "-c", process.env.E2E_PLAYWRIGHT_CMD]
  : ["npx", "playwright", "test", ...args];
const child = spawn(cmd, cmdArgs, {
  detached: true, // its own process group: Playwright, its workers, and anything they start
  stdio: "inherit",
  env: { ...process.env, E2E_RUN_ID: runId, E2E_OWNED_DIR: OWNED_DIR, E2E_LAUNCHER_PID: String(process.pid) },
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
  const status = reason === "timeout" ? 124 : reason ? 128 + ({ SIGINT: 2, SIGTERM: 15, SIGHUP: 1 }[reason] ?? 15) : code;
  if (reason) console.error(`[e2e-run] ${reason === "timeout" ? `stopped after ${maxMinutes} min` : `interrupted (${reason})`}: run ${runId} incomplete, its servers stopped`);
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
