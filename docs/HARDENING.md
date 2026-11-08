# Production hardening (seven requested items)

Requested on 2026-11-06:

1. rate limiting;
2. row-level database security;
3. request caching;
4. asynchronous jobs;
5. pre-launch load testing;
6. a professional authentication provider;
7. secure secret management.

The approach was to inventory what already existed for each, then build only the gaps that
could be demonstrated. Branch `claude/gallant-galileo-hapob6`, starting at `e684896`.

## Summary

| # | Item | State | What changed (evidence in the sections below) |
|---|---|---|---|
| 1 | Rate limiting | Done | `Retry-After` on every 429. New limits on resend, refresh, wrong passwords per account, export, restore, and saving submissions with execution off. IPv6 keyed by /64. Memory and counter-table growth fixed. AI budget exact under concurrency. A slow provider capped |
| 2 | Row-level security | Done (PostgreSQL) | RLS policies on 30 learner-owned tables, enforced in CI. Route-table access tests. `/metrics` token. One owner check fixed |
| 3 | Caching | Done | Public catalogue cached in process (60 s, keyed to published content) and by browsers (ETag/304). Everything else `no-store` |
| 4 | Async jobs | Done | Durable email outbox with retries. Housekeeping runs without the judge. AI calls can't hold every connection |
| 5 | Load testing | Done | Shipped config measured: catalogue, sign-in capacity, sign-in flood, slow-AI breaking point (found, then fixed). Sizing guide |
| 6 | Auth provider (Clerk/Firebase) | **Your decision, not done** | Not switched: it needs an external account, keys, possibly cost, and migrating existing accounts. The current auth's documented gaps were fixed instead. See below |
| 7 | Secret management | Done | Secrets never printed. Stronger production checks. Key rotation. CI secret scan. Frontend build guard |

## What the inventory found

What already existed:
- database-backed, shared rate limits on sign-in and most writes;
- ownership checks in every service, plus about 30 cross-account tests;
- a database-queue judge worker;
- earlier load-test scripts and results;
- custom auth on Argon2id, with rotating refresh tokens and reuse detection;
- secrets read from the environment.

The gaps that were real (each was reproduced or verified before it was fixed):
- **Secrets:** a failed settings check at startup printed the whole input, including the API key.
- **Secrets:** production accepted `SECRET_KEY='a'*32`, the example database password and
  `AUTO_MIGRATE=true`.
- **Config:** `cp .env.example .env` didn't start.
- **Rate limits:** the in-memory limiter never freed a key (25,000 keys gave 25,000 entries), and
  counter rows grew without bound.
- **Rate limits:** resend and refresh had no limit, and there was no per-account limit on wrong
  passwords.
- **Rate limits:** saving submissions with execution off had no limit at all.
- **Frontend:** a 429 or 5xx on refresh signed the user out.
- **Housekeeping:** guest retention ran only when the code judge was enabled, and emails sent
  after the response were lost on a crash or SMTP error.
- **Load:** a slow AI provider could hold every database connection (measured below).
- **Docs:** they didn't match the code on CORS credentials and on what logout revokes.

## 1. Rate limiting

| Change | Where | Test |
|---|---|---|
| `Retry-After` header (and `retry_after_seconds` in the body, whole seconds) on every 429 | `errors.py` (`RateLimitedError.wait`) | `test_rate_limit_hardening.py` |
| Resend verification limited per address. Refresh gets its own bucket (60/min) | `routes/auth.py` | same |
| Wrong passwords per account, from any address: 20 per 15 min (`LOGIN_FAILURES_PER_ACCOUNT`). The key is hashed, unknown addresses are counted the same, and only failures count | `routes/auth.py` | same |
| Exports and restores per user per hour (20) | `routes/me.py`, `routes/restore.py` | same |
| Saving submissions when execution is off: the same per-minute limit as judged ones | `judge/backends.py` | same |
| IPv6 clients keyed by /64. IPv4-mapped addresses unwrapped | `rate_limit.client_key` | same |
| The in-memory limiter evicts idle keys | `SlidingWindowLimiter._evict` | same |
| Counter rows carry an expiry and are purged by housekeeping (migration `9152380226e0`) | `rate_limit.purge_expired` | same |
| AI: one request per user in flight (PostgreSQL advisory lock), so the daily budget is exact. The budget 429 says when a request frees up | `ai/service.py` | same (PostgreSQL) |
| AI: at most `AI_MAX_CONCURRENT_CALLS` (8) paid-provider calls per process; when they're busy, the offline coach answers at once | `ai/bounded.py` | same; load test |
| Frontend: only a 401/403 from refresh ends the session; a 429/5xx is "try again later" | `AuthProvider.tsx` | `session.test.tsx` (the 3 new cases fail without the fix) |

## 2. Data isolation and row-level security

- **Policies.** PostgreSQL RLS with a `codecoach_owner_only` policy is enabled and FORCEd on
  30 tables (migration `248721f0fcb1`). Each table's `user_id` must equal the transaction's
  `codecoach.user_id` setting.
- **Where the setting comes from.** Authenticated requests set it per transaction
  (`db/rls.bind_user`, called from `api/deps.get_optional_user`).
- **No user, no rows, for requests and the worker** (since migration `7c1d2e3f4a5b`). A
  signed-out request and the background worker see nothing until a user is bound. One named
  maintenance step may read across learners, read-only. Operator commands and migrations are
  unrestricted. Writes are checked too (`WITH CHECK`). Runtime behaviour, pooled connections and
  the worker model: [ROW_LEVEL_SECURITY.md](ROW_LEVEL_SECURITY.md).
- **Proof:** with the notes service's owner check deliberately removed, another account still
  gets 404 (`test_a_route_that_forgot_its_owner_check_still_leaks_nothing`). The same test
  without the RLS context returns 200: the leak RLS exists for.
- **The full PostgreSQL suite runs with RLS enforced.** Locally the role is ordinary. In CI a new
  step creates an ordinary role, because the Docker image's default user is a superuser and would
  bypass RLS.
- **Route-table tests** (`test_route_access.py`):
  - only a reviewed list of 31 routes is public;
  - every other route refuses anonymous callers (401, or 404 for admin routes);
  - another account gets 404 on every GET route with your record ids (16 routes walked; the 3
    not walked have their own tests, named in the file);
  - a cross-site form can't sign anyone in.
- **Story revision restore** now checks the linked target's owner, as edits already did.
- **`/metrics`** needs `METRICS_TOKEN` when one is set, and production requires one.
- **`python -m app.cli check-rls`** reports whether RLS is enforced for the connected role.

## 3. Caching

- **Measured first.** Anonymous catalogue reads cost 3–25 ms each in process. `/careers` is the
  heaviest at about 25 ms and 26 KB, and the catalogue is the same for everyone.
- **`http_cache.CacheMiddleware`** (pure ASGI, innermost) applies three rules:
  - **Shared catalogue** (careers, problem lists and counts, topics, lessons, scenarios, formats):
    cached in process for `RESPONSE_CACHE_TTL_SECONDS` (60), keyed on path, query and the
    published-content fingerprint. Browsers may keep it for the same time (`public, max-age`),
    with a weak ETag, so revalidation costs a 304.
  - **Personalised pages** (question lists and pages, problem pages): cached only for requests
    without `Authorization`, with `Vary: Authorization`.
  - **Everything else:** `Cache-Control: no-store`, unless the route set its own header.
- **Freshness.** A correction or retirement in this process is served at once (the snapshot is
  invalidated). One made on another replica is served within the content refresh interval (5 s),
  because the middleware refreshes a stale snapshot before trusting a key.
- **Observability.** Logs and metrics still name the route on a cache hit.
- **Tests:** `test_http_cache.py` (6).

## 4. Background jobs

- **Durable email outbox** (`email_jobs`, migration `b7abe5833c3c`):
  - **Recording:** a route records the job in its own transaction, then tries it right after
    the response, as before.
  - **Retries:** with backoff (30 s, 2, 10, 30 min; 5 attempts). A job is dropped when it would
    arrive too late to be useful (a reset link past its lifetime).
  - **Claiming:** each attempt is claimed with one conditional UPDATE, so 4 parallel drainers
    send once (tested). A process that dies mid-send leaves a lease that expires.
  - **No secrets stored:** jobs hold what to send (kind, account, addresses), never a link or
    code; those are created when the email is sent. Addresses are cleared when the job finishes.
- **`app/jobs.JobsRunner`** runs in every API process (`BACKGROUND_JOBS_IN_API`) and in
  `python -m app.worker`, which now runs jobs-only when the judge is off. It:
  - retries due emails;
  - purges expired rate-limit counters every 10 minutes;
  - once a day, deletes inactive guests and email jobs finished over a week ago.

  `python -m app.cli housekeeping` runs it once.
- **AI requests** stay in the request: answers are interactive, and the offline fallback makes
  each one bounded. What was dangerous was concurrency. That is now capped per process (§1), and
  the load test shows the difference.
- **Tests:** `test_background_jobs.py` (11).

## 5. Pre-launch load tests

All on the shipped configuration (one uvicorn process, PostgreSQL 16, RLS enforced). Full numbers
are in [PERFORMANCE.md](PERFORMANCE.md#pre-launch-load-tests-2026-11-06).

- **Catalogue:** 41 req/s without the cache, 565 req/s with it (13.8×). p95 dropped from
  340–880 ms to 70 ms.
- **Sign-in capacity:** about 16 logins/s per 4 cores. This is Argon2id's deliberate cost.
- **Sign-in flood at the default limits:** 1,329 of 1,337 attempts got 429; 0 errors; readers
  stayed correct.
- **Slow AI provider (10 s per call):**
  - with no cap, other users got 503s (10 of 16 reader requests; the pool ran out 44 times);
  - with the default cap of 8, there were 0 errors for anyone.

## 6. Authentication provider (Clerk or Firebase): your decision

I didn't switch, because it can't be done responsibly without you:
- It needs an account with the provider and its keys.
- It may cost money, depending on monthly active users; check current pricing.
- Existing accounts would have to move. Either the provider imports the Argon2id password hashes
  (check that it supports them), or every user resets their password.

**What the current auth already does** (about 80 tests): Argon2id with rehash, 15-minute access
tokens, a rotating HttpOnly SameSite=Strict refresh cookie with reuse detection and lost-response
recovery, email verification, password reset, guest accounts that upgrade in place, and rate
limits.

**What this batch fixed in it:**
- per-account limits;
- key rotation;
- a login-CSRF test;
- docs that described logout and CORS wrongly.

**What it lacks, and a provider would bring:** multi-factor sign-in, passkeys, social sign-in,
breached-password checks and bot protection.

**My recommendation:**
- Keep the current auth for launch.
- If you want social sign-in or MFA soon, prefer **Firebase Auth**. Its anonymous accounts that
  link to a real account fit CodeCoach's guest flow.
- **Clerk** has the better ready-made React screens. Check how it would handle guests first.

**Either way the backend change is contained:** verify the provider's tokens against its public
keys in `api/deps.py`, and map its user id to `users.auth_provider_id` (the column exists for
this). Everything else, row-level security included, keys on our own user id. Say which you want
and I'll plan the migration.

## 7. Secret management

Everything is in [SECURITY.md §7](SECURITY.md#7-secrets-rotation-and-the-database-role). Tests:
`test_secrets.py` (15) and `secretGuard.test.ts` (3).

- **Never printed:** `SecretStr` for every secret, and a settings error never echoes its input.
- **Production refuses:** weak or placeholder keys, example database passwords,
  `AUTO_MIGRATE=true`, and metrics without a token.
- **`.env.example`** starts as is (blank means "not set").
- **Rotation:** `SECRET_KEY_PREVIOUS`; tested end to end, sessions survive rotation.
- **CI:** detect-secrets against a reviewed baseline, comparing file, type and hash, so line
  shifts don't fail it. A planted token fails it.
- **Frontend build:** refuses secret-named `VITE_*` variables, and any bundle containing a
  server secret's value. Both were verified by failing builds on purpose.

## Checks run

Local runs used Chromium headless, SQLite and PostgreSQL 16 with an ordinary role, so RLS was
enforced.

| Check | Result |
|---|---|
| Backend lint, format, types (`ruff check`, `ruff format --check`, `mypy app evals`) | clean |
| Backend, SQLite, full suite (on `f0ff201`) | 2,343 passed, 393 skipped, 2 xfailed (the rubric v10 residuals, still strict) |
| Backend, PostgreSQL with RLS enforced, full suite (on `c106615`) | 2,349 passed, **1 failed**. This was a real bug that RLS exposed: another learner naming your plan activity got a 500, not a 404. Fixed in `f0ff201`. Its tests (roadmap, route access) pass on PostgreSQL, and the new write-route walk fails without the fix. The full PostgreSQL suite after the fix runs in CI |
| Frontend type check, lint, API types match `docs/openapi.json` | pass (the OpenAPI document is unchanged) |
| Frontend unit and integration (`npx vitest run`) | 701 passed, 73 files |
| Build and budgets | shell 206.8 KB / 300 KB, largest lazy chunk 674.5 KB / 700 KB (unchanged) |
| End-to-end (`npx playwright test`, nothing else running) | 96 passed, 3 skipped, 0 failed |
| Secret scan (`scripts/check_secrets.py`) | no unreviewed findings (20 reviewed). A planted token fails it |
| Migration rehearsal (disposable PostgreSQL) | pass, as described below |

## Changed contracts and migrations

- **API:**
  - new 429s on resend, refresh, export, restore, and saving submissions with execution off;
  - `account_throttled` and `ai_request_in_progress` codes;
  - `Retry-After` headers;
  - `Cache-Control`, `ETag` and `Vary` headers.

  No request or response bodies changed.
- **Migrations (additive):**
  - `9152380226e0`: counter expiry column;
  - `248721f0fcb1`: RLS policies;
  - `b7abe5833c3c`: `email_jobs`.

  Rehearsed on a disposable PostgreSQL 16 database (`codecoach_rehearsal_load`, created and then
  dropped): upgrade, `alembic check` (no drift), downgrade 3, upgrade, seed, `check-rls`.
- **Settings:**
  - `SECRET_KEY_PREVIOUS`, `METRICS_TOKEN`;
  - `LOGIN_FAILURES_PER_ACCOUNT`, `REFRESH_RATE_LIMIT_PER_MINUTE`, `EXPORTS_PER_HOUR`,
    `RESTORES_PER_HOUR`;
  - `AI_MAX_CONCURRENT_CALLS`, `RESPONSE_CACHE_TTL_SECONDS`, `BACKGROUND_JOBS_IN_API`;
  - `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`.

  `AUTO_MIGRATE` now defaults to off in production. All are in `docs/API.md` and `.env.example`.

## Limits

- Row-level security is PostgreSQL-only, and open to operator commands and migrations (no scope). It doesn't cover
  submissions, shares, sign-in tokens or triage (reasons in `db/rls.py`). It needs an ordinary
  database role. The production layout uses one that owns nothing
  ([STORAGE.md](STORAGE.md)); the development compose file's default user is a superuser.
- The in-process cache is per process. A CDN in front would multiply the gain; none is
  configured.
- Rate limits run in the API, so a flood still costs CPU. An edge limit is the next layer.
- `POST /auth/guest` can be triggered cross-site. It starts an empty guest session and nobody
  gains access.
- The load tests ran on one 4-vCPU VM shared with the load generator, with no real AI provider
  and no real mail server.

Nothing was sent: no emails beyond test fakes and files, no provider calls, no messages, and no
deployment, merge or pull-request change.
