#!/usr/bin/env python3
"""Which tests exist, as the runners themselves collect them (Volume 9, prompt 10; docs/CI.md
"Test inventory").

    python scripts/test_inventory.py collect [--out FILE]          this tree's inventory
    python scripts/test_inventory.py compare BASE CAND [--accept FILE]
    python scripts/test_inventory.py since REF [--accept FILE]      REF's tests vs this tree's

An inventory is one line per test, "runner<TAB>file<TAB>test", from each runner's own collection:
`vitest list --json --staticParse=false`, `playwright test --list --reporter=json` (one line per project), and
`pytest --collect-only -q`. Plus one line per test file found on disk that no runner collected
("uncollected": named *.test.* or *.spec.* under frontend/src, a spec in frontend/e2e, test_*.py or
*_test.py in backend/tests), which is how a file left out of an include pattern shows up.

The comparison prints what was added, what may have been renamed (a removed test and an added one
in the same file with similar titles), and what was removed. It fails (exit 1) on removed tests
and on uncollected files, unless they're listed in an --accept file (one identity per line, or
"file<TAB>path" for a whole file; # comments). A rename is reported for review and doesn't fail.
There's no count gate: more tests can still hide a removed one, and merging tests can lower the
count legitimately.

It can't tell a test whose body was gutted from a real one, nor see a test skipped at run time.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RENAME_SIMILARITY = 0.8  # "goals return to the plan" vs "focus returns to item 1" is 0.68: not a rename


def _frontend_rel(path: str, root: Path) -> str:
    p = Path(path)
    try:
        return p.resolve().relative_to((root / "frontend").resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def parse_vitest(text: str, root: Path) -> set[str]:
    # Two cases of one table can format to the same title; the second is "title #2", so it's counted.
    out: set[str] = set()
    for t in json.loads(text):
        line, n = f"vitest\t{_frontend_rel(t['file'], root)}\t{t['name']}", 1
        while line + (f" #{n}" if n > 1 else "") in out:
            n += 1
        out.add(line + (f" #{n}" if n > 1 else ""))
    return out


def parse_playwright(text: str) -> set[str]:
    out: set[str] = set()

    def walk(suite: dict, file: str | None, titles: list[str]) -> None:
        file = suite.get("file") or file
        here = titles + ([suite["title"]] if suite.get("title") and suite.get("title") != file else [])
        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                name = " > ".join([*here, spec["title"]])
                out.add(f"playwright\te2e/{spec.get('file') or file}\t[{test.get('projectName')}] {name}")
        for child in suite.get("suites", []):
            walk(child, file, here)

    for suite in json.loads(text).get("suites", []):
        walk(suite, None, [])
    return out


def parse_pytest(text: str) -> set[str]:
    out: set[str] = set()
    for line in text.splitlines():
        if "::" in line and not line.startswith(" "):
            path, _, name = line.partition("::")
            out.add(f"pytest\tbackend/{path}\t{name}")
    return out


def files_on_disk(root: Path) -> dict[str, set[str]]:
    """Files whose names say they're tests, by the runner they'd belong to: the usual test and spec
    names, wider than each runner's configured include, so a file the include misses shows up."""
    fe, be = root / "frontend", root / "backend"

    def under(base: Path, patterns: tuple[str, ...], rel_to: Path, prefix: str = "") -> set[str]:
        if not base.is_dir():
            return set()
        return {
            prefix + p.relative_to(rel_to).as_posix()
            for pattern in patterns
            for p in base.rglob(pattern)
            if "node_modules" not in p.parts
        }

    return {
        "vitest": under(fe / "src", ("*.test.ts", "*.test.tsx", "*.spec.ts", "*.spec.tsx"), fe),
        "playwright": under(fe / "e2e", ("*.spec.ts", "*.test.ts"), fe),
        "pytest": under(be / "tests", ("test_*.py", "*_test.py"), be, "backend/"),
    }


def uncollected(collected: Iterable[str], on_disk: dict[str, set[str]]) -> set[str]:
    seen: dict[str, set[str]] = {"vitest": set(), "playwright": set(), "pytest": set()}
    for line in collected:
        runner, file, _ = line.split("\t", 2)
        seen.setdefault(runner, set()).add(file)
    return {
        f"uncollected\t{runner}\t{f}"
        for runner, files in on_disk.items()
        for f in files - seen.get(runner, set())
    }


def _run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
    if result.returncode != 0 and not result.stdout.strip():
        raise SystemExit(
            f"collection failed: {' '.join(cmd)} (exit {result.returncode})\n{result.stderr[-2000:]}"
        )
    return result.stdout


def collect(root: Path, python: str) -> list[str]:
    fe, be = root / "frontend", root / "backend"
    lines: set[str] = set()
    # Not the default static parse: it lists an it.each table as one "%s" entry and can mistake a
    # helper call for a test. Running each file's collection gives the tests a run executes.
    lines |= parse_vitest(_run(["npx", "vitest", "list", "--json", "--staticParse=false"], fe), root)
    lines |= parse_playwright(_run(["npx", "playwright", "test", "--list", "--reporter=json"], fe))
    lines |= parse_pytest(
        _run([python, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"], be)
    )
    lines |= uncollected(lines, files_on_disk(root))
    return sorted(lines)


def compare(
    base: Iterable[str], cand: Iterable[str], accepted: Iterable[str] = ()
) -> tuple[dict[str, list], bool]:
    """What changed between two inventories, and whether it should fail (unaccepted removals or
    uncollected files)."""
    base_tests = {line for line in base if not line.startswith("uncollected\t")}
    cand_all = set(cand)
    cand_tests = {line for line in cand_all if not line.startswith("uncollected\t")}
    accept = {a.strip() for a in accepted if a.strip() and not a.lstrip().startswith("#")}
    accepted_files = {a.split("\t", 1)[1] for a in accept if a.startswith("file\t")}

    removed = sorted(base_tests - cand_tests)
    added = sorted(cand_tests - base_tests)
    renamed: list[tuple[str, str]] = []
    left_added = list(added)
    for old in list(removed):
        runner, file, title = old.split("\t", 2)
        best, score = None, 0.0
        for new in left_added:
            r2, f2, t2 = new.split("\t", 2)
            if (r2, f2) != (runner, file):
                continue
            s = difflib.SequenceMatcher(None, title, t2).ratio()
            if s > score:
                best, score = new, s
        if best is not None and score >= RENAME_SIMILARITY:
            renamed.append((old, best))
            removed.remove(old)
            left_added.remove(best)
    unaccepted = [r for r in removed if r not in accept and r.split("\t", 2)[1] not in accepted_files]
    lost_files = sorted(line for line in cand_all if line.startswith("uncollected\t") and line not in accept)
    report = {
        "added": left_added,
        "renamed": renamed,
        "removed": removed,
        "removed_unaccepted": unaccepted,
        "uncollected": lost_files,
    }
    return report, bool(unaccepted or lost_files)


def print_report(report: dict[str, list], failed: bool) -> None:
    show = lambda line: line.replace("\t", " | ")  # noqa: E731
    print(f"added: {len(report['added'])}")
    for line in report["added"][:50]:
        print(f"  + {show(line)}")
    if report["renamed"]:
        print(f"renamed (review these): {len(report['renamed'])}")
        for old, new in report["renamed"]:
            print(f"  ~ {show(old)}\n    -> {show(new)}")
    print(f"removed: {len(report['removed'])} ({len(report['removed_unaccepted'])} not accepted)")
    for line in report["removed"]:
        print(f"  - {show(line)}{'' if line in report['removed_unaccepted'] else '   (accepted)'}")
    if report["uncollected"]:
        print(f"test files no runner collects: {len(report['uncollected'])}")
        for line in report["uncollected"]:
            print(f"  ! {show(line)}")
    print(
        "FAIL: tests went missing (or aren't collected); accept them with --accept if that's intended"
        if failed
        else "OK"
    )


def _read(path: str) -> list[str]:
    return Path(path).read_text(encoding="utf-8").splitlines()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--out")
    c.add_argument("--root", default=str(REPO))
    c.add_argument("--python", default=str(REPO / "backend" / ".venv" / "bin" / "python"))
    m = sub.add_parser("compare")
    m.add_argument("base")
    m.add_argument("cand")
    m.add_argument("--accept")
    s = sub.add_parser("since")
    s.add_argument("ref")
    s.add_argument("--accept")
    s.add_argument("--python", default=str(REPO / "backend" / ".venv" / "bin" / "python"))
    args = ap.parse_args(argv)
    python = getattr(args, "python", sys.executable)
    if not Path(python).exists():
        python = sys.executable

    if args.cmd == "collect":
        lines = collect(Path(args.root), python)
        text = "\n".join(lines) + "\n"
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        return 0
    if args.cmd == "compare":
        report, failed = compare(
            _read(args.base), _read(args.cand), _read(args.accept) if args.accept else ()
        )
        print_report(report, failed)
        return 1 if failed else 0

    # since REF: REF's inventory from a temporary checkout of it (sharing this tree's installed
    # dependencies), this tree's from here; the checkout is removed afterwards, and nothing else.
    tmp = Path(tempfile.mkdtemp(prefix="test-inventory-"))
    tree = tmp / "tree"
    try:
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(tree), args.ref],
            cwd=REPO,
            check=True,
            capture_output=True,
        )
        (tree / "frontend" / "node_modules").symlink_to(REPO / "frontend" / "node_modules")
        venv = REPO / "backend" / ".venv"
        if venv.exists():
            (tree / "backend" / ".venv").symlink_to(venv)
        base = collect(tree, python)
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(tree)], cwd=REPO, capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)
    cand = collect(REPO, python)
    report, failed = compare(base, cand, _read(args.accept) if args.accept else ())
    print_report(report, failed)
    return 1 if failed else 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    raise SystemExit(main())
