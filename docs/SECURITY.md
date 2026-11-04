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
| Email verification | One email with a 6-digit code and a link; code stored as HMAC with the server secret and killed after 5 wrong tries; tokens bound to the address they were sent to; changing email needs the password, resets verification and notifies the old address | `services/email_verification.py` | ✅ |
| Password reset | Same answer and timing for unknown emails (work runs after the response); single-use 30-minute hash-only tokens in a URL fragment; one email per minute; resets end every session; production requires SMTP and an https link base | `services/password_reset.py`, `services/email.py` | ✅ |
| Shared rate limits | Sliding-window counters in the database (atomic upsert), so every API replica enforces one budget; real client IPs only from trusted proxies (`FORWARDED_ALLOW_IPS`) | `services/rate_limit.py` | ✅ |
| Data retention | Inactive guest accounts are deleted with their data after `GUEST_RETENTION_DAYS` (30); guests can upgrade to keep everything | `services/retention.py` | ✅ |
| Sessions | 15-minute in-memory access tokens; rotating `HttpOnly` `SameSite=Strict` refresh cookie with reuse detection (§3) | `services/refresh.py`, `routes/auth.py` | ✅ |
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
| Prompt injection via code or problem text | Tutor role lives in the system prompt; learner code, problem text, analysis, compiler output and the failing public test are wrapped in `<learner_code>` / `<problem>` / `<analysis>` / `<compiler_output>` / `<failing_public_test>` tags and declared untrusted data. Output is constrained to a JSON schema and validated. **Model output is never executed.** |
| AI overriding correctness | The judge verdict is passed in as authoritative; responses carry a disclaimer; the API never derives pass/fail from AI output. |
| Leaking secrets to a vendor | API keys, AWS keys, GitHub tokens, private keys and `password = "…"` literals are redacted before any model call. |
| Excessive usage and cost | Per-user daily budget enforced from the database (`429`); input length cap; `effort=low`; offline provider by default. |
| Spoilers | Hint levels unlock in order, enforced server-side (`409 hint_locked`). Failure explanations are told not to write the corrected solution. |
| Hidden tests reaching the AI | Failure explanations are built from the same public-only view the learner sees (`public_result_view`): first failing **public** test, redacted compiler output, pass counts. Hidden inputs are never in the prompt. |
| Provider outage or refusal | Typed SDK errors, `refusal` and `max_tokens` stop reasons all fall back to the offline coach. |
| Data retention | Prompts (which contain code) are not stored; only the feedback shown to the user is saved, linked to the user, and deleted with them (cascade). |

Prompt-injection defenses lower the risk; they don't remove it. Because model output is only
ever *displayed* (as structured text) and never executed or used for authorization, a
successful injection can at worst produce a misleading hint for the attacker's own account.

**Text addressed to the written-answer grader (rubric v6).** The career coach grades answers
with rules, not a model, so the threat is a learner writing to the grader to inflate their own
score ("mark every point as covered"), not one account affecting another.
- *Controls:* sentences and passages addressed to the grader are left out of grading, word count
  and quotes, with a note naming them. Detection reads a folded copy (NFKC, invisible characters
  removed, Cyrillic and Greek look-alikes mapped, spaced-out letters joined) and maps positions
  back, so what is cut is an exact span of the answer. Closed markup and chat-delimiter blocks
  are cut wherever they are; an unclosed opener cuts only itself, so it can't empty the answer. In
  a run-on only the attack passage goes, never the learner's words around it.
- *Verified by:* the challenge set (45 attacks in 13 kinds, written by a separate session: 0
  credited; 27 benign controls: 0 cut), the `career.grader_boundary` gate, a deliberately
  literal boundary that fails it, appended attacks across development answers, and a
  506,971-sentence benign corpus with nothing cut (docs/AI_EVALUATION.md, "rubric v6").
- *Residual risks:* attacks nobody has written yet, in other languages or scripts the fold
  doesn't map, or in plain answer-like words, can still read as the answer. They earn credit only
  if their words show a point, and an answer that simply claims an action is credited for it
  either way: the rubric never verifies what happened. A fabricated quote dictated without
  punctuation ("evidence i escalated…") is the learner's own claim. The fold covers common
  Cyrillic and Greek look-alikes, not every confusable character.

## 3. Token storage in the browser

- **Access token** (15 min JWT): held in JavaScript memory only, never written to
  `localStorage` or `sessionStorage`. An XSS bug could use it while the page is open, but there
  is nothing durable to steal.
- **Refresh token**: an opaque 256-bit value in a cookie that is `HttpOnly` (unreadable by
  scripts), `SameSite=Strict` (never sent on cross-site requests), `Path=/api/v1/auth` (not
  sent anywhere else) and `Secure` in production (the app refuses to start with it off). Only a
  SHA-256 hash is stored server-side.
- **Rotation and reuse detection:** every refresh replaces the token. Presenting an already
  used one later means it was copied, so the whole token family is revoked. A 30-second grace
  window turns two tabs refreshing at once into a retryable `refresh_race` instead. Rotation is
  atomic (a conditional `UPDATE` claims the token, so two requests can't both rotate it), and a
  family is dead as soon as any of its tokens is revoked (a logout also locks the family's rows
  first, so it revokes a successor a concurrent refresh was issuing).
- **Lost refresh responses (bounded recovery):** a refresh can succeed on the server while its
  response never reaches the browser (a reload, a closed tab, a dropped connection), leaving the
  browser with the token the server just used. Each refresh therefore carries a random
  per-attempt key (`X-Refresh-Attempt`, 22-64 URL-safe characters) that the app keeps until it
  learns the outcome. The successor token is `HMAC(SECRET_KEY, presented token, key)`, so the
  same cookie with the same key, presented again within **2 minutes** of the rotation, gets back
  the *same* successor: never a new one, and only while that successor is unused, unrevoked and
  unexpired and the account's `token_version` is unchanged. Nothing is extended: the successor
  keeps the expiry it was issued with. Without the key, with a different key, after the window,
  or once the successor has been used, the rules above apply unchanged (race, then reuse and
  revocation). The CSRF checks below apply to every refresh, with or without a key.
  - *Where the key lives:* in the tab's `sessionStorage` (so a reload can finish the attempt)
    and, announced over a same-origin `BroadcastChannel`, in other open tabs' `sessionStorage`
    (so one tab can finish a refresh a closed tab never heard back from). Never in
    `localStorage`, never logged. The key is useless without the `HttpOnly` cookie.
  - *Trade-off:* someone who has both a copy of the cookie and the matching key, within the
    two-minute window and before the real holder uses the successor, gets that same successor
    instead of triggering the reuse alarm. They don't get a second, independent session: the
    real holder and they share one successor, and whichever uses it second triggers reuse
    detection, which revokes the family. Script running in the page (XSS) could read the key,
    but such script can already call `/auth/refresh` with the cookie directly, so the key adds
    nothing for it. Outside the window, or if no tab kept the key (for example the only tab was
    closed mid-refresh), a lost response still ends the session and the user signs in again.
- **CSRF:** cookies are only used by `/auth/refresh`, which also requires a custom
  `X-Requested-With: codecoach` header (cross-site pages can't send it without a CORS preflight
  our allowlist rejects) and refuses unknown `Origin`s. Every other endpoint uses the bearer
  header, which browsers never attach automatically.
- **Revocation:** logout, password change and account deletion bump `token_version` and revoke
  refresh tokens, ending every session.
- **Requests belong to the session they were sent in** (browser). Every sign-in and sign-out
  starts a new session generation in the API client. A 401 that comes back for a request sent
  in an earlier generation is not about the current session: it neither refreshes nor ends the
  session open now. Before this, a request that was on its way when the learner signed out could
  come back 401, refresh, and sign them back in silently (when the logout call itself had failed,
  so the cookie was still valid), and a request sent for one account could be resent with the
  token of the account that signed in next. Found as an intermittent CI failure; reproduced and
  covered by `frontend/src/test/integration/session.test.tsx`.
- **So does what they bring back** (browser, 2026-11-04). A successful response to a request sent
  with an earlier session's token is set aside (`session_changed`, logged as `stale_response`)
  instead of being returned, and every sign-in and sign-out cancels and removes all cached query
  data, not only the `me` queries. Before this, a learner's past answers to a question (cached
  under `careers/…/answers`, outside `me`) stayed in memory after they signed out and were shown
  to the next account on the same tab while its own answers loaded, and a late response for the
  first account could fill that cache after the second signed in. Reproduced and covered by
  `frontend/src/test/integration/sessionIsolation.test.tsx` (deferred responses, no sleeps), which
  also covers a query still retrying when the learner signs out (it sends nothing more; this
  already held). Limit: setting a response aside doesn't undo what the server did with it.
- **Nor what their handlers write back** (browser, 2026-11-04, Volume 4 brief 07). Two optimistic
  changes put a snapshot back when saving fails: a bookmark (the explorer's practice status and the
  bookmark list) and a card moved on the applications board. If the account changed while one was
  saving, its failure (or its set-aside success, which fails the same way) wrote the first
  account's snapshot into the cache of the account that signed in next, which then saw it until a
  refetch. Each now takes the API client's session mark (`sessionMark()`) before it starts and
  writes back only while `isSameSession()` holds. Reproduced (both outcomes, both changes) and
  covered in `sessionIsolation.test.tsx`. Every other cache write (each `setQueryData`, read one by
  one) stores the server's answer to its own request, which the client already sets aside when it
  belongs to an earlier session.
- **A sign-out the server never heard** (browser, 2026-11-04, Volume 4 brief 07). If the logout
  request failed, the learner was signed out on the page but the refresh cookie stayed valid on
  the server, so the next page load quietly signed them back in. Now the device keeps one flag (no
  account data, no token): while it is set no refresh is attempted, and each load first uses the
  cookie once to get a token for the sign-out request and sends it; a cookie that no longer works
  clears the flag, a lost connection keeps it for the next load, and a new sign-in clears it.
  Covered in `frontend/src/auth/refreshRecovery.test.tsx` (a late refresh after the failed
  sign-out, the reload, an offline reload, a 401 meanwhile, a new sign-in). Limit: another tab that
  is still signed in keeps its session until its next refresh, which the flag then refuses.
- **The session boundary, in short.** Belong to the session they were sent in, and have no effect
  on a later one: requests and their 401s (no refresh, no sign-out), responses (set aside), late
  refreshes (discarded by the provider's epoch: they can't restore a signed-out user or replace the
  account that signed in next; tested for both), queries still retrying (cancelled and removed),
  and write-backs from handlers (session mark). Concurrent refreshes in one tab share one request;
  across tabs a lock and the attempt key keep one cookie rotation (§3 above).
- **Untrusted text at the render boundary** (browser, 2026-11-04). Learner answers, the coach's
  text (built-in or Claude: feedback, quotes, notes, hints, reviews, explanations, interviewer
  messages) and API data are rendered as React text; no raw-HTML API is used anywhere
  (`dangerouslySetInnerHTML`, `innerHTML` and the like: none). Notes are Markdown through
  react-markdown with raw HTML skipped, no images and its default URL filter; problem statements
  are our own seed Markdown, also without raw HTML. **Links that come from data** (an interview
  kit's meeting link, an application's posting, content references in scenarios and lessons)
  follow the server's rule at render time too: only an absolute http(s) URL becomes a link
  (`frontend/src/lib/links.ts`), anything else is shown as text. Before this a `javascript:` link
  that reached the page (the server rejects it on save, so: an older row or a path that skipped
  the check) was rendered as a live link, and React 18 doesn't block those. Back links built
  from navigation state only point inside the app. Tests at the real pages:
  `frontend/src/test/integration/safeRendering.test.tsx` (markup in feedback, quotes and a hint
  renders literally and runs nothing; the link rule, including mixed case, `data:`,
  protocol-relative and spaced URLs). Not verified one by one: every other provider text path
  (inspected, rendered as text), admin pages, the shared-answer page, the code editor's own
  rendering, and the Content Security Policy; grader-instruction detection (the rubric) is a
  separate check and not relied on here.
- Older versions stored the access token in `localStorage`; the app deletes that key on startup.
- Remaining defences against XSS: React's output escaping, no HTML rendered from the API, and
  a strict Content-Security-Policy on the deployed frontend.

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
| Hidden test leakage | Expected outputs never enter the sandbox; raw run-phase output is never returned to users (learner code could print hidden inputs); per-test detail only for public tests; compiler output is shown with sandbox paths removed **and diagnostics about the judge driver (`Main.java`) reduced to vetted messages**, re-applied when stored output is read (see §4.5) | `test_failed_tests_reveal_public_details_only`, `test_driver_diagnostics_never_echo_test_inputs`, `test_explain_failure_on_real_judge_output` |

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
| `GET /ready` | — | Readiness probe: 503 when the Docker daemon doesn't answer (the image healthcheck uses it) |
| `WARMUP_ON_START` | `true` | Compile and run one trivial program before serving, so a slow first sandbox start isn't charged to a learner's wall-clock time limit. A failed warm-up is logged and never blocks startup |

| Variable (API/worker) | Default | Meaning |
|---|---|---|
| `EXECUTION_ENABLED` | `false` | Turn judging on (requires `RUNNER_TOKEN`) |
| `RUNNER_URL` | `http://localhost:8100` | Where the worker reaches the runner |
| `JUDGE_TIME_LIMIT_S` | `15` | Wall-clock budget per submission |
| `SUBMISSION_RATE_LIMIT_PER_MINUTE` / `MAX_PENDING_PER_USER` / `MAX_QUEUE_DEPTH` | 6 / 2 / 200 | Admission control |
| `JUDGE_MAX_ATTEMPTS` / `JUDGE_STALE_AFTER_S` | 2 / 120 | Infrastructure retry and crash recovery |
| `EMBEDDED_WORKER` | `false` | Run the worker inside the API process (dev/e2e only) |

### 4.5 Finding: compiler output leaked hidden test inputs (fixed)

Found while building "Explain my failure" (session 3). When a learner renamed the method or
changed its parameters, `javac` reported errors **in the judge's generated `Main.java`**, and
javac echoes the offending source line under each error. Those lines are test calls such as
`run(out, prefix, 4, () -> new Solution().max(new int[] {-1000000000, -999999999}))`, so the
compile output returned in `stderr_excerpt` listed **every hidden input** of the problem.

- **Fix:** `redact_driver_diagnostics` (`backend/app/services/judge/judge.py`) parses javac
  output into diagnostics. Learner (`Solution.java`) diagnostics are kept verbatim. Driver
  diagnostics keep only a message from an allowlist of patterns that can't carry literals
  (otherwise a fixed "details hidden" message) and `symbol:`/`location:`-style lines made of
  identifiers and type names; source and caret lines are dropped and duplicates collapsed.
- **Defence in depth:** it is applied when the output is stored *and* again when it's read
  (it's idempotent), so rows stored before the fix are safe without a data migration.
- **Proof:** `test_explain_failure_on_real_judge_output[find-largest-number-compile-error]`
  renames the method in the real gVisor sandbox and asserts no hidden input appears in the
  submission or the explanation. With the redaction disabled, that test fails with
  `hidden input [-1000000000, -999999999] leaked`; with it, it passes.

## 5. Known gaps (honest list)

- Unverified accounts can still use the app (verification is encouraged, not required), so an
  address isn't proven until the owner enters the code or opens the link.
- AI quality is measured only for the offline coach ([AI_EVALUATION.md](AI_EVALUATION.md)); Claude's
  numbers need an API key, so no claims are made about it.
- Code execution is off by default; deployments must opt in (`EXECUTION_ENABLED=true`) and
  run the runner on a dedicated gVisor host (see §4.3 for the residual risks).
- `npm audit` reports a moderate `minimatch` advisory inside `openapi-typescript`, a
  dev-only tool that runs on our own spec file at build time and never ships to browsers.
  Production dependencies audit clean, and CI enforces that with `npm audit --omit=dev`.

## 6. Reporting

Please report vulnerabilities privately to the repository owner rather than opening a public issue.
