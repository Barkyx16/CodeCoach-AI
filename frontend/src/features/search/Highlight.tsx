import type { ReactNode } from "react";

/**
 * Text with the searched words marked: React text nodes and <mark> elements only, never HTML from
 * the text, so markup in a note shows as the characters typed. Words are matched without regard to
 * case; overlapping matches are merged. Text whose lower-case form changes length (a few scripts)
 * is shown unmarked rather than marked in the wrong place.
 */
export function Highlight({ text, words }: { text: string; words: string[] }): ReactNode {
  const lower = text.toLowerCase();
  if (!words.length || lower.length !== text.length) return text;
  const ranges: [number, number][] = [];
  for (const word of words) {
    if (!word) continue;
    for (let at = lower.indexOf(word); at !== -1; at = lower.indexOf(word, at + word.length)) ranges.push([at, at + word.length]);
  }
  if (!ranges.length) return text;
  ranges.sort((a, b) => a[0] - b[0]);
  const merged: [number, number][] = [];
  for (const [s, e] of ranges) {
    const last = merged.at(-1);
    if (last && s <= last[1]) last[1] = Math.max(last[1], e);
    else merged.push([s, e]);
  }
  const out: ReactNode[] = [];
  let from = 0;
  merged.forEach(([s, e], i) => {
    if (s > from) out.push(text.slice(from, s));
    out.push(<mark key={i}>{text.slice(s, e)}</mark>);
    from = e;
  });
  if (from < text.length) out.push(text.slice(from));
  return <>{out}</>;
}
