"""Fail if a tracked file contains a secret that isn't in the reviewed baseline (.secrets.baseline).

Uses detect-secrets (pinned in CI) with the plugins and file filters recorded in the baseline. A
finding is identified by file, secret type and a hash of the value, never its line number, so
editing a file doesn't fail the check. Output names files, lines and types, never values.

    pip install detect-secrets==1.5.0
    python scripts/check_secrets.py                # check every tracked file
    python scripts/check_secrets.py --update       # after reviewing new findings as safe

Every entry in the baseline was reviewed as a synthetic test value, a documented local-development
default, or a non-secret that looks random. See docs/SECURITY.md "Secrets".
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from detect_secrets.core import baseline
from detect_secrets.core.secrets_collection import SecretsCollection
from detect_secrets.settings import transient_settings

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / ".secrets.baseline"


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True).stdout
    return [f for f in out.decode().split("\0") if f and (ROOT / f).is_file()]


def identities(collection: SecretsCollection) -> set[tuple[str, str, str]]:
    return {(name, s.type, s.secret_hash) for name, s in collection}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--update", action="store_true", help="rewrite the baseline from the current tree")
    args = parser.parse_args()

    recorded = baseline.load_from_file(str(BASELINE))
    known = baseline.load(recorded, str(BASELINE))
    with transient_settings(
        {"plugins_used": recorded["plugins_used"], "filters_used": recorded["filters_used"]}
    ):
        found = SecretsCollection(root=str(ROOT))
        found.scan_files(*tracked_files())
        if args.update:
            baseline.save_to_file(found, str(BASELINE))
            print(f"Baseline rewritten: {sum(1 for _ in found)} reviewed findings.")
            return 0
    new = sorted(identities(found) - identities(known))
    if not new:
        print(f"No new secrets in tracked files ({sum(1 for _ in found)} known, reviewed findings).")
        return 0
    lines = {(name, s.type, s.secret_hash): s.line_number for name, s in found}
    print("Possible secrets that aren't in the reviewed baseline:", file=sys.stderr)
    for name, kind, digest in new:
        print(f"  {name}:{lines[(name, kind, digest)]}  {kind}", file=sys.stderr)
    print(
        "\nIf one is real, remove it and rotate it (a pushed secret is compromised). If it's a test "
        "value, review it, then run `python scripts/check_secrets.py --update`.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
