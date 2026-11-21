# Release readiness: keyed answer saves, revision links, score eligibility

**Status: preparation only.** This is a reviewable decision document for the changes on branch
`claude/gallant-galileo-hapob6` since `eae8088` (Durable Saves and Release Readiness packs). It does
not approve a release. Nothing here was deployed, no production database was migrated, backed up
or restored, and no alert or monitoring was configured. Every "executed" item below ran locally,
on synthetic data, against disposable databases (`codecoach_rehearsal_*`) or the test harness.

Each check below is marked one of three ways:

- **Executed:** run, with the result shown.
- **Analysed:** reasoned from code or contracts, not run.
- **Proposed:** a step for someone with the authority to take it.

## 1. What exists (Release Readiness brief 01)

| Capability | Code | Schema | Contract | Evidence |
|---|---|---|---|---|
| **At most one saved answer per account and request key** | `_save_answer`, `_replay` in `backend/app/api/routes/careers.py`; `request_fingerprint`, `same_request` in `app/careers/answers.py` | `c4d5e6f7a8b9`: `client_request_id` (64), `request_fingerprint` (80), unique `(user_id, client_request_id)` | optional `client_request_id` (8–64 of `A-Za-z0-9_-`); replay is 200 with `Idempotent-Replayed: true`; 409 `idempotency_key_reused`; 409 `idempotency_key_unverifiable`; `/capabilities.answer_request_keys: true`. **Keyed answers go to the protected route** `POST …/answers/keyed`, which requires the key and which a server that ignores keys doesn't have (§2) | `tests/test_answer_keys.py`, `test_release_readiness.py`, `test_batch_interactions.py`; e2e `answer-replay.spec.ts`, `release-acceptance.spec.ts` |
| **Explicit revision links** | `_revision_parent` | `revises_answer_id` → `practice_answers.id`, `ON DELETE SET NULL`, indexed | optional `revises_answer_id`: your own answer to the same question, else 404 / 400 `revision_other_question`; part of the fingerprint; exported as `revises` | the same tests; e2e `learner-journey.spec.ts`, `release-acceptance.spec.ts` |
| **Score eligibility** | `app/careers/eligibility.py` and every summary listed in docs/OVERNIGHT_LOG.md (NX07) | none (reads stored feedback) | `best_scored`, `score_status` (scored / too_short / unknown), `questions_scored`, `evidence_level: "unknown"` (all additive; `best_score` keeps its raw meaning) | `tests/test_score_eligibility.py`, `scoreEligibility.test.tsx`, `upNext.test.ts`, `scoreLabel.test.ts` |
| **Client send identity** | `frontend/src/features/careers/sendKey.ts`; `QuestionPage.tsx` | none | a key is reused only for the same send. It is kept in memory only and sent only while `/capabilities` says keys are kept. The safety claim at a lost reply is made only after asking again | `sendKey.test.ts`, `keyedSends.test.tsx` |
| **Schema readiness** | `backend/app/api/routes/health.py` | reads `alembic_version` | `/health/ready` `schema`: current, behind (503), newer, unmanaged, unknown | `tests/test_health_and_platform.py`; executed on PostgreSQL (§2) |
| **Data checks** | `app/services/answer_invariants.py`, `python -m app.cli check-answers` | reads only | reason codes and ids, never text or keys | `tests/test_answer_invariants.py`; executed on rehearsal databases |
| **Signals** | `tracing.answer_save`, `codecoach_answer_saves_total{kind,result}` | none | bounded labels | `test_saves_are_counted_by_kind_and_result_without_keys_text_or_accounts`; docs/OBSERVABILITY.md "Answer saves" |

**Not implemented, and not claimed:**

- Keys aren't shared between tabs or kept across a reload.
- Keys never expire, and there's no cleanup.
- The server can't detect "accepted but ignored" by an old server; only the client's capability
  re-check covers it.
- There is no feature flag or kill switch: `answer_request_keys` is hard-coded `true` and is not
  a switch.
- The SQLite migration chain doesn't run from scratch. This is pre-existing; SQLite is test-only,
  using `create_all`.

## 2. Which versions work together (briefs 02 and 03)

Expected behaviour was written down first, then checked.

- The "old" code is `eae8088`, run from a worktree.
- The "previous schema" is `b7c1d2e3f4a5`.
- `head` is `c4d5e6f7a8b9`.
- The probes are `backend/scripts/mixed_version_probe.py` on a local PostgreSQL 16 database.

| Client | Server code | Schema | Expected | Observed | How |
|---|---|---|---|---|---|
| new | new | head | keys honoured, replay, ready | saves 201, resend 200 replayed, readiness `current` | **executed** (probe) |
| old (no key, no link) | new | head | behaves as before; added fields ignored; `best_score` raw | unkeyed saves unchanged | **executed** for the API (`test_unkeyed_answers_behave_as_before`). Contract: `scripts/api_compat.py` eae8088 → now: 205 operations compared, **0 breaking**, 2 consumer-sensitive (below), additions compatible |
| old | new | head | an answer stored with no grading metadata now lists instead of failing | **eae8088's own page code shows it as a measured score and compares it with a scored try** (its controls are right: a real low score is a score, too short shows no number) | **executed**: the historical `FeedbackCard` and `compareTries` from a worktree of `eae8088`, fed `evidence_level: "unknown"`. Restricted, not changed: such rows aren't written by any version, and stage 0 requires `check-answers` to report **0 `eligibility_unknown`** before release (§14), so no old tab can meet one. Old tabs are also offered the new version by the service worker |
| new | old (an application revert) | head | old code works on the expanded schema; keys ignored; client claims no protection | saves work; **a keyed resend saved a duplicate** (3 answers listed); `/capabilities` has no `answer_request_keys`; readiness has no `schema` field | **executed** (probe old-on-head) |
| new, capability read before the revert | old | head | no "safe to resend" claim at a lost reply | the page asks `/capabilities` once more (a read) and points to saved answers first | **executed**: `keyedSends.test.tsx` (stale and unreachable cases; failed on the previous page) and e2e `release-acceptance.spec.ts` |
| new, capabilities read from a new server, POST reaching an old one (mixed fleet) | old | head | a keyed send is never saved unprotected | the protected route is **404 on the old server and nothing is saved**; the page then asks `/capabilities`, says "your answer wasn't saved" and leaves the resend to the learner (sent without a key, to the plain route); no automatic unprotected write | **executed**: probe `protected route` against eae8088 (404, saved 0) and the new code (201, saved 1); `keyedSends.test.tsx` refused-route case; e2e specs on the protected route |
| new, older status shape | old | any | answered questions not shown as "Not answered"; no invented number | "Answered" without a number; Up next neither retries nor offers them as new (degraded) | **executed** (`scoreLabel.test.ts`); Up next **analysed** |
| any | new | previous | unsupported: deploy only after migrating | every answer save and list **500** (`UndefinedColumn`); readiness now **503 `schema: behind`** (before this change it said ready) | **executed** (probe new-on-b7c1) |
| old | old | previous | the baseline | unchanged | **analysed** |

**An old server rejecting the key field outright** is not applicable. No version of this API
rejects unknown fields: `APIModel` uses pydantic's default `extra="ignore"`, checked in
`eae8088`. That is exactly why a key sent to an old server is accepted and silently ignored.

**Consumer-sensitive changes** (the comparator's middle class, Verification brief 06). Two
responses gained the enum value `evidence_level: "unknown"`. A strict old client may reject it;
a permissive one, like `eae8088`'s page, misreads it (executed above). `api_compat.py` lists such
changes apart from breaking ones and fails on them with `--strict`. It compares names, enums and
required fields one level in. Types, formats, defaults, status codes and headers are not
compared, so a clean result there is not proof of identical behaviour.

**Readiness through its real path** (Verification brief 05). Executed with a real `uvicorn`
process against the disposable database. Head gave 200 `current`, the previous schema 503
`behind`, and SQLite `create_all` 200 `unmanaged`. With the database **unreachable**, readiness
returned **500**, because the request dependency read content state before the check. It now
opens its own session and returns **503 `database: fail`** (tested). Liveness (`/health`) is
unchanged and separate.

**Who actually consumes readiness:** nothing in this repository.

- The API image's `HEALTHCHECK` calls `/health`.
- Compose orders the schema first through its `migrate` service (`alembic upgrade head`), which
  `api` waits on.
- A deployment that routes traffic on readiness must point its probe at `/health/ready`. That is
  a production wiring step, proposed in §14 and not tested here.

**What this doesn't show.** It doesn't show that a rolling deployment is safe in general. It covers
these combinations of these two revisions only.

## 3. Replay across upgrades (brief 04)

| Case | Behaviour | Test |
|---|---|---|
| question content changed since the save | replay returns the saved answer with its own `content_version`, rubric, score and points; a new try uses the new version | `test_a_replay_after_the_question_changed_returns_the_answer_as_it_was_graded` |
| rubric or grader changed | never regraded; original `rubric_version` returned | `test_a_replay_is_never_regraded` |
| answer text differs in whitespace or case | a different request: 409 `idempotency_key_reused`, nothing saved | `test_the_answer_text_is_compared_exactly_and_never_normalised` |
| revision link added, removed or changed | a different request: 409 | `test_a_replay_cant_change_a_revision_link` |
| fingerprint from an unknown version | 409 `idempotency_key_unverifiable`, never a match and never a new row | `test_a_fingerprint_from_an_unknown_version_is_not_taken_for_a_match` |
| key stored without a fingerprint | 409 `idempotency_key_unverifiable` | `test_a_keyed_answer_without_a_fingerprint_is_never_taken_for_a_match` |
| retired question or used-up rate limit since the save | the replay is still answered, because it is checked first | `test_a_replay_is_answered_before_the_rate_limit_and_after_retirement` |

The fingerprint is `v1:` plus a sha256 of the track, question, exact answer text, story and
revised answer. A future change to what is compared needs a new version. Rows with `v1` stay
comparable only while this code computes `v1`.

## 4. Fault boundaries (brief 05)

A save is one transaction: grade (locally, deterministic, no provider), insert, flush, commit.
There is no second write to keep consistent.

| Fault point | State after | A resend with the same key | Test |
|---|---|---|---|
| before commit (grading raised) | nothing saved, no key kept | saves once (201), then replays | `test_a_failure_before_commit_leaves_nothing_and_the_retry_saves_once` |
| after commit, reply lost (serialisation raised) | one row | 200 with the same id | `test_a_reply_lost_after_commit_is_recovered_by_the_resend` |
| two copies at once | one row (database uniqueness) | the loser gets the winner's answer | `test_concurrent_resends_save_one_answer`, `test_two_requests_past_the_lookup_at_once_still_save_one` |
| a conflicting request racing the original | the conflict is refused, not saved | 409 | `test_a_conflicting_request_racing_the_original_is_refused_not_saved` |

**Guarantees.**

- At most one **saved row** per account and key.
- Grading is **not** at-most-once: two concurrent copies may both grade before one insert wins.
  That work is local and free.
- A failed save still uses one of the hour's rate allowance, because the limiter counts before
  grading.

## 5. Tabs, reloads and accounts (brief 06)

| Situation | What happens | Evidence |
|---|---|---|
| lost reply, same page | the saved-answer lookup runs first; with keys, a resend replays | `keyedSends.test.tsx`, e2e `answer-replay.spec.ts` |
| reload or tab closed after sending | the key is gone (memory only); the past-answers list shows whether it was saved; no duplicate prevention is claimed | analysed; `sendKey.ts` |
| two tabs sending the same text | two keys, so possibly two answers; nothing de-duplicates by text, on purpose | analysed |
| another account in the same browser | the key signature includes the account; nothing from the first account is shown | `sendKey.test.ts`, e2e `release-acceptance.spec.ts` |
| key storage | memory only: not in local or session storage or the URL | `keyedSends.test.tsx` |

Not implemented, and not proposed here: cross-tab coordination and a background resend queue.

## 6. Migration rehearsal, including an interrupted upgrade (brief 07)

The rehearsal is `python backend/scripts/rehearse_answer_migration.py <url of a local
codecoach_rehearsal_* database>`. It refuses any other name or host. It was **executed** on
PostgreSQL 16 and every step passed:

1. Migrated to `b7c1d2e3f4a5`, then seeded five synthetic answers: scored, too short, a legacy
   long count, a legacy short count, and nothing recorded.
2. **Interrupted upgrade:** a second connection held a read lock on `practice_answers`, so the
   upgrade's ALTER hit `lock_timeout` (`LockNotAvailable`, exit 1, about 2 s). Afterwards the
   version was still `b7c1d2e3f4a5`, no new column existed, and every row was byte-identical
   (digest of id, owner, text, score and feedback).
3. **Retry:** `alembic upgrade head` reached `c4d5e6f7a8b9` with no row rewritten. The 5/5
   existing rows have no key, fingerprint or link. `alembic check` reported "No new upgrade
   operations detected".
4. The legacy rows were classified as documented: scored, too_short, scored, too_short, unknown.

**Engine notes.**

- On PostgreSQL the whole `alembic upgrade` runs in one transaction (`migrations/env.py`), and
  DDL is transactional. A failure therefore leaves the previous revision intact, and the recovery
  is simply to remove the cause (here, the lock) and run `alembic upgrade head` again. No
  `alembic stamp` is needed or wanted.
- SQLite: the migration chain isn't supported from scratch (pre-existing), and this migration's
  batch mode would copy the table. **Not rehearsed.**

## 7. Restore rehearsal (brief 08)

The app's own restore (`/restore`) covers notes, stories, bookmarks and applications, not
practice answers. A database-level backup procedure isn't documented in this repository.

Executed instead: `python backend/scripts/rehearse_restore.py <src> <dst>` (both local
`codecoach_rehearsal_*` databases), using standard `pg_dump --format=custom` and
`pg_restore --clean --if-exists`. Every step passed:

- **Seed:** two accounts seeded through the API, each with the **same key string**, a resend, a
  revision and a too-short answer.
- **Logical comparison:** 53 tables, 6 answers, migration `c4d5e6f7a8b9`, with the same counts
  and the same answer digests.
- **Data checks:** `check-answers` was clean on the copy (6 answers, 2 accounts).
- **Smoke test:** each account signed in on the copy. Its resend returned **its own** original
  answer (200, replayed), so the two keys weren't merged, and its summaries were unchanged.

The rehearsal was extended in the Verification batch and run again. The source also holds an
answer with no grading metadata. `check-answers` must then report exactly the same on the copy as
on the source: 7 answers, 1 unknown notice and 2 revision links on both, and it passed.

**Which artifact keeps what** (Verification brief 10):

| Artifact | Answers, ids, scores, feedback | Revision links | Request keys and fingerprints (dedup state) |
|---|---|---|---|
| database dump and restore (`pg_dump`/`pg_restore`) | kept | kept | **kept**: replays work on the copy (executed) |
| account export (`GET /api/v1/me/export`) | kept | kept (`revises`) | **not included, by design** (tested). Not a recovery path for dedup state |
| app restore (`/restore`) | answers aren't imported | — | — |
| a schema downgrade, then re-upgrade | kept | **lost** | **lost**: a resend after it is a new answer (§8). A passing rehearsal step that lost them proves the loss, not protection |

Keys are never reconstructed from answers, and parents are never inferred.

This says nothing about a production backup schedule, recovery time or data-loss window. None
exists here. **Proposed:** an operator chooses and documents one before release.

## 8. Rollback limits (brief 09)

| Option | Reversible? | Effect on data | Evidence |
|---|---|---|---|
| **Revert the application only** (old code on the expanded schema) | yes, while migrations stay additive | new rows stay. Old code ignores keys and links, so a resend during the revert can save a duplicate. Old code returns no `revises_answer_id` and no eligibility fields | **executed** (probe old-on-head) |
| **Turn the feature off** | not available | there is no flag | analysed |
| **Downgrade the schema** (`alembic downgrade b7c1d2e3f4a5`) | **destroys data** | every answer, its text, score and feedback stays. **Every key, fingerprint and revision link is dropped.** Re-upgrading doesn't bring them back: in the rehearsal 2/2 keys were lost and 0 links were left | **executed** (rehearsal step 4) |

**Recommended order:** revert the application first, which preserves new rows and their links.
Then fix forward with a new migration or code. A schema downgrade should be a last resort,
decided knowing it permanently loses the keys and links.

## 9. Deletion and revision links (brief 10)

**Policy in force (unchanged).** There is no per-answer delete. Deleting an account removes all
of its answers (`ON DELETE CASCADE` from `users`). Outside that, rows are removed only by an
operator.

| Case | Behaviour | Test |
|---|---|---|
| the answer a revision points to is deleted | the revision stays, unlinked (`SET NULL`); its score still counts | `test_deleting_an_earlier_answer_leaves_its_revision_unlinked`, `test_deleting_the_revised_answer_keeps_the_revision_and_its_score` |
| a revision is deleted | the earlier answer is untouched | `test_deleting_a_revision_leaves_the_answer_it_revised` |
| a link to another account's answer | 404: existence isn't confirmed, and nothing is saved | `test_a_revision_link_must_be_yours_and_to_the_same_question` |
| an account is deleted | its answers and links go; another account with the same key string keeps its answer and its replays | `test_deleting_an_account_removes_its_answers_and_links_and_nobody_elses` |
| UI, earlier answer not listed | "revises an earlier answer that isn't in this list", with no guess | `keyedSends.test.tsx` |

## 10. Data checks (brief 11)

`python -m app.cli check-answers` is read-only: it sets a read-only transaction on PostgreSQL and
always rolls back. Rules and reason codes are in `app/services/answer_invariants.py`. Each rule
is tested with one violation, alongside valid controls (a real low score, a too-short answer, the
same key under two accounts, a valid revision). Unknown metadata is a **notice**, never a score.

It was executed on the rehearsal databases: 17 answers across 5 accounts with no violation and
1 notice (the seeded "nothing recorded" row), and the restored copy was clean. It was **not run
against any shared or production database.**

## 11. Request keys: bounds and retention (brief 12)

**Bounds.**

- A key is 8–64 characters of `A-Za-z0-9_-`. Anything else is a 422, with nothing saved
  (`test_keys_are_validated_and_a_refused_key_saves_nothing`).
- Many distinct keys and both size limits are covered by
  `test_keys_at_the_size_limits_and_many_distinct_keys`.
- Keys are untrusted identifiers, scoped to the account. They grant nothing, and the same string
  under another account is a different key.
- Keys are not in the save's span attributes or metric labels, and the export leaves them out.
  The metrics page and `me/export` are tested; that the span attributes leave them out is
  analysed from `tracing.answer_save`.

**Retention: decided by what the code does, no new policy.** A key lives exactly as long as its
answer, with no expiry and no cleanup. A resend any time later replays. The promise narrows in
these cases:

- An answer removed with its account takes its key with it.
- A schema downgrade drops every key (§8).
- A client that loses its key (reload, another tab) or makes a new one after an uncertain outcome
  sends a new request. The server can't tell it from a new try, so the page checks saved answers
  first.

**What the hourly answer allowance charges, as implemented and now pinned by tests**
(`tests/test_answer_quota.py`, Verification brief 08). The limiter counts a request after the
replay lookup and the retirement check, and before grading.

| Request | Charged? | Rows |
|---|---|---|
| a new answer | yes | +1 |
| a replay of a saved keyed request (also after the allowance is used up) | **no**: answered first | 0 |
| a key conflict (409) | no | 0 |
| a save that fails while grading | **yes** | 0 |
| each copy of a duplicate that got past the lookup at the same time | **yes, both** | +1 |
| a new answer over the allowance (429) | no | 0, and it's `rejected` in the save metric, never a learner failure |

**Charging a failed save is a product decision, not changed here.** The options are:

- **(a)** Keep charging it: abuse protection stays simple, and a broken server can't be hammered
  for free.
- **(b)** Refund the hit when the server fails (5xx). This is kinder to learners but needs a
  refund call on every failure path.
- **(c)** Charge after grading. A grading failure is then free, but grading work spent on refused
  requests rises.

**Proposed for a later decision:** whether keys should expire, which would bound the unique
index's growth (one short string per keyed answer).

## 12. Signals (brief 13)

See docs/OBSERVABILITY.md, "Answer saves: what each signal shows". There is one bounded counter
per save result, plus the span. Alert thresholds are **proposed** and not configured.

**Logs, at the real boundary** (Verification brief 09, `tests/test_log_redaction.py`). Synthetic
markers for answer text, a request key and the bearer token were checked against everything the
app's loggers write, formatted by its own JSON formatter.

- **The leak.** A real database failure during a save logged SQLAlchemy's error, which carries
  the statement's bound values: the key, and for the insert the answer text. The engine now uses
  `hide_parameters=True`, and the test fails without it, on SQLite and PostgreSQL.
- **Clean paths.** Save, replay, conflict, validation error and grading failure log none of the
  markers, and keep their span categories.
- **Not covered:**
  - external log collectors and shippers;
  - a DBAPI error whose own detail text quotes values (for example a unique-violation `DETAIL`;
    the one on request keys is caught and never logged);
  - anything not written through the `codecoach` loggers.

## 13. Browser acceptance (brief 14)

Executed with Playwright 1.63 and Chromium (the `desktop` project), against the real backend
(SQLite e2e database):

- `release-acceptance.spec.ts`: 2 tests passed. They cover a server that stopped advertising
  keys by the lost reply; a too-short answer never shown as a score; an explicit, linked revision
  that sets the best score; and another account in the same browser.
- `answer-replay`, `learner-journey`, `careers` and `session` were re-run after the question page
  changed: 5 passed.
- The full browser suite (92 tests) then ran on `7aedcd8`'s code: 88 passed, 3 skipped, 1
  failed. `progress.spec` still expected "Scored N/100" for a 17-word answer, which since the
  eligibility change is listed as "Too short to score (17 words)". Its expectation was updated in
  `e964db1`, and it then passed (2/2).

**Pending, not done:** a physical phone, a screen reader and an on-screen keyboard.

## 14. Staged release plan (brief 15): proposed, not approved

Every stage below needs a person's decision and authority. This document neither grants nor
records that authority.

| Stage | Action | Advance only when | Watch | Stop / recover |
|---|---|---|---|---|
| 0. Before | **Proposed:** take and verify a production backup with the operator's own procedure, and decide the backup schedule and retention. Run `python -m app.cli check-answers` (read-only) on the restored copy | a restore of that backup has been rehearsed on a disposable copy (`scripts/rehearse_restore.py` is a model), and `check-answers` reports **no violations and 0 `eligibility_unknown`** (an old open tab would misread such a row, §2) | — | don't start; if unknown rows exist, decide how to present them to old clients first |
| 1. Expand the schema | `alembic upgrade head` (adds three nullable columns, a unique constraint, a foreign key and an index; locks `practice_answers` briefly) | CI green on the candidate SHA, including "Migrations apply cleanly and match the models". Run at a quiet time, with a `lock_timeout`, so a long read makes it fail cleanly instead of queueing writes | the migration exits 0; `/health/ready` on the **old** code still says ready | it fails as in §6 (nothing applied): remove the cause and retry |
| 2. Deploy the new code | API first, then the web client | stage 1 done; new instances report `/health/ready` `schema: current` (an instance saying `behind` isn't ready) | `codecoach_answer_saves_total` by result; 5xx rate; `check-answers` on a **read replica or restored copy** (not run here) | revert the application (old code works on the expanded schema, §8); new rows stay |
| 3. Observe | normal traffic | an agreed period with no `key_unverifiable` and errors within the proposed thresholds (docs/OBSERVABILITY.md; no baseline exists) | as above | as above |
| — | **Not a default:** `alembic downgrade` | only by explicit decision | — | permanently drops keys and links (§8) |

**Known unknowns:**

- production data shape (no production data was inspected);
- real traffic baselines;
- the deploy platform's readiness wiring (the image's health check calls `/health`; nothing in
  the repository consumes `/health/ready`);
- whether production routes requests to a mixed fleet during a rollout. The protected route
  makes that safe for keyed sends; unkeyed sends never claimed protection;
- the old browser bundle against the new API in a real browser. Its components were executed
  against the new value; the whole bundle wasn't run.

**Decisions this needs from people:**

- whether to release;
- the backup procedure;
- whether keys should expire;
- whether the deployment's health check should use `/health/ready`;
- who watches stage 3.
