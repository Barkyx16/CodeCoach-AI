# Running code from a Mac: the remote Linux judge

CodeCoach never runs learner code in the API process or in an ordinary container. Code runs only
in the **runner** (`runner/`), which starts each submission in a fresh Docker container under
**gVisor** (`runsc`): no network, read-only root, a non-root user, and CPU, memory, PID, time and
output limits. gVisor is a Linux technology: it does **not** run natively on macOS, and Docker
Desktop's VM doesn't provide it. So on a Mac you develop the web app and API locally and point
the API at a runner on a Linux machine you control. Don't "fix" this by running the runner with
plain `runc` on a laptop; that removes the isolation the judge depends on.

```
Mac: browser → frontend (Vite) → API + worker ──(SSH tunnel or HTTPS, bearer token)──▶ Linux: runner → gVisor
```

## What the app tells learners

`GET /api/v1/capabilities` reports `execution.state` from a real, authenticated probe of the runner
(`GET /v1/status` with the token), cached for 15 seconds:

| State | When | Workspace |
| --- | --- | --- |
| `ready` | the runner accepted the token and can start sandboxes, and the queue is moving | Run (public tests only) and Submit (all tests) |
| `unavailable` | runner unreachable, token rejected, sandbox not ready, or queued work older than `QUEUE_STALL_SECONDS` | Run paused; Submit queues and is judged when the judge is back |
| `not_configured` | `EXECUTION_ENABLED=false` | Run hidden; the button says **Save attempt** (no verdict) and offers a code review |

Outside production, `execution.setup_help` explains what to fix. Learners never see hostnames,
tokens or error details. Results show only measured times; there is no invented queue position or
progress percentage. Polling is bounded (1.5 s, then 5 s after a minute, stopping after 15
minutes with a note), a reload picks up a submission that is still queued or running, and each
submission carries a `client_request_id`, so retrying after a dropped connection can't judge twice.

## Setting up a judge for development on a Mac

You need a Linux host you're authorized to use (a cloud VM, a home server, a Linux VM with
nested virtualization that supports gVisor). Nothing in this repository provisions one.

1. **On the Linux host**: install Docker and gVisor and register the runtime
   (`/etc/docker/daemon.json`: `{"runtimes": {"runsc": {"path": "/usr/local/bin/runsc"}}}`), then:
   ```bash
   git clone <this repo> && cd CodeCoach-AI
   docker build -t codecoach-java-sandbox:21 runner/sandbox-image
   export RUNNER_TOKEN=$(openssl rand -hex 32)   # keep it; the API needs the same value
   cd runner && pip install -r requirements.txt
   RUNNER_TOKEN=$RUNNER_TOKEN uvicorn app.main:app_factory --factory --host 127.0.0.1 --port 8100
   ```
   Bind to `127.0.0.1`: the runner should never be reachable from the internet.
2. **Reach it from the Mac**, either:
   - **SSH tunnel (simplest)**: `ssh -N -L 8100:127.0.0.1:8100 you@linux-host`, then on the Mac
     `RUNNER_URL=http://localhost:8100`. Traffic is encrypted by SSH and the runner stays private.
   - **HTTPS**: put a TLS reverse proxy in front of the runner, restrict it by firewall to the
     API's address, and set `RUNNER_URL=https://judge.example.internal`. For a private CA, set
     `RUNNER_CA_BUNDLE=/path/ca.pem`; certificate verification is always on.
   The API refuses to start with a plain `http://` URL to any other host.
3. **On the Mac**, in `backend/.env`: `EXECUTION_ENABLED=true`, `RUNNER_URL=…`,
   `RUNNER_TOKEN=<same value>`; start the API and the worker (`python -m app.worker`, or
   `EMBEDDED_WORKER=true` for development).
4. **Prove it works** (a setting isn't proof):
   ```bash
   cd backend && python -m app.cli judge-check
   ```
   It calls the authenticated status endpoint, judges a known-correct solution (every public test
   must pass) and a known-wrong one (it must fail), and prints no secrets. Then open
   `/problems/two-sum`: Run and Submit appear without a warning.

## Security checklist

- The token is only in server-side environment variables; it's never sent to the browser.
- `/v1/run` and `/v1/status` require the bearer token (compared in constant time). `/health` and
  `/ready` return only `{"status": …}`.
- TLS verification is never disabled; plain HTTP is allowed only to localhost or a private
  container name (e.g. `http://runner:8100` in Docker Compose).
- Hidden test inputs are never compiled into a Run, never returned to the browser and never sent
  to an AI model; raw program output isn't returned either (learner code could print inputs).
- AI feedback never decides correctness: only the judge's comparison of outputs does.

## What was verified for this release

In an isolated Linux container with Docker and gVisor: the runner's 16 hostile-code threat-model
tests, the backend's real-judge suite (correct, wrong, non-compiling, crashing, infinite loop,
excessive output, memory exhaustion, every reference solution), `judge-check` against the real
runner (and its failure with a wrong token), and the browser journeys (Run, Submit, an infinite
loop with a reload while it was judged) in Chromium. Not verified here: Safari/WebKit (only
Chromium is installed in this environment) and a judge on a separate machine over a real SSH
tunnel or TLS proxy.
