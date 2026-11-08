#!/usr/bin/env bash
# Rehearse deploy/docker-compose.production.yml on this machine, with throwaway passwords and
# synthetic data. It's a rehearsal, not a deployment: nothing is published, no DNS changes, and
# no email can leave (the SMTP host is under .invalid, which never resolves).
#
#   scripts/rehearse_production_storage.sh
#   IMAGE=codecoach-api:rehearsal scripts/rehearse_production_storage.sh   # use a prebuilt API image
#   WEB_IMAGE=codecoach-web:rehearsal ...   # also start the web service from a prebuilt image
#                                           # (built with VITE_API_BASE_URL=https://rehearsal.invalid)
#   BACKUP_IMAGE=codecoach-backup:rehearsal ...   # a prebuilt backup image (backend/Dockerfile, target backup)
#
# Checks, in order:
#   1. db + migrate + api start: the migrate job (owner role) runs alembic, seed and grant-app-role;
#      the API (app role) becomes ready.
#   2. The API container holds the app role's password only, never the owner's or the superuser's,
#      and `check-rls --strict` passes inside it. 2c: through Docker's published port, the API
#      sees the visitor's forwarded address, not Docker's gateway.
#   3. Saved work survives: an API restart, the database container being removed and recreated,
#      and `docker compose down` followed by `up`.
#   4. Readiness: 503 while the database is stopped, 200 again once it's back.
#   5. The scheduled backup (`--profile backup run --rm backup`), twice: each run backs up as the
#      owner, prunes and checks. The API can't see the backups. The newest restores into a separate
#      database with a key that the server never holds, and the saved note is in the copy.
# Everything runs under its own project and volume names (codecoach_rehearsal*), and only those are
# removed at the end. A production volume (codecoach_pgdata) is never touched.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v docker >/dev/null || { echo "needs docker"; exit 2; }

PROJECT=codecoach_rehearsal
PORT=${PORT:-18000}
WEB_PORT=${WEB_PORT:-13000}
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

: >"$WORK/recipients.txt"   # filled in step 5; it must exist before compose mounts it
{
  echo "volumes:"
  echo "  pgdata:"
  echo "    name: codecoach_rehearsal_pgdata"
  echo "  backups:"
  echo "    name: codecoach_rehearsal_backups"
  echo "services:"
  echo "  backup:"
  echo "    volumes: !override"
  echo "      - backups:/backups"
  echo "      - $WORK/recipients.txt:/run/codecoach/recipients.txt:ro"
  if [ -n "${BACKUP_IMAGE:-}" ]; then
    echo "    image: $BACKUP_IMAGE"
    echo "    build: !reset null"
  fi
  echo "  api:"
  echo "    ports: !override [\"127.0.0.1:$PORT:8000\"]"
  if [ -n "${IMAGE:-}" ]; then
    echo "    image: $IMAGE"
    echo "    build: !reset null"
    echo "  migrate:"
    echo "    image: $IMAGE"
    echo "    build: !reset null"
  fi
  if [ -n "${WEB_IMAGE:-}" ]; then
    echo "  web:"
    echo "    image: $WEB_IMAGE"
    echo "    build: !reset null"
    echo "    ports: !override [\"127.0.0.1:$WEB_PORT:8080\"]"
  fi
} >"$WORK/override.yml"
cp "$WORK/override.yml" deploy/.rehearsal.override.yml
trap 'rm -rf "$WORK" deploy/.env.app deploy/.rehearsal.override.yml' EXIT

dc() { docker compose -p "$PROJECT" --env-file "$WORK/compose.env" -f deploy/docker-compose.production.yml -f deploy/.rehearsal.override.yml "$@"; }
step() { printf '\n== %s\n' "$*"; }
api() { curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT$1"; }
wait_ready() { for _ in $(seq 1 60); do [ "$(api /health/ready)" = 200 ] && return 0; sleep 1; done; echo "API not ready"; dc logs api | tail -20; return 1; }

cleanup() { dc --profile backup down -v --remove-orphans >/dev/null 2>&1 || true; }   # this rehearsal's project and volumes only
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

if [ -n "${WEB_IMAGE:-}" ]; then
  step "2b. the web service"
  dc up -d web >/dev/null 2>&1
  for _ in $(seq 1 30); do curl -sf -o /dev/null "http://127.0.0.1:$WEB_PORT/" && break; sleep 1; done
  HEADERS=$(curl -s -D - -o "$WORK/index.html" "http://127.0.0.1:$WEB_PORT/")
  grep -q '<div id="root">' "$WORK/index.html" && echo "ok: the built app is served"
  [ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$WEB_PORT/dashboard")" = 200 ] && echo "ok: app routes fall back to the app (/dashboard)"
  grep -qi "connect-src 'self' https://rehearsal.invalid;" <<<"$HEADERS" && echo "ok: the CSP allows exactly the API origin the build calls (PUBLIC_API_URL)"
  grep -qi "x-frame-options: DENY" <<<"$HEADERS" && grep -qi "x-content-type-options: nosniff" <<<"$HEADERS" && echo "ok: framing and sniffing blocked"
fi

step "2c. client addresses through Docker's published port"
# A proxy on the host connects through Docker's gateway. The API must believe its X-Forwarded-For,
# or every visitor shares the gateway's address and its sign-in rate limit.
curl -s -o /dev/null -H 'X-Forwarded-For: 203.0.113.7' "http://127.0.0.1:$PORT/health"
sleep 1
if ! dc logs api 2>/dev/null | grep -q '203\.0\.113\.7'; then
  echo "FAIL: the API didn't see the forwarded address; it sees:"; dc logs api 2>/dev/null | grep 'GET /health ' | tail -1; exit 1
fi
echo "ok: the API sees the visitor's forwarded address, not Docker's gateway: rate limits are per visitor"

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

step "5. the scheduled backup, then a restore into a separate database"
bk() { dc --profile backup run --rm -T "$@"; }
# A throwaway key pair. The private half (identity) stays in this rehearsal's temp folder: the
# backup service only ever gets the public key.
bk --no-deps --entrypoint age-keygen backup >"$WORK/identity.txt" 2>/dev/null
grep -o 'age1[0-9a-z]*' "$WORK/identity.txt" | head -1 >"$WORK/recipients.txt"
[ -s "$WORK/recipients.txt" ] || { echo "FAIL: no age key"; exit 1; }
for night in 1 2; do
  OUT=$(bk backup 2>&1) || { echo "FAIL: backup run $night"; tail -5 <<<"$OUT"; exit 1; }
  sleep 1   # backups are named to the second
done
must() { grep -q "$1" <<<"$2" || { echo "FAIL: expected \"$1\" in:"; grep -v '^ Container' <<<"$2"; exit 1; }; }
must "^Backup written" "$OUT"; must "^Kept 2\. Deleted 0\." "$OUT"; must "^OK " "$OUT"
echo "ok: two runs of the backup job: each backed up as the owner, pruned (kept 2) and checked"
if dc exec -T api sh -c 'test -e /backups'; then echo "FAIL: the API container can see the backups"; exit 1; fi
echo "ok: the API container has no backups volume"
NEWEST=$(bk --no-deps --entrypoint sh backup -c 'ls -1 /backups/*.dump.age | sort | tail -1' 2>/dev/null)
dc exec -T db createdb -U postgres -O codecoach_owner codecoach_restored
export RESTORE_DATABASE_URL="postgresql+psycopg://codecoach_owner:$OWNER@db:5432/codecoach_restored"
RESTORED=$(bk -e RESTORE_DATABASE_URL -v "$WORK/identity.txt:/run/identity.txt:ro" backup \
  python -m app.cli restore-database "$NEWEST" --identity /run/identity.txt 2>&1) || { echo "FAIL: restore"; tail -5 <<<"$RESTORED"; exit 1; }
must "counts and row-level security policies match" "$RESTORED"
echo "ok: the newest backup restored into a separate database; row counts and policies match"
[ "$(dc exec -T db psql -U postgres -d codecoach_restored -tAc "SELECT count(*) FROM notes WHERE id = '$NOTE'")" = 1 ] \
  || { echo "FAIL: the saved note isn't in the restored copy"; exit 1; }
echo "ok: the saved note is in the restored copy"
for secret in "$OWNER" "$SUPER" "$APP"; do
  grep -qF "$secret" <<<"$OUT$RESTORED" && { echo "FAIL: a password in the output"; exit 1; }
done
echo "ok: no password in the backup or restore output"

step "done: removing this rehearsal's containers and its volumes (codecoach_rehearsal_pgdata, codecoach_rehearsal_backups)"
