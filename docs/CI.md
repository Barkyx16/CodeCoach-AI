# CI: what runs, what it proves, and how to record it

Volume 8, prompt 10. The workflow is `.github/workflows/ci.yml`. This page is the guide to reading
its results; it isn't a record of any particular run.

## The one check to read: "CI summary"

Every run ends with **CI summary**. For the exact event and SHA it lists each job, whether this
change required it, its result, and a verdict, and it **fails closed**:

- the change couldn't be classified (the `changes` job didn't succeed, or gave no lanes);
- a required job failed, was cancelled, or was skipped;
- any job that ran and failed, even one the change didn't need;
- a job the summary expects is missing from the run (a test keeps the workflow's job list and
  the summary's in step: `backend/tests/test_ci_lanes.py`).

So a required job can't be skipped into success, and a cancelled run is never green. Its table is
on the run's summary page. If branch protection is used, **CI summary** is the check to require;
that's a repository setting, and it hasn't been changed here (no merge queue is configured).

## Which jobs a change needs

`scripts/ci_classify.py` decides, conservatively. For a pull request it looks at everything the
pull request changes against its base, not only the last push; for a push, at what changed since
the previous head; a manual run (`workflow_dispatch`) runs everything.

| Path | Lanes |
|---|---|
| `.github/`, `scripts/ci_*`, `deploy/`, `docker-compose*`, dependency lists and lockfiles (`backend/requirements*`, `runner/requirements*`, `frontend/package*.json`), `pyproject.toml`, `.gitignore`, `.dockerignore` | everything |
| a deleted path, an empty or unreadable diff, any path no rule names | everything |
| `docs/openapi.json` (the API contract) | backend, frontend, e2e |
| `backend/` (migrations included) | backend (both halves), e2e, sandbox, docker |
| `frontend/` | frontend, e2e, sandbox (the judge's browser test), docker |
| `runner/` | runner, sandbox, docker |
| `scripts/rehearse_production_storage.sh` | docker |
| `scripts/rehearse_web_csp.sh` | e2e |
| `scripts/verify_*` | backend |
| `scripts/check_secrets.py`, `.secrets.baseline` | the security job (always runs) |
| other `docs/` and top-level `*.md` | documentation only |

The security job (dependency audit, secret scan) runs on every change.

A **documentation-only** change runs the security job and nothing else, and the summary says
"documentation-only change: the code jobs didn't run on this SHA … not code evidence". That
SHA's code is whatever an earlier run validated; the summary doesn't claim more. On a pull
request whose changes include code (the long-lived one included), every push runs the code jobs,
because the lanes are worked out from the whole pull request.

## Release candidates: the full route

Run the workflow by hand (**Actions → CI → Run workflow**, `workflow_dispatch`) on the candidate's
branch: it runs every lane regardless of what changed. Locally, `scripts/verify_revision.sh REV
OUT --pg URL --pg-admin ADMIN_URL --e2e` runs the same suites on a clean worktree of one revision.
A release candidate needs one of these on its exact SHA.

## When CI runs

- `pull_request`: every push to a pull request's branch.
- `push`: only `main`, `master` and `feature/premium-frontend` (the long-lived branches). Before,
  every push to a pull request's branch also started a `push` run: two identical runs per change
  (each about 72 minutes), and twice the exposure to a timing failure (runs 273 and 274 on one
  commit disagreed).
- `workflow_dispatch`: by hand, everything, any branch. A branch without a pull request gets CI
  this way.

One run per pull request at a time: a newer push cancels the older run (`concurrency`). A
cancelled run's summary is cancelled or failed, never green.

## Caches

Dependency caches only: pip (keyed by the requirements files) and npm (keyed by
`package-lock.json`), through `actions/setup-python` and `actions/setup-node`, whose keys also
include the runner platform (and, for pip, the Python version). Nothing else is cached: not test results, databases,
built images with credentials, judge or sandbox state. A cache hit only saves an install; every
required test still runs.

## Timings

Measured before the change (run 274, pull_request, `52d3bec`, all 7 jobs passed):

| Job | Duration | Waited for |
|---|---|---|
| Backend: lint, types, SQLite tests (18 min 31 s), PostgreSQL tests (35 min 53 s), migrations, reference solutions, content gates | 55 min 41 s | — |
| End-to-end | 15 min 56 s | backend, frontend |
| Sandbox | 12 min 24 s | backend, runner |
| Docker | 3 min 48 s | — |
| Frontend | 2 min 41 s | — |
| Security | 52 s | — |
| Runner | 25 s | — |
| **The run, start to finish** | **71 min 44 s** | backend → end-to-end was the critical path |

What changed, and why: end-to-end and sandbox don't use anything the backend job makes, so they no
longer wait for it; the backend's SQLite and PostgreSQL halves run as two jobs on separate runners
(each with its own database server, so no test resource is shared). Every suite still runs.
Expected critical path: the PostgreSQL half, about 38 minutes. **That is an estimate from the
numbers above, not a measurement.** The first run of the new workflow is recorded in the next
code commit's message with its own job timings, compared with this table.

## Suite time and memory

Volume 13, prompt 9. The backend suites gate every push, so their time and memory decide how often
the work can be checked. Measure them with one command (on PostgreSQL, with `TEST_DATABASE_URL` and
`TEST_DATABASE_ADMIN_URL` set as for the suite):

```bash
cd backend && python scripts/suite_table.py --out suite-run.json
```

It runs pytest with the measuring plugin (`tests/suite_measure.py`, off unless asked for; it never
changes, skips or reorders a test) and prints, per test file, the time in its tests and how much of
that was setting them up, the resident memory its tests added, and what they left behind: test
clients still entered, database connections still open (with **where each was opened**: the test
line, or the app's when no test frame led there), and apps still alive after a garbage collection.
The run's record (`--out`) keeps the wall time, the peak resident memory, **how long the process
took to exit after printing its summary**, the pass, skip, xfail and failure counts, the threads
still running at the end, every thread's stack every few seconds while the process was exiting, and
the time the plugin's own collections took (between files, counted apart so they're never charged
to a file). `tests/test_suite_measure.py` checks that a deliberately leaked client and connection
are reported against their file and a tidy file isn't, and that a thread left running is listed and
its stack written while the process waits for it.

### What was wasting it

1. **Every test's app stayed alive.** FastAPI keeps module-level caches keyed by endpoint function
   (`fastapi.dependencies.models`: whether a dependency is a generator, a coroutine…). The app's
   `/metrics` endpoint is defined inside `create_app`, so each cached entry held its app, and with
   it the app's engine, caches and everything it made: at the end of the run 1,181 apps were alive
   on SQLite and 1,229 on PostgreSQL, the process peaked at 7.4 GB and 9.1 GB, and on PostgreSQL it
   then spent 333 s freeing them after its summary. Production builds one app per process, so this
   was the suite's, not the app's: an autouse fixture (`tests/conftest.py`) clears those caches
   after each test (FastAPI recomputes the classifications on the next call). After: no app alive at
   the end, 0.76 GB and 1.26 GB.
2. **Every test's SQLite database was built from scratch** (tables, then the 303 seeded problems),
   about 0.5 s per app. Now one database is made by the app's own startup once per session, and a
   test's own database starts as a copy of it; the app then runs its whole startup on that copy as
   before, so every test still has a database of its own. PostgreSQL runs make theirs as before.
3. **Engines that tests made for themselves were never disposed**, so their pooled connections
   stayed open for the rest of the run: 28 left open by eleven files on SQLite, 46 by twelve on
   PostgreSQL, the same before and after the two fixes above. They now come from a
   `disposable_engine` fixture, disposed when the test ends; measured again on those files, 27
   became 6 on SQLite and 14 became 1 on PostgreSQL. What's left is CLI commands run inside a test (`housekeeping`, `grant-admin`, `revoke-admin`,
   `email-status`, `prune-guests`, `check-rls`): each opens the database once for its process, and
   in production each runs as its own process (compose and the backup service start one per
   command), so it isn't a leak the app has; app code is unchanged. The measurement still lists
   them, with where each was opened.

### Before and after

Each pair ran side by side on the same machine: the tree before (`4c74664`, with only the
measuring plugin added) and after (the Volume 13, prompt 10 commit with these changes). Test counts
are the same on both sides.

| | SQLite before | SQLite after | PostgreSQL before | PostgreSQL after |
|---|---|---|---|---|
| Peak resident memory | 7,388 MB | 756 MB | 9,104 MB | 1,257 MB |
| Apps alive at the end | 1,181 | 0 | 1,229 | 0 |
| Exit after the summary | not recorded | not recorded | 333 s | 22.5 s |
| Results | 3,373 passed, 46 skipped, 2 xfailed | the same | 3,417 passed, 1 failed, 1 skipped, 2 xfailed | 3,418 passed, 1 skipped, 2 xfailed |

The one failure before is the memory's doing, not the test's: `test_searching_is_rate_limited_per_account`
sends 121 searches and expects the 121st refused inside the limiter's window; in the 9 GB process
they took longer than the window. Alone on the same tree it passes in 5.2 s, and it passed in the
run after.

**Wall time is CI's.** The machine these ran on wasn't idle (each pair ran together, beside other
suites), and the "before" runs' wall times also include the plugin's own collections over a 7 to
9 GB heap, which weren't yet counted apart. So the time comparison is CI's timed steps, on the
same runner type: before, run 329 (`b3f34bf`): **SQLite tests 33 min 0 s, PostgreSQL tests 70 min
56 s** (they were 18 min 31 s and 35 min 53 s in run 274, before the suite and its memory grew).
After: run 331 (`daa009c`), the first CI run with these changes: **SQLite tests 18 min 40 s**
(from 33 min 0 s), **PostgreSQL tests 73 min 5 s** (from 70 min 56 s; that job also failed one
query-budget assertion, fixed in `8959a18`, which doesn't change its time). Memory fell on both;
time fell on SQLite only: on PostgreSQL the time is the databases' set-up (each test makes and
drops its own), which these changes didn't touch (Volume 15, prompt 1, is about that: "The
PostgreSQL suite's set-up" below).

Locally the slowest file is `test_judge_sandbox.py` (388 judged runs, 14 to 19 minutes) because
this machine has gVisor; in CI's backend jobs those tests skip and run in the sandbox job.

**SQLite, the ten slowest files** (seconds in the file's tests, of which setting up)

| Before | | After | |
|---|---|---|---|
| `test_judge_sandbox.py` | 843 (426) | `test_judge_sandbox.py` | 863 (452) |
| `test_eval_harness.py` | 125 (34) | `test_eval_harness.py` | 75 (20) |
| `test_eval_protocol.py` | 62 (0) | `test_eval_protocol.py` | 52 (0) |
| `test_email_verification.py` | 53 (28) | `test_test_design.py` | 46 (3) |
| `test_test_design.py` | 50 (3) | `test_live_eval.py` | 45 (0) |
| `test_interviews.py` | 48 (37) | `test_packet_plans.py` | 35 (8) |
| `test_judge.py` | 46 (0) | `test_tracing.py` | 32 (8) |
| `test_live_eval.py` | 40 (0) | `test_roadmap.py` | 29 (10) |
| `test_answer_keys.py` | 38 (20) | `test_disputes.py` | 27 (8) |
| `test_explore.py` | 34 (26) | `test_seed_and_reference_solutions.py` | 26 (19) |

**SQLite, the ten largest memory growths** (MB of resident memory a file's tests added)

| Before | | After | |
|---|---|---|---|
| `test_judge_sandbox.py` | 772 | `test_career_scope.py` | 56 |
| `test_tracing.py` | 256 | `test_access_log_file.py` | 27 |
| `test_disputes.py` | 234 | `test_judge_sandbox.py` | 22 |
| `test_roadmap.py` | 230 | `test_actions.py` | 17 |
| `test_story_freshness.py` | 216 | `test_requirement_versions.py` | 17 |
| `test_requirement_versions.py` | 213 | `test_applications.py` | 16 |
| `test_question_rounds.py` | 198 | `test_demo.py` | 16 |
| `test_interviews.py` | 196 | `test_related_practice.py` | 14 |
| `test_request_identity.py` | 174 | `test_lifecycle_more.py` | 13 |
| `test_explore.py` | 155 | `test_tracing.py` | 13 |

**PostgreSQL, the ten slowest files** (seconds in the file's tests, of which setting up)

| Before | | After | |
|---|---|---|---|
| `test_judge_sandbox.py` | 1032 (619) | `test_judge_sandbox.py` | 1143 (660) |
| `test_eval_harness.py` | 78 (20) | `test_test_design.py` | 76 (14) |
| `test_answer_keys.py` | 71 (46) | `test_answer_keys.py` | 75 (47) |
| `test_test_design.py` | 61 (9) | `test_eval_harness.py` | 73 (19) |
| `test_tracing.py` | 58 (34) | `test_roadmap.py` | 71 (46) |
| `test_storage.py` | 52 (1) | `test_tracing.py` | 69 (46) |
| `test_backup.py` | 51 (38) | `test_story_freshness.py` | 64 (38) |
| `test_roadmap.py` | 51 (34) | `test_refresh_recovery.py` | 64 (58) |
| `test_disputes.py` | 50 (36) | `test_storage.py` | 63 (1) |
| `test_eval_protocol.py` | 50 (0) | `test_explore.py` | 62 (54) |

**PostgreSQL, the ten largest memory growths** (MB of resident memory a file's tests added)

| Before | | After | |
|---|---|---|---|
| `test_judge_sandbox.py` | 937 | `test_career_scope.py` | 76 |
| `test_tracing.py` | 288 | `test_access_log_file.py` | 35 |
| `test_roadmap.py` | 264 | `test_answer_keys.py` | 34 |
| `test_disputes.py` | 245 | `test_shares.py` | 32 |
| `test_requirement_versions.py` | 242 | `test_execution_health.py` | 29 |
| `test_story_freshness.py` | 240 | `test_related_practice.py` | 25 |
| `test_interviews.py` | 226 | `test_tracing.py` | 25 |
| `test_question_rounds.py` | 220 | `test_plan_updates.py` | 23 |
| `test_request_identity.py` | 196 | `test_account.py` | 22 |
| `test_explore.py` | 181 | `test_roadmap.py` | 22 |

Over the whole run, the files' growths add up to 7,291 MB before and 485 MB after on SQLite, and
9,041 MB and 1,005 MB on PostgreSQL. Resident memory alone can't say whether what's left is live
objects or memory the allocator kept after freeing them, so the plugin now also records the live
Python objects after each file's collection (`objects_after`): flat while resident memory rises
means nothing is leaking.

The SQLite runs' exit delay wasn't recorded: the first version of the script didn't recognise
pytest's `-q` summary line, fixed before the PostgreSQL pair ran.

### What's left

- **The exit after the summary, explained.** Measured again with the threads' stacks written
  every 3 s while the process exits (`SUITE_MEASURE_EXIT_STACKS`): 11.5 s on SQLite and 24.7 s on
  PostgreSQL, and in both the main thread is in pytest's own `unraisableexception` clean-up
  (`gc_collect_harder` in `_ensure_unconfigure`), which runs several full garbage collections at the
  end of the session to surface any exception raised in a finaliser. Its time follows what's still
  in memory (917 MB and 1,509 MB at the peak), so it isn't a hang or a thread being waited for: the
  only thread left is the fake SMTP server's accept loop (`tests/smtp_fake.py`), a daemon, which
  exit doesn't wait for. Turning the plugin off would save the time and lose the check, so it stays.
- CLI commands run inside tests still leave their one connection each, listed by the measurement.

## The PostgreSQL suite's set-up

Volume 15, prompt 1. The PostgreSQL suite proves row-level security and the real database on every
push, and it was the slowest job (70 min 56 s of tests in CI run 329, 60 min 57 s in run 332):
before each test the `database_url` fixture dropped every table, and the app's startup then made
them again, applied the row-level security policies and seeded the problem bank.

### Where the set-up went

Measured first, on a disposable database on this machine (`pg_setup_phases`, median of five; the
machine was also running the SQLite suite, so the absolute numbers are high and the proportions are
what matter):

| Step, per test | From scratch | On a database already made and seeded |
|---|---|---|
| The fixture's `drop_all` | 185 ms | |
| `create_all` | 537 ms | 3 ms |
| `add_missing_columns` | 249 ms | 255 ms |
| `rls.apply` (policies) | 112 ms | 164 ms |
| `seed_problems` | 703 ms | 628 ms (reads only: one query per problem and its tests) |
| **Total** | **1,804 ms** | **1,052 ms** |

Two ways to restore a clean, seeded state, measured the same way: emptying the 69 tables the seed
doesn't fill (`TRUNCATE … RESTART IDENTITY CASCADE`) took 357 ms; recreating the database from a
template (`CREATE DATABASE … TEMPLATE`, with the drop) took 77 ms.

### What it does now

**A template, cloned per test.** At the start of the session, a database is made by the app's own
startup, as the app's role: its tables, the row-level security policies, the seeded problem bank
(`_seeded_postgres_template` in `tests/conftest.py`), and then closed to connections. It's named
for the session's process (`<test database>_template_<pid>`), so a pytest run inside a test
(`tests/test_suite_measure.py` runs one with this conftest) makes and drops its own and never this
one; a template left by a session that was killed is dropped by the next. Before each
test, the test database is dropped (closing any connection a test left open: `WITH (FORCE)`) and
recreated from that template with the same owner, so its tables, policies, grants and seeded rows
are exactly the template's, whatever the test before wrote, changed or left connected. A template
copy is a copy of the files, so it beats emptying tables (77 ms against 357 ms) and it can't miss a
table, a sequence or a seeded row a test changed.

**The startup doesn't redo it.** A test's app on that copy starts with `auto_migrate` off (a test
setting; no app code changes): the template is what that very startup made, on the same models, seed
and policies, so running it again would change nothing and cost about a second. A test that sets
`auto_migrate` itself, or uses another database, gets what it asks for. SQLite is unchanged: each
test's database is a copy of a seeded file, and its app runs the whole startup on it, as before.

It needs a role that may create databases: CI's PostgreSQL job already gives the suite one
(`TEST_DATABASE_ADMIN_URL`, the service's superuser, for the storage rehearsals). Without it the
suite drops and remakes the tables before each test, as before. A run stopped between a test
database's drop and its copy leaves none; the next session makes it again, empty, before its first
check.

**Isolation, checked.** `tests/test_database_isolation.py`: the first test changes a seeded problem
(its title and tests), adds an account and leaves a connection open; the next finds the problem bank
exactly as seeded, no account, and every table the seed doesn't fill empty. A negative control that
skips the per-test restore is caught by it. Tests that need an empty database, migrations or roles
of their own (the storage and backup rehearsals, `check_migrations.py`) keep making their own.

### Before and after

Both on this machine, one after the other, on the same tree (`690f000` and that tree with this
change), PostgreSQL as the app's role with row-level security enforced, with the measuring plugin:
every test file but `test_judge_sandbox.py` (this machine has gVisor, so there it's 14 to 19 minutes
of judged runs; in CI's PostgreSQL job it skips, and it runs in the sandbox job).

| | Before (drop and remake) | After (template copy) |
|---|---|---|
| Set-up time inside the tests | 2,672 s (0.83 s per test) | 400 s (0.12 s per test) |
| Time inside the tests | 4,306 s | 1,688 s |
| Wall time | 85 min 11 s | 34 min 7 s |
| Peak resident memory | 1,571 MB | 1,016 MB |
| Exit after the summary | not recorded (the run was given `-q` twice, which hides pytest's summary line) | 10.0 s |
| Results | 3,216 passed, 1 skipped, 2 xfailed | 3,218 passed, 1 skipped, 2 xfailed (the two isolation tests added) |

The first "after" run found a real fault, now fixed: the template had one fixed name, so the pytest
run inside `test_suite_measure.py` made and then dropped it, and the 99 tests after that file
couldn't be set up (and the test database was left dropped). Each session now names its own
template and makes a missing test database again; the run above is after that fix.

**In CI** the PostgreSQL step's time varies a lot between runs on the same fixture: 60 min 57 s
(run 332), 73 min 5 s (run 331), 77 min 10 s (run 342), 47 min 51 s (run 343). The first run with
this change is recorded in the next commit; one run against that spread proves less than the
same-machine pair above.

## Recording CI evidence without churn

The canonical record of a run is its **CI summary** for the exact SHA, on GitHub. Evidence is
quoted in the next **code** commit's message (run numbers, jobs, results), not in a separate
documentation commit made only to record it: such a commit would start another run whose only
subject is the record of the last one. A commit that only changes documentation is labelled as
such by the summary, and is never presented as the code jobs passing on that SHA.

A timing failure is a finding, not something to retry away: no blanket retries, larger timeouts
or skipped coverage. After a fix, the evidence is the complete suite on the fixed revision, not
a few isolated reruns of the test that failed.

## Test inventory and browser candidates

Two checks from Volume 9, prompt 10, for two mistakes that happened: four navigation tests
overwritten by new ones in the same file (the total went up, so a count didn't notice), and a
browser run served from a tree that was being edited while it ran.

### Which tests exist: `scripts/test_inventory.py`

```bash
python scripts/test_inventory.py since origin/main            # that ref's tests vs this tree's
python scripts/test_inventory.py since origin/main --accept accepted.txt
python scripts/test_inventory.py collect --out after.txt      # or two saved inventories:
python scripts/test_inventory.py compare before.txt after.txt
```

An inventory is one line per test, `runner<TAB>file<TAB>test`, from each runner's own collection:
`vitest list --json --staticParse=false` (each file's collection is run, so an `it.each` table is
one line per case, exactly the tests a run executes: 1012 when this was added, the number `vitest run` counted),
`playwright test --list --reporter=json` (a line per project) and `pytest --collect-only -q`.
Plus a line for each test file on disk (by its name: `*.test.ts(x)`, `e2e/*.spec.ts`,
`tests/test_*.py`) that no runner collected. `since REF` collects REF in a temporary checkout
that shares this tree's installed dependencies, and removes only that checkout.

The comparison lists what was added, what may have been renamed (a removed test and an added one
in the same file with titles at least 80% alike) and what was removed. **It fails** (exit 1) on a
removed test or an uncollected file, unless an `--accept` file lists it (one identity per line, or
`file<TAB>path` for a whole file; `#` comments): that's how a deliberate removal or merge is
reviewed. A rename is listed under "renamed (review these)" and doesn't fail. **There's no count
gate**: more tests can still hide removed ones, and merging tests can lower the count for good
reasons. Vitest's default static listing isn't used: it lists an `it.each` table as one `%s`
entry (696 entries for 1011 tests when measured) and listed a helper call as a test.

What it can't see: a test whose body was emptied or weakened (the name stays), a test skipped at
run time (`test.skip(condition)` is still collected), a renamed test whose title changed by more
than the threshold (it shows as one removed and one added, so it fails until accepted), and test
files named outside those patterns. It isn't run by CI: run it before pushing, or in review.

### Which source a browser run tested: `scripts/e2e-run.mjs`

At the start the launcher prints the commit and the runtime inputs that differ from it (tracked
or not: `frontend/src`, `frontend/e2e`, `frontend/public`, `index.html`, the Vite, Playwright,
TypeScript and npm files, `backend/app`, `backend/requirements.txt`), and hashes them. At the end
it hashes them again. Then it prints, and writes to `test-results/e2e-provenance.json`:

| Outcome | Meaning | Exit |
|---|---|---|
| `passed` | every test ran and passed | 0 |
| `passed, N skipped` | passed, with N not run; they're named (without `E2E_JUDGE=1` the real-judge tests skip, so this isn't a full real-sandbox pass) | 0 |
| `failed` | a test failed | Playwright's |
| `canceled` / `timed-out` | Ctrl+C or a signal / `--max-minutes`: incomplete | 128+N / 124 |
| `contaminated (…)` | a runtime input changed during the run: the results describe neither the commit nor the tree it started with | 3 |
| `unverified (…)` | the inputs couldn't be listed again at the end (git failed): nothing can be said about the source, so it isn't called unchanged | 3 |

"Candidate: <sha>, runtime inputs unchanged from the commit" plus `passed` is a pass of that
commit. "<sha> plus N changed runtime file(s)" is a pass of that working tree, not of the commit.
Files git ignores (screenshots, logs, the e2e databases and outboxes) aren't inputs, so a run's
own output doesn't count. The launcher only reads: it never resets, cleans or stops anything to
make a tree look clean.

For a run worth recording, test the commit in its own checkout:

```bash
git worktree add --detach ../cc-candidate <sha>
ln -s "$PWD/frontend/node_modules" ../cc-candidate/frontend/node_modules
cd ../cc-candidate/frontend && E2E_PORT_OFFSET=20 PYTHON=<repo>/backend/.venv/bin/python npm run e2e
cd - && git worktree remove ../cc-candidate   # after removing the symlink
```

What it can't prove: the hashes are taken at the start and the end, so a file changed and put back
during the run looks unchanged; in the demonstration below, one of four runs with a line added
mid-run reported no change, and the cause wasn't found (the next three caught it; a failed end
check, one possible cause, now says so instead of passing silently); the dev server serves files as it reads them, so this is about
the files, not proof of every byte Vite served; dependencies inside `node_modules` and the Python
environment aren't hashed (the lockfiles are); and a run started outside the launcher
(`npx playwright test`) records nothing. The demonstrations are in LAUNCH_READINESS.md, Volume 9 row 10.

