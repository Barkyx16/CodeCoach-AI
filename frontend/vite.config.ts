/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath, URL } from "node:url";
import { defineConfig, type Plugin } from "vite";

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

export default defineConfig({
  plugins: [react(), offlineShell()],
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
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    restoreMocks: true,
  },
});
