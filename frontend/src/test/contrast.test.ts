/** Re-checks the real colors in tokens.css: every text/background pair the app uses, per theme. */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const css = readFileSync(resolve(__dirname, "../styles/tokens.css"), "utf8");

function block(selector: string): Record<string, string> {
  const start = css.indexOf(`${selector} {`);
  if (start < 0) throw new Error(`no ${selector} block`);
  const body = css.slice(start, css.indexOf("\n}", start));
  const out: Record<string, string> = {};
  for (const m of body.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6}\b|rgba\([^)]*\))/g)) out[m[1]!] = m[2]!;
  return out;
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!;
}
/** A translucent tint (rgba) painted over an opaque background, as the browser composites it. */
function over(rgba: string, base: string): string {
  const [r, g, b, a] = rgba.match(/[\d.]+/g)!.map(Number) as [number, number, number, number];
  const bg = [1, 3, 5].map((i) => parseInt(base.slice(i, i + 2), 16));
  return `#${[r, g, b].map((c, i) => Math.round(c * a + bg[i]! * (1 - a)).toString(16).padStart(2, "0")).join("")}`;
}

const ratio = (a: string, b: string) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi! + 0.05) / (lo! + 0.05);
};

const dark = block(":root");
const light = { ...dark, ...block(':root[data-theme="light"]') };
const darkHigh = { ...dark, ...block(':root[data-contrast="high"]') };
const lightHigh = { ...light, ...block(':root[data-theme="light"][data-contrast="high"]') };
const FG = ["color-text", "color-text-muted", "color-text-subtle", "color-link", "color-success", "color-warning", "color-danger", "color-info"];
const BG = ["color-bg", "color-surface", "color-surface-raised"];
const TINTED = [["color-link", "color-primary-soft"], ["color-text", "color-primary-soft"], ["color-success", "color-success-soft"],
  ["color-warning", "color-warning-soft"], ["color-danger", "color-danger-soft"], ["color-info", "color-info-soft"]] as const;

describe.each([
  ["dark", dark, 4.5],
  ["light", light, 4.5],
  ["dark, higher contrast", darkHigh, 7],
  ["light, higher contrast", lightHigh, 7],
])("%s theme", (_name, t, minimum) => {
  it.each(FG.flatMap((fg) => BG.map((bg) => [fg, bg])))("%s on %s meets the minimum", (fg, bg) => {
    expect(ratio(t[fg]!, t[bg]!)).toBeGreaterThanOrEqual(minimum);
  });
  // Badges, banners and the active nav item put coloured text on its own tint.
  it.each(TINTED.flatMap(([fg, tint]) => BG.map((bg) => [fg, tint, bg])))("%s on %s over %s meets the minimum", (fg, tint, bg) => {
    expect(ratio(t[fg]!, over(t[tint]!, t[bg]!))).toBeGreaterThanOrEqual(minimum);
  });
  it("white text on the primary button meets the minimum", () => {
    expect(ratio("#ffffff", t["color-primary"]!)).toBeGreaterThanOrEqual(minimum);
  });
});
