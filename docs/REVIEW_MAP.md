# Review map: the batch after `eae8088`

This is a local guide for reviewing the commits on `claude/gallant-galileo-hapob6` after `eae8088`,
the last revision whose CI was checked before this batch. It is kept here and not on the pull
request: under these packs the PR was not modified and no comment was posted.

## The pull request and its base

- [Barkyx16/CodeCoach-AI#10](https://github.com/Barkyx16/CodeCoach-AI/pull/10) is open. It
  merges `claude/gallant-galileo-hapob6` into `feature/premium-frontend`. The metadata, read on
  2026-11-05, showed 129 commits, about 646k lines added and 1,351 files changed. Most of that
  size is generated content and evaluation reports.
- Its description dates from `eae8088`. Several items it lists as open or as risks are now done:
  - the `best_score` and too-short policy;
  - revision links;
  - request keys;
  - the tour-finish race;
  - the toolbar overlap.

  **Whether to update the description is the owner's decision.** It wasn't edited.
- **Ancestry** (`git merge-base`, read-only):
  - `feature/premium-frontend` (`7ace293`) is an ancestor of this branch: 129 commits ahead,
    0 behind.
  - There is no `main` branch on the remote. Its branches are `feature/premium-frontend`, this
    branch and Dependabot's.
  - Dependabot's branches are based on `3b08ccf`, which is 9 commits behind
    `feature/premium-frontend`. That suggests the default branch was at `3b08ccf` or is another
    ref not visible here.
- **So whether `feature/premium-frontend` is the right base can't be confirmed from what's
  visible.** It is ambiguous and recorded as such. The base wasn't changed, nothing was rebased,
  and the PR wasn't split.

## Commits, grouped

| Group | Commits | Files to read first |
|---|---|---|
| **Persistence and API** | `83e4362` (keys and revision links: model, migration `c4d5e6f7a8b9`, route, export); `8ebd98d` (`evidence_level: "unknown"`); `3322c9d` (readiness schema state; with UI parts) | `backend/migrations/versions/20261104_c4d5e6f7a8b9_practice_answer_keys_revisions.py`, `backend/app/models/__init__.py` (`PracticeAnswer`), `backend/app/api/routes/careers.py` (`_save_answer`, `_replay`, `_revision_parent`), `backend/app/careers/answers.py`, `backend/app/api/routes/health.py` |
| **Score summaries** | `59f267f` (eligibility everywhere it's summarised) | `backend/app/careers/eligibility.py`, then `services/activity.py`, `explore.py`, `roles.py`, `roadmap.py` (docs/OVERNIGHT_LOG.md NX07 has the consumer table) |
| **Scoring** | `27bdc8f` (rubric v9), `b4674d8` (its results) | `backend/app/careers/grading.py` (`_denied_spans`, `_ADVICE_FRAME`), `backend/tests/test_rubric_v9.py`, `backend/evals/results/rubric-v8-vs-v9.md` |
| **Measurement process** | `731a7df` (review sample), `01bc41a` (freeze tool), `f86e159` (protocol v8), `8591307` (freeze record) | `backend/evals/review_sample.py`, `backend/evals/freeze.py`, `docs/FRESH_MEASUREMENT_PLAN.md`, `backend/evals/protocol.json` (`next_measurement`) |
| **UI** | `cd4ddac` (toolbar), `1db96ff` (tour finish), `e2f5a29` (keys and links on the question page), parts of `59f267f`, `3322c9d`, `8ebd98d` | `frontend/src/features/careers/QuestionPage.tsx`, `sendKey.ts`, `scoreLabel.ts`, `AnswerRecap.tsx`, `FeedbackCard.tsx`, `frontend/src/features/onboarding/TourFinishReconciler.tsx` |
| **Operations** | `cb0b8d2` (`check-answers`), `acf3675` (answer-save counter and the signals guide) | `backend/app/services/answer_invariants.py`, `backend/app/tracing.py` (`answer_save`), docs/OBSERVABILITY.md "Answer saves" |
| **Verification** | `413c66a`, `973b84d`, `7aedcd8` (rehearsal and contract scripts), `9842193` (browser acceptance), `9dfc59e` and `e964db1` (two existing tests brought up to this batch's behaviour, found by CI and the full browser run), plus the tests in each commit above | `backend/scripts/rehearse_answer_migration.py`, `rehearse_restore.py`, `mixed_version_probe.py`, `api_compat.py`; `frontend/e2e/release-acceptance.spec.ts`; docs/RELEASE_READINESS.md |

Generated files change with the API: `docs/openapi.json` and `frontend/src/api/schema.d.ts`. CI
checks that they match (`npm run api:types` in "API types match docs/openapi.json").

## How the pieces interact

- **Keys and links.** The revision link is part of the fingerprint, so a resend can't change it
  (409). A replay returns the link as saved.
- **Keys and summaries.** A replay adds no row, so no count or best score changes.
- **Links and summaries.** A link never makes two scores comparable by itself. The comparison
  still needs the same question version, rubric and coach, and both answers long enough to score.
  An unlinked revision whose parent was deleted keeps its score.
- These are checked together in `backend/tests/test_batch_interactions.py` on SQLite and
  PostgreSQL.

## Compatibility and migration notes

- **Migration order.** `c4d5e6f7a8b9` follows `b7c1d2e3f4a5`. It is the only migration in this
  batch, and it is additive and nullable. CI runs upgrade to head, `alembic check` and downgrade
  to base on PostgreSQL.
- **Deploy order is schema first, then code.** New code on the old schema fails every answer
  save, and readiness now says `behind`. Old code on the new schema works but ignores keys.
- **Rollback.** A schema downgrade drops every key and link, permanently.
- The executed matrix, the rehearsals and the staged plan are in docs/RELEASE_READINESS.md. The
  deployment notes there are a proposal: nothing was deployed.
- **Unsupported environments:**
  - running the SQLite migration chain from scratch (pre-existing; tests use `create_all`);
  - a physical phone, a screen reader and an on-screen keyboard (not exercised).

## The Verification batch (after `b08c3a0`, the first all-green CI revision since `eae8088`)

| Group | Commits | Files to read first |
|---|---|---|
| **Persistence and API** | `8f7da18` (the protected keyed route; readiness opens its own session) | `backend/app/api/routes/careers.py` (`answer_question_keyed`), `backend/app/schemas/careers.py` (`KeyedAnswerRequest`), `backend/app/api/routes/health.py` |
| **Privacy** | `92c3522` (`hide_parameters=True` on the engine) | `backend/app/db/session.py`, `backend/tests/test_log_redaction.py` |
| **Scoring** | `4da65a7` (rubric v10), `9ae001b` and `d7ecb36` (protocol v9, the v10 freeze) | `backend/app/careers/grading.py` (`_UNDONE`, `_denied_spans`), `backend/tests/test_rubric_v10.py`, `backend/evals/results/rubric-v9-vs-v10.md` |
| **Evaluation tooling** | `77d0459` (evals type-check clean, gated in CI; review ingestion) | `backend/evals/faults.py` (httpx2), `backend/evals/run.py` (`Reviewer`, `Hinter`), `backend/evals/review_sample.py`, `.github/workflows/ci.yml` |
| **UI** | `8f7da18` (keyed sends to the protected route; "wasn't saved" when it's refused) | `frontend/src/api/endpoints.ts`, `frontend/src/features/careers/QuestionPage.tsx` |
| **Verification** | `2f45ca3` (fixed-revision checks, pipefail), `92c3522` (comparator classes, quota tests), `1c0750a` (restore rehearsal), `31b4f72` (Pixel 7 critical flows) | `scripts/verify_revision.sh`, `backend/scripts/api_compat.py`, `backend/tests/test_answer_quota.py`, `frontend/e2e/critical-flows-mobile.spec.ts` |

**How the pieces interact.**

- **The protected route** shares the plain route's key space and handler, so replay, conflict,
  quota and metrics behave identically. It is only an extra route, so `api_compat.py` classes it
  as a compatible addition.
- **Rubric v10** changes no decision on any existing set. It does change `RUBRIC_VERSION`, so
  new answers record `v10`, and the try comparison, which requires the same rubric, won't compare
  a v9 try with a v10 one.
