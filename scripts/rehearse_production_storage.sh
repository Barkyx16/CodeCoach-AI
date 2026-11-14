#!/usr/bin/env bash
# Rehearse deploy/docker-compose.production.yml on this machine, with throwaway passwords and
# synthetic data. It's a rehearsal, not a deployment: nothing is published, no DNS changes, and
# no email can leave (the SMTP host is under .invalid, which never resolves).
#
#   scripts/rehearse_production_storage.sh
#   IMAGE=codecoach-api:rehearsal scripts/rehearse_production_storage.sh   # use a prebuilt API image
#   FORWARDED_ALLOW_IPS=127.0.0.1 ...       # override the compose default (shows the shared-limit defect)
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
#      owner, prunes and checks; a run that can't encrypt fails. The API can't see the backups. The
#      newest restores into a separate database with a key the server never holds; the app then runs
#      on that copy as its app role (sign-in, own notes only); a damaged backup is refused.
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
${FORWARDED_ALLOW_IPS:+FORWARDED_ALLOW_IPS=$FORWARDED_ALLOW_IPS}
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

cleanup() { docker stop codecoach_rehearsal_restored_api >/dev/null 2>&1 || true; dc --profile backup down -v --remove-orphans >/dev/null 2>&1 || true; }   # this rehearsal's project and volumes only
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
# or every visitor shares the gateway's address and its sign-in rate limit. The proof is the
# effect: separate limits for separate visitors (below). The API logs no visitor addresses at all.
# The effect on real limits (synthetic documentation addresses, never a real service): one visitor
# who uses up the sign-in limit (AUTH_RATE_LIMIT_PER_MINUTE=100 here) gets 429 with Retry-After,
# while a second visitor still gets through.
login_as() {  # $1 = forwarded address, $2 = email; prints the status code
  curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:$PORT/api/v1/auth/login" -H "X-Forwarded-For: $1" \
    -H 'Content-Type: application/json' -d "{\"email\":\"$2\",\"password\":\"wrong-password\"}"
}
# The limit is a sliding-window estimate: the previous minute's count is weighed by how much of it
# is still inside the last 60 s. A burst that straddles a minute boundary is estimated a little
# low, so the refusal can come a few attempts after the 100th (CI run 276 met that at 03:32:00).
# So: the first 100 must all be let through (the limit isn't lower), and a 429 must come within
# the next 10 (it holds).
for i in $(seq 1 100); do
  [ "$(login_as 203.0.113.10 "visitor-a-$i@example.com")" = 401 ] || { echo "FAIL: visitor A was limited before 100 attempts ($i)"; exit 1; }
done
limited=""
for i in $(seq 1 10); do [ "$(login_as 203.0.113.10 "visitor-a-x$i@example.com")" = 429 ] && { limited=1; break; }; done
[ -n "$limited" ] || { echo "FAIL: visitor A wasn't limited"; exit 1; }
curl -s -D - -o /dev/null -X POST "http://127.0.0.1:$PORT/api/v1/auth/login" -H 'X-Forwarded-For: 203.0.113.10' \
  -H 'Content-Type: application/json' -d '{"email":"a@example.com","password":"x"}' | grep -qi '^retry-after:' \
  || { echo "FAIL: the 429 has no Retry-After"; exit 1; }
[ "$(login_as 203.0.113.11 visitor-b@example.com)" = 401 ] || { echo "FAIL: visitor B shared visitor A's limit"; exit 1; }
echo "ok: visitor A is limited (429, Retry-After) while visitor B still signs in normally: separate limits"
# And the per-account limit still holds across addresses: 20 wrong passwords for one account, each
# from a different address, pause sign-in to that account for the 21st address too.
for i in $(seq 1 20); do login_as "198.51.100.$i" throttled@example.com >/dev/null; done
[ "$(login_as 198.51.100.99 throttled@example.com)" = 429 ] || { echo "FAIL: the per-account limit didn't hold across addresses"; exit 1; }
echo "ok: the per-account limit holds no matter how many addresses the attempts come from"
if dc logs api 2>/dev/null | grep -qE '203\.0\.113\.|198\.51\.100\.'; then
  echo "FAIL: a visitor's address is in the API's logs"; exit 1
fi
echo "ok: none of those visitors' addresses is in the API's logs"

step "3. save work, then restart and recreate"
TOKEN=$(curl -s -X POST "http://127.0.0.1:$PORT/api/v1/auth/register" -H 'Content-Type: application/json' \
  -d '{"email":"rehearsal@example.com","password":"CorrectHorse42","display_name":"Rehearsal"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
NOTE=$(curl -s -X POST "http://127.0.0.1:$PORT/api/v1/me/notes" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"title":"Survives restarts","body":"synthetic"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
echo "saved note $NOTE"
# A second account with its own note: after a restore, each must still see only its own.
TOKEN_B=$(curl -s -X POST "http://127.0.0.1:$PORT/api/v1/auth/register" -H 'Content-Type: application/json' \
  -d '{"email":"rehearsal-b@example.com","password":"CorrectHorse42","display_name":"Rehearsal B"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
NOTE_B=$(curl -s -X POST "http://127.0.0.1:$PORT/api/v1/me/notes" -H "Authorization: Bearer $TOKEN_B" -H 'Content-Type: application/json' \
  -d '{"title":"B only","body":"synthetic"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
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
# The compatibility matrix, from the tools themselves (no credentials in any of it).
echo "versions: server $(dc exec -T db psql -U postgres -tAc 'SHOW server_version' | tr -d '\r') ·" \
  "$(bk --no-deps --entrypoint sh backup -c 'pg_dump --version; pg_restore --version; printf "age "; age --version' 2>/dev/null | tr '\n' ' ')"
# A failing job must fail the run, not report success: here, no usable public key.
cp "$WORK/recipients.txt" "$WORK/recipients.good"; : >"$WORK/recipients.txt"
if bk backup >/dev/null 2>&1; then echo "FAIL: the backup job exited 0 without a usable key"; exit 1; fi
cp "$WORK/recipients.good" "$WORK/recipients.txt"
echo "ok: a backup job that can't encrypt exits non-zero (the scheduler's alert fires)"
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
# The signup emails couldn't go out here (the SMTP host never resolves), so the backup holds them
# unsent. On the copy they must be held, not queued: the restored API would send them at once.
outbox_of() { dc exec -T db psql -U postgres -d "$1" -tAc "SELECT coalesce(string_agg(status || '=' || n || ' (attempts ' || tries || ')', ', '), 'empty') FROM (SELECT status, count(*) n, sum(attempts) tries FROM email_jobs GROUP BY status ORDER BY status) s" | tr -d '\r'; }
must "unsent at backup time are held" "$RESTORED"
HELD_AT_RESTORE=$(outbox_of codecoach_restored)
grep -q 'held=' <<<"$HELD_AT_RESTORE" && ! grep -qE '(pending|sending)=' <<<"$HELD_AT_RESTORE" \
  || { echo "FAIL: the unsent emails on the restored copy aren't held: $HELD_AT_RESTORE"; exit 1; }
echo "ok: the emails unsent at backup time are held on the copy, not queued: $HELD_AT_RESTORE"
[ "$(dc exec -T db psql -U postgres -d codecoach_restored -tAc "SELECT count(*) FROM notes WHERE id = '$NOTE'")" = 1 ] \
  || { echo "FAIL: the saved note isn't in the restored copy"; exit 1; }
echo "ok: the saved note is in the restored copy"
OUT_CHECK=$(bk backup python -m app.cli check-backups --dir /backups 2>&1) || { echo "FAIL: check-backups after the restore"; echo "$OUT_CHECK"; exit 1; }
must "restore rehearsal: 0 days ago" "$OUT_CHECK"
echo "ok: check-backups now reports when recovery was last rehearsed"

# The app itself on the restored copy, as its least-privilege role: sign-in, data, isolation.
RPORT=$((PORT + 1))
export DATABASE_URL="postgresql+psycopg://codecoach_app:$APP@db:5432/codecoach_restored"
dc run -d --rm --no-deps --name codecoach_rehearsal_restored_api -p "127.0.0.1:$RPORT:8000" -e DATABASE_URL api >/dev/null 2>&1
unset DATABASE_URL
for _ in $(seq 1 60); do [ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$RPORT/health/ready")" = 200 ] && break; sleep 1; done
[ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$RPORT/health/ready")" = 200 ] || { echo "FAIL: the API on the restored copy isn't ready"; docker logs codecoach_rehearsal_restored_api 2>&1 | tail -5; exit 1; }
docker exec codecoach_rehearsal_restored_api python -m app.cli check-rls --strict >/dev/null || { echo "FAIL: check-rls --strict on the restored copy"; exit 1; }
T_A=$(curl -s -X POST "http://127.0.0.1:$RPORT/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"rehearsal@example.com","password":"CorrectHorse42"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
LIST_A=$(curl -s "http://127.0.0.1:$RPORT/api/v1/me/notes" -H "Authorization: Bearer $T_A")
grep -q "$NOTE" <<<"$LIST_A" && ! grep -q "$NOTE_B" <<<"$LIST_A" || { echo "FAIL: account A's notes on the restored copy"; exit 1; }
[ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$RPORT/api/v1/me/notes/$NOTE_B" -H "Authorization: Bearer $T_A")" = 404 ] \
  || { echo "FAIL: account A can reach B's note on the restored copy"; exit 1; }
echo "ok: the app runs on the restored copy as its app role: check-rls --strict, sign-in, own notes only, B's note 404"
# Its email loop runs every 5 s: give it more than one pass, then nothing held may have moved.
sleep 7
[ "$(outbox_of codecoach_restored)" = "$HELD_AT_RESTORE" ] \
  || { echo "FAIL: the restored API touched held emails: $(outbox_of codecoach_restored), was $HELD_AT_RESTORE"; exit 1; }
echo "ok: after the restored API ran its email loop, the held emails are untouched (no attempt made)"
# The operator's view and decision, inside the API image as the app role: the domain, never the address.
q() { docker exec codecoach_rehearsal_restored_api python -m app.cli email-quarantine "$@" 2>&1; }
LISTING=$(q) || { echo "FAIL: email-quarantine"; echo "$LISTING"; exit 1; }
must "email(s) held" "$LISTING"; must "@example.com" "$LISTING"
if grep -q "rehearsal@\|rehearsal-b@" <<<"$LISTING"; then echo "FAIL: email-quarantine shows a full address"; exit 1; fi
must "held by a rehearsal" "$LISTING"
# A rehearsal's copy holds real people's addresses: releasing them over SMTP is refused.
if REFUSED=$(q --release --kind verify_email --apply); then echo "FAIL: a rehearsal's held emails were released over SMTP"; exit 1; fi
must "Not released" "$REFUSED"
must "Would suppress" "$(q --suppress --kind verify_email)"
[ "$(outbox_of codecoach_restored)" = "$HELD_AT_RESTORE" ] || { echo "FAIL: a refusal or a dry run changed the outbox"; exit 1; }
echo "ok: releasing a rehearsal's held emails over SMTP is refused (exit 1); the outbox is unchanged"
must "Suppressed" "$(q --suppress --kind verify_email --apply)"
AFTER=$(outbox_of codecoach_restored)
grep -q 'dropped=' <<<"$AFTER" && ! grep -q 'held=' <<<"$AFTER" || { echo "FAIL: suppressing left: $AFTER"; exit 1; }
echo "ok: email-quarantine lists them by domain only, a dry run changes nothing, suppress finishes them: $AFTER"
docker stop codecoach_rehearsal_restored_api >/dev/null 2>&1 || true

# A damaged backup is refused before anything is written.
# One byte is flipped (XOR), so the copy always differs. Writing a fixed character there used to
# leave the file unchanged whenever that byte already was the character (1 in 64: the age
# header there is base64), and CI run 239 "restored a damaged backup" that wasn't damaged.
bk --no-deps --entrypoint sh backup -c "cp '$NEWEST' /backups/codecoach-damaged.dump.age && cp '${NEWEST%.dump.age}.manifest.json' /backups/codecoach-damaged.manifest.json && python -c \"p = '/backups/codecoach-damaged.dump.age'; b = bytearray(open(p, 'rb').read()); b[100] ^= 0xFF; open(p, 'wb').write(b)\" && ! cmp -s '$NEWEST' /backups/codecoach-damaged.dump.age" 2>/dev/null \
  || { echo "FAIL: couldn't make a damaged copy that differs from the backup"; exit 1; }
dc exec -T db createdb -U postgres -O codecoach_owner codecoach_restored_twice
export RESTORE_DATABASE_URL="postgresql+psycopg://codecoach_owner:$OWNER@db:5432/codecoach_restored_twice"
if DAMAGED=$(bk -e RESTORE_DATABASE_URL -v "$WORK/identity.txt:/run/identity.txt:ro" backup \
  python -m app.cli restore-database /backups/codecoach-damaged.dump.age --identity /run/identity.txt 2>&1); then
  echo "FAIL: a damaged backup restored"; exit 1
fi
must "damaged or incomplete" "$DAMAGED"
[ "$(dc exec -T db psql -U postgres -d codecoach_restored_twice -tAc "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'" | tr -d '\r')" = 0 ] \
  || { echo "FAIL: the refused restore wrote something"; exit 1; }
echo "ok: a damaged backup is refused, and its target stays empty"
for secret in "$OWNER" "$SUPER" "$APP"; do
  grep -qF "$secret" <<<"$OUT$RESTORED$OUT_CHECK$DAMAGED" && { echo "FAIL: a password in the output"; exit 1; }
done
grep -q "AGE-SECRET-KEY" <<<"$OUT$RESTORED$OUT_CHECK$DAMAGED" && { echo "FAIL: the private key in the output"; exit 1; }
echo "ok: no password in the backup or restore output"

step "done: removing this rehearsal's containers and its volumes (codecoach_rehearsal_pgdata, codecoach_rehearsal_backups)"
