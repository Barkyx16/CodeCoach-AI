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

## 4. Secure Java execution: design (NOT YET BUILT, needs approval)

> **Status:** `EXECUTION_ENABLED=false`. Submitted code is stored but **never executed**
> anywhere: not on the API server, not in CI. The only Java this project runs is its own
> trusted reference solutions, in a developer/CI script.

### 4.1 Threat model
Treat every submission as hostile. An attacker controls the Java source and can try to:

| Threat | Example | Required control |
|---|---|---|
| Resource exhaustion | `while(true){}`, allocation bombs, fork via `ProcessBuilder` | Hard CPU-time and wall-clock limits; memory cgroup; pids limit; bounded queue |
| Host filesystem access | Read `/etc`, env files, other submissions | No host mounts; ephemeral rootfs; read-only base; separate empty workdir |
| Network abuse | Exfiltration, scanning, crypto mining pools | No network namespace or interface at all |
| Sandbox escape | Kernel exploit from inside a container | A real isolation boundary: gVisor (user-space kernel) or a Firecracker microVM, plus seccomp, non-root, dropped capabilities |
| Output floods | Printing gigabytes | Cap stdout/stderr bytes; truncate; redact |
| Result forgery | Printing fake `@@CC_RESULT@@` lines | Per-run random nonce in the result prefix, unknown to user code; driver and solution compiled separately; first result per index wins |
| Judge data theft | Reading hidden tests from disk | Hidden expected outputs never enter the sandbox: the driver prints actual outputs only, and comparison happens outside |
| Abuse at scale | Thousands of submissions | Auth required, per-user quotas, queue depth limits, monitoring |

### 4.2 Proposed architecture
```
API ──enqueue(job id)──▶ queue (Redis / Postgres SKIP LOCKED)
                              │
                     ┌────────▼─────────┐    separate host or VM pool, no DB credentials,
                     │  runner service  │    no secrets; only "fetch job, post result"
                     └────────┬─────────┘
                              │ per job: fresh sandbox
                 ┌────────────▼─────────────────────────────────────┐
                 │ gVisor (runsc) container  OR  Firecracker microVM │
                 │  · JDK only, read-only image, non-root uid       │
                 │  · --network=none, tmpfs workdir (size-limited)  │
                 │  · cgroups: 1 CPU, 256–512 MB RAM, pids ≤ 64     │
                 │  · seccomp profile, no capabilities              │
                 │  · javac (time-limited) → java -Xmx… (time-limited)│
                 │  · stdout/stderr capped at e.g. 64 KB            │
                 └───────────────────────────────────────────────────┘
                              │ bounded stdout
                     harness.judge_cases()  (outside the sandbox)
                              │
                     POST result → API → ExecutionResult + status
```
Already built and tested toward this: the test-driver generator and result comparison
(`services/judge/harness.py`), the `ExecutionBackend` interface, the status model, the
`ExecutionResult` table, and public-only result serialization.

### 4.3 Options to choose from

| Option | Isolation | Effort | Notes |
|---|---|---|---|
| **A. Managed judge (e.g. Judge0 hosted)** | Vendor's | Low | Fastest path to a working judge; data leaves our system; per-call cost |
| **B. gVisor (`runsc`) containers on a dedicated VM** | Strong (user-space kernel) | Medium | Recommended. Well-documented, used by Google for untrusted workloads |
| **C. Firecracker microVMs** | Strongest (hardware virtualization) | High | Best isolation; more infrastructure work |
| ~~Plain Docker on the API host~~ | Insufficient | — | Rejected: shared kernel, and the blueprint forbids it |

**Recommendation:** Option B for the portfolio build, keeping the runner behind the existing
`ExecutionBackend` interface so A or C can be swapped in. **Implementation starts only after
this design is approved.**

## 5. Known gaps (honest list)

- No refresh tokens yet; access tokens last 60 minutes.
- The auth rate limiter is per process (move to Redis for multiple replicas).
- No email verification or password reset (needs an email provider).
- No account deletion endpoint yet (the database cascades are ready).
- The AI evaluation suite (30+ labeled samples, spoiler and hallucination rates) is not built,
  so no AI accuracy claims are made anywhere.
- Code execution is disabled (see §4).
- `npm audit` reports a moderate `minimatch` advisory inside `openapi-typescript`, a
  dev-only tool that runs on our own spec file at build time and never ships to browsers.
  Production dependencies audit clean, and CI enforces that with `npm audit --omit=dev`.

## 6. Reporting

Please report vulnerabilities privately to the repository owner rather than opening a public issue.
