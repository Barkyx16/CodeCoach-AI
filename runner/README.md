# CodeCoach Runner

The isolated execution service. It compiles and runs one untrusted Java submission per
request inside a fresh **gVisor** container, and returns the bounded output. It holds no
database credentials and no application secrets, only the bearer token the judge worker uses
to call it.

Design, threat model and residual risks: [docs/SECURITY.md §4](../docs/SECURITY.md#4-secure-java-execution-implemented-gvisor-sandbox).

## Requirements
- Docker with gVisor registered as the `runsc` runtime (`runsc install && systemctl restart docker`)
- The sandbox image: `docker build -t codecoach-java-sandbox:21 sandbox-image`

## Run
```bash
pip install -r requirements.txt
export RUNNER_TOKEN=$(openssl rand -hex 32)      # the API/worker must use the same value
uvicorn app.main:app_factory --factory --port 8100
```
`SANDBOX_RUNTIME=runc` (plain Docker, **not** a security boundary) is refused unless
`ALLOW_INSECURE_RUNTIME=true` is set, for local development on machines without gVisor.

## API
`POST /v1/run` (header `Authorization: Bearer <RUNNER_TOKEN>`)
```json
{"files": {"Solution.java": "…", "Main.java": "…"}, "nonce": "<16–64 hex>", "time_limit_s": 15}
```
→ `{"status": "ok|compile_error|timeout|memory_limit|output_limit|sandbox_error", "exit_code": 0,
"stdout": "…", "stderr": "…", "compile_output": null, "run_started": true, "output_truncated": false,
"duration_ms": 4012}`. Returns `503` when all `MAX_CONCURRENCY` slots are busy, so the caller retries.

`sandbox_error` means the learner's code **never started** (the entrypoint's run marker was
never printed and it wasn't a compile error, timeout, output flood or OOM kill): Docker
unreachable, image missing, a bad payload. The API treats it as infrastructure: it retries and
then reports `INTERNAL_ERROR` ("not your fault"), never a runtime error in the learner's code.

`GET /health` → `{"status": "ok"}` (liveness: the process is up).
`GET /ready` → `200 {"status": "ok"}` or `503 {"status": "unavailable"}` (readiness: the Docker
daemon answers). The image's healthcheck uses `/ready`. There are no public docs endpoints
(private service).

## Tests
```bash
pip install -r requirements-dev.txt
pytest -m "not sandbox"    # unit tests: flags, classification, auth, limits (no Docker needed)
pytest -m sandbox          # 16 threat-model checks with hostile Java in the REAL gVisor sandbox
```

## Deploying
Give the runner its **own VM** with nothing else on it: it controls the Docker daemon, which is
root-equivalent on that host. Keep only the runner's port reachable, and only from the worker.
