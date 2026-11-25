# Support report (Volume 7, prompt 8)

A learner who hits a problem can make a small report, read every line of it, and then copy it or
save it as a file. Nothing is sent anywhere: there is no support backend, email, upload or
analytics behind it. Sharing the copied text or the file is a separate choice the learner makes
afterwards, somewhere else.

## Where it is

- **Next to a failure.** A failed action (`ActionError`: a submission, a hint, a code review, the
  data download, starting an interview), a page or section that couldn't load (`ErrorState`), and
  the answer and story saves (`InlineError` with an `action`) offer **Get help with this** when a
  report could help: no reply, a wait, a service down, a fault on the server, a refusal, or an
  unknown kind. Not for a form to correct or a sign-in to redo. The report opens in place, under
  the message, so typed work on the page stays where it is.
- **From Help.** Help → *Something not working?* → `/help/report`. It works signed out, offline
  and while the server is down.

The preview is a read-only text box holding the exact string that **Copy the report** puts on the
clipboard and **Download** saves (`codecoach-support-report-YYYYMMDD-HHMM.json`, local time).

## What's in it, and what each field helps with

Format `codecoach-support-report`, version `1`, JSON, fields in this order:

| Field | What it holds | Helps to tell |
|---|---|---|
| `created_at`, `time_zone` | the time the report was opened (UTC) and the browser's time zone name | which server logs to read; a date or deadline shown in the wrong zone |
| `app.build`, `app.mode` | the commit the build came from (or `unknown`); production or development | whether a fix had reached this learner |
| `page.name`, `page.path` | the route's title and its path, with numbers, ids, long tokens and address-like parts as `:id`, and no `?query` or `#fragment` | which page, without which record |
| `browser` | family (Chrome, Edge, Firefox, Safari, Opera, other), main version, OS family, language without region (`en`), and whether the browser thinks it's online | a browser-specific fault; an offline device |
| `session` | `signed_in`, `guest`, `signed_out` or `checking`: never which account | a guest limit; a sign-in that lapsed |
| `server_said` | from the public `GET /capabilities`: the code judge's state and reason, the AI coach in use (`offline` or `anthropic`), whether emails are delivered. Or `not answered yet`, or `unknown: the server's status couldn't be loaded` | a judge that's down or not set up; email that's printed, not sent |
| `problem` | the failure the learner asked about: the app's name for the action, its kind and what that kind establishes (`meaning`), the error code, the HTTP status (0: no reply) and the server's request id. `null` from Help | the server log line for that request |
| `recent_failed_requests` | up to five requests that failed in this session: method, masked path, status, error code, request id. Not the refused session check a signed-out visitor's page makes on load (that's how "signed out" is learned) | what failed around it |
| `description` | what the learner typed, up to 500 characters, with a warning not to include passwords, codes or anything private | the learner's own account of it |

**Never in it**, by construction (an allowlist, not a filter): answers, code, notes, transcripts,
stories, applications, target jobs, recordings, screenshots; email address, name, account id;
passwords, tokens, cookies, request or response bodies and headers, query strings, fragments; the
full user agent; error *messages* (they can quote input); environment or server configuration.

Values are bounded (each string cut to a fixed length; the whole report is a few KB). Request ids
are reported only when they have the server's shape (hex), so nothing else is passed off as one,
and none is ever made up: no reply means `request_id: null`.

## Evidence that stays unavailable

- **What happened on the server.** The report gives the request id; the matching log lines and
  trace (`/admin/traces`) are on the server, for an administrator to read.
- **Whether a request with no reply arrived.** `offline` means no reply came back. The report can't
  tell a dropped connection from a server that's down, and doesn't call it an outage.
- **Failures from before a reload, from another tab, or from an earlier session.** The failed-request
  log is in this tab's memory; it's emptied on sign-in, sign-out and account change, so one
  account's failures never appear in another's report.
- **Timing and a full network trace.** Not collected. The development-only diagnostics
  (`lib/diagnostics`) are a separate, opt-in tool.
- **Which build, for an image built without a build id.** The frontend image has no `.git`; pass
  `--build-arg CODECOACH_BUILD_ID=<commit>` or the report says `unknown`.
- **The judge's or AI provider's own state** beyond what `/capabilities` says.

## Tests

- `frontend/src/features/support/report.test.ts` (10): the exact keys at every level and the
  version; synthetic secrets and an address in the URL, the build id, the request id and request
  paths never reach the text; unknown states said, not guessed; every value bounded; markup kept
  as text; the filename; coarse browser parsing; the log masks ids, holds five and is emptied when
  the session changes.
- `frontend/src/test/integration/supportReport.test.tsx` (10): reports for a failed answer save, an
  unavailable judge, a blocked AI request (429 with a wait) and a page that can't load offline, each
  checked field by field and for synthetic secrets seeded in the URL, the error message, the typed
  answer, `localStorage` and a cookie; the typed answer stays on the page; Copy puts exactly the
  preview on the clipboard; denied copying and a download that can't start both select the report
  to copy by hand; the download is the preview byte for byte, a `.json` file, and its temporary
  address is revoked; a long description is cut at 500 and markup in it isn't rendered; signing out
  empties the log; a signed-out visitor's report lists no failed requests.
- `frontend/e2e/support-report.spec.ts` (2, Chromium, real API): a hint whose connection drops opens
  the report in place with the code still in the editor; the clipboard and the downloaded file both
  equal the preview exactly; a synthetic secret in the URL and storage isn't in it; the report page
  by keyboard alone, signed out, with markup kept as text; no axe WCAG A/AA violations; no sideways
  scroll at 1440 or 360 px.
- Negative controls (each mutation applied alone, then reverted): not clearing the log on a session
  change, reporting the raw path, never revoking the file address, copying the error message,
  reporting the full user agent, not selecting the report on copy denial, and logging the refused
  session check. Each fails 1 to 4 of these tests.

## Limits

- Local only. If sharing is ever built, it needs its own destination, authorization, retention and
  access rules; this report must not be wired to one silently.
- A description is the learner's own text: the warning asks them not to paste private things, but
  what they type is in the report.
- The failed-request log covers requests made through the app's API client, not other fetches
  (fonts, the service worker).
