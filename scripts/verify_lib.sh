# Shared by scripts/verify_revision.sh. Source it with OUT set to an output directory.
#
# run_sh NAME "COMMAND"  runs COMMAND with bash -o pipefail (a failure anywhere in a pipeline
# fails the step), writes its output to $OUT/NAME.log, appends one line to $OUT/summary.txt and
# returns the command's own exit code. FAILED counts the steps that failed.

FAILED=${FAILED:-0}

run_sh() {
  local name=$1 cmd=$2 log="$OUT/$1.log" rc
  printf '== %s\n$ %s\n' "$name" "$cmd" >"$log"
  bash -o pipefail -c "$cmd" >>"$log" 2>&1
  rc=$?
  printf '%-18s rc=%-3s %s\n' "$name" "$rc" "$(grep -v '^\s*$' "$log" | tail -n 1 | cut -c1-140)" >>"$OUT/summary.txt"
  if [ "$rc" -ne 0 ]; then FAILED=$((FAILED + 1)); fi
  return "$rc"
}
