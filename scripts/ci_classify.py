"""Which CI lanes a change needs (Volume 8, prompt 10; docs/CI.md).

    python scripts/ci_classify.py --base SHA --head SHA     # writes lane=true|false to $GITHUB_OUTPUT
    python scripts/ci_classify.py --full                    # everything (manual runs, release candidates)

Conservative by construction: a path is only treated as narrow when a rule says so. Workflows,
lockfiles and dependency lists, shared configuration, the CI scripts themselves, deleted or
renamed paths, an empty or unreadable diff, and any path no rule recognises all mean every lane.
A change touching only documentation gets the documentation lane: the secret scan and dependency
audit run, the code jobs don't, and the summary says so. That isn't the code jobs passing.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Iterable

LANES = ("backend", "frontend", "e2e", "runner", "sandbox", "docker")

# Any of these means everything runs.
FULL_PREFIXES = (
    ".github/",
    "scripts/ci_",
    "deploy/",
    "docker-compose",
    "backend/requirements",
    "runner/requirements",
    "frontend/package.json",
    "frontend/package-lock.json",
    "backend/pyproject.toml",
    "runner/pyproject.toml",
    "pyproject.toml",
    ".dockerignore",
    ".gitignore",
    ".gitattributes",
)

# (prefix, lanes it needs). First match wins, so the more specific prefixes come first.
RULES: tuple[tuple[str, frozenset[str]], ...] = (
    # The API contract: generated from the backend, checked by the frontend, used by the browser tests.
    ("docs/openapi.json", frozenset({"backend", "frontend", "e2e"})),
    ("docs/", frozenset()),
    ("backend/migrations/", frozenset({"backend", "e2e", "sandbox", "docker"})),
    ("backend/", frozenset({"backend", "e2e", "sandbox", "docker"})),
    ("frontend/", frozenset({"frontend", "e2e", "sandbox", "docker"})),
    ("runner/", frozenset({"runner", "sandbox", "docker"})),
    ("scripts/rehearse_production_storage.sh", frozenset({"docker"})),
    ("scripts/rehearse_web_csp.sh", frozenset({"e2e"})),
    ("scripts/verify_", frozenset({"backend"})),
    ("scripts/check_secrets.py", frozenset()),  # the security job, which always runs
    (".secrets.baseline", frozenset()),
)
DOC_SUFFIXES = (".md", ".png", ".jpg", ".jpeg", ".svg", ".txt")


def classify(paths: Iterable[str], deleted_or_renamed: bool = False) -> dict[str, bool]:
    """lane -> needed, plus "docs_only" and "full"."""
    paths = [p.strip() for p in paths if p.strip()]
    if not paths or deleted_or_renamed:
        return {**dict.fromkeys(LANES, True), "docs_only": False, "full": True}
    needed: set[str] = set()
    for path in paths:
        if path.startswith(FULL_PREFIXES):
            return {**dict.fromkeys(LANES, True), "docs_only": False, "full": True}
        for prefix, lanes in RULES:
            if path.startswith(prefix):
                needed |= lanes
                break
        else:
            # Top-level documentation (README.md, LICENSE notes) is documentation; anything
            # else nobody classified means everything.
            if "/" not in path and path.endswith(DOC_SUFFIXES):
                continue
            return {**dict.fromkeys(LANES, True), "docs_only": False, "full": True}
    return {**{lane: lane in needed for lane in LANES}, "docs_only": not needed, "full": needed == set(LANES)}


def changed_paths(base: str, head: str) -> tuple[list[str], bool]:
    """Paths changed from base to head (three-dot: since they diverged), and whether any was
    deleted or renamed. Raises if git can't answer."""
    out = subprocess.run(
        ["git", "diff", "--name-status", "--no-renames", f"{base}...{head}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    paths, removed = [], False
    for line in out.splitlines():
        status, _, path = line.partition("\t")
        if status.startswith("D"):
            removed = True
        paths.append(path)
    return paths, removed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args(argv)
    reason = "full run requested"
    if args.full or not args.base or set(args.base) == {"0"}:
        lanes = classify([], True)
        if not args.full:
            reason = "no base to compare with: everything"
    else:
        try:
            paths, removed = changed_paths(args.base, args.head or "HEAD")
            lanes = classify(paths, removed)
            reason = f"{len(paths)} changed path(s) since {args.base[:12]}"
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            lanes = classify([], True)
            reason = f"couldn't read the diff ({type(exc).__name__}): everything"
    print(f"{reason}: {json.dumps(lanes)}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            for key, value in lanes.items():
                f.write(f"{key}={'true' if value else 'false'}\n")
            f.write(f"lanes={json.dumps(lanes)}\n")
            f.write(f"reason={reason}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
