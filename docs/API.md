# CodeCoach AI — API Reference

The REST API every client (the React app, scripts, tests) talks to. The examples below are
real responses captured from the running server, trimmed only where marked `…`.

- **Base URL (local):** `http://localhost:8000`
- **Interactive docs:** `http://localhost:8000/docs` (Swagger UI) and `/redoc`
- **Machine-readable contract:** [`docs/openapi.json`](openapi.json). A test fails if this
  file falls out of sync with the code. Regenerate with `cd backend && python -m app.cli openapi`.
- **Versioning:** all application routes live under `/api/v1`. Breaking changes go into `/api/v2`.

## Contents

1. [Conventions](#conventions)
2. [Authentication flow](#authentication-flow)
3. [Error codes](#error-codes)
4. [Endpoints](#endpoints): [Health](#health) · [Auth](#auth) · [Problems](#problems) ·
   [Submissions](#submissions) · [AI coach](#ai-coach) · [Mock interviews](#mock-interviews) · [Progress](#progress)
5. [Environment variables](#environment-variables)
6. [Running locally](#running-locally)

---

## Conventions

| Topic | Rule |
|---|---|
| Format | JSON in, JSON out. `Content-Type: application/json`. |
| Field names | `snake_case`. |
| Timestamps | ISO-8601 with an explicit UTC offset (`2026-11-01T09:49:54.443943Z`). |
| IDs | Users, submissions and AI interactions use UUID strings. Problems are addressed by `slug`. |
| Pagination | `?page=1&page_size=20` (max 100). Responses are `{items, total, page, page_size}`. |
| Errors | Always the [error envelope](#error-codes). Branch on `error.code`, never on `message`. |
| Request IDs | Every response has an `X-Request-ID` header. Send your own (8–64 chars of `A-Za-z0-9._-`) to correlate client and server logs. It is also echoed inside error bodies. |
| Ownership | Resources owned by another user return **404**, not 403, so IDs can't be probed. |
| Hidden data | Hidden test cases, hint text and reference solutions never appear in any response. |

### Pagination example

```http
GET /api/v1/problems?page=1&page_size=2
```

```json
{
  "items": [
    {"slug": "find-largest-number", "title": "Find Largest Number", "difficulty": "easy",
     "topics": ["arrays", "iteration"],
     "summary": "Return the largest value in an integer array, and define what happens when the array is empty."},
    {"slug": "reverse-string", "title": "Reverse a String", "difficulty": "easy",
     "topics": ["strings", "two-pointers"], "summary": "Return a string with its characters in reverse order."}
  ],
  "total": 12,
  "page": 1,
  "page_size": 2
}
```

---

## Authentication flow

Two tokens with different jobs:
- **Access token:** a short-lived JWT (15 minutes) returned in the JSON body. Keep it **in
  memory only** and send it as `Authorization: Bearer <access_token>`.
- **Refresh token:** an opaque random value in an **`HttpOnly`, `SameSite=Strict` cookie**
  named `cc_refresh`, scoped to `Path=/api/v1/auth` and `Secure` in production. Page scripts
  can't read it, so an XSS bug can't steal a long-lived credential. The server stores only its
  SHA-256 hash.

```
┌────────┐  POST /auth/login (or /register, /guest)                  ┌─────┐
│ client │ ───────────────────────────────────────────────────────▶ │ API │
│        │ ◀── { access_token, expires_at, user } + Set-Cookie ──── │     │
│        │                                                          │     │
│        │  GET /api/v1/...   Authorization: Bearer <access_token>  │     │
│        │ ───────────────────────────────────────────────────────▶ │     │
│        │                                                          │     │
│        │  page load, or ~1 min before expiry, or on a 401:        │     │
│        │  POST /auth/refresh  (cookie + X-Requested-With)         │     │
│        │ ───────────────────────────────────────────────────────▶ │     │
│        │ ◀── new access token + rotated Set-Cookie ───────────── │     │
└────────┘                                                          └─────┘
```

1. **Sign in** with `POST /api/v1/auth/register`, `/login` or `/guest`. Each starts a new
   refresh-token *family* and sets the cookie. Cross-origin clients must send
   `credentials: "include"` on `/api/v1/auth/*` calls so the browser stores and sends it.
2. **Call the API** with the access token in the `Authorization` header. Never put it in a URL
   or in `localStorage`.
3. **Refresh** with `POST /api/v1/auth/refresh` and the header `X-Requested-With: codecoach`.
   The response is a normal `TokenResponse` plus a **rotated** cookie. The web app refreshes on
   page load (to restore the session), about a minute before expiry, and once after a `401`
   before retrying the request.
4. **Refresh errors** (`401`): `invalid_refresh` (missing, expired or revoked: sign in again);
   `refresh_reused` (an already-used token was presented later, so it was copied: the whole
   family was revoked); `refresh_race` (two tabs refreshed with the same cookie within 30 s:
   retry once and the browser will send the new cookie). `403 csrf_rejected` means the custom
   header was missing or the `Origin` isn't an allowed one.
5. **Logout:** `POST /api/v1/auth/logout` ends *this device's* session (its refresh-token family)
   and clears the cookie; discard the in-memory access token. `POST /api/v1/auth/logout-all`
   increments `token_version` and revokes every refresh token: every session on every device ends.
6. **Password change:** `POST /api/v1/auth/password` ends every other session and returns a
   fresh access token and cookie for this one. **Account deletion** clears the cookie too.

Public endpoints (no token needed): `/health*`, `GET /api/v1/problems`, `GET /api/v1/topics`,
`GET /api/v1/problems/{slug}`. Sending a token to `GET /problems/{slug}` is optional; if you
do, the visit is recorded in the user's progress. An **invalid** token is always a 401, even on
public endpoints, so client bugs surface early.

**Password rules:** 10–128 characters, upper- and lower-case letters, at least one digit, no
leading or trailing whitespace. **Rate limit:** register, login, guest and password change
allow `AUTH_RATE_LIMIT_PER_MINUTE` attempts per client IP per minute (default 10).

---

## Error codes

Every non-2xx response has this shape:

```json
{
  "error": {
    "code": "hint_locked",
    "message": "Hints unlock one level at a time. Request level 1 first.",
    "request_id": "793487bfd3e54942838d602978f1c0e3",
    "details": {"next_unlockable_level": 1}
  }
}
```

| HTTP | `error.code` | When | Suggested UI |
|---|---|---|---|
| 400 | `bad_request` | Generic bad input | Show `message` |
| 400 | `payload_too_large` | Source code over `MAX_SOURCE_CHARS` (`details.max_source_chars`) | Inline editor error |
| 400 | `guest_disabled` | Guest sessions turned off | Hide the guest button |
| 401 | `unauthorized` | No token on a protected route | Redirect to login |
| 401 | `invalid_token` | Token invalid, expired, or revoked | Clear token, redirect to login |
| 401 | `invalid_refresh` / `refresh_reused` / `refresh_race` | Refresh cookie missing/expired/revoked, replayed (family revoked), or two tabs racing (retry once) | Sign in again / retry |
| 403 | `csrf_rejected` | `/auth/refresh` without `X-Requested-With: codecoach` or from an unknown `Origin` | (client bug) |
| 401 | `invalid_credentials` | Wrong email/password (deliberately identical for unknown emails) | Form error |
| 404 | `not_found` | Unknown route, problem, or a resource owned by someone else | Not-found state |
| 405 | `method_not_allowed` | Wrong HTTP method | (client bug) |
| 409 | `email_taken` | Registration with an existing email | Form error on email |
| 409 | `hint_locked` | Hint level requested before the previous one (`details.next_unlockable_level`) | Disable later hint buttons |
| 409 | `interview_in_progress` | Starting an interview while one is active (`details.interview_id`) | Offer "Resume" |
| 409 | `interview_closed` | Sending a message to a finished, expired or abandoned interview (`details.status`) | Show the results view |
| 400 | `turn_limit_reached` | Interview message cap reached (`details.max_candidate_turns`) | Prompt to finish |
| 409 | `not_judged` | Explain-failure on a submission that's still queued or running | Wait for the verdict |
| 409 | `not_failed` | Explain-failure on a submission that passed | Hide the button |
| 409 | `judge_error` | Explain-failure on an `INTERNAL_ERROR` (the judge's fault, not the code's) | Suggest resubmitting |
| 429 | `submission_pending` | A previous submission is still being judged (`details.max_pending`) | Wait for the verdict |
| 503 | `judge_busy` | The judge queue is full | Retry in a minute |
| 503 | `execution_disabled` | `mode: run` on a deployment without code execution (check `GET /capabilities` first) | Hide the Run button |
| 422 | `validation_error` | Body or query failed validation. `details` is a list of `{loc, msg, type}` | Map `loc[-1]` to form fields |
| 429 | `rate_limited` | Auth attempts or the daily AI budget exceeded (`details.retry_after_seconds` or `details.daily_limit`) | Show a cooldown |
| 500 | `internal_error` | Unexpected server error (logged with the request id) | Generic error + request id |
| 503 | — | `/health/ready` only, when the database is unreachable | — |

Validation error example (`GET /api/v1/problems?page=0`):

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "request_id": "c3c1…",
    "details": [{"loc": ["query", "page"], "msg": "Input should be greater than or equal to 1", "type": "greater_than_equal"}]
  }
}
```

---

## Endpoints

Summary (🔒 = requires `Authorization: Bearer …`):

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | – | Liveness |
| GET | `/health/ready` | – | Readiness (database check) |
| GET | `/api/v1/capabilities` | – | What this deployment supports (code execution, AI provider) |
| POST | `/api/v1/auth/register` | – | Create account → token |
| POST | `/api/v1/auth/login` | – | Log in → token |
| POST | `/api/v1/auth/refresh` | cookie | New access token from the refresh cookie (rotates it) |
| POST | `/api/v1/auth/upgrade` | 🔒 | Turn the current guest into a full account, keeping its data |
| POST | `/api/v1/auth/verify-email` | – | Confirm an email with the emailed link token |
| POST | `/api/v1/auth/verify-email/code` | 🔒 | Confirm your email with the emailed 6-digit code |
| POST | `/api/v1/auth/verify-email/resend` | 🔒 | Send a new code and link |
| POST | `/api/v1/auth/email` | 🔒 | Change your email (needs your password) |
| POST | `/api/v1/auth/logout-all` | 🔒 | Sign out of every device |
| POST | `/api/v1/auth/password-reset` | – | Email a reset link (same answer for unknown emails) |
| POST | `/api/v1/auth/password-reset/confirm` | – | Set a new password with a reset token |
| POST | `/api/v1/auth/guest` | – | Demo session → token |
| GET | `/api/v1/auth/me` | 🔒 | Current user |
| POST | `/api/v1/auth/logout` | 🔒 | Revoke all of this user's tokens |
| POST | `/api/v1/auth/password` | 🔒 | Change password → new token |
| PATCH | `/api/v1/auth/me` | 🔒 | Update display name |
| DELETE | `/api/v1/auth/me` | 🔒 | Permanently delete the account and all data |
| GET | `/api/v1/me/export` | 🔒 | Download all of your data (JSON) |
| GET | `/api/v1/problems` | – | List / filter / search problems |
| GET | `/api/v1/topics` | – | Topics with counts (for filter chips) |
| GET | `/api/v1/problems/{slug}` | optional | Problem workspace data |
| POST | `/api/v1/submissions` | 🔒 | Submit a solution, or `mode: run` to check the public tests only (async job) |
| GET | `/api/v1/submissions/{id}` | 🔒 | Poll a submission |
| GET | `/api/v1/me/submissions` | 🔒 | Attempt history |
| POST | `/api/v1/ai/hint` | 🔒 | Progressive hint |
| POST | `/api/v1/ai/review` | 🔒 | Structured code review |
| POST | `/api/v1/ai/explain-failure` | 🔒 | Explain why a judged submission failed |
| GET | `/api/v1/ai/usage` | 🔒 | Remaining AI budget |
| GET | `/api/v1/me/ai-history` | 🔒 | Saved hints and reviews |
| POST | `/api/v1/interviews` | 🔒 | Start a timed mock interview |
| GET | `/api/v1/interviews` | 🔒 | Interview history |
| GET | `/api/v1/interviews/{id}` | 🔒 | State, transcript, evaluation |
| POST | `/api/v1/interviews/{id}/messages` | 🔒 | Candidate answer → interviewer reply |
| POST | `/api/v1/interviews/{id}/finish` | 🔒 | End + rubric feedback (idempotent) |
| POST | `/api/v1/interviews/{id}/abandon` | 🔒 | End early (still evaluated) |
| GET | `/api/v1/me/progress` | 🔒 | Dashboard analytics |
| GET | `/api/v1/me/recommendations` | 🔒 | Personalized next problems |
| GET | `/metrics` | – | Prometheus metrics (operators; not in OpenAPI) |

### Health

#### `GET /health`
Liveness probe. Deliberately reveals no versions or infrastructure details.
```json
{"status": "ok"}
```

#### `GET /health/ready`
Readiness probe: checks the database connection. `200` when ready, `503` when not.
```json
{"status": "ok", "checks": {"database": "ok"}}
```

### Auth

#### `POST /api/v1/auth/register` → `201`
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email": "ada@example.com", "password": "CorrectHorse42", "display_name": "Ada"}'
```
| Field | Type | Rules |
|---|---|---|
| `email` | string | Valid email. Stored lower-cased; must be unique. |
| `password` | string | See [password rules](#authentication-flow). |
| `display_name` | string? | 1–40 chars. |

Response (`TokenResponse`):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOi…",
  "token_type": "bearer",
  "expires_at": "2026-11-01T09:49:54.443943Z",
  "user": {
    "id": "fc82e050-3876-4620-86aa-9963231d3fcb",
    "email": "ada@example.com",
    "display_name": "Ada",
    "is_guest": false,
    "created_at": "2026-11-01T08:49:54.440682Z"
  }
}
```
Errors: `409 email_taken`, `422 validation_error`, `429 rate_limited`.

#### `POST /api/v1/auth/login` → `200`
```json
{"email": "ada@example.com", "password": "CorrectHorse42"}
```
Returns a `TokenResponse`. Wrong password **and** unknown email both return:
```json
{"error": {"code": "invalid_credentials", "message": "Incorrect email or password", "request_id": "78e0…", "details": null}}
```

#### `POST /api/v1/auth/guest` → `201`
Body is optional: `{"display_name": "Visitor"}`. Returns a `TokenResponse` whose
`user.is_guest` is `true` and `user.email` is `null`. Guest accounts can do everything
except change a password.

#### `GET /api/v1/auth/me` 🔒 → `200`
Returns the `user` object shown above.

#### `POST /api/v1/auth/logout` 🔒 → `204`
No body. Every token previously issued to this user stops working.

#### `POST /api/v1/auth/password` 🔒 → `200`
```json
{"current_password": "CorrectHorse42", "new_password": "BatteryStaple99"}
```
Returns a fresh `TokenResponse`; all older tokens are revoked. `401 invalid_credentials`
if the current password is wrong (or the user is a guest).

#### `PATCH /api/v1/auth/me` 🔒 → `200`
`{"display_name": "Grace"}` (1–40 chars, or `null` to clear). Returns the updated `user`.

#### `POST /api/v1/auth/upgrade` 🔒 → `200`
Guest accounts only. Same body and rules as `/register`; the account keeps its id, so every
attempt, hint, review and interview is kept. Returns a `TokenResponse` and a new refresh
cookie. `409 email_taken`, `409 not_a_guest`.

#### Email verification
New accounts (registration or guest upgrade) and changed emails get one email containing **both**
a 6-digit code and a link (`APP_BASE_URL/verify-email#token=…`). `UserOut.email_verified` reports
the state. Each send supersedes the previous code and link; at most one per minute per account.

- `POST /api/v1/auth/verify-email/code` 🔒 `{"code": "123456"}` → `200 UserOut`. Five wrong codes
  kill that code (`400 too_many_attempts`); otherwise `400 invalid_verification_code` with
  `details.attempts_left`. Codes are stored as HMAC-SHA256 keyed with the server secret.
- `POST /api/v1/auth/verify-email` `{"token": "…"}` → `200 UserOut` (no sign-in needed, so the link
  works on another device). `400 invalid_verification_token` if used, superseded, expired, or the
  account's email changed since it was sent.
- `POST /api/v1/auth/verify-email/resend` 🔒 → `202`. `409 already_verified`, `409 not_applicable`
  (guests).
- `POST /api/v1/auth/email` 🔒 `{"new_email": "…", "password": "…"}` → `200 UserOut` with
  `email_verified: false`. Sends a code to the new address and a notice to the old one.
  `401 invalid_credentials`, `409 email_taken`, `409 same_email`.

#### `POST /api/v1/auth/password-reset` → `202`
```json
{"email": "ada@example.com"}
```
```json
{"status": "accepted", "message": "If an account exists for that email, we've sent a link to reset the password."}
```
The answer, and its timing, is identical for registered, unknown and guest addresses: the lookup
and the email happen after the response. At most one email per account per minute, and only the
newest link works. The emailed link is `APP_BASE_URL/reset-password#token=…`: a URL fragment, so
the token never reaches servers, proxies or `Referer` headers. Rate-limited like sign-in.

#### `POST /api/v1/auth/password-reset/confirm` → `204`
```json
{"token": "…from the link…", "new_password": "BatteryStaple99"}
```
Single use, valid for `PASSWORD_RESET_TTL_MINUTES` (default 30). Sets the password and **ends
every session** (access tokens and refresh cookies). `400 invalid_reset_token` if it's unknown,
used, superseded or expired; `422` if the password breaks the rules.

#### `DELETE /api/v1/auth/me` 🔒 → `204`
```json
{"password": "CorrectHorse42", "confirm": "DELETE"}
```
`confirm` must be exactly `DELETE` (`400 confirmation_required` otherwise). `password` is
required for email/password accounts (`401 invalid_credentials` if wrong) and omitted for
guests. Submissions, results, AI feedback, interviews and activity are deleted in the same
transaction (database `ON DELETE CASCADE`), and all tokens stop working. The email can be
registered again afterwards.

#### `GET /api/v1/me/export` 🔒 → `200`
A downloadable JSON document (`Content-Disposition: attachment`, `Cache-Control: no-store`):
`{export_version, exported_at, profile, submissions[], ai_feedback[], interviews[], activity[]}`.
Submissions include your source code and results; interviews include full transcripts and
evaluations. Credentials (password hash, token version) are never included.

### Capabilities

#### `GET /api/v1/capabilities` → `200`
Public. Lets the client show only features that work on this deployment. Deliberately coarse:
no versions, hostnames, model names or limits.
```json
{"execution_enabled": true, "ai_provider": "offline", "guest_retention_days": 30}
```

### Problems

#### `GET /api/v1/problems` → `200`
| Query | Type | Notes |
|---|---|---|
| `difficulty` | `easy` \| `medium` \| `hard` | optional |
| `topic` | string | exact topic slug from `/topics`, e.g. `hash-maps` |
| `q` | string | case-insensitive search over title and summary |
| `page`, `page_size` | int | defaults 1 and 20, max page size 100 |

Response: `Page[ProblemSummary]` (see the [pagination example](#pagination-example)).

#### `GET /api/v1/topics` → `200`
```json
[{"topic": "arrays", "count": 6}, {"topic": "binary-search", "count": 1}, {"topic": "hash-maps", "count": 3}, "…"]
```

#### `GET /api/v1/problems/{slug}` → `200`
Everything the workspace screen needs. `statement` is Markdown (inline code in backticks,
`**bold**`, paragraphs). `hidden_test_count` says how many extra tests the judge runs, without
revealing them.
```json
{
  "slug": "two-sum",
  "title": "Two Sum",
  "difficulty": "easy",
  "topics": ["arrays", "hash-maps"],
  "summary": "Find the indices of two numbers that add up to a target.",
  "statement": "Given an integer array `nums` and an integer `target`, return the indices `[i, j]` …",
  "constraints": ["2 <= nums.length <= 10^4", "-10^9 <= nums[i], target <= 10^9", "Exactly one valid answer exists", "Return indices in increasing order"],
  "examples": [
    {"input": "nums = [2, 7, 11, 15], target = 9", "output": "[0, 1]", "explanation": "nums[0] + nums[1] = 2 + 7 = 9."},
    {"input": "nums = [3, 2, 4], target = 6", "output": "[1, 2]", "explanation": null}
  ],
  "starter_code": "class Solution {\n    public int[] twoSum(int[] nums, int target) {\n        // TODO: write your solution here\n        return new int[0];\n    }\n}\n",
  "signature": {"method": "twoSum", "params": [{"name": "nums", "type": "int[]"}, {"name": "target", "type": "int"}], "returns": "int[]"},
  "public_tests": [
    {"id": 15, "input": {"nums": [2, 7, 11, 15], "target": 9}, "expected_output": [0, 1]}
  ],
  "hidden_test_count": 4,
  "hint_levels": 4
}
```
`expected_output` may also be `{"throws": "IllegalArgumentException"}` when the contract is
to throw (see `find-largest-number`). Errors: `404 not_found`.

### Submissions

Submissions are **asynchronous jobs**: `POST` returns `202 Accepted` right away and the client
polls `GET /submissions/{id}` until `is_terminal` is `true`.

> **Execution on/off:** when the deployment has `EXECUTION_ENABLED=true`, submissions are
> judged in the isolated gVisor runner ([SECURITY.md §4](SECURITY.md#4-secure-java-execution-implemented-gvisor-sandbox)),
> typically within a few seconds. When it's off, `execution_enabled` is `false` and submissions
> stay `QUEUED` forever, so the UI should show `status_detail` and **stop polling**. Poll every
> ~1.5 s while `is_terminal` is `false` and `execution_enabled` is `true`.

Status lifecycle:
`QUEUED → RUNNING → PASSED | FAILED | COMPILE_ERROR | RUNTIME_ERROR | TIME_LIMIT | MEMORY_LIMIT | INTERNAL_ERROR`

#### `POST /api/v1/submissions` 🔒 → `202`
```json
{"problem_slug": "two-sum", "language": "java", "source_code": "class Solution { … }", "mode": "submit"}
```
`mode` is optional: `submit` (default) judges against **all** tests and records the attempt;
`run` checks the **public tests only** for quick feedback. A run never counts as an attempt or
a solve, isn't listed in `GET /me/submissions` (unless `?mode=run`) and isn't in progress stats;
hidden test inputs aren't even compiled into its driver. Runs share the same admission limits,
and are refused with `503 execution_disabled` when the deployment can't run code. A run's
`result` has `hidden_total: 0`. Explanations work on failed runs too.
`language` is optional and must be `java`. `source_code` must be non-blank and at most
`MAX_SOURCE_CHARS` characters. When execution is enabled, admission control applies:
`429 rate_limited` (more than `SUBMISSION_RATE_LIMIT_PER_MINUTE`), `429 submission_pending`
(a previous submission is still being judged), `503 judge_busy` (global queue full).
```json
{
  "id": "9098460d-619d-4f69-89fb-459bc700ef0b",
  "problem_slug": "two-sum",
  "problem_title": "Two Sum",
  "language": "java",
  "mode": "submit",
  "status": "QUEUED",
  "status_detail": "Saved and queued. Automatic judging is turned off until the sandboxed Java runner is approved and deployed, so this submission will not run yet.",
  "is_terminal": false,
  "execution_enabled": false,
  "created_at": "2026-11-01T08:49:54.608581Z",
  "updated_at": "2026-11-01T08:49:54.610668Z",
  "result": null,
  "source_code": "class Solution { … }"
}
```
When judged, `result` looks like this (real output from the gVisor sandbox for a wrong
answer to *Valid Parentheses*; first two public tests shown):
```json
{
  "runtime_ms": 2, "memory_kb": null,
  "passed_count": 5, "total_count": 8, "hidden_passed": 3, "hidden_total": 5,
  "public_results": [
    {"index": 0, "passed": true, "input": {"s": "()[]{}"}, "expected_output": true, "actual_output": true,
     "exception": null, "exception_message": null, "missing": false, "line": null, "runtime_ms": 1.532},
    {"index": 1, "passed": false, "input": {"s": "([)]"}, "expected_output": false, "actual_output": true,
     "exception": null, "exception_message": null, "missing": false, "line": null, "runtime_ms": 0.005}
  ],
  "stderr_excerpt": null
}
```
- Per-test detail is only ever given for **public** tests. Hidden tests contribute to
  `passed_count`/`total_count` and `hidden_passed`/`hidden_total` only.
- `exception` + `exception_message`: the test threw (e.g. `ArrayIndexOutOfBoundsException`,
  `Index 2 out of bounds for length 2`). An expected exception (`{"throws": …}`) counts as a pass.
- `line`: the line **in the learner's code** where that exception was thrown (innermost
  `Solution.java` stack frame), or `null`. Lines up with Monaco line numbers.
- `missing: true`: the test never reported because the program crashed, exited or hit the time limit first.
- `stderr_excerpt` is set **only** for `COMPILE_ERROR` (compiler output, with sandbox paths
  removed). Program output is never returned, because learner code could print hidden inputs.
  Errors javac reports in the judge's own `Main.java` (e.g. after renaming the method) are
  reduced to a vetted message plus `symbol:` lines and labelled `Main.java (judge driver)`,
  because javac would otherwise echo driver source lines that contain hidden test inputs
  ([SECURITY.md](SECURITY.md#4-secure-java-execution-implemented-gvisor-sandbox)).
- `runtime_ms` is time spent inside the learner's method. `memory_kb` is `null`: peak memory
  isn't measured yet, and the API never invents numbers.

Verdicts: `PASSED` (all tests) · `FAILED` (some wrong answers) · `COMPILE_ERROR` ·
`RUNTIME_ERROR` (crashed/exited before finishing, StackOverflowError, output flood) ·
`TIME_LIMIT` · `MEMORY_LIMIT` · `INTERNAL_ERROR` (judge infrastructure failed after retries; not
the learner's fault).

#### `GET /api/v1/submissions/{id}` 🔒 → `200`
Same shape as above. `404` if it doesn't exist **or** belongs to another user.

#### `GET /api/v1/me/submissions` 🔒 → `200`
Query: `problem_slug`, `status` (e.g. `QUEUED`, `PASSED`), `mode` (`submit` default, or `run`), `page`, `page_size`. Newest first.
```json
{
  "items": [{"id": "9098…", "problem_slug": "two-sum", "problem_title": "Two Sum", "mode": "submit", "status": "QUEUED",
             "created_at": "2026-11-01T08:49:54.608581Z", "duration_ms": null}],
  "total": 1, "page": 1, "page_size": 20
}
```

### AI coach

All AI endpoints count against the user's **daily budget** (`AI_DAILY_REQUEST_LIMIT` per
rolling 24 hours) and are saved to the user's history. The response shapes are identical
whichever provider (offline or Claude) produced them; `provider` says which one did.
`"offline (fallback)"` means the AI provider failed and the curated offline coach answered.

#### `POST /api/v1/ai/hint` 🔒 → `200`
```json
{"problem_slug": "two-sum", "level": 1, "source_code": "class Solution { … }"}
```
| Level | Name | What the learner gets |
|---|---|---|
| 1 | nudge | A question pointing at the key insight |
| 2 | concept | The data structure or technique, and why it fits |
| 3 | pseudocode | Step-by-step pseudocode |
| 4 | full explanation | Complete approach, complexity and edge cases |

Levels **unlock one at a time** per user and problem. Asking for level 3 before level 2
returns `409 hint_locked` with `details.next_unlockable_level`. Re-asking an unlocked level is
allowed.
```json
{
  "level": 1,
  "level_name": "nudge",
  "content": {
    "hint": "For each number, you already know exactly which other value you'd need. How could you check whether you've seen it, quickly?",
    "focus_area": "getting unstuck",
    "encouragement": "Start small: get the simplest correct version working first, then improve it."
  },
  "max_level": 4,
  "next_level_available": true,
  "provider": "offline",
  "grounded": true
}
```

#### `POST /api/v1/ai/review` 🔒 → `200`
```json
{"problem_slug": "two-sum", "source_code": "class Solution { … }", "submission_id": null}
```
`submission_id` (optional, must be yours) attaches the judge verdict once it exists. The AI is
told the verdict is authoritative and must never contradict it.
```json
{
  "review": {
    "summary": "1 thing to look at. Most important: Nested loops make this roughly O(n^2), but an O(n) approach exists.",
    "complexity": {"time": "O(n^2)", "space": "O(1)"},
    "issues": [{
      "severity": "medium",
      "category": "complexity",
      "detail": "Nested loops make this roughly O(n^2), but an O(n) approach exists.",
      "suggestion": "Ask what the inner loop is searching for, and whether a HashMap/HashSet or two pointers could answer that question without rescanning.",
      "line_hint": 3
    }],
    "strengths": ["No unguarded first-element access was detected.", "Code is free of the common style issues this reviewer checks for."],
    "next_step": "Ask what the inner loop is searching for, and whether a HashMap/HashSet or two pointers could answer that question without rescanning.",
    "confidence": "medium"
  },
  "provider": "offline",
  "expected_complexity": {"time": "O(n)", "space": "O(n)"},
  "judge_status": null,
  "disclaimer": "AI feedback can be wrong. Pass/fail comes only from the test judge, never from the AI."
}
```
Enums: `severity` ∈ `low | medium | high`; `category` ∈ `correctness | edge-case |
complexity | readability | style`; `confidence` ∈ `low | medium | high`. `line_hint` is
1-based (or `null`) and lines up with Monaco line numbers.

#### `POST /api/v1/ai/explain-failure` 🔒 → `200`
```json
{"submission_id": "9098460d-619d-4f69-89fb-459bc700ef0b"}
```
Explains why a judged submission failed, in plain English, grounded in evidence the learner
can already see: the verdict, the (redacted) compiler output, the **first failing public
test**, the exception line, and pass counts. Hidden test inputs are never sent to the AI or
returned. One explanation per submission: asking again returns the saved one with
`"cached": true` and **doesn't use budget**.

Errors: `404` (not found / not yours), `409 not_judged`, `409 not_failed` (it passed),
`409 judge_error` (`INTERNAL_ERROR`), `429 rate_limited` (budget).

Offline-coach output for an `ArrayIndexOutOfBoundsException` (a `<=` loop bound) on
*Find Largest Number*:
```json
{
  "submission_id": "9098460d-619d-4f69-89fb-459bc700ef0b",
  "status": "FAILED",
  "explanation": {
    "cause": "index-out-of-bounds",
    "headline": "An index went out of range at line 5.",
    "explanation": "The code read index 5 past the end. Valid indexes are 0 to length - 1, so the usual culprits are a loop condition with `<=` instead of `<`, or reading `i + 1` on the last element.",
    "evidence": "Public test 1 (nums = [3, 7, 2, 9, 4]) threw ArrayIndexOutOfBoundsException: Index 5 out of bounds for length 5 at line 5",
    "line_hint": 5,
    "next_steps": [
      "Trace line 5 with the input from public test 1.",
      "Line 4 loops while the index is `<=` the length: that last step is one too far.",
      "Make sure empty and single-element inputs are handled first."
    ],
    "concept": "Array bounds and off-by-one errors",
    "confidence": "high"
  },
  "provider": "offline",
  "cached": false,
  "disclaimer": "Explanations are based only on the public tests and compiler output. Hidden test inputs are never shown to the AI or to you."
}
```
`cause` ∈ `compile-error | index-out-of-bounds | null-reference | arithmetic | number-format |
recursion-depth | time-limit | memory-limit | crash | wrong-answer | hidden-edge-case |
overflow | other`. Text fields may contain `` `code` `` spans (render as inline code, not
HTML). When only hidden tests failed, the cause is `hidden-edge-case`, confidence is `low`,
and the explanation suggests *kinds* of edge cases to try instead of naming an input.

#### `GET /api/v1/ai/usage` 🔒 → `200`
```json
{"used_today": 2, "daily_limit": 50, "remaining_today": 48, "provider": "offline"}
```

#### `GET /api/v1/me/ai-history` 🔒 → `200`
Query: `problem_slug`, `action` (`hint` | `review` | `explain_failure`), `page`, `page_size`.
Newest first. `response` holds the exact `content` (hints), `review` (reviews) or
`explanation` (failure explanations) originally returned.
```json
{
  "items": [{
    "id": "a59a489a-8699-4c5d-a588-bd14ea005967",
    "problem_slug": "two-sum", "problem_title": "Two Sum",
    "action": "review", "hint_level": null, "provider": "offline",
    "created_at": "2026-11-01T08:49:54.660919Z",
    "response": {"summary": "…", "complexity": {"time": "O(n^2)", "space": "O(1)"}, "issues": ["…"], "strengths": ["…"], "next_step": "…", "confidence": "medium"}
  }],
  "total": 2, "page": 1, "page_size": 1
}
```

### Interview review, retries and the review queue

- `GET /api/v1/interviews/{id}/review` 🔒 (finished interviews only; `409 interview_in_progress`
  otherwise): `{status_label, completed, elapsed_seconds, notices, items, overall, improvements,
  disclaimer, final_code, …}`. Built from stored data only: no evaluator runs on read. Items are
  questions (round) or transcript turns (coding) with recorded times; each round answer carries
  `dimensions` with a `status` of `evaluated | not_evaluated | not_applicable`. Improvements cite
  `evidence` (`item_key` of a question or turn, or `code` with a line).
- `POST /api/v1/interviews/{id}/questions/{index}/retries` 🔒 `{answer, source}` → `201`
  `Comparison`: the retry is a separate graded answer; the interview's answer is untouched.
  `GET …/comparison` returns `{original, retries, latest, comparable, comparability_note,
  improved, still_missing, newly_missing, score_change}`; `score_change` is null unless both were
  scored by the same evaluator and rubric version. Rounds only (`409` for coding interviews).
- `GET|POST /api/v1/me/reviews`, `POST /api/v1/me/reviews/{id}/snooze {days: 1|3|7}`,
  `DELETE /api/v1/me/reviews/{id}` 🔒: the spaced review queue. Items move along 1, 3, 7, 14, 30
  days only when the question is answered again (85+ moves up, below 70 resets to 1 day); every
  item says why it's due. Nothing is sent anywhere.

### Target roles ("Prepare for this role")

All under `/api/v1/targets` 🔒 and scoped to the owner (another user's id is a 404).

- `GET /targets`, `POST /targets` `{title, employer?, description (≤ 20,000 chars), track?,
  interview_date?, notes?}` → `201` with the full target. Requirements are extracted by rules
  (`app/services/jd_extract.py`); the text is never executed or treated as instructions.
- `GET /targets/{id}`: the target with `requirement_list` (each `{category, text, origin:
  explicit|inferred|user, quote, quote_in_description, skills, removed, coverage: {level:
  practised|some|limited|gap, label, …}, practice: [{kind, title, href, why}]}`),
  `next_activity`, `targeted_session` and `mock_interview` (`{title, scope, round}` for
  `POST /interviews`), `recent_attempts`, `experience`.
- `PATCH /targets/{id}` edits fields, `archived`, or `selected` (one active target); editing the
  description keeps requirements and attempts. `DELETE /targets/{id}` removes the target only.
- `POST /targets/{id}/extract` adds requirements found in the current description that aren't
  there yet. `POST /targets/{id}/requirements` adds one; `PATCH …/requirements/{rid}` corrects,
  re-maps (`skills` must be the career's), removes or restores.
- `POST|PUT|DELETE /targets/{id}/experience[/{eid}]`: your own examples, linkable only to this
  target's requirements. Targets, requirements and examples are in the data export and are
  deleted with the account.

### Question explorer, bookmarks and collections

- `GET /api/v1/careers/{slug}/explore?q=&difficulty=&kind=&skill=&sort=relevance|library&page=&page_size≤100`
  (public): `{track, career_title, items, total, page, page_size, facets, explanation,
  suggestions, sorts}`. Search covers titles, skills, tags, the career's name and the question
  text; an exact title match ranks first. `facets.difficulty|kind|skill` give, for each option,
  how many results choosing it would return with the *other* filters applied. Items carry
  `estimated_minutes: null` (the bank doesn't time questions; nothing is invented). Never
  contains personal data, even when a token is sent.
- `GET /api/v1/me/explore/{slug}` 🔒: the same plus `status=attempted|unattempted|bookmarked`,
  `sort=last_practiced|lowest_score`, and a `status` map (`best_score, attempts,
  last_practiced_at, bookmarked, collection_ids`) for the questions on the page. Sorts are stable,
  so pages never shuffle; there is no "recently added" or "personalized" order because the data
  doesn't support one.
- `GET /api/v1/me/bookmarks`, `PUT /api/v1/me/bookmarks {item_type: question|problem, track,
  ref_id}` (idempotent, 404 for items not in the library), `DELETE
  /api/v1/me/bookmarks?item_type=&track=&ref_id=` (idempotent; works for retired items) 🔒.
- Collections 🔒, private to the owner (another user's id is a 404): `GET|POST
  /api/v1/me/collections` (`GET` with `item_type, track, ref_id` adds `contains` to each),
  `GET|PATCH|DELETE /me/collections/{id}`, `POST /me/collections/{id}/items` (`409
  already_in_collection`; the unique constraint also settles races), `DELETE …/items/{item_id}`,
  `PUT …/order {item_ids}` (every id exactly once, else `400 invalid_order`), `PUT …/queue
  {position}` (start or move the practice queue; `409 empty_collection`), `PUT
  …/items/{item_id}/done {done}`. Items keep stable ids; an item that leaves the library comes
  back `available: false` with an `unavailable_reason` and is never swapped for another.
  `queue_done` is queue progress only; `practiced_since_added` comes from real answers or judged
  submissions. Limits: 50 collections, 200 items each. Bookmarks and collections are in the data
  export and deleted with the account.

### Learn mode

Units are authored in the repository ([docs/LEARN_CONTENT.md](LEARN_CONTENT.md)); no model runs
on these endpoints.

- `GET /api/v1/learn?track=` (public): `{track, career_title, units, coverage_note,
  careers_with_units}`. A career without units gets `units: []` and says so.
- `GET /api/v1/learn/units/{id}` (public): the full unit (objective, prerequisites, explanation,
  worked example, mistakes, exercise with `guided_steps` and a `solution`, check questions
  **without answers**, `pass_rule`, practice link, references with `url: null` when no link is
  recorded, review status, scope note, version and `changes`).
- `GET /api/v1/learn/related?track=&question_id=` or `?problem_slug=`: units that prepare for it.
- `GET /api/v1/me/learn?track=` 🔒 and `GET /api/v1/me/learn/units/{id}` 🔒: progress per unit
  (`versions_used, started, read, check_attempts, check_passed, passed_versions, practiced,
  practiced_evidence, events, next_action`). Reading progress also records `practiced` once a
  real answer/submission to the unit's practice item exists after the learner started.
- `POST /api/v1/me/learn/units/{id}/events {kind: started|read, version}` 🔒 and `POST
  …/check {version, answers: {question_id: option_index}}` 🔒 → `{passed, correct, total,
  results: [{id, chosen, correct, answer, explanation}], progress}`. Both are `409 unit_changed`
  (with `details.current_version`) when `version` isn't the current one. Every check attempt is
  kept; `check_passed` is recorded once per version. Learn events are in the data export and are
  deleted with the account.
- The practice plan may include a `learn` item (before the retry it prepares for) whose completion
  is a passed check after it was planned; reading alone never completes it.

### Notebook

All under `/api/v1/me/notes` 🔒; a note is only ever visible to its owner (anyone else gets 404).

- `GET /me/notes?q=&career=&source_type=question|problem|lesson|interview&source_id=&tag=&status=active|archived|all`
  → `{items, total, page, page_size, tags, careers, pinned_limit}`; pinned notes first, then most
  recently updated. Search covers titles, text, reflections and tags.
- `POST /me/notes {title, body, reflection, tags, source?: {type, id, track?, question_index?}, excerpt?, excerpt_kind?: quote|code}`
  → `201`. The source must exist (interviews must be yours); its id, version (when one exists)
  and title are stored, and `excerpt` is a snapshot. Bounds: title 200, body 20,000, reflection
  5,000, excerpt 4,000 characters, 12 tags.
- `GET|PATCH|DELETE /me/notes/{id}`. Text changes need `base_revision`; if the note changed since,
  the answer is `409 note_conflict` with `details.current` (the saved note) and nothing is
  overwritten. `pinned` (at most 5, `409 pin_limit`) and `archived` don't need a revision and
  don't conflict. `source.available` is false once the source leaves the library; the note stays.
- `DELETE` starts a 10-minute undo window (`{restorable_until}`); `POST /me/notes/{id}/restore`
  undoes it; afterwards the note is purged.
- `POST /me/notes/{id}/key-points` → `{points, method}`: a deterministic, non-AI helper that
  lists the note's own action or lesson sentences. Nothing is saved until the client sends them
  as `key_points` in a `PATCH`.
- Bodies are stored as untrusted text and never logged; the web app renders Markdown without HTML
  or images. Notes are in the data export and deleted with the account.

### Branching scenarios

Authored graphs ([docs/SCENARIOS.md](SCENARIOS.md)); no model is used.

- `GET /api/v1/scenarios?track=` and `GET /api/v1/scenarios/{id}` (public): role, objective,
  `minutes` (author's estimate), scope, version, `decisions`, `endings`, review, `validated:
  false`, references.
- `POST /api/v1/me/scenarios/{id}/attempts {mode: assessed|exploration, parent_id?}` 🔒: starts
  an attempt, or returns your in-progress assessed attempt (resume). `exploration` needs a
  finished `parent_id` and creates a separate attempt; the original is never changed.
- `GET /api/v1/me/scenario-attempts[?scenario_id=]` and `GET …/{attempt_id}` 🔒: the current node
  (choice options without their quality or feedback), recorded steps (with the authored rule for
  each decision and covered/missing points for written responses), and the `debrief` once
  finished (outcome, path, decisions with alternatives, strengths, references, disclaimer).
- `POST /api/v1/me/scenario-attempts/{attempt_id}/steps {node_id, choice_id?, text?}` 🔒: answers
  the current node; the server picks the next one from the graph. Repeating the last recorded
  step returns the attempt unchanged; any other node is `409 stale_step`; an unknown option is
  `400 invalid_choice`; finished attempts are `409 attempt_finished`; an attempt on an older
  scenario version is `409 scenario_updated` (kept, readable, not continuable). Attempts are
  owner-only, in the data export and deleted with the account.

### Practice plan

Deterministic rules over recorded evidence (`app/services/roadmap.py` documents them); no AI.

- `GET /api/v1/me/goals?track=` / `PUT /api/v1/me/goals` 🔒: every field optional
  (`specialty, experience: new|early|mid|senior, target_date, weekly_minutes, focus_areas,
  formats: written|voice|coding, confidence: {skill: 1-5}, setup_skipped`). Focus and confidence
  skills must belong to the career (`400 unknown_skill`); `coding` only for careers with coding
  problems (`400 no_coding`). Saving never changes recorded progress.
- `GET /api/v1/me/plan?track=&minutes=15` 🔒 returns the current plan version: `items` (each with
  `kind, skill, title, reason, completion, minutes, status: pending|done|skipped|replaced,
  evidence, href | round`), `changes` (why this version differs), `today` (`primary`,
  `follow_up`, `session_minutes`, `note`) sized to `minutes`, `progress`, and `assessment`
  (`self_reported`, `evaluated`, `coding` kept separate; `state: building_baseline |
  baseline_ready`). Reading the plan marks items done from evidence recorded after they were
  planned; completed work or changed goals produce a new version.
- `POST /api/v1/me/plan/items/{id}/skip | replace | reviewed` 🔒: skip records `skipped` (never
  done); replace swaps in another activity of the same kind and skill; `reviewed` is only for
  "review feedback" items (`409 not_self_reportable` otherwise). Closed items are `409`.
- Rounds started from the plan use `POST /interviews` with `purpose: "baseline"` (three questions:
  knowledge, behavioral, scenario) or `question_ids: [...]` (a targeted round).

### Activity, career analytics and resume

Derived from what is already recorded (problem opens, submissions, coaching, written answers and
interview sessions), so nothing is back-filled or counted twice. All scoped to the caller.

- `GET /api/v1/me/activity` 🔒 `?career=<slug|coding>&type=&status=&skill=&since=&until=&q=&page=&page_size=`
  returns `Page[ActivityItem]`: `{id ("<type>:<source id>"), type, occurred_at, career,
  career_title, title, detail, skills, status, status_label, score, session_id, target: {href,
  …ids}}`. `type` is `problem_opened | code_submission | coaching | written_answer | interview`;
  `status` is one of `opened, saved_not_judged, awaiting_judge, passed, failed,
  evaluation_unavailable, scored, completed, in_progress, expired, abandoned`. A submission is
  `saved_not_judged` when the deployment has no judge. A skill filter leaves interviews out (they
  span skills).
- `GET /api/v1/me/activity/facets` 🔒 `?career=` gives filter options with counts; `skills` is
  filled for one career (coding topics, or the career's skills, tools and competencies).
- `GET /api/v1/me/careers/{slug}/analytics` 🔒 `?since=&until=` works for any career, not just the
  user's current one: questions practised, answers, strong questions, per-skill coverage (with
  `average_best_score: null` when not practised), question types, interview outcomes, weekly
  score trends **per evaluator and rubric version** (never merged), daily counts and
  `definitions` for every metric.
- `GET /api/v1/me/resume` 🔒 returns the interview in progress (with its real
  `seconds_remaining`), the latest submitted-but-unsolved problem and the last answered question.
- `GET /api/v1/me/ai-history/{id}` 🔒 returns one saved hint, review or failure explanation.

Problem opens are recorded at most once per user, problem and UTC day, enforced by a unique key
so concurrent requests can't double-count.

### Mock interviews

A timed interview with an AI interviewer that moves through five phases:

```
clarify → approach → coding → complexity → wrap_up → (phase null: interviewer has wrapped up)
status: in_progress → completed (finish) | expired (deadline passed) | abandoned (end early)
```

- **One active interview per user.** Starting another returns `409 interview_in_progress` with
  `details.interview_id`, so the UI can offer "Resume".
- **Server-side clock.** `deadline_at` is authoritative. When it passes, the next read or write
  closes the interview as `expired` and evaluates it. Clients show a countdown from
  `deadline_at` and re-fetch at zero.
- **Phases only move forward.** The interviewer advances when the candidate covers the phase,
  and a phase auto-advances after 3 answers so a session can't get stuck.
- **Cost.** Each interviewer reply (including the opening) uses one request from the daily AI
  budget. The final evaluation always runs: if the budget is used up, the offline scorer grades
  it, so finished work never goes without feedback.
- **Limits.** Answers are 1–4,000 characters; code up to 20,000; 30 answers per interview.

#### `POST /api/v1/interviews` 🔒 → `201`
```json
{"problem_slug": "two-sum", "duration_minutes": 30}
```
`problem_slug` is optional (omit it to use the learner's top recommendation);
`duration_minutes` is 10–60 (default 30).
```json
{
  "id": "f4f619a9-11a3-4ed9-84eb-1c11998e0b0e",
  "status": "in_progress",
  "phase": "clarify",
  "phase_index": 0,
  "phase_guide": "Restate the problem and ask clarifying questions about inputs, outputs and edge cases.",
  "problem": {"slug": "two-sum", "title": "Two Sum", "difficulty": "easy"},
  "duration_seconds": 1800,
  "started_at": "2026-11-01T09:35:21.103676Z",
  "deadline_at": "2026-11-01T10:05:21.103676Z",
  "ended_at": null,
  "seconds_remaining": 1799,
  "candidate_turns_remaining": 30,
  "provider": "offline",
  "turns": [{
    "seq": 0, "role": "interviewer", "phase": "clarify",
    "content": "Hi, thanks for joining. Today we'll work on \"Two Sum\" and we have about 30 minutes. …",
    "created_at": "2026-11-01T09:35:21.110668Z"
  }],
  "final_code": null,
  "evaluation": null
}
```

#### Question rounds (`"kind": "questions"`)

A mock interview made of one career's written questions (any career, including those without
coding). It shares the coding interview's rules: one active interview per user (of either kind),
a server-side deadline, `abandon`, and the same history list. It makes no AI calls.

```json
{"kind": "questions", "track": "registered-nurse", "difficulty": "easy", "duration_minutes": 15}
```
`track` defaults to the user's career; `difficulty` to `easy`. The server picks five questions:
one of every kind the level has (easy: motivation, knowledge, behavioral; medium and hard:
scenario, behavioral, leadership), unanswered ones first, in interview order. The response has
`kind: "questions"`, `problem: null`, `track`, `career_title`, and
`questions: [{index, id, title, prompt, kind, difficulty, status, answer}]` where `status` is
`current | pending | answered | skipped`, plus `round_summary: {answered, skipped, unanswered,
average_score, focus}`. Each question asked and answered is a turn in `turns`.

- `POST /api/v1/interviews/{id}/answers` `{"question_index": 0, "answer": "…", "source": "voice"}`
  grades the answer (saved as an ordinary practice answer) and asks the next question; after the
  last one the round is `completed`. **Idempotent per question:** a repeat for an answered
  question returns the current state without grading again. Answering a later question first is
  `409 question_not_current` with `details.current_question_index`. Counts toward the hourly
  practice-answer limit (`429`).
- `POST /api/v1/interviews/{id}/skip` `{"question_index": 1}` records a skip (never an answer).
- `POST /api/v1/interviews/{id}/abandon` ends early: `abandoned`, unanswered questions stay
  unanswered. `finish` on a round with questions left is `409 questions_remaining`.
- `source` is `typed | voice | mixed` and is recorded for review only; it never affects scoring.
  Audio is never sent to the server.

**Simulated engagement.** Candidate turns (both kinds) carry `engagement: {state, label, reason,
evidence}` with `state` one of `not_enough_evidence | more_detail | following | explore_further`.
It is computed deterministically from the answer text only (topic relevance, specific details,
rubric coverage, "I" vs "we" for behavioral questions; for coding, the phase's goal: clarifying
questions, a named approach, a stated Big-O, a walked-through test). It isn't a real person's
opinion and doesn't predict hiring decisions. See `app/services/engagement.py`.

#### `POST /api/v1/interviews/{id}/messages` 🔒 → `200`
```json
{"message": "Can the array be empty or contain duplicates?", "code": "class Solution { … }", "source": "typed"}
```
`code` (optional) is the current editor content; the latest version is kept as `final_code`.
`source` (optional, `typed | voice | mixed`) is recorded with the turn for review.
Returns the full interview. The last two turns are the candidate's message and the
interviewer's reply:
```json
{"phase": "approach", "phase_index": 1, "candidate_turns_remaining": 29,
 "turns": ["…", {"seq": 1, "role": "candidate", "phase": "clarify", "content": "Can the array be empty or contain duplicates?"},
                 {"seq": 2, "role": "interviewer", "phase": "approach",
                  "content": "Good questions. You can rely on the constraints, e.g. 2 <= nums.length <= 10^4. How would you approach this? …"}]}
```
Errors: `409 interview_closed`, `400 turn_limit_reached`, `429 rate_limited`, `404`.

#### `POST /api/v1/interviews/{id}/finish` 🔒 → `200`
Optional body `{"code": "…"}`. Closes the interview and returns it with `evaluation`. Calling it
again returns the same result. `POST …/abandon` works the same way, with `status: "abandoned"`.
```json
{
  "scores": [
    {"dimension": "problem_solving", "score": 1, "evidence": "No working code was written during the session."},
    {"dimension": "communication", "score": 3, "evidence": "About 8 words per answer across 1 answer; asked clarifying questions."},
    {"dimension": "code_quality", "score": 1, "evidence": "No code beyond the starter template."},
    {"dimension": "complexity_analysis", "score": 1, "evidence": "Time/space complexity was never stated in Big-O terms."},
    {"dimension": "testing", "score": 2, "evidence": "Mentioned tests or edge cases once."}
  ],
  "overall": "needs_work",
  "summary": "Strongest area: communication. Biggest opportunity: problem solving.",
  "strengths": ["…"],
  "improvements": ["Name a concrete data structure and the single pass you'd make before coding.", "…"],
  "confidence": "low"
}
```
Scores are 1–4 (`1` needs work, `2` developing, `3` solid, `4` strong). `overall` ∈
`needs_work | developing | solid | strong`. Every dimension appears exactly once, in this
order: `problem_solving, communication, code_quality, complexity_analysis, testing`.

#### `GET /api/v1/interviews` 🔒 → `200`
```json
{"items": [{"id": "f4f6…", "status": "completed", "problem": {"slug": "two-sum", "title": "Two Sum", "difficulty": "easy"},
            "started_at": "2026-11-01T09:35:21.103676Z", "ended_at": "2026-11-01T09:35:21.144553Z",
            "overall": "needs_work", "average_score": 1.6}],
 "total": 1, "page": 1, "page_size": 20}
```

### Careers

Interview questions are generated from the career catalog (`backend/app/careers/`), so a question
id like `m-walk-3` always means the same question for a given career.

| Method & path | Auth | Description |
|---|---|---|
| `GET /api/v1/careers` | none | All careers: `slug, title, category, summary, has_coding, question_count` (300) |
| `GET /api/v1/careers/{slug}/questions` | optional | `?difficulty=easy\|medium\|hard&q=…&page&page_size` (≤200). Signed in: each item has your `best_score` |
| `GET /api/v1/careers/{slug}/questions/counts` | none | `{easy, medium, hard}` matching `?q=` (the library tab badges) |
| `GET /api/v1/careers/{slug}/questions/{id}` | optional | Prompt, kind, tips, `rubric_labels` |
| `POST /api/v1/careers/{slug}/questions/{id}/answers` | required | `{answer}` (1-6000 chars) → `201` feedback: `score` 0-100, `rating`, `summary`, `points[{label, covered, advice}]`, `notes`, `outline`, `word_count`, `coach`. Limited to `PRACTICE_ANSWERS_PER_HOUR` (default 60) per user; `429 rate_limited` after that |
| `GET /api/v1/careers/{slug}/questions/{id}/answers` | required | Your past answers, newest first (max 20) |
| `GET /api/v1/careers/{slug}/progress` | required | `{answered, strong, by_difficulty, total_questions}` |

The user's job is `career_track` on the user object. Set it with `career_track` on
`POST /auth/register`, `/auth/guest` or `/auth/upgrade`, or change it with `PATCH /auth/me`
(only the fields you send change). Unknown slugs are a `422`.

`GET /api/v1/problems` also takes a keyword `q` ranked by relevance, and
`GET /api/v1/problems/counts` gives per-difficulty totals for the same `topic`/`q`.

### Progress

#### `GET /api/v1/me/progress` 🔒 → `200`
One call returns everything the dashboard needs.
```json
{
  "total_problems": 12, "attempted": 1, "solved": 0,
  "submissions": 1, "accepted_submissions": 0, "acceptance_rate": null,
  "hints_used": 1, "reviews_requested": 1,
  "current_streak_days": 1, "longest_streak_days": 1,
  "last_active_at": "2026-11-01T08:49:54.661188Z",
  "by_topic": [{"topic": "arrays", "total_problems": 6, "attempted": 1, "solved": 0}, "…"],
  "by_difficulty": [{"difficulty": "easy", "total_problems": 10, "solved": 0}, {"difficulty": "medium", "total_problems": 2, "solved": 0}],
  "problems": [{"slug": "two-sum", "status": "attempted", "last_submission_status": "QUEUED", "submissions": 1, "hints_used": 1}, "…"],
  "activity": [{"day": "2026-10-05", "events": 0}, "… 28 days, oldest first …", {"day": "2026-11-01", "events": 4}],
  "weakest_topics": ["arrays", "hash-maps"],
  "recommended_next": ["two-sum", "find-largest-number", "contains-duplicate"]
}
```
- `problems[].status` ∈ `solved | attempted | in_progress | not_started`. `in_progress` means
  the problem was opened or a hint/review was requested but nothing was submitted.
- `acceptance_rate` is `PASSED / judged` submissions, or `null` when nothing has been judged.
- `activity` always has exactly 28 entries, ready for a contribution-style heatmap.
- A streak counts consecutive UTC days with activity, and stays alive until the end of the
  day after the last active day.

#### `GET /api/v1/me/recommendations?limit=5` 🔒 → `200`
Every recommendation has a human-readable `reason` and a `kind`:
`retry` (attempted, not solved) · `weak_topic` · `next_step` (difficulty ladder).
```json
[
  {"slug": "two-sum", "title": "Two Sum", "difficulty": "easy", "topics": ["arrays", "hash-maps"],
   "reason": "You've submitted this once without a pass. Finish it while it's fresh.", "kind": "retry"},
  {"slug": "find-largest-number", "title": "Find Largest Number", "difficulty": "easy", "topics": ["arrays", "iteration"],
   "reason": "Builds your weakest area so far: arrays.", "kind": "weak_topic"}
]
```

---

## Environment variables

All configuration is environment variables (or a `.env` file; see
[`.env.example`](../.env.example)). Secrets are only ever read on the server.

| Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `development` | `development`, `test` or `production`. Production refuses to start with the default `SECRET_KEY` or a `*` CORS origin. |
| `LOG_LEVEL` | `INFO` | Python log level for the JSON logs. |
| `DATABASE_URL` | `postgresql+psycopg://codecoach:codecoach@localhost:5432/codecoach` | SQLAlchemy URL. `sqlite:///./codecoach.db` works for a quick start. |
| `AUTO_MIGRATE` | `true` | Create tables and seed problems on startup. Set `false` when migrations run separately (Docker Compose, production). |
| `SECRET_KEY` | insecure dev value | **Secret.** Signs JWTs. At least 32 characters; required in production. |
| `ACCESS_TOKEN_TTL_MINUTES` | `15` | Access-token lifetime (5–1440). |
| `REFRESH_TOKEN_TTL_DAYS` | `30` | Refresh-cookie lifetime; it rotates on every use (1–90). |
| `REFRESH_COOKIE_SECURE` | unset | Unset: `Secure` in production only. `false` is refused in production. |
| `ALLOW_GUEST_SESSIONS` | `true` | Enables `POST /auth/guest`. |
| `AUTH_RATE_LIMIT_PER_MINUTE` | `10` | Per-IP attempts per minute for register, login, guest, upgrade, password change and password reset. |
| `RATE_LIMIT_BACKEND` | `database` | `database`: counters shared by every API replica (sliding window, atomic upsert). `memory`: one process only. |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1` | (uvicorn) Proxies whose `X-Forwarded-For` is trusted. Set it to your load balancer's address, or every user shares the proxy's IP for rate limiting. Untrusted headers are ignored, so they can't be spoofed. |
| `GUEST_RETENTION_DAYS` | `30` | Guest accounts with no activity for this long are deleted with their data (worker, daily; or `python -m app.cli prune-guests`). `0` keeps them. |
| `APP_BASE_URL` | `http://localhost:5173` | Public web-app URL used in emailed links. Must be `https` in production. |
| `EMAIL_BACKEND` | `console` | `console` (log), `file` (write to `EMAIL_FILE_DIR`, for tests) or `smtp`. Production requires `smtp`. |
| `EMAIL_FROM`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_STARTTLS` | –, –, `587`, –, –, `true` | SMTP delivery settings. |
| `PASSWORD_RESET_TTL_MINUTES` | `30` | Lifetime of a reset link. |
| `EMAIL_VERIFICATION_TTL_HOURS` | `48` | Lifetime of a verification code and link. |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated browser origins allowed to call the API. |
| `AI_PROVIDER` | `offline` | `offline` (curated hints + static analysis, free) or `anthropic` (Claude). |
| `ANTHROPIC_API_KEY` | — | **Secret.** Required when `AI_PROVIDER=anthropic`. |
| `ANTHROPIC_MODEL` | `claude-opus-5-5` | Model ID used for hints and reviews. |
| `ANTHROPIC_EFFORT` | `low` | `low`, `medium` or `high`. Higher is deeper and more expensive. |
| `AI_DAILY_REQUEST_LIMIT` | `50` | AI calls per user per rolling 24 hours. |
| `AI_MAX_CODE_CHARS` | `12000` | Code beyond this length is truncated before reaching a model. |
| `EXECUTION_ENABLED` | `false` | Judge submissions in the gVisor runner (requires `RUNNER_TOKEN` and the judge services) |
| `RUNNER_URL` | `http://localhost:8100` | Runner service address (used by the worker) |
| `RUNNER_TOKEN` | — | **Secret.** Shared API↔runner bearer token, ≥ 32 characters |
| `JUDGE_TIME_LIMIT_S` | `15` | Wall-clock budget per submission |
| `SUBMISSION_RATE_LIMIT_PER_MINUTE` / `MAX_PENDING_PER_USER` / `MAX_QUEUE_DEPTH` | `6` / `2` / `200` | Admission control |
| `JUDGE_MAX_ATTEMPTS` / `JUDGE_STALE_AFTER_S` | `2` / `120` | Infrastructure retries / crashed-worker recovery |
| `EMBEDDED_WORKER` | `false` | Run the worker inside the API process (local dev and e2e only) |
| `MAX_SOURCE_CHARS` | `20000` | Maximum submission size. |
| `METRICS_ENABLED` | `true` | Serves Prometheus metrics at `/metrics`. |
| `POSTGRES_PASSWORD` | `codecoach` | Used by `docker-compose.yml` only. |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Frontend build-time API URL. **Public**: never put secrets in `VITE_*`. |

---

## Running locally

### Option A: Docker (closest to production)
```bash
cp .env.example .env          # optional; defaults work for local dev
docker compose up --build     # Postgres + migrations + seed + API on :8000
```

### Option B: Python only
```bash
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
# Use your own Postgres, or SQLite for a zero-setup run:
export DATABASE_URL=sqlite:///./codecoach.db
uvicorn app.main:app --reload                          # http://localhost:8000/docs
```

### Smoke test from the command line
```bash
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/guest | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s localhost:8000/api/v1/problems/two-sum | head -c 300
curl -s -X POST localhost:8000/api/v1/ai/hint -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"problem_slug":"two-sum","level":1}'
```

### Tests
```bash
cd backend
pytest                                   # SQLite
TEST_DATABASE_URL=postgresql+psycopg://codecoach:codecoach@localhost:5432/codecoach_test pytest
python scripts/verify_reference_solutions.py   # needs a JDK; checks every seeded test case
```
