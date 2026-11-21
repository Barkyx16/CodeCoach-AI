import { readdirSync } from "node:fs";
import { join, relative } from "node:path";

// A Mac's file system (and Windows') ignores letter case. With `Reminders.tsx` and `reminders.ts`
// side by side, `import { Reminders } from "./Reminders"` opened `reminders.ts` there (.ts is tried
// before .tsx): the build failed on a Mac and the development page stayed blank, while Linux and
// CI, which tell the two apart, passed. So no two source files may share a name that differs
// only in case or in their script extension.

const SRC = join(__dirname, "..");
const SCRIPT = /\.(?:tsx?|jsx?|mts|mjs)$/;

function files(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory() ? files(join(dir, entry.name)) : [join(dir, entry.name)],
  );
}

it("no two source files share an import path that differs only in case or extension", () => {
  const byPath = new Map<string, string[]>();
  for (const file of files(SRC)) {
    const path = relative(SRC, file);
    const key = (SCRIPT.test(path) ? path.replace(SCRIPT, "") : path).toLowerCase();
    byPath.set(key, [...(byPath.get(key) ?? []), path]);
  }
  const clashes = [...byPath.values()].filter((paths) => paths.length > 1);
  expect(clashes).toEqual([]);
});
