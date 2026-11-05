#!/usr/bin/env bash
# Start CodeCoach on this computer: the API on http://localhost:8000 and the site on
# http://localhost:5173, in one terminal. Ctrl+C stops both.
#
#   ./dev.sh
#
# The first run creates backend/.venv and installs the Python and Node packages (a few
# minutes); later runs start straight away. Data is kept in backend/codecoach.db (SQLite).
set -euo pipefail
cd "$(dirname "$0")"

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
stop() { printf '\n\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

# --- tools ---------------------------------------------------------------------------------
mac_hint=""
[ "$(uname)" = "Darwin" ] && mac_hint=" On a Mac: install Homebrew from https://brew.sh, then run: brew install python@3.13 node"
PY=""
for c in python3.13 python3.12 python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
    PY=$c
    break
  fi
done
[ -n "$PY" ] || stop "Python 3.12 or newer wasn't found.$mac_hint"
command -v node >/dev/null 2>&1 || stop "Node.js wasn't found (version 20 or newer is needed).$mac_hint"
[ "$(node -p 'process.versions.node.split(".")[0]')" -ge 20 ] || stop "Node.js $(node --version) is too old: 20 or newer is needed.$mac_hint"

# --- first-run setup -----------------------------------------------------------------------
# An environment made earlier with an older Python (e.g. the Mac's built-in python3) can't install
# the packages: replace it.
if [ -e backend/.venv ] && ! backend/.venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
  say "backend/.venv was made with $(backend/.venv/bin/python --version 2>&1 || echo 'another Python'), too old: making it again with $($PY --version)..."
  rm -rf backend/.venv
fi
if [ ! -x backend/.venv/bin/python ]; then
  say "Creating the Python environment (backend/.venv) with $($PY --version)..."
  "$PY" -m venv backend/.venv
fi
if [ ! -f backend/.venv/.installed ] || [ backend/requirements-dev.txt -nt backend/.venv/.installed ] || [ backend/requirements.txt -nt backend/.venv/.installed ]; then
  say "Installing the backend's packages (first run only)..."
  backend/.venv/bin/python -m pip install --quiet --upgrade pip
  backend/.venv/bin/python -m pip install --quiet -r backend/requirements-dev.txt
  touch backend/.venv/.installed
fi
if [ ! -d frontend/node_modules ] || [ frontend/package-lock.json -nt frontend/node_modules ]; then
  say "Installing the frontend's packages (first run only)..."
  (cd frontend && npm ci --no-audit --no-fund)
  touch frontend/node_modules
fi

# --- start both, stop both -----------------------------------------------------------------
listening() { # is anything accepting connections on this port? IPv4 or IPv6: on a Mac the site's
  # server can listen on ::1 (IPv6) only, which a check of 127.0.0.1 alone never sees.
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null && return 0
  (exec 3<>"/dev/tcp/::1/$1") 2>/dev/null && return 0
  command -v curl >/dev/null 2>&1 || return 1
  local rc=0
  curl -s -o /dev/null --max-time 2 "http://localhost:$1/" || rc=$?
  [ "$rc" -ne 6 ] && [ "$rc" -ne 7 ] && [ "$rc" -ne 28 ] # 6, 7, 28: no name, refused, no answer
}
wait_for() { # port, pid, name
  local _
  for _ in $(seq 1 240); do
    listening "$1" && return 0
    kill -0 "$2" 2>/dev/null || stop "$3 stopped while starting: see the messages above."
    sleep 0.5
  done
  say "$3 hasn't answered on port $1 after two minutes; carrying on (see the messages above)."
}
for port in 8000 5173; do
  if listening "$port"; then
    stop "Something is already using port $port (an earlier run still open?). Close it, or find it with: lsof -i :$port"
  fi
done
pids=()
killtree() { # a server and everything it started (npm runs Vite as a grandchild)
  local child
  for child in $(pgrep -P "$1" 2>/dev/null); do killtree "$child"; done
  kill "$1" 2>/dev/null || true
}
cleanup() {
  local pid
  for pid in "${pids[@]+"${pids[@]}"}"; do killtree "$pid"; done
  wait 2>/dev/null || true
  printf '\nStopped.\n'
}
trap cleanup EXIT
trap 'exit 130' INT TERM

say "Starting the API on http://localhost:8000 ..."
(cd backend && DATABASE_URL="${DATABASE_URL:-sqlite:///./codecoach.db}" exec .venv/bin/python -m uvicorn app.main:app --reload --port 8000) &
pids+=($!)
wait_for 8000 "${pids[0]}" "The API"

say "Starting the site on http://localhost:5173 ..."
# CODECOACH_FORWARD_CONSOLE: the browser's errors are printed here too (frontend/vite.config.ts).
(cd frontend && CODECOACH_FORWARD_CONSOLE=1 exec npm run dev -- --port 5173 --strictPort) &
pids+=($!)
wait_for 5173 "${pids[1]}" "The site"

say "CodeCoach is running: open http://localhost:5173 (Ctrl+C here stops it)."
printf '%s\n' "If the page stays blank, reload it once. Errors from the browser are printed here."
if [ "$(uname)" = "Darwin" ] && [ -z "${NO_OPEN:-}" ]; then open http://localhost:5173 || true; fi
wait
