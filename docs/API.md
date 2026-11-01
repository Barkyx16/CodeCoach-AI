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

CodeCoach uses **bearer tokens** (short-lived JWTs). There are no cookies, so CSRF does not
apply and CORS is configured with `allow_credentials=false`.

```
┌────────┐  POST /auth/register  or  /auth/login  or  /auth/guest   ┌─────┐
│ client │ ───────────────────────────────────────────────────────▶ │ API │
│        │ ◀─────────── { access_token, expires_at, user } ──────── │     │
│        │                                                          │     │
│        │  GET /api/v1/...   Authorization: Bearer <access_token>  │     │
│        │ ───────────────────────────────────────────────────────▶ │     │
│        │ ◀──────────────── 200 …  or  401 invalid_token ───────── │     │
└────────┘                                                          └─────┘
```

1. **Get a token** from one of:
   - `POST /api/v1/auth/register`: new email/password account.
   - `POST /api/v1/auth/login`: existing account.
   - `POST /api/v1/auth/guest`: instant demo account with no email. Good for a "Try it" button.
2. **Store it** in memory, or `localStorage` if you accept the XSS trade-off (see
   [SECURITY.md](SECURITY.md#token-storage-in-the-browser)). Never put it in a URL.
3. **Send it** on every authenticated request: `Authorization: Bearer <access_token>`.
4. **Expiry:** tokens last `ACCESS_TOKEN_TTL_MINUTES` (default 60). `expires_at` is in the
   response; on a `401` with `error.code == "invalid_token"`, send the user back to login.
5. **Logout:** `POST /api/v1/auth/logout` increments the user's `token_version`, which
   revokes *every* token issued to that user on every device. Then discard the token client-side.
6. **Password change:** `POST /api/v1/auth/password` also revokes all old tokens and returns
   a fresh one.

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
| 401 | `invalid_credentials` | Wrong email/password (deliberately identical for unknown emails) | Form error |
| 404 | `not_found` | Unknown route, problem, or a resource owned by someone else | Not-found state |
| 405 | `method_not_allowed` | Wrong HTTP method | (client bug) |
| 409 | `email_taken` | Registration with an existing email | Form error on email |
| 409 | `hint_locked` | Hint level requested before the previous one (`details.next_unlockable_level`) | Disable later hint buttons |
| 409 | `interview_in_progress` | Starting an interview while one is active (`details.interview_id`) | Offer "Resume" |
| 409 | `interview_closed` | Sending a message to a finished, expired or abandoned interview (`details.status`) | Show the results view |
| 400 | `turn_limit_reached` | Interview message cap reached (`details.max_candidate_turns`) | Prompt to finish |
| 429 | `submission_pending` | A previous submission is still being judged (`details.max_pending`) | Wait for the verdict |
| 503 | `judge_busy` | The judge queue is full | Retry in a minute |
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
| POST | `/api/v1/auth/register` | – | Create account → token |
| POST | `/api/v1/auth/login` | – | Log in → token |
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
| POST | `/api/v1/submissions` | 🔒 | Submit a solution (async job) |
| GET | `/api/v1/submissions/{id}` | 🔒 | Poll a submission |
| GET | `/api/v1/me/submissions` | 🔒 | Attempt history |
| POST | `/api/v1/ai/hint` | 🔒 | Progressive hint |
| POST | `/api/v1/ai/review` | 🔒 | Structured code review |
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
{"problem_slug": "two-sum", "language": "java", "source_code": "class Solution { … }"}
```
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
     "exception": null, "exception_message": null, "missing": false, "runtime_ms": 1.532},
    {"index": 1, "passed": false, "input": {"s": "([)]"}, "expected_output": false, "actual_output": true,
     "exception": null, "exception_message": null, "missing": false, "runtime_ms": 0.005}
  ],
  "stderr_excerpt": null
}
```
- Per-test detail is only ever given for **public** tests. Hidden tests contribute to
  `passed_count`/`total_count` and `hidden_passed`/`hidden_total` only.
- `exception` + `exception_message`: the test threw (e.g. `ArrayIndexOutOfBoundsException`,
  `Index 2 out of bounds for length 2`). An expected exception (`{"throws": …}`) counts as a pass.
- `missing: true`: the test never reported because the program crashed, exited or hit the time limit first.
- `stderr_excerpt` is set **only** for `COMPILE_ERROR` (compiler output, with sandbox paths
  removed). Program output is never returned, because learner code could print hidden inputs.
- `runtime_ms` is time spent inside the learner's method. `memory_kb` is `null`: peak memory
  isn't measured yet, and the API never invents numbers.

Verdicts: `PASSED` (all tests) · `FAILED` (some wrong answers) · `COMPILE_ERROR` ·
`RUNTIME_ERROR` (crashed/exited before finishing, StackOverflowError, output flood) ·
`TIME_LIMIT` · `MEMORY_LIMIT` · `INTERNAL_ERROR` (judge infrastructure failed after retries; not
the learner's fault).

#### `GET /api/v1/submissions/{id}` 🔒 → `200`
Same shape as above. `404` if it doesn't exist **or** belongs to another user.

#### `GET /api/v1/me/submissions` 🔒 → `200`
Query: `problem_slug`, `status` (e.g. `QUEUED`, `PASSED`), `page`, `page_size`. Newest first.
```json
{
  "items": [{"id": "9098…", "problem_slug": "two-sum", "problem_title": "Two Sum", "status": "QUEUED",
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

#### `GET /api/v1/ai/usage` 🔒 → `200`
```json
{"used_today": 2, "daily_limit": 50, "remaining_today": 48, "provider": "offline"}
```

#### `GET /api/v1/me/ai-history` 🔒 → `200`
Query: `problem_slug`, `action` (`hint` | `review`), `page`, `page_size`. Newest first.
`response` holds the exact `content` (for hints) or `review` (for reviews) originally returned.
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

#### `POST /api/v1/interviews/{id}/messages` 🔒 → `200`
```json
{"message": "Can the array be empty or contain duplicates?", "code": "class Solution { … }"}
```
`code` (optional) is the current editor content; the latest version is kept as `final_code`.
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
| `ACCESS_TOKEN_TTL_MINUTES` | `60` | Token lifetime (5–1440). |
| `ALLOW_GUEST_SESSIONS` | `true` | Enables `POST /auth/guest`. |
| `AUTH_RATE_LIMIT_PER_MINUTE` | `10` | Per-IP attempts for register, login, guest and password change. |
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
