# Observability: following one user action across the system

The question this answers: **when a learner says "my answer didn't go through", what happened,
where, and how often does it happen?** One real flow is instrumented end to end, submitting an
answer in an interview round, plus the one piece of background work the app has (the judge).
It reuses what was already there: request ids, JSON logs, Prometheus metrics and health checks.
There's no tracing SDK, collector or monitoring stack.

## How one action is followed

```
browser click ──► new W3C trace (lib/trace.ts) ──► POST …/answers  traceparent: 00-<trace>-<span>-01
                                                     │
API  http ────────────────────────────────────────── │  span: route template, status
      └─ round.action  (action, format, result)      │  result: advanced | followup | completed | duplicate
           ├─ evaluate (evaluator=rubric)            │  outcome: ok | rejected | error | db_error | timeout
           └─ db.commit                              ▼
response  X-Request-ID, X-Trace-ID ──► browser waits for the next state on screen (≤ 5 s)
                                        └─► POST /api/v1/telemetry/ui  {trace_id, action, outcome, duration_ms, …}
admin  GET /api/v1/admin/traces/{trace id | request id}  ──► server spans + browser reports, together
```

Background work: a code submission stores the trace id of the request that queued it
(`submissions.trace_id`). The judge worker continues that trace for each job: a `judge.run`
span records language, attempt, queue wait and verdict, and a `judge.recover` span (outcome
`timeout`) records a job that ran past its time. The trace context is set per job and reset
afterwards (`tracing.start_trace`), so one job's trace never leaks into the next.

| Span | Where | Attributes (allowlisted) | Outcomes |
|---|---|---|---|
| `http` | every request (`observability.py`) | method, route template, status | ok, rejected (4xx), error (5xx) |
| `round.action` | answer, skip, reply, skip follow-up (`services/interviews.py`) | action, format, result, error_code | ok, rejected, error, db_error |
| `evaluate` | grading an answer (`services/question_rounds.py`) | evaluator | ok, error |
| `db.commit` | saving the round | (none) | ok, db_error |
| `judge.run` | the worker judging a job (`worker.py`) | language, attempt, queue_wait_ms, verdict, result | ok, judge_unavailable |
| `judge.recover` | a job past its time limit | attempt, result | timeout |

Each span is one JSON log line (logger `codecoach.trace`, level INFO) with `trace_id`,
`span_id`, `parent_id`, `span`, `duration_ms`, `outcome`, `attrs` and `request_id`. It is also
kept in a bounded in-memory store for the admin lookup (500 traces, 200 spans each, 1 hour;
`TRACE_STORE_MAX_TRACES`, `TRACE_STORE_TTL_SECONDS`; 0 turns the store off). The store lives in
one API process. With several replicas, an admin looks up the replica that served the request,
or searches the logs (below).

### Coaching requests and fallbacks (2026-11-04)

Every hint, review and failure explanation runs inside the span `coach.provider` (attributes
`provider`: anthropic or offline; `attempt`: requests sent, retries included). Its outcome is `ok`,
or `fallback_<reason>` when the offline coach answered instead: `timeout`, `connection`,
`rate_limited`, `http_5xx`, `http_4xx`, `refusal`, `cut_off`, `invalid_output`, `invalid_body`.
So `codecoach_span_duration_seconds_count{span="coach.provider"}` counts fallbacks by reason, a
fixed set of label values, with no learner text, ids or model output. The same reason code is in
the `anthropic request failed` warning (under `attrs`). Example:
`sum by (outcome) (increase(codecoach_span_duration_seconds_count{span="coach.provider"}[1h]))`.

### What the browser reports

For each round action, the page reports how it ended **on screen**, which the server can't see:

| Outcome | Meaning |
|---|---|
| `rendered` | the next question, follow-up or results appeared |
| `rejected` | the server refused it (4xx; `error_code` says why) |
| `server_error` | the server failed (5xx) |
| `network_error` | no response arrived (offline, dropped connection, lost response) |
| `not_rendered` | the server answered 200 but the screen didn't change within 5 s |
| `ignored` | the answer box swallowed a click although it looked ready (a stuck submit guard) |

Reports go only to this app's own API, in batches of up to 20, at most one batch in flight,
never retried, and never refreshing the session or signing anyone out (`noRefresh`). They are
sent only when `/api/v1/capabilities` says `ui_telemetry: true`. Turn them off with
`UI_TELEMETRY_ENABLED=false` (the browser then sends nothing and the endpoint returns 404). The
server rate-limits them (120 batches per account per 10 minutes) and drops the excess silently,
so a misbehaving page can't cause a retry storm.

## Metrics and service-level indicators

All on `/metrics` (Prometheus text). Labels are fixed vocabularies: route **templates**, span
names chosen in code, outcomes from a closed set (anything else becomes `other`). Never user
ids, interview or question ids, or raw URLs.

| Metric | Type | Labels | Measured by |
|---|---|---|---|
| `codecoach_http_requests_total`, `codecoach_http_request_duration_seconds` | counter, histogram | method, route, status | server |
| `codecoach_span_duration_seconds` | histogram | span, outcome | server |
| `codecoach_round_actions_total` | counter | action, outcome | server, once per request (a repeated submit is `duplicate`) |
| `codecoach_ui_actions_total`, `codecoach_ui_action_seconds` | counter, histogram | action, outcome | **browser**, click to outcome |
| `codecoach_judge_queued_jobs`, `codecoach_judge_oldest_queued_seconds` | gauge | none | database, read at scrape time (right wherever the worker runs) |
| `codecoach_telemetry_dropped_total` | counter | kind | server: telemetry not recorded; the request itself was fine |

The SLIs are recording rules in [`ops/prometheus/codecoach-rules.yml`](../ops/prometheus/codecoach-rules.yml):

| SLI | Numerator | Denominator | Excluded | Window |
|---|---|---|---|---|
| Round actions handled (server) | outcomes advanced, followup, completed, duplicate | all outcomes except rejected | refusals (4xx: a stale tab, a finished round) | 30 min |
| Answers that reached the screen (browser) | `rendered` | rendered + network_error + not_rendered | refusals and server errors (counted on the server), ignored clicks (own alert) | 30 min |
| Answer latency (browser) | p95 of `codecoach_ui_action_seconds{action="answer",outcome="rendered"}` | | failed actions | 30 min |
| Evaluation latency (server) | p95 of the `evaluate` span | | | 30 min |
| API latency (server) | p95 per route template | | `/metrics`, `/health*`, unmatched routes | 5 min |
| Server errors | 5xx responses | all responses | | 5 min |

Client- and server-measured latency are kept apart on purpose. The browser number includes the
network, React's render and the browser's own scheduling; the server number doesn't. The gap is
the part the server can't see.

Collection limits: one browser report per action, a server span per traced step. Label values
are bounded as above. Browser reports are capped per account; the in-memory store is capped by
count and age.

### Proposed objectives

For a **single-region, self-hosted deployment of the web app and API** (the docker-compose
setup), measured over 28 days. These are targets to start from, not measurements: there is no
production traffic to measure availability against.

- 99.5% of round actions handled without a server failure.
- 99% of answers that were sent show their result on screen.
- 95% of rendered answers on screen within 2 s of the click (browser-measured).
- No code submission waits more than 5 minutes for a judge.

## Alerts

Also in `ops/prometheus/codecoach-rules.yml`. Each alert has to hold for 10-30 minutes before it
fires, and each ratio alert needs real traffic in its window (for example at least 50 actions in
30 minutes), so one failure on a quiet night doesn't page anyone. They are written to catch
sustained problems, not every isolated error.

| Alert | Fires when | Severity |
|---|---|---|
| `CodeCoachRoundActionsFailing` | round-action success < 98% (≥ 50 actions) for 15 min | page |
| `CodeCoachAnswersNotReachingTheScreen` | rendered < 95% (≥ 50 actions) for 15 min | page |
| `CodeCoachClicksIgnored` | ≥ 5 ignored clicks in an hour, for 10 min | ticket |
| `CodeCoachJudgeQueueStuck` | oldest queued submission > 5 min, for 10 min | page |
| `CodeCoachServerErrors` | 5xx > 5% (≥ 100 requests) for 10 min | page |
| `CodeCoachTelemetryDropping` | the server can't record its own telemetry, for 30 min | ticket |

`ops/alertmanager/alertmanager.yml` routes everything to a webhook on `127.0.0.1` only: validating
rules never contacts a person or a paid service. Checks:

- `backend/tests/test_ops_rules.py` (runs in CI): every metric and label in the rules is one the
  app exports, every alert waits and links a runbook here, and every ratio alert has a traffic guard.
- `promtool check rules ops/prometheus/codecoach-rules.yml` and
  `promtool test rules ops/prometheus/codecoach-rules.test.yml`: syntax, and alert timing on
  synthetic series (a sustained failure fires after its `for`; the same rate on low traffic
  doesn't; a stuck queue fires). **Not run in this environment**: running a downloaded
  `promtool` binary wasn't permitted here, so these two are unverified until run where Prometheus
  is installed.

## Finding the evidence for a report

1. **Start from a request id.** Error messages in the app show one. In the browser's dev
   tools, every API response carries `X-Request-ID` and `X-Trace-ID`.
2. **Admin lookup:** `/admin/traces` (linked from the admin Reports page), or
   `GET /api/v1/admin/traces/{trace id or request id}`. It shows the server's steps nested in
   order, with timing and outcome, next to what the browser reported.
3. **Logs** (one JSON object per line; any replica, any age the log store keeps):
   ```bash
   # every span and request line of one action
   jq -c 'select(.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736")' api.log
   # which trace a request id belongs to
   jq -r 'select(.request_id == "<request id>") | .trace_id' api.log | sort -u
   # slow evaluations in the last log file
   jq -c 'select(.span == "evaluate" and .duration_ms > 250)' api.log
   ```
4. **Metrics** for "how often": the recording rules above, or directly, for example
   `sum by (outcome) (increase(codecoach_ui_actions_total{action="answer"}[1h]))`.

How to read the combinations:

| Server `round.action` | Browser | What happened |
|---|---|---|
| ok, result advanced | `rendered` | worked |
| ok, result advanced | `network_error` | saved, but the response was lost. Retrying is safe (the server answers `duplicate` and grades nothing twice) |
| ok | `not_rendered` | saved and answered, but the page didn't update: a front-end bug (stale cache, missing re-render) |
| (no span) | `network_error` | never reached the server |
| rejected / error | `rejected` / `server_error` | the server refused or failed; `error_code` and the span say which step |
| (no span) | `ignored` | the click sent nothing: the answer box's guard was stuck |

## Privacy checklist

- [x] Spans carry only allowlisted attributes (`tracing.ALLOWED_ATTRS`): short strings,
      numbers and booleans. Anything else is dropped before it is logged or stored.
- [x] Never recorded in spans, browser reports or metrics: answers, replies, code, transcripts,
      job documents, emails, names, tokens, cookies, authorization headers, user ids, interview,
      question or submission ids. Tested in `tests/test_tracing.py` (an answer marker, the email
      and the token are searched for in the trace store and the trace/access logs).
- [x] Database errors are categorised (`db_error`); their messages are not recorded.
- [x] The access log keeps the request **path** (it can contain a resource id), never the query
      string.
- [x] Browser reports go only to this app's API; nothing is sent to a third party. Off with
      `UI_TELEMETRY_ENABLED=false`. The server's in-memory store is off with
      `TRACE_STORE_MAX_TRACES=0`; log retention is the deployment's own.
- [x] Sampling: every traced action is recorded. Volume is one browser report per action
      and a handful of spans per request; the per-account cap bounds a misbehaving page.
- [x] Telemetry can't break practice: recording failures are swallowed and counted
      (`codecoach_telemetry_dropped_total`); browser reports are dropped, never retried, and
      never touch the session. Tested on both sides.
- [x] Local and offline development: everything works without any collector; the store is
      in-process, and in development the page's own breadcrumbs (`window.__ccDiag`) are available
      for failing browser tests (`e2e/fixtures.ts`).

## Runbooks

### Runbook: round actions failing

Look at `sum by (outcome, action) (increase(codecoach_round_actions_total[30m]))`. For `db_error`,
check `/health/ready` and the database; for `error`, take a recent failing trace from the logs
(`jq 'select(.span=="round.action" and .outcome=="error")'`) and open it in the admin lookup to see
which step failed (`evaluate` or `db.commit`).

### Runbook: answers not reaching the screen

Split by outcome: mostly `network_error` with server spans `ok` means responses are being lost
between the API and browsers (proxy timeouts, connectivity). Retries are safe. `not_rendered`
means a front-end regression: look at the release that started it.

### Runbook: clicks ignored

A stuck submit guard in the answer box (see the incident below). Find the release; reproduce with
`src/test/integration/roundSubmit.test.tsx`.

### Runbook: judge queue stuck

`codecoach_judge_oldest_queued_seconds` rising: is a worker running (`python -m app.worker`) and
can it reach the runner? `/api/v1/capabilities` shows the judge state. `judge.run` spans with outcome
`judge_unavailable` mean the runner is down; `judge.recover` spans with outcome `timeout` mean jobs
are being cut off.

### Runbook: server errors

`codecoach:http_seconds:p95_5m` and `sum by (route) (rate(codecoach_http_requests_total{status=~"5.."}[5m]))`
show where. Each 5xx has an `http` span with outcome `error`, and its trace shows the failing step.

### Runbook: telemetry dropping

The trace store, a metric or the queue probe is failing. `codecoach_telemetry_dropped_total` by
`kind` says which. Practice is unaffected; fix when convenient.

## Incident walkthroughs

### The panel interview that "stalled" after Finish interview (2026-11-03)

CI's browser journey failed intermittently with "Timeout 15000ms exceeded while waiting on the
predicate" after the last answer. The failure report (`e2e/fixtures.ts`, the browser-side
predecessor of this tracing) showed all five answers succeeding, the round completing, and the
review loading within 24 ms; the page showed the results. So the app hadn't stalled. The trace
of Playwright's own calls then showed the test asking "is the question line visible?" (yes),
the round ending, and the next call waiting for a line that never came back. The fix was in the
test. With this tracing the same evidence is available for a real learner: server
`round.action` ok and result `completed`, and a browser report of `rendered`.

While investigating, a real bug with the same symptom was found and fixed: the answer box's
double-submit guard could stay shut after a quickly saved answer, so the next click did nothing.
The browser now reports such a click as `ignored`, and `CodeCoachClicksIgnored` would surface it.

### Sign-outs after a cut-off session refresh (2026-11-03)

Several journeys failed after a quick navigation. The breadcrumbs showed a refresh request
cut off by the navigation, then `refresh_race` responses on the next load and a redirect to sign
in. The server had rotated the cookie but the browser never got the answer. That led to the
refresh-recovery design in [SECURITY.md §3](SECURITY.md).

## Measured overhead

Measured with `backend/scripts/bench_tracing.py` in this development container (Python 3.13,
4 CPUs, SQLite), twice. These are not production measurements:

- One span with the in-memory store and metrics: **7-8 µs** when the INFO log line is filtered
  out, **29-34 µs** when its JSON line is written (to `/dev/null`). An answer records about 5
  spans, so well under 0.2 ms per request.
- A full answer request (TestClient, 50 answers after 10 warm-up), trace store on vs off:
  median 18.0 vs 19.4 ms in one run, 20.2 vs 20.4 ms in the other; p95 23.5 vs 23.4 ms and
  24.9 vs 28.6 ms. The difference is within run-to-run noise in both directions.
