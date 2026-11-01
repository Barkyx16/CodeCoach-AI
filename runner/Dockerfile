# syntax=docker/dockerfile:1
# The runner service. It starts sandbox containers through the host's Docker daemon, so it must
# be deployed on a DEDICATED host/VM that has gVisor (runsc) registered as a Docker runtime,
# never next to the database or the API. Holding the Docker socket is root-equivalent on that
# host; the isolation boundary for user code is gVisor, applied to every sandbox container.
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# Docker CLI only (the daemon runs on the host).
COPY --from=docker:27-cli /usr/local/bin/docker /usr/local/bin/docker
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
EXPOSE 8100
HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8100/health', timeout=2).status == 200 else 1)"
CMD ["uvicorn", "app.main:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8100"]
