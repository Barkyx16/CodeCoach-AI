#!/bin/sh
# Runs once, when the PostgreSQL container starts on an EMPTY data volume (the official image runs
# every script in /docker-entrypoint-initdb.d then, and never again). It never deletes anything.
#
# Makes two ordinary roles (no superuser, no BYPASSRLS, can't create roles or databases):
#   owner: owns the database's schema and, after migrations, every table. Used only by the
#          one-shot migrate job (alembic, seed, grant-app-role).
#   app:   what the API uses. Gets row access from `python -m app.cli grant-app-role`, owns nothing,
#          so row-level security applies to it and it can't alter or drop tables.
# Passwords come from the environment (deploy/production.env.example names them); none is stored here.
set -eu
: "${CODECOACH_OWNER_PASSWORD:?set CODECOACH_OWNER_PASSWORD}"
: "${CODECOACH_APP_PASSWORD:?set CODECOACH_APP_PASSWORD}"
OWNER_ROLE="${CODECOACH_OWNER_ROLE:-codecoach_owner}"
APP_ROLE="${CODECOACH_APP_ROLE:-codecoach_app}"

psql -v ON_ERROR_STOP=1 --no-psqlrc --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v db="$POSTGRES_DB" -v owner="$OWNER_ROLE" -v app="$APP_ROLE" \
  -v owner_pw="$CODECOACH_OWNER_PASSWORD" -v app_pw="$CODECOACH_APP_PASSWORD" <<'SQL'
CREATE ROLE :"owner" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD :'owner_pw';
CREATE ROLE :"app" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD :'app_pw';
ALTER DATABASE :"db" OWNER TO :"owner";
ALTER SCHEMA public OWNER TO :"owner";
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO :"app";
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO :"app";
SQL
echo "codecoach: created roles $OWNER_ROLE (owner) and $APP_ROLE (app) in $POSTGRES_DB"
