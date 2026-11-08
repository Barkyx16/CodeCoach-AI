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
| `career_track` | varchar(64), default `software-engineer` | The job they're preparing for: a slug from `app/careers` |
| `is_admin` | boolean, default false | Content triage access. Set only from the command line (`python -m app.cli grant-admin EMAIL`); no endpoint changes it |

### `practice_answers`

Written answers to career interview questions, with the feedback shown. Questions are generated
from the career catalog, so they're referenced by `(track, question_id)`, not a foreign key.

| Column | Type | Notes |
|---|---|---|
| `id` | varchar(36) PK | UUID4 |
| `user_id` | FK → users (cascade delete) | Included in the data export, deleted with the account |
| `track`, `question_id` | varchar(64) | Indexed with `user_id` |
| `difficulty` | varchar(16) | Copied from the question for progress counts |
| `answer` | text | What the learner wrote (max 6000 chars) |
| `score` | integer | 0-100 |
| `feedback` | JSONB | rating, summary, rubric points, notes, outline, word count |
| `provider` | varchar(32) | Which coach graded it (`built-in (offline)` today) |
| `content_version` | integer null | The question version it was written against (NULL for answers from before versioning, which means version 1). Never rewritten when the question is corrected |
| `created_at` | timestamptz | |

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

### `email_verification_tokens`
| Column | Type | Notes |
|---|---|---|
| `id` | varchar(36) PK | UUID4 |
| `user_id` | FK → users (cascade), indexed | |
| `email` | varchar(320) | The address it was sent to; it only verifies while that's still the account's email |
| `token_hash` | varchar(64) unique | SHA-256 of the link token |
| `code_hash`, `code_attempts` | varchar(64), integer | HMAC-SHA256 (server secret) of the 6-digit code; 5 wrong tries kill it |
| `created_at`, `expires_at`, `used_at` | timestamptz | 48 h lifetime; superseded by any newer send |

`users.email_verified_at` (timestamptz null) records verification. `users.pending_email` (varchar(320) null) and
`users.pending_email_at` (timestamptz null) hold a requested new address until its code or link is used.
The address then becomes `users.email`, verified at that moment. Migration `dd8a6dc39c8f`.

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

### Saved items and Learn progress
- `bookmarks`: `(user_id, item_type, track, ref_id)` unique; `item_type` is `question` (with its
  career in `track`) or `problem` (`track` empty). Items are referenced by stable id, so a retired
  question shows as unavailable instead of being replaced. `content_version` remembers the version
  a question was saved at, so a significant correction since then can be pointed out.
- `practice_collections` / `collection_items`: an ordered list per collection (`position`), one
  copy of an item per collection, queue progress (`queue_position`, `queue_done_at`) kept apart
  from scores.
- `learn_events`: `started | read | check_attempted | check_passed | practiced` per unit version;
  only check attempts repeat.
- `notes`: private notebook entries; `revision` increments on text edits so a stale save is
  refused (409) rather than overwriting; `deleted_at` keeps a deleted note restorable for 10
  minutes before it is purged.

### Shared answers
- `shares`: an owner's answer shared through an unlisted link. `token_hash` is the SHA-256 of the
  link's secret (unique; the secret itself is never stored). `snapshot` is the exact reviewer view,
  fixed at creation; `source_id` + `source_digest` let the owner see whether the original changed
  or is gone. `expires_at`, `closed_at` (no new feedback) and `revoked_at` (link off for good).
  Cascades with the owner.
- `share_feedback`: structured feedback (`clear`, `needs_evidence`, `next_step`, `comments` anchored
  to snapshot sentence indices). `reviewer_id` is set for signed-in registered reviewers and set to
  NULL if that account is deleted; `guest_name` is unverified. `(share_id, client_request_id)` is
  unique so a retried submission is stored once. Never linked to scores.

### Content quality
Generated questions and seeded problems live in code; these tables hold what happened to them
since. Content is referenced by `(content_type, content_id)` (`question` + `track/question_id`,
or `problem` + slug), not a foreign key, so a report outlives a renamed or retired item.

- `content_reports`: a learner's report. `content_version` is the version they saw; `context` is
  `content` or `feedback` (then `answer_id` names their own answer); `details` and the optional
  `excerpt` are plain text the learner chose to send. `status` is `open | investigating | resolved
  | not_actionable` and `resolution` is the public explanation. `duplicate_of` groups a likely
  duplicate under the first report (set NULL if that one is ever removed; nothing is merged).
  Cascades with the reporter; indexed by content and status.
- `content_versions`: published corrections. One row per version ≥ 2 (version 1 is the generated
  original), with the changed fields, a learner-facing `change_note` and `significant`. Unique per
  `(content_type, content_id, version)`; versions only grow. `created_by` is set NULL if that
  admin's account is deleted.
- `content_status`: one row per retired item (primary key `(content_type, content_id)`): the
  learner-facing `reason`, who retired it and when. No row means active; restoring deletes the
  row (the audit log keeps the history).
- `content_checks`: recorded automated checks (today `reference_solution`) with the test
  `content_version` they ran against, `passed`, a short `detail` and `checked_at`. Unique per
  content and check; the "reference solution passed" label is built only from these rows.
- `content_audit`: append-only log of reports, groupings, status changes, corrections,
  retirements and restores: `actor_id` (set NULL if the account is deleted), `action`, `detail`
  (JSON), optional admin-only `internal_note`, `report_id` (no foreign key, so the trail stays even
  if a report is deleted with its reporter's account).

### Answer reviews
- `answer_self_reviews`: one per answer (primary key `answer_id`, cascading with the answer and
  the account): `went_well`, `improve`, `ratings` (JSON, by criterion label), `skipped`,
  `before_feedback`, `updated_at`.
- `answer_flags`: one per answer and criterion (unique): `kind` (unclear|disagree), private
  `note`.
- `answer_evaluations`: later evaluations of an answer (the original stays on
  `practice_answers`): `rubric_version`, `content_version`, `score`, `feedback` (JSON), `reason`.
- `practice_answers.feedback` now also stores `evidence` per point, `evidence_level` and
  `rubric_version` (older rows are read as before; nothing is back-filled).

### Communication drills
- `drill_attempts`: one row per attempt (cascade with the account), indexed by user and drill:
  `drill_id`, `track` and `prompt` as they were, `text` (typed, or a transcript the learner
  checked), `source` (typed|voice), `spoken_seconds` (only when a recording was timed),
  `rubric_version`, `feedback` (JSON), `client_request_id` (unique per user), `created_at`.
  Audio is never stored.

### Whiteboard practice
- `whiteboard_drafts`: one row per user and prompt (primary key `user_id`, `prompt_id`; cascade
  with the account): `diagram` (JSON), `explanation`, `revision` (checked on save),
  `updated_at`.
- `whiteboard_attempts`: frozen attempts (cascade with the account), indexed by user and prompt:
  `prompt_id`, `prompt_version`, `rubric_version`, `diagram` (JSON as sent), `digest` (a
  fingerprint of it), `explanation`, `feedback` (JSON), `created_at`.

### Restores
- `import_batches`: one per restore (cascade with the account): `file_sha256` (to recognise the
  same file; the file itself isn't stored), `export_version`, `categories`, `status`
  (applied|failed|removed), `counts` and `removal` (JSON), `removed_at`.
- `imported_records`: which record each batch added (`kind`, `record_id`) with a `fingerprint` of
  it as restored, so removal can leave anything edited since.

### Interview reflections
- `interview_reflections`: one per application event (primary key `event_id`, cascading with the
  event, the application and the account): copies of `role_title`, `employer`, `stage`,
  `event_title` and `event_on` as they were, `questions`, `topics`, `observations`
  (`[{text, kind}]`), `practice`, `story_ids` and `outcome_history` (JSON), `clear`, `difficult`,
  `follow_ups`, `outcome`, `revision`.
- `reflection_actions`: suggested next steps (cascade with the reflection), unique per reflection
  and `key` (what they were suggested from): `kind` (practice|note|gap), `title`, `detail`, `ref`,
  `status` (suggested|accepted|dismissed), `target` and `applied_ref` (the note, entry or bookmark
  it created).

### Interview-day kits
- `interview_kits`: one row per interview event (primary key `event_id`, cascading with the event
  and so with its application; `user_id` cascades with the account), created on the first save:
  `format`, `location`, `meeting_link` (http(s), never fetched), `interviewers`, `notes`,
  `checklist`, `questions` and `story_ids` (JSON, in the learner's order).

### Schedule
- `schedule_settings`: one row per account (cascade): `timezone` (IANA), `reminders` (off by
  default), `reminder_minutes`, `quiet_start`, `quiet_end`.
- `schedule_entries`: `kind` + `ref` (the activity's id), `title` (for display and export),
  `all_day`, `on_date`, `local_time`, `timezone`, `fold`, `starts_at` (UTC, timed only),
  `duration_min`, `status` (scheduled|cancelled), `uid` (unique, for calendar files), `sequence`
  (grows with each change), `notes`, `client_request_id` (unique per user); indexed by user and
  date.

### Applications
- `applications`: one row per real application (owner cascade): `employer`, `role_title`, `link`
  (http(s), never fetched), `applied_on` and `next_action_due` (plain dates, unknown allowed),
  `stage`, `next_action`, `notes`, `target_id` (`fk_application_target`, SET NULL), `story_ids`
  (JSON list of story ids), `archived`, `client_request_id` (unique per user, for safe retries).
- `application_stage_changes`: append-only history (`from_stage`, `to_stage`, `correction`,
  `note`, and `role_title`/`employer` as they were then), cascading with the application.
- `application_events`: one row per interview or other event: `kind`, `title`, `on_date`,
  `local_time` (HH:MM), `timezone` (IANA), `starts_at` (UTC, derived only when all three are
  known), `notes`, `client_request_id` (unique per application).

### Story bank
- `experience_entries` holds **stories** (also the examples written in a job target): `title`,
  `track`, `context`, `situation`, `task`, `action`, `result`, `reflection`, `notes`, `evidence`,
  `competencies`, `tags`, `question_refs` (stable `track/question_id` links), `short_version`,
  `long_version`, `revision`, `archived`, and `target_id` + `requirement_ids` for one job target.
  `target_id` is `ON DELETE SET NULL` (`fk_experience_target`): deleting a target unlinks its
  stories instead of deleting them.
- `story_revisions`: one full snapshot per saved version (`story_id`, `revision`, `reason`
  created|edited|assisted|restored, `fields` JSON), unique per story and revision, cascading with
  the story. At most 100 per story; the first is always kept.
- `practice_answers.story_id` (`fk_answer_story`, `ON DELETE SET NULL`): the story an answer
  rehearsed. The answer is never changed when the story is.

### First-session introduction
- `user_onboarding`: one row per account (primary key `user_id`, cascades with the user), created
  on the first choice. `tour_status` (`not_started | in_progress | paused | completed |
  skipped`), `tour_kind` (`written | coding`), `tour_step`, `tour_version`, `start_choice`
  (`practice | intro | library | later`), `intro_track` (career at the welcome),
  `career_intros_seen` and `dismissed` (JSON lists of slugs and reminder keys), and timestamps
  (`welcomed_at`, `tour_started_at`, `tour_finished_at`, `updated_at`). No answer text; whether a
  real activity happened is derived from `practice_answers` and `submissions`.

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
| `236640408846` email verification | Adds `users.email_verified_at` (nullable: existing accounts start unverified) and `email_verification_tokens` |
| `e1a7c5b9d204` bookmarks and collections | Adds `bookmarks` (unique per user, type, career and item), `practice_collections` (name, queue position, queue start) and `collection_items` (position, `queue_done_at`, unique per collection and item). New tables, cascading with the user |
| `f3b8d1e6c527` learn events | Adds `learn_events` (unit id and version, kind, detail, `dedupe_key` unique per user so once-per-version events can't race). New table, cascading with the user |
| `a5c9e2f7d318` notes | Adds `notes` (text, tags, source reference and snapshot, pin/archive, `revision` for conflict detection, `deleted_at` for the undo window) with an index on `(user_id, updated_at)`. New table, cascading with the user |
| `b7d2f4a9c613` scenario attempts | Adds `scenario_attempts` (scenario id and version, mode, parent attempt, current node, recorded steps with text/feedback snapshots, ending). New table, cascading with the user |
| `c3e8a1d5f924` submission client request id | Adds nullable `submissions.client_request_id` with a unique constraint on `(user_id, client_request_id)` so a retried POST returns the original submission. Safe on populated tables |
| `d4f1b8c2e637` shares and share feedback | Adds `shares` (owner, hashed link secret, source reference and digest, snapshot, expiry/close/revoke times) and `share_feedback` (structured feedback, reviewer or guest name, unique retry key). New tables; shares cascade with the owner, a reviewer's deletion clears `reviewer_id` |
| `e5a2c7f1b948` content quality | Adds `content_reports`, `content_versions`, `content_status`, `content_checks` and `content_audit`; nullable `content_version` on `practice_answers` and `bookmarks` (NULL means version 1, so existing rows need no backfill); `users.is_admin` with server default false. New tables and nullable/defaulted columns, so populated databases migrate safely; round-tripped (upgrade, downgrade, upgrade) on PostgreSQL |
| `d52cf325b19a` onboarding state | Adds `user_onboarding` (one row per account, cascading with the user). New table, safe on populated databases; round-tripped on PostgreSQL |
| `178db0129ee0` story bank | Adds story columns to `experience_entries` (text with server default `''`, JSON lists with `'[]'`, `revision` 1, `archived` false), `story_revisions`, and `practice_answers.story_id`; changes `experience_entries.target_id` to `ON DELETE SET NULL`. Existing examples keep every word, get their target's career and a first revision with their exact text. Verified on PostgreSQL with seeded data, and round-tripped |
| `4e7000f6addb` applications | Adds `applications`, `application_stage_changes` and `application_events`. New tables, cascading with the user; round-tripped on PostgreSQL |
| `f781df0f6728` schedule | Adds `schedule_settings` and `schedule_entries`. New tables, cascading with the user; round-tripped on PostgreSQL |
| `5f47fa286244` interview kits | Adds `interview_kits` (one per interview event). New table, cascading with the event and the user; round-tripped on PostgreSQL |
| `1bbae318ce1d` whiteboard practice | Adds `whiteboard_drafts` (one per user and prompt) and `whiteboard_attempts`. New tables, cascading with the user; round-tripped on PostgreSQL |
| `99be925bf8d1` drill attempts | Adds `drill_attempts`. New table, cascading with the user; round-tripped on PostgreSQL |
| `c2cc8ed140c2` answer reviews | Adds `answer_self_reviews`, `answer_flags` and `answer_evaluations`. New tables, cascading with the answer and the user; round-tripped on PostgreSQL |
| `76e9a3e567dc` interview reflections | Adds `interview_reflections` (one per event) and `reflection_actions`. New tables, cascading with the event, application and user; round-tripped on PostgreSQL |
| `9fa5ab598fa5` restores | Adds `import_batches` and `imported_records`. New tables, cascading with the user; round-tripped on PostgreSQL |

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
