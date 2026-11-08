#!/usr/bin/env bash
# The production web image's Content-Security-Policy, from a real browser. Builds the image for a
# non-default API origin, serves it from its own nginx, runs a real API at that origin, and drives
# Chromium through frontend/scripts/check-csp.mjs. Also shows that a bad API URL fails the build.
#
#   scripts/rehearse_web_csp.sh
#   WEB_DOCKERFILE=path/to/Dockerfile ... (+ WEB_BUILD_ARGS="--build-context ca=…")   # sandbox only
#
# Needs docker, the backend's Python dependencies (PYTHON, default python3) and the frontend's
# node_modules with Playwright's Chromium. Everything it starts is its own: one container with a
# unique name, one API process, removed at the end. Synthetic data only.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON=${PYTHON:-python3}
WEB_PORT=${WEB_PORT:-13100}
API_PORT=${API_PORT:-18100}
API="http://127.0.0.1:$API_PORT"
WEB="http://127.0.0.1:$WEB_PORT"
RUN_ID="csp-$$-$(date +%s)"
WORK=$(mktemp -d)
CONTAINER="codecoach_csp_rehearsal_$RUN_ID"
API_PID=""
cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  [ -n "$API_PID" ] && kill "$API_PID" 2>/dev/null || true
  rm -rf "$WORK"
}
trap cleanup EXIT

# --progress=plain keeps each step's own output (the refusal's reason) in the log.
build() { docker build --progress=plain ${WEB_DOCKERFILE:+-f "$WEB_DOCKERFILE"} ${WEB_BUILD_ARGS:-} --build-arg "VITE_API_BASE_URL=$1" -t "$2" frontend; }

echo "== 1. a bad API URL fails the build, before the bundle is built"
# The credentials case is assembled here: a credential-shaped literal would trip the secret scan.
WITH_CREDENTIALS=$(printf 'https://%s@api.example.com' "user:not-a-password")
for bad in 'https://api.example.com; script-src *' 'ftp://api.example.com' "$WITH_CREDENTIALS"; do
  if build "$bad" "codecoach-web:csp-bad-$RUN_ID" >"$WORK/bad.log" 2>&1; then
    echo "FAIL: the build accepted $bad"; exit 1
  fi
  grep -q "csp-origin:" "$WORK/bad.log" || { echo "FAIL: no reason given for $bad"; tail -5 "$WORK/bad.log"; exit 1; }
done
echo "ok: a URL with a policy injection, another scheme or credentials fails the build, with the reason"

echo "== 2. build for $API, serve it, run the API there"
build "$API" "codecoach-web:csp-$RUN_ID" >"$WORK/build.log" 2>&1 || { echo "FAIL: build"; tail -20 "$WORK/build.log"; exit 1; }
docker run -d --name "$CONTAINER" -p "127.0.0.1:$WEB_PORT:8080" "codecoach-web:csp-$RUN_ID" >/dev/null
(cd backend && DATABASE_URL="sqlite:///$WORK/csp.db" CORS_ORIGINS="$WEB" SECRET_KEY="csp-rehearsal-secret-key-at-least-32-characters" \
  EMAIL_BACKEND=file EMAIL_FILE_DIR="$WORK/out" AI_PROVIDER=offline LOG_LEVEL=WARNING \
  exec "$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port "$API_PORT") >"$WORK/api.log" 2>&1 &
API_PID=$!
for _ in $(seq 1 60); do curl -sf -o /dev/null "$API/health/ready" && curl -sf -o /dev/null "$WEB/" && break; sleep 1; done
curl -sf -o /dev/null "$API/health/ready" || { echo "FAIL: API not ready"; tail -5 "$WORK/api.log"; exit 1; }

echo "== 3. the policy, from the browser"
(cd frontend && node scripts/check-csp.mjs "$WEB" "$API")
echo "== done: removing the container, the API and the test images"
docker rmi -f "codecoach-web:csp-$RUN_ID" >/dev/null 2>&1 || true
