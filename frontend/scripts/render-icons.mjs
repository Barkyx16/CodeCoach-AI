// Renders the app icons from the SVG mark with the installed Chromium (no extra dependencies).
// Run: node scripts/render-icons.mjs   (re-run if the mark changes)
import { chromium } from "playwright";
import { writeFileSync } from "node:fs";

const mark = (size, padding) => `<!doctype html><html><body style="margin:0;background:#0b1324">
<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 32 32">
  <rect width="32" height="32" fill="#0b1324"/>
  <g transform="translate(${16 - 16 * (1 - padding)} ${16 - 16 * (1 - padding)}) scale(${1 - padding})">
    <path d="M12 10l-6 6 6 6M20 10l6 6-6 6" stroke="#38bdf8" stroke-width="2.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  </g>
</svg></body></html>`;

const browser = await chromium.launch();
const page = await browser.newPage({ deviceScaleFactor: 1 });
// "any": full-bleed square (platforms round it); "maskable": the mark inside the 80% safe zone.
for (const [name, size, padding] of [
  ["icon-192.png", 192, 0.1], ["icon-512.png", 512, 0.1],
  ["icon-maskable-512.png", 512, 0.3], ["apple-touch-icon.png", 180, 0.15],
]) {
  await page.setViewportSize({ width: size, height: size });
  await page.setContent(mark(size, padding));
  writeFileSync(`public/icons/${name}`, await page.screenshot({ type: "png", omitBackground: false }));
}
await browser.close();
console.log("icons written to public/icons/");
