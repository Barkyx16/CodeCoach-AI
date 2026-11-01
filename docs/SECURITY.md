# CodeCoach AI — Security

This document separates **what is implemented and tested** from **what is designed but not
built yet**. Nothing in the "designed" sections should be described as working.

## 1. Implemented controls

| Area | Control | Where | Tested |
|---|---|---|---|
| Passwords | Argon2id hashing with automatic rehash on parameter upgrade | `services/auth.py` | ✅ |
| Login enumeration | Identical error for unknown email vs. wrong password; dummy hash keeps timing similar | `routes/auth.py` | ✅ |
| Brute force | Per-IP sliding-window limit on register, login, guest and password change | `services/rate_limit.py` | ✅ |
| Tokens | HS256 JWT with `exp`, `iat`, `iss`, `typ`; `token_version` claim enables revocation | `services/auth.py`, `api/deps.py` | ✅ |
| Logout / password change | Revokes every previously issued token | `routes/auth.py` | ✅ |
| Authorization | Every user-owned query filters by `user_id`; other users' resources return 404 | routes, `CoachService` | ✅ |
| Hidden tests | Never serialized; hint text and reference solutions never leave the server | `routes/problems.py` | ✅ (checks every problem) |
| Input limits | Pydantic validation on every body and query; source-size cap; AI input cap | schemas, routes | ✅ |
| Secrets | Read from the environment only; production refuses the default `SECRET_KEY` | `config.py` | ✅ |
| CORS | Explicit origin allow-list, no credentials, explicit headers; `*` refused in production | `main.py`, `config.py` | ✅ |
| Error hygiene | Unexpected errors return a generic 500 with a request id; the stack trace only goes to logs | `errors.py` | — |
| Health endpoints | Reveal no versions or infrastructure details | `routes/health.py` | ✅ |
| Container | Non-root user, slim base image, no secrets baked in | `backend/Dockerfile` | ✅ (built and run) |
| Dependencies | Pinned versions, `pip-audit` and `npm audit --omit=dev` in CI, Dependabot for pip, npm and Actions | CI | ✅ |
| Frontend headers | CSP (`script-src 'self'`, no third-party origins, `frame-ancestors 'none'`), `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options` on every response | `frontend/nginx.conf`, `security-headers.conf` | ✅ (verified in a browser, no CSP violations) |
| XSS surface | React escapes output; Markdown is rendered without raw HTML; no `dangerouslySetInnerHTML`; no third-party scripts (Monaco is self-hosted) | `frontend/src` | — |

## 2. AI-specific safeguards

| Risk | Mitigation |
|---|---|
| Prompt injection via code or problem text | Tutor role lives in the system prompt; learner code, problem text and analysis are wrapped in `<learner_code>` / `<problem>` / `<analysis>` tags and declared untrusted data. Output is constrained to a JSON schema and validated. **Model output is never executed.** |
| AI overriding correctness | The judge verdict is passed in as authoritative; responses carry a disclaimer; the API never derives pass/fail from AI output. |
| Leaking secrets to a vendor | API keys, AWS keys, GitHub tokens, private keys and `password = "…"` literals are redacted before any model call. |
| Excessive usage and cost | Per-user daily budget enforced from the database (`429`); input length cap; `effort=low`; offline provider by default. |
| Spoilers | Hint levels unlock in order, enforced server-side (`409 hint_locked`). |
| Provider outage or refusal | Typed SDK errors, `refusal` and `max_tokens` stop reasons all fall back to the offline coach. |
| Data retention | Prompts (which contain code) are not stored; only the feedback shown to the user is saved, linked to the user, and deleted with them (cascade). |

Prompt-injection defenses lower the risk; they don't remove it. Because model output is only
ever *displayed* (as structured text) and never executed or used for authorization, a
successful injection can at worst produce a misleading hint for the attacker's own account.

## 3. Token storage in the browser

The API uses bearer tokens rather than cookies (no CSRF surface). The frontend keeps the token
in memory and mirrors it to `localStorage` so a page refresh doesn't log the user out. The
trade-off: an XSS bug could read it. Mitigations are short token lifetimes, server-side
revocation, React's default output escaping, rendering no HTML from the API, and a strict
Content-Security-Policy on the deployed frontend. A future hardening step is moving to an
`HttpOnly`, `SameSite=Strict` refresh-token cookie with in-memory access tokens.

## 4. Secure Java execution (implemented: gVisor sandbox)

> **Status:** implemented, approved design (gVisor). Every control below is exercised by an
> automated test that runs hostile Java inside the **real** sandbox (`runner/tests/test_threat_model.py`,
> 16 checks) and by real end-to-end judging (`backend/tests/test_judge_sandbox.py`,
> `frontend/e2e/judge.spec.ts`). CI installs a pinned, checksum-verified gVisor release to run
> them. `EXECUTION_ENABLED` stays `false` by default, so deployments opt in explicitly.

### 4.1 Architecture

```
Browser ──POST /submissions──▶ API ──(row: QUEUED)──▶ PostgreSQL
                                 ▲                       │ FOR UPDATE SKIP LOCKED
                                 │ poll GET /submissions │
                                 │                 ┌─────▼─────┐   POST /v1/run (bearer token)   ┌──────────────┐
                                 └── verdict ──────│  worker   │────────────────────────────────▶│   runner     │
                                                   │ (judging) │◀── stdout (nonce-tagged lines) ──│ (no DB creds)│
                                                   └───────────┘                                  └──────┬───────┘
                                                   compares outputs here:                    docker run --runtime=runsc
                                                   expected outputs never                     (one fresh container per run)
                                                   enter the sandbox                                     │
                                                                                         ┌───────────────▼──────────────┐
                                                                                         │ gVisor sandbox                 │
                                                                                         │ javac + java, user "nobody"    │
                                                                                         └────────────────────────────────┘
```

- **API process:** never executes code. It validates the submission, applies admission
  control, and stores it as `QUEUED`.
- **Worker** (`python -m app.worker`, its own process or container): claims jobs with
  `FOR UPDATE SKIP LOCKED`, generates the test driver, sends `Solution.java` + `Main.java` and a
  random nonce to the runner, judges the output, and stores the verdict. It retries only
  infrastructure failures, at most `JUDGE_MAX_ATTEMPTS` times, and recovers jobs from a crashed
  worker after `JUDGE_STALE_AFTER_S`.
- **Runner** (`runner/`, its own service): holds **no database credentials or app secrets**,
  only its bearer token. It starts one fresh sandbox per run, with bounded concurrency
  (`MAX_CONCURRENCY`; 503 when full, so the worker retries instead of the runner queueing).
  Because it controls Docker, it belongs on a **dedicated VM**, never next to the database.

### 4.2 Threat model and controls (all tested in the real sandbox)

| Threat | Control | Test |
|---|---|---|
| Kernel / container escape | gVisor (`--runtime=runsc`): syscalls hit a user-space kernel, not the host's. The runner **refuses to start** with plain `runc` unless `ALLOW_INSECURE_RUNTIME=true` is set for local development | `test_runs_inside_gvisor_as_nobody`, `test_runc_is_refused_unless_explicitly_allowed` |
| Infinite loops | Wall-clock limit; the container is killed with `docker kill` | `test_infinite_loop_hits_wall_clock_limit` |
| Memory exhaustion | `--memory` = `--memory-swap` (no swap), `-Xmx`, `ExitOnOutOfMemoryError` | `test_memory_bomb_is_stopped` |
| Fork bombs | `--pids-limit=64` | `test_fork_bomb_is_contained_by_pid_limit` |
| Network abuse / exfiltration | `--network=none`: no interface, no DNS | `test_no_network_access`, `test_no_dns` |
| Tampering with the image | `--read-only` root filesystem | `test_root_filesystem_is_read_only` |
| Dropping and running binaries | `/tmp` tmpfs with `noexec,nosuid,nodev` | `test_tmp_is_noexec` |
| Disk filling | tmpfs size cap + `--ulimit fsize` | `test_tmp_is_size_capped` |
| Reading host files | **No bind mounts**: source arrives over stdin as a base64 tar; a host canary file is invisible; no Docker socket inside | `test_host_files_are_not_visible` |
| Privilege escalation | `--user 65534:65534`, `--cap-drop=ALL`, `--security-opt=no-new-privileges` | command-flag unit test |
| Secret theft | Sandbox environment has no secrets; the runner holds no DB credentials | `test_no_secrets_in_environment` |
| Output floods | stdout/stderr capped (64 KB); the run is killed on overflow; `--log-driver=none` | `test_output_flood_is_truncated_and_stopped` |
| Cross-run leakage | `--rm`, a fresh container per run; stale containers removed at startup | `test_each_run_starts_from_a_clean_sandbox` |
| Abusive traffic | Auth required; per-user rate limit and pending-job cap; global queue-depth limit (503) | `backend/tests/test_judge.py` |
| Forged results | Per-run nonce read from stdin **before** learner code runs (not in env/argv); results written through a captured stream; first report per test wins | `test_nonce_is_not_in_env_or_argv`, `test_forgery_attempt_from_inside_the_sandbox`, JVM forgery test |
| Hidden test leakage | Expected outputs never enter the sandbox; raw run-phase output is never returned to users (learner code could print hidden inputs); per-test detail only for public tests; compiler output is shown with sandbox paths removed | `test_failed_tests_reveal_public_details_only` |

### 4.3 Residual risks (honest)

- **Same-JVM tampering:** learner code shares a JVM with the driver, so deep reflection could,
  in principle, alter the *learner's own* verdict. It can't affect other users or the host.
  The fix would be a separate process per test, at a large performance cost.
- **Hidden inputs are readable inside the sandbox** (they're compiled into `Main.class`), but
  nothing printed is returned to the user, so they can't be extracted through the API.
- **The runner holds the Docker socket**, which is root-equivalent on its host. That's why the
  runner must run on its own VM with nothing else on it.
- **Peak memory isn't measured yet**, so `memory_kb` stays `null` rather than showing an invented number.
- gVisor reduces kernel attack surface dramatically, but no sandbox is perfect. Keep the gVisor
  release current (it's pinned in CI and Dependabot watches the sandbox image).

### 4.4 Configuration

| Variable (runner) | Default | Meaning |
|---|---|---|
| `RUNNER_TOKEN` | — | Required shared secret (≥ 32 chars); must match the API/worker |
| `SANDBOX_RUNTIME` | `runsc` | gVisor. `runc` is refused unless `ALLOW_INSECURE_RUNTIME=true` |
| `SANDBOX_IMAGE` | `codecoach-java-sandbox:21` | Built from `runner/sandbox-image` |
| `MAX_CONCURRENCY` | `2` | Parallel sandboxes; excess requests get 503 |
| `WALL_TIMEOUT_S`, `MEMORY_MB`, `HEAP_MB`, `PIDS_LIMIT`, `CPUS`, `TMPFS_MB`, `OUTPUT_LIMIT_BYTES` | 20 s, 512, 192, 64, 1, 64, 64 KB | Hard ceilings (requests may only ask for less) |

| Variable (API/worker) | Default | Meaning |
|---|---|---|
| `EXECUTION_ENABLED` | `false` | Turn judging on (requires `RUNNER_TOKEN`) |
| `RUNNER_URL` | `http://localhost:8100` | Where the worker reaches the runner |
| `JUDGE_TIME_LIMIT_S` | `15` | Wall-clock budget per submission |
| `SUBMISSION_RATE_LIMIT_PER_MINUTE` / `MAX_PENDING_PER_USER` / `MAX_QUEUE_DEPTH` | 6 / 2 / 200 | Admission control |
| `JUDGE_MAX_ATTEMPTS` / `JUDGE_STALE_AFTER_S` | 2 / 120 | Infrastructure retry and crash recovery |
| `EMBEDDED_WORKER` | `false` | Run the worker inside the API process (dev/e2e only) |

## 5. Known gaps (honest list)

- No refresh tokens yet; access tokens last 60 minutes.
- The auth rate limiter is per process (move to Redis for multiple replicas).
- No email verification or password reset (needs an email provider).
- No account deletion endpoint yet (the database cascades are ready).
- The AI evaluation suite (30+ labeled samples, spoiler and hallucination rates) is not built,
  so no AI accuracy claims are made anywhere.
- Code execution is off by default; deployments must opt in (`EXECUTION_ENABLED=true`) and
  run the runner on a dedicated gVisor host (see §4.3 for the residual risks).
- `npm audit` reports a moderate `minimatch` advisory inside `openapi-typescript`, a
  dev-only tool that runs on our own spec file at build time and never ships to browsers.
  Production dependencies audit clean, and CI enforces that with `npm audit --omit=dev`.

## 6. Reporting

Please report vulnerabilities privately to the repository owner rather than opening a public issue.
