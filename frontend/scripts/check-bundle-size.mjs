// Bundle budgets (docs/PERFORMANCE.md, "Frontend"). Run after `npm run build`:
//   npm run size:check
// Gzipped sizes, level 9. The shell is what index.html loads up front (entry script, preloaded
// chunks and CSS); lazy chunks (the code editor) load only when a page needs them.
// Budgets are today's sizes plus a little headroom: raise one deliberately, with a reason, rather
// than letting the app grow unnoticed.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { gzipSync } from "node:zlib";

const BUDGET_KB = { shell: 300, largestLazyChunk: 700 };
const dist = new URL("../dist/", import.meta.url).pathname;
const gz = (file) => gzipSync(readFileSync(join(dist, file)), { level: 9 }).length / 1024;

const html = readFileSync(join(dist, "index.html"), "utf8");
const shellFiles = [...new Set([...html.matchAll(/(?:src|href)="\/(assets\/[^"]+\.(?:js|css))"/g)].map((m) => m[1]))];
const shell = shellFiles.reduce((sum, f) => sum + gz(f), 0);
const lazy = readdirSync(join(dist, "assets"))
  .filter((f) => f.endsWith(".js") && !shellFiles.includes(`assets/${f}`))
  .map((f) => [f, gz(join("assets", f))])
  .sort((a, b) => b[1] - a[1]);
const [largestName, largest] = lazy[0] ?? ["(none)", 0];

const rows = [
  ["shell (index.html loads it)", shell, BUDGET_KB.shell, shellFiles.join(", ")],
  ["largest lazy chunk", largest, BUDGET_KB.largestLazyChunk, largestName],
];
let failed = false;
for (const [name, kb, budget, detail] of rows) {
  const ok = kb <= budget;
  failed ||= !ok;
  console.log(`${ok ? "ok  " : "OVER"} ${name}: ${kb.toFixed(1)} KB gzip (budget ${budget} KB) · ${detail}`);
}
if (failed) {
  console.error("Bundle over budget. Find what grew (npx vite-bundle-visualizer), or raise the budget deliberately.");
  process.exit(1);
}
