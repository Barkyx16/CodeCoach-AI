#!/usr/bin/env bash
# Writes the two settings files the production compose needs, with every secret generated here on
# the server. Run it once, from the repository's root, before the first `docker compose up`:
#
#   deploy/setup.sh --domain demo.example.com                 # the public demo (recommended start)
#   deploy/setup.sh --domain demo.example.com --judge         # ... and judge code in gVisor sandboxes
#   deploy/setup.sh --domain app.example.com --mode full      # real accounts (needs a mail provider)
#
# It writes deploy/.env.production and deploy/.env.app (readable by you only), never prints a
# secret, and never overwrites an existing file: the database volume keeps the passwords it was
# created with, so new ones would lock the app out of its own data. docs/GO_LIVE.md walks through
# the whole launch.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: deploy/setup.sh --domain NAME [--mode demo|full] [--judge] [--no-https]

  --domain NAME   the site's address without https://, e.g. demo.example.com (its DNS A record
                  must point at this server before the certificate can be issued)
  --mode demo     (default) the public portfolio demo: guest sessions only, fictional sample
                  learners, no email and no real accounts (docs/DEMO.md)
  --mode full     real accounts with email verification: you fill in the mail provider's SMTP
                  settings in deploy/.env.app afterwards (docs/EMAIL.md)
  --judge         also run learners' code in gVisor sandboxes on this server (needs gVisor
                  installed and registered with Docker as "runsc": docs/GO_LIVE.md)
  --no-https      don't start the bundled Caddy proxy (you have your own https proxy in front of
                  127.0.0.1:3000 for the app and 127.0.0.1:8000 for /api and /health)
EOF
}

domain="" mode="demo" judge="false" https="true"
while [ $# -gt 0 ]; do
  case "$1" in
    --domain) domain="${2:-}"; shift 2 ;;
    --mode) mode="${2:-}"; shift 2 ;;
    --judge) judge="true"; shift ;;
    --no-https) https="false"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "setup: unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

fail() { echo "setup: $*" >&2; exit 1; }

[ -n "$domain" ] || { usage >&2; fail "--domain is required"; }
domain="$(printf '%s' "$domain" | tr '[:upper:]' '[:lower:]')"
case "$domain" in
  http://*|https://*) fail "--domain takes the name only, without http(s):// (e.g. demo.example.com)" ;;
esac
# A hostname: labels of letters, digits and hyphens, separated by dots. No ports, paths or spaces.
if ! printf '%s' "$domain" | grep -Eq '^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$'; then
  fail "--domain '$domain' isn't a host name (letters, digits, hyphens and dots only)"
fi
case "$mode" in demo|full) ;; *) fail "--mode is demo or full, not '$mode'" ;; esac

here="$(cd "$(dirname "$0")" && pwd)"
prod_file="$here/.env.production"
app_file="$here/.env.app"
for f in "$prod_file" "$app_file"; do
  if [ -e "$f" ]; then
    fail "$f already exists, so nothing was changed. Edit it by hand; or, only if no database was
       ever started with it, delete both files and run this again (the database volume keeps the
       passwords it was created with)."
  fi
done

command -v openssl >/dev/null || fail "openssl is needed to generate the secrets (apt-get install openssl)"
secret() { openssl rand -hex 32; }   # 64 hex characters: strong, and safe inside database URLs

site="https://$domain"
db_name="codecoach"; [ "$mode" = "demo" ] && db_name="codecoach_demo"
profiles=""
[ "$https" = "true" ] && profiles="https"
[ "$judge" = "true" ] && profiles="${profiles:+$profiles,}judge"

if [ "$judge" = "true" ] && command -v docker >/dev/null; then
  if ! docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -q '"runsc"'; then
    echo "setup: note: Docker here doesn't list the gVisor runtime \"runsc\" yet. Install it before" >&2
    echo "       starting the judge (docs/GO_LIVE.md, step 3); the runner refuses to run code without it." >&2
  fi
fi

umask 077   # both files: readable and writable by this user only

{
  echo "# Written by deploy/setup.sh on $(date -u +%Y-%m-%d). Read by docker compose (--env-file) only."
  echo "# Never commit it, paste it or send it; .gitignore excludes .env.*."
  echo "COMPOSE_PROFILES=$profiles"
  echo "POSTGRES_SUPERUSER_PASSWORD=$(secret)"
  echo "CODECOACH_OWNER_PASSWORD=$(secret)"
  echo "CODECOACH_APP_PASSWORD=$(secret)"
  echo "CODECOACH_DB=$db_name"
  echo "# The address the browser uses for the API: the site itself (the proxy routes /api and /health)."
  echo "PUBLIC_API_URL=$site"
  echo "SITE_ADDRESS=$domain"
  if [ "$judge" = "true" ]; then
    echo "# Shared by the API, the worker and the runner; the runner accepts nothing without it."
    echo "RUNNER_TOKEN=$(secret)"
  fi
} > "$prod_file"

{
  echo "# Written by deploy/setup.sh on $(date -u +%Y-%m-%d): the API's settings (migrate, api, worker, backup)."
  echo "# Never commit it, paste it or send it; .gitignore excludes .env.*. DATABASE_URL is built by the compose file."
  echo "SECRET_KEY=$(secret)"
  echo "METRICS_TOKEN=$(secret)"
  echo "APP_BASE_URL=$site"
  echo "CORS_ORIGINS=$site"
  echo "RATE_LIMIT_BACKEND=database"
  if [ "$mode" = "demo" ]; then
    cat <<'EOF'

# The public demo (docs/DEMO.md): fictional sample learners, each visitor a guest, no email.
DEMO_MODE=true
EMAIL_BACKEND=file
EMAIL_FILE_DIR=/tmp/codecoach-demo-outbox
ALLOW_GUEST_SESSIONS=true
GUEST_RETENTION_DAYS=1
GUEST_SESSIONS_PER_DAY=20
EOF
  else
    cat <<'EOF'

# Real accounts: production sends email only over SMTP with TLS. Fill these in from your mail
# provider before starting (docs/EMAIL.md); the API refuses to start until they're set.
EMAIL_BACKEND=smtp
SMTP_HOST=
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USERNAME=
SMTP_PASSWORD=
EMAIL_FROM=
EOF
  fi
  cat <<'EOF'

# The built-in coach: nothing is paid for. For Claude, set AI_PROVIDER=anthropic and
# ANTHROPIC_API_KEY here, keep the daily ceiling low, and set a limit in the provider's console too.
AI_PROVIDER=offline
AI_APP_DAILY_PAID_CALL_LIMIT=100
AI_UNVERIFIED_DAILY_REQUEST_LIMIT=10
EOF
  echo
  if [ "$judge" = "true" ]; then
    echo "# Judge code in gVisor sandboxes (the runner and worker of profile judge)."
    echo "EXECUTION_ENABLED=true"
  else
    echo "# No judge: submissions are saved and said not to be run. deploy/setup.sh --judge turns it on."
    echo "EXECUTION_ENABLED=false"
  fi
} > "$app_file"

chmod 600 "$prod_file" "$app_file"

compose="docker compose --env-file deploy/.env.production -f deploy/docker-compose.production.yml"
echo "Wrote deploy/.env.production and deploy/.env.app (readable by you only; secrets generated here, not shown)."
echo "  site:     $site"
echo "  mode:     $mode$([ "$mode" = "demo" ] && echo " (guests only, no email, database $db_name)")"
echo "  https:    $([ "$https" = "true" ] && echo "Caddy, certificate from Let's Encrypt once $domain points here" || echo "your own proxy (not started here)")"
echo "  judge:    $([ "$judge" = "true" ] && echo "on (gVisor sandboxes on this server)" || echo "off")"
echo
echo "Next:"
step=1
if [ "$mode" = "full" ]; then
  echo "  $step. Fill in SMTP_* and EMAIL_FROM in deploy/.env.app from your mail provider (docs/EMAIL.md)."; step=$((step + 1))
fi
echo "  $step. Start it:          $compose up -d --build"; step=$((step + 1))
if [ "$mode" = "demo" ]; then
  echo "  $step. Sample learners:   $compose run --rm migrate python -m app.cli demo-reset --confirm $db_name"; step=$((step + 1))
fi
echo "  $step. Check it:          $compose exec api python -m app.cli preflight"; step=$((step + 1))
echo "  $step. Open $site in a private window (docs/GO_LIVE.md, \"Check it\")."
