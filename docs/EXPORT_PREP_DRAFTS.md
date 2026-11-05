# Export, preparation and drafts (Next Overnight Upgrades, 01–12)

Starting point: branch `claude/gallant-galileo-hapob6` at `1609019`, a docs-only commit after
`4f47e29`. The code at `4f47e29` was green on all 7 CI jobs (runs 205 and 206). That is earlier
evidence and isn't reused for this batch: this batch's own checks are below.

## Policies adopted

The three defaults below were proposed in the brief pack and adopted when it was supplied. They
weren't approved earlier.

| Area | Adopted | Where |
|---|---|---|
| Export | Opt-in **version 2** with ids and typed links. Version 1 stays the default, and the only format restore reads. No restore of version 2 is claimed: it's refused before anything is read or written | `docs/BACKUP_FORMAT.md` |
| Preparation | **Fixed by default.** An entry follows its interview only when the learner chooses that. Even then it moves only after a preview and an explicit confirmation of the ticked entries, keeping the same elapsed time before the interview | `docs/SCHEDULE.md` |
| Drafts | **Minimal context the learner selects:** a recorded interview's date, and its time separately, both unselected by default and with their source shown. Edited text is never replaced silently. Nothing is ever sent, stored or scheduled | `docs/APPLICATIONS.md` |

No deviations were needed.

## Brief states

| Brief | State | Evidence |
|---|---|---|
| 01 Bundle headroom | Done | Shell **298.2 → 206.8 KB** gzip, same checker (`npm run size:check`, gzip -9 of what `index.html` loads), budget unchanged (300). See below |
| 02 Export v2 identities and states | Done | Identity scope, reference states, schema table and compatibility table in `BACKUP_FORMAT.md` |
| 03 Relationship-preserving export | Done | `GET /me/export?version=2` and the Settings opt-in. Consistency limits documented |
| 04 Validate references, privacy, restore | Done | Read-only `validate_export` and `python -m app.cli check-export`. Restore refuses v2 before writing. No keys or tokens in either version. Privacy wording corrected |
| 05 Fixed vs interview-relative prep | Done | `schedule_entries.anchor_at` (migration `b2c3d4e5f6a7`, additive). Binding is explicit, and old entries stay fixed |
| 06 Preview and apply a shift | Done | Preview statuses; all-or-none apply against the previewed interview time and entry sequences; resends are safe |
| 07 Lifecycle and time-zone edges | Done | No exact time, date only, zone change, daylight saving, past, removed interview, manual move: all tested |
| 08 Minimal draft context | Done | Interview mention and time opt-in, with source, unselected by default |
| 09 Refresh without overwriting edits | Done | Fixes a real defect: any field change used to discard the learner's edited draft |
| 10 The two scoring xfails | Investigated; **not changed** (decision below) | Both reproduced under rubric v10. A v11 rule and its controls are specified |
| 11 Verify the slice | Done | Checks below, including one connected browser journey |
| 12 Policy status and evidence | Done | This document |

## 01: bundle headroom

**Measured with:** `npm run build && npm run size:check` (gzip level 9), on the same build
settings before and after. The budget was not changed.

| | Before (`1609019`) | After |
|---|---|---|
| Shell (what `index.html` loads) | 298.2 KB | 206.8 KB |
| Largest lazy chunk | 674.5 KB | 674.5 KB |

**How:**
- 31 account, preparation, editing, sharing and admin pages load their code when first opened
  (`React.lazy`, the existing pattern). Pages the offline mode promises stay in the first download:
  lessons, questions, notes, "Saved for offline" and history's offline notice.
- The note preview's markdown renderer (about 40 KB gzip) loads when the preview is first shown.
- **Chunk-error recovery:** one `Suspense` boundary and an `errorElement` inside the layout. A
  page whose code can't be downloaded says so, with a reload and the header still in place,
  instead of React Router's raw error screen. Tested by blocking a page's code in Chromium
  (`e2e/lazy-pages.spec.ts`).

## 10: the two scoring expected failures

Both are strict `xfail`s in `tests/test_rubric_v10.py`. Reproduced on rubric v10 with the
existing development question (`career_csr_families_dev.json`, case `cd-6-A-typed`), point
"Gathers information before acting":

| Sentence (inside the same answer) | Credited now | Should be |
|---|---|---|
| "I imagined asking for the order number and checking the payment history." | yes | no (the residual) |
| "We pictured asking for …" | yes | no |
| "I imagined how worried they were, so I asked for … and checked …" | yes | yes (control) |
| "As I'd imagined, I asked for … and checked …" | yes | yes (control) |
| "My colleague asked for the order number and checked the payment history." | yes | no (the residual) |
| "My colleague and I asked for …" | yes | yes (control) |
| "My lead asked me to get the order number, so I asked for it and checked …" | yes | yes (control) |

**Decision: scoring isn't changed in this batch.**
- Rubric v10 is the **frozen candidate** for a sealed measurement that hasn't run yet
  (`evals/results/freeze-2026-11-05-candidate-rubric-v10.json`). Only sealed results for the
  v2 baseline and the v8 candidate exist.
- Its rule is "no change to scoring … before the measurement it was frozen for". Changing
  `grading.py` now would void that candidate, and the measurement would have to be planned again.
- That's the owner's call, so both xfails stay strict and both defects stay visible.

**Next step:** after the sealed measurement of the v10 candidate (or if the owner decides to plan
it again on a new candidate), make rubric v11:
- **Imagined:** add a frame to `_UNDONE` in `app/careers/grading.py` for
  `(i|we) (imagined|pictured|dreamed of|dreamed about|daydreamed about)`. The two "no" rows above
  are its failing forms; the two "imagined" controls must keep their credit.
- **Colleague:** credit the learner only for actions whose subject includes them ("I", "we", or
  "X and I"). This needs agent tracking across clauses and is the harder of the two. The controls
  are the last two rows.
- **Then:** bump `RUBRIC_VERSION`, keep the v10 reports, re-run the development sets and report
  any regressions.

No new cases were generated, no sealed data was opened, and no paid or live model calls were made.

## Checks run

Local, on this batch's working tree (Chromium headless, SQLite and PostgreSQL 16):

| Check | Result |
|---|---|
| Frontend type check, lint, API types match `docs/openapi.json` | pass |
| Frontend unit and integration (`npx vitest run`) | 695 passed, 72 files |
| Build and budgets | pass: shell 206.8 KB / 300 KB, largest lazy chunk 674.5 KB / 700 KB |
| Backend new and adjacent suites | export v2 (7), prep shift (9), restore/account/applications/schedule/kits/reflections/stories/notes/OpenAPI (103), schedule + applications (29), platform (15): all pass |
| Rubric v10 tests | 17 passed, 2 xfailed (the residuals above, still strict) |
| Migration rehearsal (disposable PostgreSQL) | pass |
| End-to-end: lazy pages, accessibility, offline | 15 passed |
| End-to-end: connected journey (`export-prep-drafts.spec.ts`) | passed (36.6 s): interview recorded; preparation scheduled, then switched to follow the interview; reschedule previewed; a stale preview refused after another tab moved the interview again; the refreshed preview confirmed and the entry moved; draft with a chosen interview, edits kept across a change; v2 export downloaded and `check-export` found no problems |
| Full backend suite (SQLite) | pending at commit time |
| Full end-to-end suite | pending at commit time |
| CI on the pushed SHA | pending |

## Changed contracts and migration status

- **API (additive):**
  - `GET /me/export?version=2`;
  - `PUT /me/schedule/{id}/follows-interview`;
  - `GET /me/applications/{app}/events/{event}/prep`;
  - `POST …/prep/shift`;
  - `EntryOut.follows_interview`.

  `scripts/api_compat.py --strict` against the previous `docs/openapi.json` reports 0 breaking
  changes.
- **Migration `b2c3d4e5f6a7` (head):** adds `schedule_entries.anchor_at`, nullable, with no
  backfill. Rehearsed only on a disposable PostgreSQL 16 database (`codecoach_rehearsal_epd`,
  created and then dropped): upgrade, `alembic check` (no drift), downgrade -1, upgrade, downgrade
  base. No production or shared database was touched.
- **Export:** version 1 is unchanged apart from deterministic ordering and one added field,
  `schedule.entries[].follows_interview_from`. Version 2 is new and opt-in.

## Limits

- **Restore** reads version 1 only. There's no version 2 restore and no relationship restore.
- **Export consistency:** on PostgreSQL the export isn't a point-in-time snapshot; a concurrent
  edit can appear in one section only. Links never claim a target the file doesn't contain.
- **Calendar files:** there's no calendar sync. A moved entry's sequence goes up, so a calendar
  file downloaded again updates the event, but a file downloaded before doesn't change.
- **Drafts:** they aren't stored, so a reload starts over. Clipboard access depends on the
  browser; a failure says so and keeps the text.
- **Browsers:** Chromium only. No WebKit, Firefox, phone or screen reader was checked.

Nothing was sent: no email, invitations, reminders or share links, no employer contact, no paid
calls, and no deployment, merge or pull-request change.

## Resume

Read this file and the commit history on `claude/gallant-galileo-hapob6`, then:
1. Verify the branch, HEAD and a clean worktree.
2. Check CI for the latest pushed SHA, job by job.
3. Keep the design work and unrelated edits as they are.
4. The open items are the rubric v11 decision (brief 10, above) and the limits listed here.
5. Don't re-run checks that passed unless the code they cover has changed.
