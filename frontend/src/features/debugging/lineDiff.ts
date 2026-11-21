/** A line diff (longest common subsequence) between the code an attempt started from and the code
 * sent: what the learner changed, shown next to the judge's verdict. Small inputs only (capped). */
export type DiffLine = { kind: "same" | "removed" | "added"; text: string };

const MAX_LINES = 400;

export function lineDiff(before: string, after: string): DiffLine[] | null {
  const a = before.replace(/\r\n/g, "\n").split("\n");
  const b = after.replace(/\r\n/g, "\n").split("\n");
  if (a.length > MAX_LINES || b.length > MAX_LINES) return null; // too long to show usefully
  const n = a.length;
  const m = b.length;
  const lcs: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      lcs[i]![j] = a[i] === b[j] ? lcs[i + 1]![j + 1]! + 1 : Math.max(lcs[i + 1]![j]!, lcs[i]![j + 1]!);
    }
  }
  const out: DiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { out.push({ kind: "same", text: a[i]! }); i++; j++; }
    else if (lcs[i + 1]![j]! >= lcs[i]![j + 1]!) { out.push({ kind: "removed", text: a[i]! }); i++; }
    else { out.push({ kind: "added", text: b[j]! }); j++; }
  }
  while (i < n) out.push({ kind: "removed", text: a[i++]! });
  while (j < m) out.push({ kind: "added", text: b[j++]! });
  return out;
}

/** Changed lines with one line of context around each change; "…" marks skipped unchanged lines. */
export function changedHunks(diff: DiffLine[]): (DiffLine | "gap")[] {
  const changed = (d: DiffLine | undefined) => d !== undefined && d.kind !== "same";
  const keep = diff.map((d, k) => changed(d) || changed(diff[k - 1]) || changed(diff[k + 1]));
  const out: (DiffLine | "gap")[] = [];
  diff.forEach((d, k) => {
    if (keep[k]) out.push(d);
    else if (out.at(-1) !== "gap") out.push("gap");
  });
  return out;
}
