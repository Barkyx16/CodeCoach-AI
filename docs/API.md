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
   before retrying the request. Optionally send `X-Refresh-Attempt: <random key>` (22-64 URL-safe
   characters) and keep the key until you get an answer: if the response is lost, presenting the
   same cookie with the same key within 2 minutes returns the same new session instead of
   `refresh_race`/`refresh_reused` (see SECURITY.md §3).
4. **Refresh errors** (`401`): `invalid_refresh` (missing, expired or revoked: sign in again);
   `refresh_reused` (an already-used token was presented later, so it was copied: the whole
   family was revoked); `refresh_race` (another request used the same cookie within 30 s:
   wait briefly and retry, a few times at most, and the browser will send the new cookie). `403 csrf_rejected` means the custom
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
| 401 | `invalid_refresh` / `refresh_reused` / `refresh_race` | Refresh cookie missing/expired/revoked, replayed (family revoked), or another request using it right now (retry a few times, with a short wait) | Sign in again / retry |
| 403 | `csrf_rejected` | `/auth/refresh` without `X-Requested-With: codecoach` or from an unknown `Origin` | (client bug) |
| 401 | `invalid_credentials` | Wrong email/password (deliberately identical for unknown emails) | Form error |
| 404 | `not_found` | Unknown route, problem, or a resource owned by someone else | Not-found state |
| 405 | `method_not_allowed` | Wrong HTTP method | (client bug) |
| 409 | `email_taken` | Registration with an existing email | Form error on email |
| 409 | `hint_locked` | Hint level requested before the previous one (`details.next_unlockable_level`) | Disable later hint buttons |
| 409 | `interview_in_progress` | Starting an interview while one is active, from any tab or device (`details.interview_id`, and `details.interview`: its summary with progress, time left and last activity). Two Starts at once make one interview: the database enforces it | Offer "Resume" with that context |
| 409 | `interview_closed` | Sending a message to a finished, expired or abandoned interview (`details.status`) | Show the results view |
| 409 | `interview_advanced` | A coding message sent with `after_seq` older than the transcript: another tab or device moved the interview on (`details.turns`, `details.status`). Nothing was appended, nothing was asked of the AI | Load the latest; keep the unsent text |
| 409 | `question_answered_elsewhere` | A round answer to a question that already has a different answer or a skip (`details.question_index`, `details.skipped`, `details.current_question_index`). The same text again is a retry: 200 | Show the next question; keep the unsent text visible |
| 400 | `turn_limit_reached` | Interview message cap reached (`details.max_candidate_turns`) | Prompt to finish |
| 409 | `not_judged` | Explain-failure on a submission that's still queued or running | Wait for the verdict |
| 409 | `not_failed` | Explain-failure on a submission that passed | Hide the button |
| 409 | `judge_error` | Explain-failure on an `INTERNAL_ERROR` (the judge's fault, not the code's) | Suggest resubmitting |
| 409 | `content_retired` | Answering, retrying or submitting retired content (`details.reason`) | Keep it readable; disable answering |
| 429 | `submission_pending` | A previous submission is still being judged (`details.max_pending`; `details.pending_submission_id`, `problem_slug` and `mode` name the caller's own oldest pending one). No wait | Show that submission's status, not a new submit |
| 503 | `judge_busy` | The judge queue is full; nothing was saved. `Retry-After` (and `details.retry_after_seconds`) only when the judge finished something in the last 5 minutes: the average gap between those completions, 5–120 s. A retry hint, not a completion time | Count down when given; otherwise check `GET /capabilities` |
| 503 | `judge_unavailable` | `mode: run` while the judge is unreachable, not ready or misconfigured (Submit still queues). No wait | Check `GET /capabilities`; offer Submit |
| 503 | `execution_disabled` | `mode: run` on a deployment without code execution (check `GET /capabilities` first). No wait | Hide the Run button |
| 422 | `validation_error` | Body or query failed validation. `details` is a list of `{loc, msg, type}` | Map `loc[-1]` to form fields |
| 429 | `rate_limited` | Auth attempts or the daily AI budget exceeded (`details.retry_after_seconds` or `details.daily_limit`) | Show a cooldown |
| 429 | `ai_request_in_progress` | Another of this account's AI requests is still running (`Retry-After: 2`) | Wait, then retry |
| 409 | `idempotency_key_reused` | A `client_request_id` already used for a different request | (client bug) |
| 500 | `internal_error` | Unexpected server error (logged with the request id) | Generic error + request id |
| 503 | — | `/health/ready` only, when the database is unreachable or its schema is older than this code needs | — |

**Waits.** A 429, and a 503 `server_busy` or `database_unavailable`, carry `Retry-After` in
seconds. Where the error has one, `details.retry_after_seconds` gives the same wait more precisely.
The header is exposed to browser pages on other origins (CORS `Access-Control-Expose-Headers`), so
a page can count it down. A client should also accept the HTTP-date form, which proxies send, and
read it against the response's `Date` header (also exposed). Of the judge's 503s, only
`judge_busy` can carry a wait, and only when the server can justify one; `judge_unavailable` and
`execution_disabled` never do. A refused submission (429 or 503) saved nothing: its key isn't used
up, and the same key may be sent again later.

**Lost responses.** A request with a `client_request_id` can be sent again after its response was
lost, and it isn't done twice. Which writes are keyed and which aren't:
[RECOVERY.md](RECOVERY.md).

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
| GET | `/api/v1/demo` | – | Demo servers only (404 otherwise): the fictional sample learners and their labelled example answers (docs/DEMO.md) |
| POST | `/api/v1/auth/register` | – | Create account → token |
| POST | `/api/v1/auth/login` | – | Log in → token |
| POST | `/api/v1/auth/refresh` | cookie | New access token from the refresh cookie (rotates it) |
| POST | `/api/v1/auth/upgrade` | 🔒 | Turn the current guest into a full account, keeping its data |
| POST | `/api/v1/auth/verify-email` | – | Confirm an email with the emailed link token (says why a link doesn't work) |
| GET | `/api/v1/auth/verify-email/status` | 🔒 | Where your code went (masked), what became of the email, when you can resend |
| POST | `/api/v1/auth/verify-email/code` | 🔒 | Confirm your email with the emailed 6-digit code |
| POST | `/api/v1/auth/verify-email/resend` | 🔒 | Send a new code and link |
| POST | `/api/v1/auth/email` | 🔒 | Change your email (needs your password; waits for the new address's code) |
| DELETE | `/api/v1/auth/email/pending` | 🔒 | Cancel a pending change of email |
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
| GET | `/api/v1/careers/{slug}/questions/{question_id}/follow-up` | 🔒 | A reviewed follow-up question after repeated practice (docs/FOLLOW_UPS.md) |
| GET | `/api/v1/me/careers/{slug}/analytics/attempts?since=&until=&offset=&limit≤100` | 🔒 | Every answer in an analytics range: in the trend or why not, each with its comparison with the answer before it (docs/COMPARING_ATTEMPTS.md) |
| POST | `/api/v1/me/attempt-conditions` | 🔒 | The in-app help shown before each of up to 50 submissions and answers (docs/ATTEMPT_CONDITIONS.md) |
| POST | `/api/v1/ai/hint` | 🔒 | Progressive hint |
| POST | `/api/v1/ai/review/preview` | 🔒 | What a review would send, exactly (no coach call, no budget) |
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
Readiness probe: checks the database connection and how its migration revision relates to this
code. `200` when ready, `503` when not.

- `schema` is `current` when the database is at this code's migration head.
- It is `behind` (`503`) when the database is at an older revision this code knows, so the
  migration hasn't run yet. This code would fail on the columns the migration adds.
- It is `newer` when the database is at a revision this code doesn't know, such as an
  application revert onto an expanded schema (supported while migrations are additive).
- It is `unmanaged` when there is no migration ledger (tables made by `create_all` in
  development and tests).
- It is `unknown` when this code's migrations couldn't be read.

No revision id is shown.
```json
{"status": "ok", "checks": {"database": "ok", "schema": "current"}}
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
New accounts (registration or guest upgrade) and requested new emails get one email containing
**both** a 6-digit code and a link (`APP_BASE_URL/verify-email#token=…`). `UserOut.email_verified` reports
the state. Each send supersedes the previous code and link; at most one per minute per account.

- `POST /api/v1/auth/verify-email/code` 🔒 `{"code": "123456"}` → `200 UserOut`. Five wrong codes
  kill that code (`400 too_many_attempts`); otherwise `400 invalid_verification_code` with
  `details.attempts_left`. Codes are stored as HMAC-SHA256 keyed with the server secret.
- `POST /api/v1/auth/verify-email` `{"token": "…", "other_account_ok": false}` → `200 VerifyLinkOut`
  (no sign-in needed, so the link works on another device). Send the session's bearer token if
  there is one:
  - the account's own session gets `{"account": "this", "user": UserOut, …}`. Anyone else gets
    `account` (`signed_out` or `other`), `email_masked` and `changed_email`, nothing more about the
    account. (Before Volume 7 this returned `UserOut` to anyone holding the link.)
  - A link that can't be used: `400 invalid_verification_token`, with `details.reason` one of
    `malformed`, `unknown`, `expired`, `superseded` (a newer email replaced it), `already_verified`,
    `address_changed` (the change it was for was cancelled or replaced), or `stopped` (too many wrong
    codes). `details.account` says whose link it was: `this`, `other`, `signed_out`, or `unknown`.
    Only the holder of the link (a 256-bit secret) can ask, so this reveals nothing about other
    accounts.
  - A usable link for a different account than the signed-in one: `409
    verification_link_other_account` with `details.link_for` (masked), and nothing changes. Sent
    again with `other_account_ok: true`, it confirms that account's address. This session is
    unchanged, and gets no details of that account.
- `GET /api/v1/auth/verify-email/status` 🔒 → `VerificationStatusOut`, for the signed-in owner only:
  - `state`: `pending`, `verified`, or `not_applicable` (guests). `address_masked` (`a•••e@example.com`:
    the domain shows, so a typo there is visible). `changing_email`.
  - `delivery.state`: what became of the latest email, in terms the outbox can back up: `queued`,
    `retrying` (with `next_try_at`), `sent_to_provider` (the mail server accepted it, which isn't proof
    of inbox delivery), `kept_locally` (a development server printed or saved it), `failed`, or
    `unknown` (no record). There is no "delivered". No SMTP code, host or error class is included.
  - `transport` (`smtp`, `console`, `file`). `code_expires_at` and `code_tries_left`, for the newest
    code, null when none works. `resend_available_in_seconds`, the server's cooldown.
- `POST /api/v1/auth/verify-email/resend` 🔒 → `202`, with the address masked in `message`. `429
  resend_cooldown` (with `Retry-After`), `409 already_verified`, `409 not_applicable` (guests).
- `POST /api/v1/auth/email` 🔒 `{"new_email": "…", "password": "…"}` → `200 UserOut`. Nothing
  changes yet: `pending_email` holds the new address and a code and link go there. A verified
  current address also gets a notice. The address changes when that code
  (`/verify-email/code`, signed in) or link (`/verify-email`) is used, and the old address is told.
  `401 invalid_credentials`, `409 email_taken`, `409 same_email` (which also cancels a pending
  change). A new request replaces a pending one.
- `DELETE /api/v1/auth/email/pending` 🔒 → `200 UserOut` with `pending_email: null`. Codes and links
  sent to that address stop working. A password reset or change also cancels it.
- Confirming a pending address that another account took meanwhile: `409 email_taken`, and the
  change is cancelled.

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

`GET /api/v1/capabilities` (public) → `{execution_enabled, ai_provider, execution, guest_retention_days, ui_telemetry, emails_delivered, answer_request_keys, demo_mode}`. On a demo server (`DEMO_MODE`), registration, guest upgrade, password reset, email change and verification emails answer 403 `demo_mode`.
`execution` is `{state: ready|unavailable|not_configured, reason, message, run_available,
submit_mode: judged|queued_until_available|saved_only, checked_at, setup_help}` from an
authenticated runner probe (cached 15 s) plus a check that the queue is moving; `setup_help` is null
in production. See [docs/REMOTE_JUDGE.md](REMOTE_JUDGE.md).

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

> **Idempotency:** send a `client_request_id` (8–64 characters, `[A-Za-z0-9_-]`) with each new
> submission and reuse it when retrying after a network error: the same id returns the original
> submission (`409 idempotency_key_reused` if the body differs). **Run while the judge is
> unavailable** is refused with `503 judge_unavailable`; Submit still queues. The web client polls
> every 1.5 s, every 5 s after a minute, and stops after 15 minutes.

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
(a previous submission is still being judged; it names that submission), `503 judge_busy` (global
queue full; a measured wait when one can be justified). An account's submissions are admitted one
at a time on PostgreSQL, so two tabs can't both pass the pending check.
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

`client_request_id` (optional, 8–64 of `A-Za-z0-9_-`, the same on `/ai/review`):
- One key per request. Sent again with the same key, because its response was lost, a request gets
  the first answer back. There is no second provider call and no second use of the daily budget,
  even if the budget has run out since.
- The same key for a different action, problem or level is `409 idempotency_key_reused`.
- Without a key (older clients), every request is a new one.

A spent budget is `429 rate_limited` and another request still running is `429
ai_request_in_progress`. Both carry `details.retry_after_seconds` and `Retry-After`.
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
told the verdict is authoritative and must never contradict it. `share_verdict: false` leaves the
verdict out. `approved_context` (the `context_fingerprint` from `POST /api/v1/ai/review/preview`,
same body without the key) sends the review only if the material rebuilt now is exactly what was
previewed; otherwise `409 context_changed` with the fresh preview in `details.preview`, and nothing
is sent (docs/COACH_CONTEXT.md).
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
  re-maps (`skills` must be the career's), removes or restores, versioned as below.
- Versions (docs/REQUIREMENT_VERSIONS.md): each requirement has `version`; the target has
  `requirements_revision`, `action_links` (accepted improvements practising a requirement, each
  `{action_id, title, requirement_id, linked_version, current_version, status, label,
  reused_from}`), and each example's `requirement_links` say the version it was linked to.
  `POST …/requirements/revision/preview` `{expected_revision, items: [{id|null, category, text,
  removed}], same_as: [{index, requirement_id}]}` → `{summary, counts, changes, suggestions,
  revision}` (nothing stored); `PUT …/requirements` saves the same body (`409 stale_revision`
  with `details.current`, the saved target, when the set changed since); `GET
  …/requirements/{rid}/history` lists its recorded versions. `POST
  …/experience/{eid}/requirements/{rid}/reuse` and `POST …/actions/{aid}/requirements/{rid}/reuse`
  move a link to the current wording, recorded as a reuse.
- `PUT /targets/{id}/experience/{eid}` takes an optional `expected_revision` (the story's revision, `ExperienceOut.revision`): if the story changed since, `409 stale_revision`, as in the story bank.
- Each requirement link has `story_freshness` (docs/STORY_FRESHNESS.md): whether the story changed since the link was made, apart from the requirement's own version. `POST /targets/{id}/experience/{eid}/review {reviewed_revision, decision: refresh|keep, requirement_ids}` → the target: one decision for those links, recorded once; `409 source_changed` if the story moved on; a link the story doesn't have, or another account's story, is `404`.
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
- `POST /me/notes {title, body, reflection, tags, source?: {type, id, track?, question_index?}, excerpt?, excerpt_kind?: quote|code, client_request_id?}`
  → `201`. A repeat with the same `client_request_id` (unique per account) returns the note the
  first one made, so an autosave retry after a lost response creates nothing twice. The source must exist (interviews must be yours); its id, version (when one exists)
  and title are stored, and `excerpt` is a snapshot. Bounds: title 200, body 20,000, reflection
  5,000, excerpt 4,000 characters, 12 tags.
- `GET|PATCH|DELETE /me/notes/{id}`. Text changes need `base_revision`; if the note changed since,
  the answer is `409 note_conflict` with `details.current` (the saved note) and nothing is
  overwritten. `pinned` (at most 5, `409 pin_limit`) and `archived` don't need a revision and
  don't conflict. `source.available` is false once the source leaves the library; the note stays.
- `DELETE` starts a 10-minute undo window (`{restorable_until}`); `POST /me/notes/{id}/restore`
  undoes it; afterwards the note is purged.
- `GET /me/notes/{id}/archive-preview` → `Impact`; `POST /me/notes/{id}/archive`
  `{expected_fingerprint, client_request_id?}` → `LifecycleOutcome` (archived and unpinned; a
  changed scope is `409 impact_changed`). Setting `archived` with `PATCH` does the same change
  (docs/LIFECYCLE.md).
- `POST /me/notes/{id}/key-points` → `{points, method}`: a deterministic, non-AI helper that
  lists the note's own action or lesson sentences. Nothing is saved until the client sends them
  as `key_points` in a `PATCH`.
- Bodies are stored as untrusted text and never logged; the web app renders Markdown without HTML
  or images. Notes are in the data export and deleted with the account.

### Sharing an answer for feedback

Owner endpoints under `/api/v1/me/shares` 🔒 (anyone else's share is a 404). The security and
retention model is in [SHARING.md](SHARING.md). Every response is `Cache-Control: no-store`,
`X-Robots-Tag: noindex, nofollow`, `Referrer-Policy: no-referrer`.

- `POST /me/shares/preview {answer_id, sentences?: [int] | null, include_ai_feedback, include_followup, note}`
  → `{source_sentences, has_followup, view}`. `view` is exactly what a reviewer will see. Errors:
  `404` (not your answer), `409 interview_in_progress`, `400 empty_selection | unknown_sentence`.
- `POST /me/shares {…selection, expires_in_days: 1|7|30, acknowledge_link_access: true}` → `201
  {share, token, path}`. `path` is `/shared#t=<token>`; the token is returned **only here** (only
  its SHA-256 is stored). `acknowledge_link_access` must be true (`400 acknowledgement_required`).
  At most 50 working links per account (`409 share_limit`); creation is rate-limited per user.
- `GET /me/shares?answer_id=` → summaries (status `active | closed | revoked | expired`, counts).
- `GET /me/shares/{id}` → the snapshot, feedback, `source_changed`, `source_missing`.
- `POST /me/shares/{id}/close | reopen | revoke`; `POST /me/shares/{id}/link` replaces the link
  (old one stops working; new token returned once); `DELETE /me/shares/{id}` removes the share,
  snapshot and feedback.
- `PUT /me/shares/{id}/feedback/{fid}/useful {useful}`, `DELETE /me/shares/{id}/feedback/{fid}`.

Link holders (no account needed; a signed-in reviewer is named as such). The secret is always in
the JSON body, never a URL:

- `POST /shared/open {token}` → `{status: active|closed, expires_at, view, reviewer}`.
  `404 share_not_found` (unknown or replaced), `410 share_revoked | share_expired`.
- `POST /shared/feedback {token, client_request_id, clear, needs_evidence, next_step, comments: [{sentence, text}], guest_name}`
  → `201 {feedback, duplicate: false}`, or `200` with `duplicate: true` for a retry with the same
  `client_request_id`. Bounds: 1,500 characters per box, 8 comments of 600, a 60-character
  guest name, 30 pieces of feedback per share. `409 share_closed | own_share | feedback_limit`,
  `400 empty_feedback | unknown_sentence` (comments only on shared sentences). Both endpoints
  are rate-limited per client IP (`429`).

### Interview-day kit

One kit per recorded interview event ([INTERVIEW_KIT.md](INTERVIEW_KIT.md)). Owner-only, `Cache-Control: no-store`.

- `GET /api/v1/me/applications/{id}/events/{event_id}/kit` 🔒 → `{event details, format:
  remote|in_person|phone|unknown, location, meeting_link, interviewers: [{name, role}], notes,
  checklist: [{id, text, origin: suggested|yours, done, hidden}], questions: [{id, text, group,
  origin, excluded, note}], stories: [{id, title, short_version}], target_title, saved}`. Until
  the first change, `saved` is false and everything is a suggestion (nothing stored).
- `PUT …/kit {format?, location?, meeting_link?, clear_meeting_link?, interviewers?, notes?,
  checklist?, questions?, story_ids?}` → the kit. Lists are saved in the order sent (priority).
  A new format swaps untouched suggestions only. Links must be `http(s)` (`422`); someone else's
  story `404`.
- Each chosen story also has `prepared` (the story as this kit prepared it: revision, title, short
  version) and `freshness` (docs/STORY_FRESHNESS.md: `current`, `needs_review` with what changed,
  `kept`, `unknown`); the kit has `kept_stories` (stories deleted since, with what was kept).
- `POST …/kit/stories/{story_id}/review {reviewed_revision, decision: refresh|keep}` 🔒 → the kit:
  refresh to the revision reviewed, or keep it as prepared; recorded once. `409 source_changed` (with
  `current_revision`) if the story moved on meanwhile; nothing changes. `DELETE
  …/kit/stories/{story_id}/kept` removes what the kit kept from a deleted story.

### How answers are evaluated, and your reflection

Rubric transparency and self-review for written answers ([RUBRIC_TRANSPARENCY.md](RUBRIC_TRANSPARENCY.md)).

- `GET /api/v1/careers/{slug}/questions/{id}/criteria` (public) → `{question_id, content_version,
  rubric_version, coach, criteria: [{label, description, levels: [{level: not_yet|there,
  text}]}], checks: [{kind: "deterministic", text}], disclaimer}`. The matching patterns are
  never included.
- Answers (`AnswerOut`) now include `rubric_version`, `evidence_level`
  (`sufficient|insufficient`: under 40 words, show "not enough to score" rather than the number)
  and, per point, `evidence`: the learner's own sentence where it was found (`null` when missing
  or for answers saved before this).
- `GET /api/v1/me/answers/{id}/review` 🔒 → `{answer, self_review, perspectives: [{criterion,
  yours, coach}], repeated: [{criterion, times, of}], flags, evaluations, can_reevaluate,
  reevaluate_note}` (`Cache-Control: no-store`).
- `PUT …/self-review {went_well, improve, ratings: {label: no|partly|yes}, skipped,
  before_feedback}` → the review. Never changes the answer or its score; `400 unknown_criterion`
  for a rating on a point the answer doesn't have.
- `POST …/flags {criterion (a point's label or "Overall"), kind: unclear|disagree, note}` (one per
  criterion; saving again updates it), `DELETE …/flags/{flag_id}`. Each flag has `disputed`
  (an "I disagree" not counted again), `disputed_at` (`null` for flags from before it was
  recorded) and `reinstated_at`.
- `POST …/flags/{flag_id}/reinstate` 🔒 → the review: counts a disputed point in the plan again
  (docs/DISPUTES.md). The flag and its note stay. Sending it again, or for a flag that isn't a
  standing dispute, changes nothing and returns the review; another account's answer or flag is
  `404`.
- `POST …/evaluations {reason}` → a new evaluation stored beside the original, only when the
  rubric or the question's version changed since the last one; otherwise `409 no_reevaluation`
  with the reason (the built-in coach is deterministic). At most three per answer.

### Communication drills

Short drills with career-aware prompts ([DRILLS.md](DRILLS.md)). Owner-only.

- `GET /api/v1/me/drills` 🔒 → `[{id, title, objective, looks_for, target_seconds, prompt,
  attempts}]` (five drills; `target_seconds` only for the introduction; `prompt` is built from
  the learner's career). `GET /api/v1/me/drills/{id}` → one; `404` for an unknown drill.
- `POST /api/v1/me/drills/{id}/attempts` 🔒 `{text, source: typed|voice, spoken_seconds?,
  client_request_id?}` → `201` `{id, drill_id, prompt, text, source, spoken_seconds,
  rubric_version, feedback: {observations: [{point, present, detail}], generalities, measured:
  {words, spoken_seconds?, reading_estimate_seconds}, notes, limitations},
  compared_with_previous}`; a retry with the same `client_request_id` returns the first with
  `200`. `400 too_little` under three words (nothing is saved); `400 invalid_measure` for spoken
  time on a typed answer; `429` from the practice limiter; at most 200 attempts per drill.
- `GET /api/v1/me/drills/{id}/attempts` → newest first, each compared with the one before it
  (only under the same rubric version).
- Drills can also be bookmarked and added to collections (`item_type: "drill"`, empty `track`)
  and scheduled (`kind: "drill"`, `ref` = the drill id).

### Whiteboard practice

System-design practice with a small, plain-text diagram ([WHITEBOARD.md](WHITEBOARD.md)).
Owner-only.

- `GET /api/v1/me/whiteboard/prompts` 🔒 → `{prompts: [{id, version, title, objective, brief,
  requirements: [{id, text}]}], note}`. The note says what's offered for the learner's career
  (system design only; no process maps yet).
- `POST /api/v1/me/whiteboard/validate` 🔒 a diagram → the cleaned diagram, or `422`. Saves
  nothing; used before an imported file is loaded.
- Diagram: `{format: "codecoach-whiteboard", version: 1, nodes: [{id, label, kind, x, y,
  group}], edges: [{id, source, target, label}], notes: {assumptions, requirements, capacity,
  tradeoffs}}`. Ids match `^[a-z][a-z0-9-]{0,15}$`; up to 40 nodes and 80 edges; plain text with
  length limits; unknown fields are refused (`422`).
- `GET /api/v1/me/whiteboard/{prompt_id}/draft` 🔒 → `{diagram, explanation, revision,
  updated_at, differs_from_last_attempt}` (revision `0` before the first save).
- `PUT …/{prompt_id}/draft {diagram, explanation, expected_revision}` → the draft; `409
  stale_revision` with `details.current_revision` if it was saved elsewhere.
- `POST …/{prompt_id}/attempts {diagram, explanation}` → `201` `{id, prompt_version,
  rubric_version, diagram, digest, explanation, feedback: {checks, rubric: [{requirement, text,
  addressed, evidence: [{kind: component|connection|note|explanation, id, text}]}], reasoning,
  limitations}}`. `400 explanation_required` under 15 words. An empty diagram is allowed.
- `GET …/{prompt_id}/attempts` → summaries (`addressed`, `total`, versions); `GET
  /api/v1/me/whiteboard/attempts/{id}` → one frozen attempt.

### Restore from a backup

Bring your own data back from a CodeCoach backup ([BACKUP_FORMAT.md](BACKUP_FORMAT.md)). Additive
only; ids, account details, roles and results in the file are never trusted.

- `POST /api/v1/me/restore/preview` 🔒 (the backup file as the JSON body, at most 5 MB) →
  `{export_version, exported_at, file_sha256, from_other_account, categories: [{key: notes|stories|
  bookmarks|applications, label, found, new, duplicates, skipped: [{reason, count}], samples}],
  not_restored: [{key, count, reason}], ignored_fields, previous}`. Nothing changes. `400
  invalid_json | not_a_backup | unsupported_version (details.supported) | file_too_large`.
- `POST /api/v1/me/restore?categories=notes&categories=stories…` 🔒 (the same file) → `201` the
  batch `{id, status: applied, categories, counts: {category: {added, duplicates, skipped}}}`, or
  `200` with the earlier batch when the same file and categories were already restored. One
  transaction: `400 restore_failed` (and a recorded `failed` batch) means nothing was changed;
  `400 over_limit` when the account limits would be exceeded.
- `GET /api/v1/me/restore/batches` → your restores, newest first.
- `POST /api/v1/me/restore/batches/{id}/remove` → removes the records the batch added that are
  still exactly as restored; `removal: {removed, kept_edited, already_gone}`. Idempotent.

### Interview reflections

A private debrief of a real interview event ([REFLECTIONS.md](REFLECTIONS.md)). Owner-only,
`Cache-Control: no-store`, never sent to an AI provider, never logged.

- `GET /api/v1/me/applications/{id}/events/{event_id}/reflection` 🔒 → `{event and application
  details (copied on first save), questions, topics, clear, difficult, observations: [{text, kind:
  observed|interpretation}], follow_ups, practice, story_ids, outcome, outcome_history, revision,
  saved, warnings, actions}`. Before the first save, `saved` is false and everything is empty.
- `PUT …/reflection {…, expected_revision}` → the reflection (every part optional); `409
  stale_revision` with `details.current_revision`; `404` for someone else's story id. `warnings`
  point out what looks like an email address, phone number or ID number; nothing is blocked.
- `POST …/reflection/suggestions` → suggestions built deterministically from what was written:
  `practice` (a matching question, with `href`), `gap` (no matching content; notebook only) and
  `note` (follow-up commitments). Nothing is applied; accepted and dismissed ones are left alone.
- `PATCH …/reflection/actions/{action_id} {status?: suggested|dismissed, title?, detail?}`;
  `409 already_accepted` once added.
- `POST …/reflection/actions/{action_id}/accept {target: notebook|schedule|saved, on_date?,
  timezone?}` → adds a note, a schedule entry (a date is required) or a bookmark. Accepting again
  returns the same result and creates nothing new.
- `PUT …/reflection/outcome {outcome: unknown|awaiting|another_round|offer|not_selected|withdrawn,
  update_application}` → the outcome is recorded with its time; the application's stage changes
  only when `update_application` is true and the outcome maps to a stage (waiting never does).
- `GET /api/v1/me/reflections?q=&outcome=&include_archived=` 🔒 → summaries, newest first.

### Schedule

Existing activities on dates and times you choose ([SCHEDULE.md](SCHEDULE.md)). Owner-only.

- `GET /api/v1/me/schedule?from=&to=&include_cancelled=` 🔒 → entries (`all_day`, `on_date`,
  `local_time`, `timezone`, `starts_at`/`ends_at` UTC, `status`, `done_at` from the activity's
  own rules, `available`, `conflicts`, `uid`, `sequence`). Up to 120 days per request.
- `POST /api/v1/me/schedule` 🔒 `{kind: plan_item|review_item|question|problem|application_event,
  ref, on_date, all_day, local_time?, timezone?, fold?, duration_min, notes, client_request_id?}`
  → `201` (or `200` with the first for a retry). `404` for someone else's activity; `409
  not_available` for retired content; `400 time_required | invalid_timezone | invalid_time |
  nonexistent_time | ambiguous_time`.
- `PATCH /api/v1/me/schedule/{id}` (move; `SEQUENCE` + 1; `409 entry_cancelled`), `POST
  …/{id}/cancel` (idempotent), `GET …/{id}`.
- `GET /api/v1/me/schedule/schedulable` → open plan steps, reviews due within two weeks and
  upcoming interview events.
- `GET` / `PUT /api/v1/me/schedule/settings` `{timezone, reminders, reminder_minutes,
  quiet_start, quiet_end}` (a zone is required before anything else is saved).
- `GET /api/v1/me/schedule/export.ics?ids=a,b` or `?from=&to=` → `text/calendar` attachment
  (`Cache-Control: no-store`); a range includes cancelled entries as `STATUS:CANCELLED`.

### Applications

A private tracker of real applications ([APPLICATIONS.md](APPLICATIONS.md)). Owner-only (404 for
anyone else). Nothing is sent or submitted anywhere.

- `GET /api/v1/me/applications?archived=` 🔒 → summaries (`stage`, `applied_on`, `next_action`,
  `next_action_due`, `target`, `next_event`).
- `POST /api/v1/me/applications` 🔒 `{employer, role_title, stage?, link?, applied_on?,
  next_action?, next_action_due?, notes?, target_id?, story_ids?, client_request_id?}` → `201`,
  or `200` with the first one for a retry with the same `client_request_id`. Links must be
  `http(s)` (`422`); someone else's target or story `404`; up to 300.
- `GET …/{id}` → details with `events`, `history` (newest first, with the title and employer as
  they were) and linked `stories`.
- `PATCH …/{id} {fields…, clear: [link|applied_on|next_action_due|target_id]}` → details.
- `POST …/{id}/stage {stage: saved|applied|interviewing|offer|closed|withdrawn, note, correction}`
  → appended to the history; the same stage again is a no-op.
- `POST …/{id}/archive`, `…/unarchive`; `DELETE …/{id}` (`204`).
- `GET …/{id}/delete-preview` → `Impact`: every record deleting it would delete, unlink, keep or
  make unavailable, by kind and title, with a `fingerprint`; nothing is changed. `POST …/{id}/delete`
  `{expected_fingerprint, client_request_id?}` → `LifecycleOutcome`: carries out the same plan,
  worked out again; a changed scope is `409 impact_changed` with the new preview in
  `details.current`, and nothing is done; a repeated key answers `replayed: true`. `DELETE …/{id}`
  carries out the plan as it is now. A create sent again after its application was deleted is
  `410 deleted_earlier` (docs/LIFECYCLE.md).
- `POST …/{id}/events {kind: phone_screen|interview|assessment|other, title, on_date?,
  local_time? (HH:MM), timezone? (IANA), fold? (0|1), notes, client_request_id?}`, `PUT
  …/events/{event_id}`, `DELETE …/events/{event_id}`. `starts_at` (UTC) is set only when date,
  time and zone are known. `400 invalid_timezone | invalid_time | time_without_date |
  nonexistent_time | ambiguous_time` (`details.first_offset`, `details.second_offset`: send
  `fold` to choose).

### Story bank

Your own STAR stories ([STORIES.md](STORIES.md)). Everything is owner-only (404 for anyone else).
Job-target examples (`/targets/{id}/experience`) are the same stories.

- `GET /api/v1/me/stories?archived=&q=&competency=` 🔒 → summaries (`missing` sections, `target`,
  `practice_count`, `preview`, `revision`). `q` matches every word across everything you wrote.
- `POST /api/v1/me/stories` 🔒 `{title, track?, context?, situation, task, action, result,
  reflection, notes, evidence, competencies, tags, short_version, long_version, target_id?,
  question_refs?, client_request_id?}` → `201` the story. The same `client_request_id` again (a lost
  response) returns the story the first request made, not a second one. Up to 200 stories (`400 too_many_stories`); unknown career
  `400 unknown_career`; a question ref that doesn't exist `400 unknown_question`; someone else's
  target `404`.
- `GET /api/v1/me/stories/{id}` 🔒 → the story with `questions`, `practice` (answers that
  rehearsed it) and `privacy_hints`.
- `PATCH /api/v1/me/stories/{id}` 🔒 `{…fields to change, expected_revision, reason:
  edited|assisted, clear_target}` → a new revision, or `409 stale_revision`
  (`details.current_revision`) if it changed since. Nothing changed: no new revision.
- `POST …/{id}/archive` and `…/unarchive`; `DELETE …/{id}` (`204`; answers that rehearsed it are
  kept).
- `GET …/{id}/revisions` → every saved version, newest first; `POST
  …/{id}/revisions/{n}/restore {expected_revision}` → saved as a new version.
- `POST …/{id}/assist {action: check|shorten|clarity, situation?, task?, action_text?, result?,
  reflection?}` → `{method, proposals: [{field, original, proposed, changes}], questions}`.
  Built-in rules, not AI; nothing is saved; proposals only ever remove words.
- Answers: `POST /api/v1/careers/{slug}/questions/{id}/answers` takes an optional `story_id`
  (your own story, else `404`); `AnswerOut.story_id` echoes it.

### First-session introduction

The optional welcome and guided tour ([ONBOARDING.md](ONBOARDING.md)). Owner-only (`/me`).
Nothing here stores answer text or creates practice activity.

- `GET /api/v1/me/onboarding` 🔒 → `{tour_status: not_started|in_progress|paused|completed|skipped,
  tour_kind: written|coding|null, tour_step, tour_steps, start_choice, welcome_due, resume_due,
  career_intro: {track, title, kind}|null, first_activity_at, starter: {kind: question|problem,
  track, ref, title, difficulty, href, minutes}|null, format}`. `starter` is a real, easy,
  non-retired item from the learner's own career; `first_activity_at` comes from their answers
  and submissions. Reading never creates a row.
- `PATCH /api/v1/me/onboarding` 🔒 `{start_choice?: practice|intro|library|later, tour?:
  start|step|pause|complete|skip, tour_kind?, tour_step? (0-20), dismiss?: welcome|resume_tour,
  career_intro_seen?: true}` → the new state. Each change is idempotent: `step` only moves a
  running or paused tour (clamped to the last step), `complete` and `skip` don't reopen anything,
  `start` (also used to replay) begins at step 0. Unknown values are `422`.

### Content quality: labels, reports, corrections and retirement

How content is labelled, reported, corrected and retired is described in
[CONTENT_QUALITY.md](CONTENT_QUALITY.md). Content ids are `track/question_id` for career
questions and the slug for coding problems.

- `GET /api/v1/content/{question|problem}/{id}/meta` (public) → `{content_type, content_id,
  version, version_label, career, topic, level, status: active|retired, retired_reason, labels:
  [{key, text}], changes: [{version, note, significant, at}]}`. Labels come only from recorded
  facts: `generated` (or `authored`), `not_expert_reviewed`, `reference_verified` (only a recorded
  passing check for the problem's current test version) or `tests_not_checked`, and `corrected`.
- `GET /api/v1/careers/{slug}/questions/{id}/versions/{n}` (public) → `{version, title, prompt}`
  as the question read at version `n` (for answers written against it). Versions only grow.
- `POST /api/v1/reports` 🔒 `{content_type, content_id, content_version, category, details,
  context: content|feedback, answer_id?, excerpt?}` → `201` the report as the reporter sees it.
  Categories: `ambiguous_wording | incorrect_example | outdated_guidance | wrong_career_topic |
  accessibility | technical_bug | other`; `details` ≤ 2,000 characters. `content_version` is the version on screen (`400 invalid_version` if it
  doesn't exist). Feedback reports need your own `answer_id` (`400 answer_required`, `404`
  otherwise); `excerpt` (≤ 1,500 characters) is only what the learner chose to attach. Text is
  stored as plain text with control characters removed. The same person can't file the same open
  report twice (`409 already_reported`, `details.report_id`); someone else's matching report is
  grouped as a likely duplicate. Rate-limited per user (`429`).
- `GET /api/v1/me/reports` 🔒 → your reports with status (`open | investigating | resolved |
  not_actionable`) and the public `resolution`; never other reporters or internal notes.

Admin routes (`/api/v1/admin/…`) answer **404** to anyone who isn't an admin. Admin is granted
only from the command line (`python -m app.cli grant-admin EMAIL`); no endpoint can grant it.
Every change is written to the append-only `content_audit` table.

- `GET /admin/reports?status=` → reports grouped by content, duplicates included (`open` also
  matches `investigating`; omit for all). Reporters are named by display name, never email.
- `GET /admin/reports/{id}` → the report, `duplicates`, `current_version`, the content's `meta`
  and the `audit` trail (with internal notes).
- `POST /admin/reports/{id}/status {status, resolution?, internal_note?, include_duplicates}`:
  `resolved` and `not_actionable` need a `resolution` for the reporter
  (`400 resolution_required`); grouped duplicates follow by default.
- `POST /admin/reports/{id}/duplicate {duplicate_of: id | null, internal_note?}`: group under
  another report about the same content (`400 invalid_duplicate`) or ungroup. Nothing is merged
  or deleted.
- `POST /admin/content/question/{slug}/{id}/corrections {title?, prompt?, tips?, outline?,
  change_note, significant, report_ids, internal_note?}` → the new `meta`. Publishes the next
  version (`400 no_change` if nothing differs); linked reports and their duplicates are resolved
  with "Corrected in version N: …" (`400 invalid_reports` for reports about other content).
  Existing answers keep their `content_version` and score.
- `POST /admin/content/{type}/{id}/retire {reason, report_ids, internal_note?}` and
  `POST /admin/content/{type}/{id}/restore {internal_note?}` → the new `meta`. Retired content
  leaves lists, rounds, plans and recommendations, and answering or submitting it is
  `409 content_retired`; it stays readable in history and saved items.

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
  planned; completed work or changed goals produce a new version. Each item has `disputed`
  (`{text, href, answer_id, criterion}` when it was derived from feedback the learner disputes,
  else `null`), and the plan `withheld` (`[{text, href, reinstated}]`: what this version didn't
  suggest because of a dispute, one line each). The same `disputed` note is on accepted actions
  (`GET /me/actions`) and schedule entries (`GET /me/schedule`) derived from a disputed point;
  they're never removed or cancelled for it (docs/DISPUTES.md).
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
  score trends **per score basis** (the comparison contract, docs/COMPARING_ATTEMPTS.md: the same
  scale, kind of evaluator and recorded rubric, long enough to score; never merged), where each
  series' `attempts` and each week's `answers` are the average's denominator and `not_in_trend`
  counts the rest by reason, daily counts and `definitions` for every metric.
- `GET /api/v1/me/resume` 🔒 returns the interview in progress (with its real
  `seconds_remaining`), the latest submitted-but-unsolved problem and the last answered question.
- `GET /api/v1/me/ai-history/{id}` 🔒 returns one saved hint, review or failure explanation.

Problem opens are recorded at most once per user, problem and UTC day, enforced by a unique key
so concurrent requests can't double-count.

### Interview formats and follow-ups

- `GET /api/v1/interviews/formats?track=&difficulty=` (public): every format (`mixed`, `behavioral`,
  `situational`, `technical`, `panel`) with `available`, `unavailable_reason`, `follow_ups`, the
  panel `roles` (generic titles, never a real employer) and a `structure` preview (who asks what,
  no questions). A career without a reviewed panel gets the panel as unavailable with a reason.
- `POST /api/v1/interviews {kind: "questions", format, difficulty, …}`: `409 format_unavailable`
  when the level can't fill the format; `400 format_not_allowed` with `question_ids` or a
  baseline. The format can't change once started. `round_format` on the interview reports
  `{id, title, version, rubric_version, roles, followups_used, followups_max, pending_followup}`;
  each question carries `speaker` (panel) and `followup`.
- After an answer the server may ask one follow-up (at most two per round) about a detail the
  answer left out and no earlier reply supplied. While it's pending, answering the next question
  is `409 followup_pending`. `POST /interviews/{id}/followup {answer, source}` replies (a repeat of
  the same reply is a no-op) and `POST /interviews/{id}/followup/skip` skips; then the next
  question is asked. Replies are stored on the question's turn and don't change its score.
- The review adds who asked each question, the follow-up and reply, a "Follow-up questions"
  dimension, `round_format`, and for panels `perspectives` (the same rubric split by role; not
  independent judgments). See [docs/INTERVIEW_FORMATS.md](INTERVIEW_FORMATS.md).

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
| `POST /api/v1/careers/{slug}/questions/{id}/answers/keyed` | required | The protected route: the same body with `client_request_id` **required** (8–64 of `A-Za-z0-9_-`). A resend with the same key returns the saved answer (`200`, `Idempotent-Replayed: true`); the same key with a different request is `409 idempotency_key_reused`. A server that doesn't keep one answer per key has no such route, so it refuses the request (`404`) instead of saving it unprotected: send keyed answers here. The plain route also accepts a key (same key space) for compatibility |
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
| `AUTO_MIGRATE` | on outside production | Create tables and seed problems on startup. Off by default in production, which refuses `true` (run `alembic upgrade head` and `python -m app.cli seed`). |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | `5` / `10` | Database connections per process. Keep processes × (pool + overflow) under PostgreSQL's `max_connections` ([PERFORMANCE.md](PERFORMANCE.md#sizing)). |
| `DB_POOL_TIMEOUT_SECONDS` | `10` | A request waiting longer for a connection gets `503 server_busy` with `Retry-After`. A database that can't be reached, a cancelled or timed-out statement, a shutdown or a deadlock gets `503 database_unavailable` with `Retry-After: 5` (other database errors stay 500). |
| `SECRET_KEY` | insecure dev value | **Secret.** Signs access tokens and keys the email-code and refresh-recovery HMACs. Production refuses the dev value, placeholder text and repetitive strings. |
| `SECRET_KEY_PREVIOUS` | (none) | **Secret.** Comma-separated keys being rotated out: accepted when checking, never used to sign ([SECURITY.md §7](SECURITY.md#7-secrets-rotation-and-the-database-role)). |
| `ACCESS_TOKEN_TTL_MINUTES` | `15` | Access-token lifetime (5–1440). |
| `REFRESH_TOKEN_TTL_DAYS` | `30` | Refresh-cookie lifetime; it rotates on every use (1–90). |
| `REFRESH_COOKIE_SECURE` | unset | Unset: `Secure` in production only. `false` is refused in production. |
| `ALLOW_GUEST_SESSIONS` | `true` | Enables `POST /auth/guest`. |
| `SHARE_OPENS_PER_10_MINUTES` | `120` | Per-IP opens of shared-answer links. |
| `SHARE_FEEDBACK_PER_HOUR` | `20` | Per-IP feedback submissions on shared answers. |
| `SHARES_CREATED_PER_HOUR` | `30` | Share links (new or replaced) per user per hour. |
| `CONTENT_REPORTS_PER_HOUR` | `10` | Content reports per user per hour. |
| `AUTH_RATE_LIMIT_PER_MINUTE` | `10` | Per-address attempts per minute (IPv6 by /64) for sign-in, registration, guests, verification, resend, reset, email and password changes. |
| `LOGIN_FAILURES_PER_ACCOUNT` | `20` | Wrong passwords for one account in 15 minutes, from any address, before sign-in to it pauses (`429 account_throttled`). |
| `REFRESH_RATE_LIMIT_PER_MINUTE` | `60` | Session refreshes per address per minute (the app treats a 429 here as "try later", never as signed out). |
| `EXPORTS_PER_HOUR` / `RESTORES_PER_HOUR` | `20` / `20` | Data exports, and backup checks or restores, per user per hour. |
| `RATE_LIMIT_BACKEND` | `database` | `database`: counters shared by every API replica (sliding window, atomic upsert). `memory`: one process only. |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1` | (uvicorn) Proxies whose `X-Forwarded-For` is trusted. Set it to your load balancer's address, or every user shares the proxy's IP for rate limiting. Untrusted headers are ignored, so they can't be spoofed. The production compose file sets the private ranges, because a proxy on the host reaches the container through Docker's gateway, never 127.0.0.1 ([STORAGE.md](STORAGE.md)). |
| `GUEST_RETENTION_DAYS` | `30` | Guest accounts with no activity for this long are deleted with their data (background jobs, daily; or `python -m app.cli housekeeping` / `prune-guests`). `0` keeps them. |
| `BACKGROUND_JOBS_IN_API` | `true` | Email retries and housekeeping in a thread in each API process (safe with any number of replicas). Off only if `python -m app.worker` runs them. |
| `RESPONSE_CACHE_TTL_SECONDS` | `60` | How long the public catalogue is cached per process and by browsers. `0` turns the in-process cache off. |
| `APP_BASE_URL` | `http://localhost:5173` | Public web-app URL used in emailed links. Must be `https` in production. |
| `EMAIL_BACKEND` | `console` | `console` (log), `file` (write to `EMAIL_FILE_DIR`, for tests) or `smtp`. Production requires `smtp`. |
| `INSTANCE_LABEL` | — | A test server's label, sent as the `X-CodeCoach-Instance` header so a test suite can recognise its own server (the e2e suite sets `e2e`). Not secret. Refused in production. |
| `EMAIL_FROM`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_STARTTLS` | –, –, `587`, –, –, `true` | SMTP delivery settings. |
| `PASSWORD_RESET_TTL_MINUTES` | `30` | Lifetime of a reset link. |
| `EMAIL_VERIFICATION_TTL_HOURS` | `48` | Lifetime of a verification code and link. |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated browser origins allowed to call the API. |
| `AI_PROVIDER` | `offline` | `offline` (curated hints + static analysis, free) or `anthropic` (Claude). |
| `ANTHROPIC_API_KEY` | — | **Secret.** Required when `AI_PROVIDER=anthropic`. |
| `ANTHROPIC_MODEL` | `claude-opus-5-5` | Model ID used for hints and reviews. |
| `ANTHROPIC_EFFORT` | `low` | `low`, `medium` or `high`. Higher is deeper and more expensive. |
| `AI_DAILY_REQUEST_LIMIT` | `50` | AI calls per user per rolling 24 hours (exact under concurrency on PostgreSQL: one AI request per user at a time). |
| `AI_MAX_CONCURRENT_CALLS` | `8` | Paid-provider calls at once per process; when all are busy the offline coach answers immediately. |
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
| `SMTP_SECURITY` | `starttls` | How the mail server connection is protected: `starttls`, `ssl` (implicit TLS) or `none` (refused in production). Certificates and hostnames are always verified. |
| `SMTP_CA_BUNDLE` | (none) | A private CA to trust for the mail server (adds trust; never disables verification). |
| `SMTP_TIMEOUT_SECONDS` | `10` | Per-attempt limit for talking to the mail server. |
| `METRICS_TOKEN` | (none) | **Secret.** When set, `/metrics` needs `Authorization: Bearer <token>` (else 404). Required in production while metrics are on. |
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
