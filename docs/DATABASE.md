# CodeCoach AI — Database

PostgreSQL 16 in development (Docker Compose) and production. The test suite also runs on
SQLite for speed, and CI runs it on both. Schema changes go through **Alembic** migrations in
`backend/migrations/versions/`.

## Entity-relationship diagram

```
┌──────────────┐ 1      * ┌──────────────┐ *      1 ┌──────────────┐ 1      * ┌──────────────┐
│    users     │──────────│ submissions  │──────────│   problems   │──────────│  test_cases  │
└──────┬───────┘          └──────┬───────┘          └──────┬───────┘          └──────────────┘
       │ 1                       │ 1                       │
       │                         │ 0..1                    │
       │                  ┌──────▼────────────┐            │
       │                  │ execution_results │            │
       │                  └───────────────────┘            │
       │ 1      *  ┌─────────────────┐  *      1            │
       ├───────────│ ai_interactions │───────────────────────┤
       │           └────────┬────────┘   (optional link to a submission)
       │ 1      *  ┌─────────────────┐  *      1            │
       ├───────────│ progress_events │───────────────────────┘
       │           └─────────────────┘
       │ 1      *  ┌───────────────────┐ 1     *  ┌─────────────────┐
       └───────────│ practice_sessions │──────────│ interview_turns │
                   └─────────┬─────────┘          └─────────────────┘
                             │ * → 1 problems
```

## Tables

### `users`
| Column | Type | Notes |
|---|---|---|
| `id` | varchar(36) PK | UUID4 string |
| `email` | varchar(320) unique, null | Lower-cased. `NULL` for guest accounts. |
| `auth_provider_id` | varchar(128) unique | `password:<uuid>` or `guest:<uuid>`; leaves room for `github:<id>` later |
| `password_hash` | varchar(255) null | Argon2id hash (includes salt and parameters). Never returned by the API. |
| `display_name` | varchar(80) null | |
| `is_guest` | boolean | |
| `token_version` | integer | Incremented on logout or password change; JWTs carrying an older version are rejected |
| `created_at`, `last_login_at` | timestamptz | |

### `problems`
| Column | Type | Notes |
|---|---|---|
| `id` | serial PK | |
| `slug` | varchar(80) unique, indexed | Public identifier used in URLs |
| `title`, `summary` | varchar | |
| `difficulty` | varchar(32), indexed | `easy` \| `medium` \| `hard` |
| `topics` | JSONB | `["arrays", "hash-maps"]` |
| `statement` | text | Markdown |
| `constraints`, `examples` | JSONB | |
| `starter_code` | text | Java `class Solution { … }` |
| `signature` | JSONB | `{method, params:[{name,type}], returns}`, which drives the test driver generator |
| `hints` | JSONB | Four-level curated ladder. **Server-only.** |
| `expected_complexity` | JSONB | `{time, space}` |
| `order_index` | integer | Curated display order |

### `test_cases`
| Column | Type | Notes |
|---|---|---|
| `id` | serial PK | |
| `problem_id` | FK → problems (cascade delete), indexed | |
| `position` | integer | Order within the problem |
| `input` | JSONB | Named arguments: `{"nums": [2,7], "target": 9}` |
| `expected_output` | JSONB | Value, or `{"throws": "IllegalArgumentException"}` |
| `visibility` | varchar | `public` \| `hidden`. Hidden rows are never serialized. |
| `version` | integer | Bumped by the seeder when a problem's tests change, so results stay traceable to the test set that judged them |

### `submissions`
| Column | Type | Notes |
|---|---|---|
| `id` | varchar(36) PK | UUID4 |
| `user_id` | FK → users (cascade), indexed | Ownership. Every query filters on it. |
| `problem_id` | FK → problems, indexed | |
| `language` | varchar(16) | `java` |
| `source_code` | text | Size-limited by `MAX_SOURCE_CHARS` |
| `status` | varchar(32) | Judge status model: `QUEUED`, `RUNNING`, `PASSED`, `FAILED`, `COMPILE_ERROR`, `RUNTIME_ERROR`, `TIME_LIMIT`, `MEMORY_LIMIT`, `INTERNAL_ERROR` |
| `status_detail` | varchar(500) null | Human-readable explanation |
| `mode` | varchar(32), default `submit` | `submit` (judged on all tests; counts toward progress, history and acceptance) or `run` (public tests only; never an attempt). Runs share the queue, worker and abuse limits |
| `attempts` | integer (default 0) | Judge attempts; only infrastructure failures are retried |
| `judge_started_at`, `judged_at` | timestamptz null | Claim time (used for crashed-worker recovery) and verdict time |
| `test_version` | integer null | Version of the test set that produced the verdict |
| `created_at`, `updated_at` | timestamptz | Composite index `(user_id, created_at)` for history pages |

### `refresh_tokens`
| Column | Type | Notes |
|---|---|---|
| `id` | varchar(36) PK | UUID4 |
| `user_id` | FK → users (cascade), indexed | Deleted with the account |
| `family_id` | varchar(36), indexed | All rotations of one sign-in; revoked together on reuse |
| `token_hash` | varchar(64) unique | SHA-256 of the cookie value; the raw token is never stored |
| `token_version` | integer | The user's `token_version` at issue; logout/password change invalidate it |
| `created_at`, `expires_at` | timestamptz | Expired rows are pruned when the user gets a new token |
| `used_at`, `revoked_at` | timestamptz null | Rotation and revocation; used rows are kept until expiry so a replay is recognised |

### `password_reset_tokens`
| Column | Type | Notes |
|---|---|---|
| `id` | varchar(36) PK | UUID4 |
| `user_id` | FK → users (cascade), indexed | |
| `token_hash` | varchar(64) unique | SHA-256 of the emailed token; the token itself is never stored |
| `created_at`, `expires_at` | timestamptz | 30-minute lifetime by default; `created_at` also enforces one email per minute |
| `used_at` | timestamptz null | Set on use, and on every older link when a new one is issued |

### `rate_limit_counters`
| Column | Type | Notes |
|---|---|---|
| `key`, `window` | varchar(160), integer; composite PK | e.g. `auth:<client ip>` and epoch-seconds ÷ 60 |
| `count` | integer | Incremented by an atomic `INSERT … ON CONFLICT DO UPDATE … RETURNING`; windows older than the previous one are deleted on the next hit |

### `execution_results` (1:1 with submissions)
`submission_id` (PK and FK, cascade), `runtime_ms`, `memory_kb`, `passed_count`, `total_count`,
`public_results` (JSONB, **public tests only**), `stderr_excerpt` (bounded, redacted).

### `ai_interactions`
| Column | Type | Notes |
|---|---|---|
| `id` | varchar(36) PK | |
| `user_id` | FK → users (cascade) | |
| `problem_id` | FK → problems | |
| `submission_id` | FK → submissions (SET NULL), null | Set when a review referenced a submission |
| `action` | varchar | `hint` \| `review` \| `explain_failure` \| `mock_interview` |
| `hint_level` | integer null | Used to enforce unlock order |
| `provider`, `model` | varchar | E.g. `anthropic` / `claude-opus-5-5`, or `offline (fallback)` |
| `input_tokens`, `output_tokens`, `latency_ms` | integer | Cost and performance accounting |
| `response` | JSONB | The structured feedback shown to the user (saved history). **Prompts are not stored.** |
| `created_at` | timestamptz | Indexes: `(user_id, created_at)` for the rolling budget, `(user_id, problem_id, action)` for unlock checks |

### `progress_events`
Append-only activity log: `opened` (deduplicated per user, problem and day), `submitted`,
`solved`, `hint_used`, `review_requested`, `interview_completed`. Drives streaks and the 28-day heatmap. Index
`(user_id, created_at)`.

### `practice_sessions` (mock interviews when `mode = 'interview'`)
| Column | Type | Notes |
|---|---|---|
| `id` | varchar(36) PK | |
| `user_id` | FK → users (cascade), indexed | |
| `mode` | varchar | `practice` \| `interview` |
| `problem_id` | FK → problems (`fk_practice_sessions_problem_id`), null | |
| `status` | varchar | `in_progress` \| `completed` \| `expired` \| `abandoned`; server default backfills old rows |
| `phase` | varchar null | `clarify` → `approach` → `coding` → `complexity` → `wrap_up`; `NULL` once the interviewer wraps up |
| `duration_seconds` | integer | |
| `started_at`, `deadline_at`, `ended_at` | timestamptz | `deadline_at` is the authoritative clock |
| `final_code` | text null | Latest editor content sent with an answer |
| `evaluation` | JSONB null | Rubric scores, summary, strengths and improvements (written once when the interview ends) |
| `provider` | varchar null | Who ran the interview (`offline`, `anthropic`, `… (fallback)`) |

### `interview_turns`
`id`, `session_id` (FK, cascade, indexed), `seq` (order), `role` (`interviewer` \| `candidate`),
`phase` (phase the turn belongs to), `content` (text), `created_at`. This is the saved
transcript; `ai_interactions` rows for interview turns keep only cost and latency
(`response` is NULL), so text isn't duplicated.

## Design notes

- **Enums are stored as strings** (`native_enum=False`), so adding a status is a code change,
  not an `ALTER TYPE` migration, and the schema stays portable.
- **JSONB for content, columns for facts.** Things we filter or join on (difficulty,
  ownership, status, timestamps) are real columns with indexes. Display-only structures
  (examples, signature) are JSONB.
- **Derived data isn't stored.** Solved counts, streaks and acceptance rate are computed from
  `submissions`, `ai_interactions` and `progress_events`, so they can't drift out of sync.
  If the computation becomes slow at scale, add a materialized summary table.
- **Timestamps** are `timestamptz` and always UTC; a `UTCDateTime` type normalizes SQLite too.

## Migrations

| Revision | What it does |
|---|---|
| `64de41a0f941` initial schema | Users, problems, test cases, submissions, results, AI interactions, progress events, practice sessions |
| `60629f1baf0b` mock interviews | Adds interview columns to `practice_sessions` (with a server default so populated tables migrate safely) and the `interview_turns` table; names its foreign key so the downgrade works |
| `b10c8038ad7f` judge queue | Adds `attempts` (server default 0), `judge_started_at`, `judged_at`, `test_version` to `submissions`, plus the `(status, created_at)` index the worker's queue scan uses |
| `6fa2a814f068` submission mode | Adds `submissions.mode` (`submit` \| `run`) with server default `submit`, so existing rows stay attempts and populated tables migrate safely |
| `9b08bedc4ed0` refresh tokens | Adds the `refresh_tokens` table (new table, so safe on populated databases) |
| `991fd8b47342` password reset tokens | Adds `password_reset_tokens` |
| `aacf788a8eb5` rate limit counters | Adds `rate_limit_counters` |

Migration files never import application code: `migrations/env.py` renders app-specific
column types (like `UTCDateTime`) as plain SQLAlchemy types, so old migrations keep running
after the models change.

```bash
cd backend
alembic upgrade head                                  # apply
alembic revision --autogenerate -m "describe change"  # create after editing models
alembic check                                         # CI: fails if models and migrations differ
alembic downgrade -1                                  # roll back one
python -m app.cli seed                                # upsert problems (idempotent)
```
CI applies every migration on a clean PostgreSQL, runs `alembic check`, then downgrades to
base, so every migration is proven reversible.
