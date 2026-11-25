# syntax=docker/dockerfile:1
# Multi-stage build: dependencies are installed into a virtualenv in a builder stage and
# copied into a slim runtime image that runs as an unprivileged user.

FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM python:3.12-slim AS app-base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:$PATH"
RUN groupadd --system app && useradd --system --gid app --home /app app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app . .

# The scheduled backup job (compose service `backup`, docs/BACKUP.md): the same app plus pg_dump
# and age. Built only when asked for (`target: backup`); the API image below doesn't carry them.
# The client tools must be the SERVER's major version (PG_MAJOR = the compose file's postgres:16).
# Debian's own postgresql-client is a newer major: its backups of a 16 server could only be restored
# into 17 or newer, and its pg_restore can't restore into 16 (CI's rehearsal caught exactly that).
# So they come from PostgreSQL's own apt repository, pinned to that major.
FROM app-base AS backup
ARG PG_MAJOR=16
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates postgresql-common \
 && /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y \
 && apt-get install -y --no-install-recommends "postgresql-client-${PG_MAJOR}" age \
 && ln -s "/usr/lib/postgresql/${PG_MAJOR}/bin/pg_dump" "/usr/lib/postgresql/${PG_MAJOR}/bin/pg_restore" /usr/local/bin/ \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir /backups && chown app:app /backups
USER app
CMD ["python", "-m", "app.cli", "check-backups", "--dir", "/backups"]

# The API (the default target: the last stage).
FROM app-base AS runtime
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"
# Migrations run in the compose "migrate" service (or your deploy pipeline), not here.
# Worker processes: WEB_CONCURRENCY (uvicorn reads it; default 1). Size the database pool with it
# (docs/PERFORMANCE.md "Sizing"). Behind a proxy, set FORWARDED_ALLOW_IPS to its address.
# --no-access-log: uvicorn's own access log writes every visitor's IP address and full path
# (query string included) on every request. The app logs each request itself (method, route,
# status, duration, request id), without addresses or query strings (docs/PRIVACY.md).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-access-log"]
