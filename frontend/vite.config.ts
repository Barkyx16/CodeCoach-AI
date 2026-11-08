/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath, URL } from "node:url";
import { defineConfig, loadEnv, type Plugin } from "vite";

import { leakedServerSecrets, secretLookingPublicVars } from "./src/build/secretGuard.ts";

/**
 * Fills in the service worker's file lists after a production build: the app shell (index.html,
 * the files it loads, fonts, icons) to precache, and every built asset that may be cached when
 * first used. The version changes whenever any of them does, which is what triggers an update.
 */
function offlineShell(): Plugin {
  let outDir = "dist";
  let failed = false;
  return {
    name: "codecoach-offline-shell",
    apply: "build",
    configResolved(config) {
      outDir = resolve(config.root, config.build.outDir);
    },
    // closeBundle also runs after a failed build. Then there's nothing to fill in, and throwing
    // here would replace the build's own error with "no such file: dist/index.html".
    buildEnd(error) {
      if (error) failed = true;
    },
    renderError() {
      failed = true;
    },
    closeBundle() {
      if (failed || !existsSync(join(outDir, "index.html"))) return;
      const html = readFileSync(join(outDir, "index.html"), "utf8");
      const list = (dir: string, prefix: string) =>
        existsSync(join(outDir, dir)) ? readdirSync(join(outDir, dir)).filter((f) => !f.endsWith(".map")).map((f) => `${prefix}${f}`) : [];
      const entry = [...html.matchAll(/(?:src|href)="(\/assets\/[^"]+)"/g)].map((m) => m[1]!);
      const shell = [...new Set(["/index.html", "/display-init.js", "/boot-check.js", "/favicon.svg", "/manifest.webmanifest",
        ...list("icons", "/icons/"), ...list("fonts", "/fonts/").filter((f) => f.endsWith(".woff2")), ...entry])].sort();
      const assets = list("assets", "/assets/").sort();
      const hash = createHash("sha256").update(html);
      for (const file of assets) hash.update(file);
      const version = hash.digest("hex").slice(0, 12);
      const swPath = join(outDir, "sw.js");
      const sw = readFileSync(swPath, "utf8")
        .replace('/*__SHELL_VERSION__*/ "dev"', JSON.stringify(version))
        .replace("/*__SHELL_FILES__*/ []", JSON.stringify(shell))
        .replace("/*__BUILD_ASSETS__*/ []", JSON.stringify(assets));
      if (sw.includes("__SHELL_")) throw new Error("sw.js placeholders were not filled in");
      writeFileSync(swPath, sw);
    },
  };
}

/**
 * Keeps secrets out of the browser bundle (src/build/secretGuard.ts). Refuses to start or build if
 * a VITE_* variable is named like a secret (Vite publishes every VITE_* value), and fails a build
 * whose output contains the value of a server-side secret from the environment or a .env file
 * (frontend/ or the repository root). Errors name the variable, never its value.
 */
function noSecretsInBundle(): Plugin {
  let env: Record<string, string | undefined> = {};
  return {
    name: "codecoach-no-secrets",
    configResolved(config) {
      const publicVars = secretLookingPublicVars({ ...process.env, ...config.env });
      if (publicVars.length > 0) {
        throw new Error(`${publicVars.join(", ")}: VITE_* variables are published in the browser bundle, so they can't hold secrets. Keep secrets in the backend's environment.`);
      }
      env = { ...loadEnv(config.mode, resolve(config.root, ".."), ""), ...loadEnv(config.mode, config.envDir || config.root, ""), ...process.env };
    },
    generateBundle(_options, bundle) {
      for (const [file, output] of Object.entries(bundle)) {
        const code = output.type === "chunk" ? output.code : typeof output.source === "string" ? output.source : Buffer.from(output.source).toString("latin1");
        const leaked = leakedServerSecrets(code, env);
        if (leaked.length > 0) this.error(`${file} contains the value of ${leaked.join(", ")}. Server secrets must never be in frontend code.`);
      }
    },
  };
}

/**
 * Which build this is, for the support report: CODECOACH_BUILD_ID when the build sets it (CI, an
 * image build without .git), else the commit it was built from, else "unknown". A commit id
 * only: never a branch name, path or anything else from the build machine.
 */
function buildId(): string {
  const given = process.env.CODECOACH_BUILD_ID?.trim();
  if (given && /^[A-Za-z0-9._-]{1,40}$/.test(given)) return given;
  try {
    const sha = execFileSync("git", ["rev-parse", "--short=12", "HEAD"], { stdio: ["ignore", "pipe", "ignore"] }).toString().trim();
    return /^[0-9a-f]{7,40}$/.test(sha) ? sha : "unknown";
  } catch {
    return "unknown";
  }
}

export default defineConfig({
  define: { __CODECOACH_BUILD__: JSON.stringify(buildId()) },
  plugins: [react(), offlineShell(), noSecretsInBundle()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 5173,
    strictPort: true,
    // ./dev.sh sets this so the browser's errors (a page that stays blank in Safari, say) are
    // printed in the terminal running it. Unset, Vite's default applies.
    forwardConsole: process.env.CODECOACH_FORWARD_CONSOLE === "1" ? { unhandledErrors: true, logLevels: ["error"] } : undefined,
  },
  build: {
    sourcemap: true,
    // Monaco is only imported by the lazily-loaded workspace route, so it lands in its own
    // async chunk and is never downloaded on the landing or library pages.
    chunkSizeWarningLimit: 3500,
  },
  test: {
    globals: true,
    css: false,
    restoreMocks: true,
    projects: [
      {
        // The app: a browser-like DOM, and MSW standing in for the API.
        extends: true,
        test: {
          name: "app",
          environment: "jsdom",
          include: ["src/**/*.test.{ts,tsx}"],
          exclude: ["src/**/*.node.test.ts"],
          setupFiles: ["./src/test/setup.ts"],
        },
      },
      {
        // Build and test tooling (real processes, real sockets): plain Node, no MSW.
        extends: true,
        test: { name: "tooling", environment: "node", include: ["src/**/*.node.test.ts"] },
      },
    ],
  },
});
