# Row-level security at runtime

PostgreSQL row-level security (RLS) is the second line of defence. The first is the application's
own owner checks in every query ([SECURITY.md](SECURITY.md)). RLS means a query that forgot its
owner filter still returns nothing of anyone else's. This page records how it behaves in the
running application: which roles connect, how each transaction gets its identity, why a pooled
connection can't carry one person's identity into the next request, and what the background
work may see. It also lists the tests that would fail if any of that broke.

**SQLite has no RLS.** On a `./dev.sh` run (SQLite), only the application's owner checks keep
accounts apart. Every database-enforced statement below is about PostgreSQL.

## Roles

| Where | Connects as | Owner of the tables? | Subject to RLS? |
|---|---|---|---|
| Production (prepared: `deploy/docker-compose.production.yml`) | API: `codecoach_app`. Migrate job: `codecoach_owner` | app: **no**. Owner: yes | app: yes (ordinary role, policies apply). Owner: yes, because the policies are FORCEd, but an owner could switch them off, so the API never connects as it |
| Local PostgreSQL tests (this sandbox) | `codecoach`, an ordinary role that owns its test tables | yes | yes (FORCE) |
| CI, PostgreSQL step | `codecoach_app`, ordinary, owns its test database | yes | yes (FORCE) |
| CI and local storage rehearsals (`tests/test_storage.py`) | a fresh owner and app role per test, made by the real init script | app: no | yes |
| Development compose (`docker-compose.yml`) | the image's superuser | yes | **no**: superusers bypass RLS |

- `python -m app.cli check-rls` reports the role, whether it bypasses RLS, and whether any
  protected table lacks its policy.
- `--strict` also fails when the role owns tables, can create objects, or can create roles. In
  the production rehearsal, the app role passes and the owner fails.
- Start-up logs a warning when RLS isn't enforced, and in production when the role owns tables.

## Policies

There are two policies on each of the 34 learner-owned tables (`app/db/rls.py`
`PROTECTED_TABLES`). The first 30 (`BASE_TABLES`) got them from migrations `248721f0fcb1` and
`7c1d2e3f4a5b`; a table added later gets them from the migration that creates it, listed in
`ADDED_TABLES` (`5b7e2c9d4a10`: `code_review_attempts`, `code_review_drafts`; `c4a9e2f71b35`:
`work_sample_attempts`, `work_sample_drafts`), and a test checks
each such migration installs exactly the current policies. Both compare the row's `user_id` with
two transaction-local settings.

| Transaction has | Sees | Can write |
|---|---|---|
| `codecoach.user_id` = U (any scope) | U's rows only | U's rows only (`WITH CHECK`) |
| no user, scope `request` (every API request) | **nothing** | **nothing** |
| no user, scope `worker` (judge worker, jobs thread) | **nothing** | **nothing** |
| no user, scope `maintenance` (one named step, below) | every learner's rows | **nothing** (SELECT-only policy) |
| no user, no scope (operator commands, migrations, tests' own sessions) | everything | everything |

Until this batch, "no user" always meant everything. A signed-out request, or a route that forgot
to authenticate, ran unrestricted, and so did the worker. Now a request is denied until it
authenticates (`api/deps.get_db` sets the `request` scope; `get_optional_user` binds the user),
and the worker is denied unless it binds the learner it's working for.

## Why a pooled connection can't leak an identity

- Both settings are set with `set_config(name, value, true)`: **transaction-local**. They end with
  the transaction, whether it commits, rolls back, fails, times out or is cancelled.
- A SQLAlchemy session re-applies its user and scope at the start of **every** transaction it opens
  (`after_begin`). So a request that commits and continues stays narrowed, and the next session
  on the same connection starts with nothing.
- A request session always sets both settings, an empty user included. Even a setting left
  behind by a bug would be overwritten at the next request's first transaction.

Tests, run through a pool of **one** connection so every request reuses it
(`tests/test_rls_runtime.py`; each asks the database what it sees, through a probe route that
applies no owner filter of its own):

| Test | Shows |
|---|---|
| `test_one_pooled_connection_serves_each_user_only_their_own_rows` | A, B, signed out, A, signed out on the same backend pid: 2, 1, 0, 2, 0 rows |
| `test_nothing_is_left_on_the_connection_after_an_error_or_a_timeout` | after an exception once the user was bound, and after `statement_timeout`: the same connection, user empty, 0 rows |
| `test_a_query_cancelled_from_outside_leaves_nothing_behind` | `pg_cancel_backend` mid-query: the same connection afterwards is clean |
| `test_concurrent_requests_never_see_each_others_rows` | 60 interleaved requests from A, B and signed out, over 2 connections, 8 threads: each sees exactly its own count |
| `test_the_probe_would_catch_a_request_that_isnt_denied_by_default` | sensitivity: without the request scope, a signed-out request sees all 3 rows |
| `test_the_probe_would_catch_a_setting_that_outlives_its_transaction` | sensitivity: a session-wide setting would follow the connection after a commit; the real one doesn't |
| `test_an_administrator_reads_no_learner_rows_either` | an admin's request, through a route with its owner check removed: 404 |

Also, from earlier work:
- `test_a_route_that_forgot_its_owner_check_still_leaks_nothing`: another account gets 404 even
  with the notes owner check removed.
- `tests/test_route_access.py`: every GET and every write route, called by another account with
  your record ids. Not found, never someone else's data, and no 500 that would confirm a record
  exists.

## Background work: who may see what, and why

| Work | Scope | Learner rows it touches | Model |
|---|---|---|---|
| Email outbox (jobs thread, or after a response) | worker | none (users, tokens and email jobs aren't covered) | denied |
| Rate-limit counter purge | worker | none | denied |
| Finished-email purge | worker | none | denied |
| Guest clean-up (daily) | worker, plus **maintenance** for one read | reads each guest's latest progress-event time; deletes users, whose rows go by cascade | `rls.maintenance(db, "guest clean-up: …")`: read-only, logged with its reason, then back to worker |
| Judge worker: claim and judge a submission | worker | submissions aren't covered | denied |
| Judge worker: claim and run a test-design run | worker | `test_design_runs` isn't covered (like submissions) | denied |
| Judge worker: record "solved" | worker, bound to the submitter | writes one progress event for that learner | `rls.bind_user(db, sub.user_id)` |
| CLI (`prune-guests`, `check-answers`, `grant-admin`, …), migrations, seed | none | as each needs | operator: run deliberately, with operator or owner credentials, never from a request |

`test_the_guest_clean_up_still_sees_recent_activity` keeps a guest who was active yesterday. In
its sensitivity half, the same run without the maintenance read deletes active guests too: the
worker scope really does hide learner rows. `test_maintenance_reads_every_learner_and_can_change_nothing`
checks that an update changes 0 rows and an insert is refused.

Cascading deletes (deleting a user removes their rows) are referential actions. PostgreSQL runs
them regardless of RLS, which is what lets the clean-up delete a guest's data without write
access to it.

## Linked records

- Tables without a `user_id` (collection items, plan items, story revisions, interview turns,
  application events, …) aren't covered by a policy. They're reached through a covered parent,
  and the application looks that parent up first. Under RLS that lookup finds nothing of anyone
  else's, so the request ends in 404.
- **Limit:** PostgreSQL checks foreign keys without RLS. A route that inserted a child row by a
  parent id **without** looking the parent up would let another account attach rows to your
  record. The write-route walk (`test_another_account_changes_nothing_of_yours_on_any_write_route`)
  is what guards that, not RLS.
- Not covered, deliberately (reasons in `app/db/rls.py`): submissions and execution results,
  test-design runs (queued for the worker like submissions), sign-in tokens, shares (the recipient
  reads a snapshot, never the owner's rows), and content triage.

## Limits

- Effective only for roles that don't bypass RLS. The development compose file's superuser does.
- Operator sessions (no scope) see everything. That's deliberate for migrations and the CLI,
  and it's why the production API holds only the app role's credentials.
- The policies compare `user_id` text. A bug that bound the **wrong** user id to a request would
  show that user's rows; RLS can't catch an authentication mistake.
- Not verified on a deployment: none exists yet. Verified locally on PostgreSQL 16 (this sandbox)
  and, for everything that existed before this batch, in CI.
