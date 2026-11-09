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

## Recording CI evidence without churn

The canonical record of a run is its **CI summary** for the exact SHA, on GitHub. Evidence is
quoted in the next **code** commit's message (run numbers, jobs, results), not in a separate
documentation commit made only to record it: such a commit would start another run whose only
subject is the record of the last one. A commit that only changes documentation is labelled as
such by the summary, and is never presented as the code jobs passing on that SHA.

A timing failure is a finding, not something to retry away: no blanket retries, larger timeouts
or skipped coverage. After a fix, the evidence is the complete suite on the fixed revision, not
a few isolated reruns of the test that failed.
