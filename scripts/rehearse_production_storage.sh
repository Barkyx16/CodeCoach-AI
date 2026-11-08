#!/usr/bin/env bash
# Rehearse deploy/docker-compose.production.yml on this machine, with throwaway passwords and
# synthetic data. It's a rehearsal, not a deployment: nothing is published, no DNS changes, and
# no email can leave (the SMTP host is under .invalid, which never resolves).
#
#   scripts/rehearse_production_storage.sh
#   IMAGE=codecoach-api:rehearsal scripts/rehearse_production_storage.sh   # use a prebuilt API image
#
# Checks, in order:
#   1. db + migrate + api start: the migrate job (owner role) runs alembic, seed and grant-app-role;
#      the API (app role) becomes ready.
#   2. The API container holds the app role's password only, never the owner's or the superuser's,
#      and `check-rls --strict` passes inside it.
#   3. Saved work survives: an API restart, the database container being removed and recreated,
#      and `docker compose down` followed by `up`.
#   4. Readiness: 503 while the database is stopped, 200 again once it's back.
# Everything runs under its own project and volume names (codecoach_rehearsal*), and only those are
# removed at the end. A production volume (codecoach_pgdata) is never touched.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v docker >/dev/null || { echo "needs docker"; exit 2; }

PROJECT=codecoach_rehearsal
PORT=${PORT:-18000}
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
hex() { openssl rand -hex 32; }
SUPER=$(hex); OWNER=$(hex); APP=$(hex)

cat >"$WORK/compose.env" <<EOF
POSTGRES_SUPERUSER_PASSWORD=$SUPER
CODECOACH_OWNER_PASSWORD=$OWNER
CODECOACH_APP_PASSWORD=$APP
PUBLIC_API_URL=https://rehearsal.invalid
EOF
# The compose file reads deploy/.env.app; a rehearsal brings its own and removes it afterwards.
if [ -e deploy/.env.app ]; then echo "deploy/.env.app exists: refusing to overwrite it"; exit 2; fi
cat >deploy/.env.app <<EOF
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
APP_BASE_URL=https://rehearsal.invalid
CORS_ORIGINS=https://rehearsal.invalid
METRICS_TOKEN=$(hex)
EMAIL_BACKEND=smtp
SMTP_HOST=smtp.rehearsal.invalid
SMTP_USERNAME=rehearsal
SMTP_PASSWORD=$(hex)
EMAIL_FROM=CodeCoach AI <no-reply@rehearsal.invalid>
AUTH_RATE_LIMIT_PER_MINUTE=100
EOF
trap 'rm -rf "$WORK" deploy/.env.app' EXIT

{
  echo "volumes:"
  echo "  pgdata:"
  echo "    name: codecoach_rehearsal_pgdata"
  echo "services:"
  echo "  api:"
  echo "    ports: !override [\"127.0.0.1:$PORT:8000\"]"
  if [ -n "${IMAGE:-}" ]; then
    echo "    image: $IMAGE"
    echo "    build: !reset null"
    echo "  migrate:"
    echo "    image: $IMAGE"
    echo "    build: !reset null"
  fi
} >"$WORK/override.yml"
cp "$WORK/override.yml" deploy/.rehearsal.override.yml
trap 'rm -rf "$WORK" deploy/.env.app deploy/.rehearsal.override.yml' EXIT

dc() { docker compose -p "$PROJECT" --env-file "$WORK/compose.env" -f deploy/docker-compose.production.yml -f deploy/.rehearsal.override.yml "$@"; }
step() { printf '\n== %s\n' "$*"; }
api() { curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT$1"; }
wait_ready() { for _ in $(seq 1 60); do [ "$(api /health/ready)" = 200 ] && return 0; sleep 1; done; echo "API not ready"; dc logs api | tail -20; return 1; }

cleanup() { dc down -v --remove-orphans >/dev/null 2>&1 || true; }   # this rehearsal's project and volume only
trap 'cleanup; rm -rf "$WORK" deploy/.env.app deploy/.rehearsal.override.yml' EXIT

step "1. start db, migrate (owner) and api (app role)"
dc up -d db migrate api >/dev/null 2>&1
wait_ready && echo "ok: API ready"
[ "$(dc ps -a --format '{{.Service}} {{.ExitCode}}' | awk '$1=="migrate"{print $2}')" = 0 ] && echo "ok: migrate job exited 0"

step "2. what the API container holds"
ENVDUMP=$(dc exec -T api env)
grep -q "$OWNER" <<<"$ENVDUMP" && { echo "FAIL: owner password inside the API container"; exit 1; }
grep -q "$SUPER" <<<"$ENVDUMP" && { echo "FAIL: superuser password inside the API container"; exit 1; }
grep -q "codecoach_app:" <<<"$ENVDUMP" && echo "ok: API connects as codecoach_app; neither the owner's nor the superuser's password is in its environment"
dc exec -T api python -m app.cli check-rls --strict | tail -2

step "3. save work, then restart and recreate"
TOKEN=$(curl -s -X POST "http://127.0.0.1:$PORT/api/v1/auth/register" -H 'Content-Type: application/json' \
  -d '{"email":"rehearsal@example.com","password":"CorrectHorse42","display_name":"Rehearsal"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
NOTE=$(curl -s -X POST "http://127.0.0.1:$PORT/api/v1/me/notes" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"title":"Survives restarts","body":"synthetic"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
echo "saved note $NOTE"
has_note() {
  local t
  t=$(curl -s -X POST "http://127.0.0.1:$PORT/api/v1/auth/login" -H 'Content-Type: application/json' \
    -d '{"email":"rehearsal@example.com","password":"CorrectHorse42"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
  curl -s "http://127.0.0.1:$PORT/api/v1/me/notes" -H "Authorization: Bearer $t" | grep -q "$NOTE"
}
dc restart api >/dev/null 2>&1 && wait_ready && has_note && echo "ok: after an API restart"
dc rm -sf db >/dev/null 2>&1 && dc up -d db migrate api >/dev/null 2>&1 && wait_ready && has_note && echo "ok: after the database container was removed and recreated"
dc down >/dev/null 2>&1 && dc up -d db migrate api >/dev/null 2>&1 && wait_ready && has_note && echo "ok: after docker compose down and up (the volume is kept)"

step "4. readiness follows the database"
dc stop db >/dev/null 2>&1
sleep 2
echo "database stopped: /health/ready=$(api /health/ready) /health=$(api /health)"
dc start db >/dev/null 2>&1
wait_ready && echo "database back: /health/ready=$(api /health/ready)"

step "done: removing this rehearsal's containers and its volume (codecoach_rehearsal_pgdata)"
