#!/usr/bin/env node
/**
 * Wraps one e2e web server so the run that started it can stop it later, and only it.
 *
 * Playwright starts each web server as the leader of its own process group. If Playwright is
 * killed outright, those groups outlive it: an orphaned API on :8000, which the next run would
 * reuse. Under scripts/e2e-run.mjs (E2E_RUN_ID set), this records the server's process group in
 * E2E_OWNED_DIR/<run>.<name>.json, so the launcher can stop exactly that group. It never stops
 * anything by name or by port. Without a run id (plain `npx playwright test`), it just runs the
 * command.
 *
 * It also watches the launcher (E2E_LAUNCHER_PID). If the launcher is gone, even killed outright
 * with no chance to clean up, this stops its own server within about a second. A server that was
 * still starting when the run was interrupted doesn't start at all.
 *
 * The command comes from E2E_OWNED_COMMAND, so the config doesn't have to nest its quoting.
 */
import { execFileSync, spawn } from "node:child_process";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const name = process.env.E2E_OWNED_NAME ?? "server";
const command = process.env.E2E_OWNED_COMMAND;
if (!command) {
  console.error("e2e-owned: E2E_OWNED_COMMAND is empty");
  process.exit(2);
}

const launcherPid = Number(process.env.E2E_LAUNCHER_PID) || null;
function launcherAlive() {
  if (!launcherPid) return true; // plain `npx playwright test`: nothing to watch
  try {
    process.kill(launcherPid, 0);
    return true;
  } catch (e) {
    return e.code === "EPERM";
  }
}
if (!launcherAlive()) process.exit(0); // the run ended while this server was starting

let pgid = process.pid;
try {
  pgid = Number(execFileSync("ps", ["-o", "pgid=", "-p", String(process.pid)], { encoding: "utf8" }).trim()) || pgid;
} catch {
  /* no ps: the pid itself is still a useful record */
}

const runId = process.env.E2E_RUN_ID;
const dir = process.env.E2E_OWNED_DIR;
let record = null;
if (runId && dir) {
  mkdirSync(dir, { recursive: true });
  record = join(dir, `${runId}.${name}.json`);
  // Names and numbers only: no environment, no command line (it can carry test tokens).
  writeFileSync(record, JSON.stringify({ run: runId, name, pgid, pid: process.pid, started_at: new Date().toISOString() }));
}

const child = spawn(command, { shell: true, stdio: "inherit" });
for (const sig of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(sig, () => child.kill(sig));
}
if (launcherPid) {
  setInterval(() => {
    if (launcherAlive()) return;
    // The launcher is gone: stop this server's whole group (the shell, the server, its children),
    // or at least the server itself when this isn't a group of our own.
    try {
      process.kill(-pgid, "SIGTERM");
    } catch {
      child.kill("SIGTERM");
    }
  }, 1000).unref();
}
child.on("exit", (code, signal) => {
  if (record) rmSync(record, { force: true });
  process.exit(code ?? (signal ? 128 + (signal === "SIGKILL" ? 9 : 15) : 1));
});
