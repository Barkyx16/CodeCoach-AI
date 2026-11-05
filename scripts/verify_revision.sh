#!/usr/bin/env bash
# Run the repository's checks against one fixed revision, in a clean worktree, so edits made while
# the checks run can't leak into them (Verification brief 02).
#
#   scripts/verify_revision.sh REV OUT_DIR [--pg DATABASE_URL] [--e2e]
#
# OUT_DIR must be outside the repository: it receives the worktree (OUT_DIR/tree), one log per
# step and summary.txt (revision, tool versions, each step's exit code). The main checkout's
# backend/.venv and frontend/node_modules are reused only when the revision's dependency files
# are identical to the checkout's; otherwise it refuses. Steps run one after another. The exit
# status is 0 only if every step passed.
set -u
REV=${1:?revision}
OUT=${2:?output directory}
shift 2
PG=""
E2E=0
while [ $# -gt 0 ]; do
  case $1 in
    --pg) PG=$2; shift 2 ;;
    --e2e) E2E=1; shift ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
done
ROOT=$(git rev-parse --show-toplevel) || exit 2
SHA=$(git -C "$ROOT" rev-parse --verify "$REV^{commit}") || exit 2
OUT=$(realpath -m "$OUT")
case "$OUT/" in "$ROOT"/*) echo "OUT_DIR must be outside the repository" >&2; exit 2 ;; esac
mkdir -p "$OUT" || exit 2
for f in backend/requirements.txt backend/requirements-dev.txt frontend/package-lock.json; do
  if ! git -C "$ROOT" diff --quiet "$SHA" -- "$f"; then
    echo "refused: $f differs between $SHA and the checkout whose environment would be reused" >&2
    exit 2
  fi
done
TREE="$OUT/tree"
git -C "$ROOT" worktree remove --force "$TREE" >/dev/null 2>&1
git -C "$ROOT" worktree add --detach "$TREE" "$SHA" >/dev/null || exit 2
ln -s "$ROOT/frontend/node_modules" "$TREE/frontend/node_modules"
PY="$ROOT/backend/.venv/bin/python"
# shellcheck source=scripts/verify_lib.sh
. "$ROOT/scripts/verify_lib.sh"
{
  echo "revision:  $SHA ($(git -C "$ROOT" log -1 --format=%s "$SHA" | cut -c1-80))"
  echo "worktree:  $TREE (clean checkout of the revision)"
  echo "python:    $("$PY" --version 2>&1)  node: $(node --version 2>&1)"
  echo "postgres:  ${PG:+$(echo "$PG" | sed -E 's#//([^:/@]+):[^@]*@#//\1:***@#')}${PG:-not run}"
  echo "started:   $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} >"$OUT/summary.txt"
B="cd '$TREE/backend' &&"
F="cd '$TREE/frontend' &&"
run_sh backend-lint "$B '$PY' -m ruff check . && '$PY' -m ruff format --check ."
run_sh backend-types "$B '$PY' -m mypy app"
run_sh backend-sqlite "$B TEST_DATABASE_URL= '$PY' -m pytest -q -p no:cacheprovider"
if [ -n "$PG" ]; then
  run_sh backend-pg "$B TEST_DATABASE_URL='$PG' '$PY' -m pytest -q -p no:cacheprovider"
fi
run_sh frontend-lint "$F npm run -s lint"
run_sh frontend-types "$F npm run -s typecheck"
run_sh frontend-api "$F npm run -s api:check"
run_sh frontend-unit "$F npm test --silent"
run_sh frontend-build "$F npm run -s build"
run_sh frontend-size "$F npm run -s size:check"
if [ "$E2E" -eq 1 ]; then
  run_sh e2e "$F PYTHON='$PY' npx playwright test --reporter=line"
fi
echo "finished:  $(date -u +%Y-%m-%dT%H:%M:%SZ), $FAILED step(s) failed" >>"$OUT/summary.txt"
cat "$OUT/summary.txt"
[ "$FAILED" -eq 0 ]
