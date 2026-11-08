# Where personal data goes, and how long it stays

A map of every place CodeCoach puts data about a person, what removes it, and what happens on
account deletion. It describes the code as it is. It is not a certification or a compliance
claim; nothing here has been independently audited. What keeps one account's data from another
is in [ROW_LEVEL_SECURITY.md](ROW_LEVEL_SECURITY.md) and [SECURITY.md](SECURITY.md).

## The map

| Data | Where | Kept until | On account deletion |
|---|---|---|---|
| Account: email, password **hash**, name, career, pending email change | database | you delete the account | deleted at once |
| Your work: answers, code submissions, notes, stories, applications, schedule, kits, reflections, plans, drills, whiteboards, bookmarks, AI feedback ([PERSISTENCE.md](PERSISTENCE.md)) | database | you delete it, or the account | deleted at once (`ON DELETE CASCADE`) |
| A note you deleted | database | a 10-minute undo window, then purged | deleted at once |
| Answers you shared: the snapshot and feedback received | database; visible to anyone with the link until it expires or you revoke it | revoke, expiry, or deletion | deleted, and the link stops working |
| Feedback you wrote on someone else's share | database, with their share | their share's lifetime | stays with them, labelled "a former CodeCoach user" |
| Sign-in sessions, reset links, email codes (**hashes**, never the tokens) | database | 30 days / 30 min / 48 h, then **purged a week after expiry** (daily housekeeping, new in this batch) | deleted at once |
| Emails waiting to be sent (outbox) | database; change notices carry the two addresses until sent | the payload is cleared when the job finishes; the row is purged 7 days later | deleted at once; a job already running sends nothing to a deleted account |
| Rate-limit counters (IP address, IPv6 by /64, or a **hash** of the account) | database | their window (a minute to an hour), then purged | not linked to the account row; expire on their own |
| Guest accounts | database | 30 days without use, then deleted with everything in them | — |
| Restore imports (what a backup file added) | database | as your other work | deleted at once |
| Exports ("Download my data") | generated on request, **never stored** on the server | the downloaded file is yours | — |
| AI coaching | built-in coach (default): nothing leaves the server. With Claude enabled (`AI_PROVIDER=anthropic`): the problem and your code, with secret-looking strings redacted, go to Anthropic's API under its data policy | we keep the feedback, never the prompt | feedback deleted at once; Anthropic's copy follows Anthropic's policy |
| Emails sent to you | your mailbox; the mail provider's delivery logs | the provider's own retention (none chosen yet) | not recalled: an email that went can't be unsent |
| Server logs | the host's log storage | the host's setting | not linked: the app logs each request's method, route path (no query string), status, duration and request id, plus job ids and SMTP codes. Never email addresses, IP addresses, codes, links, bodies or cookies. uvicorn's own access log, which writes each visitor's IP and full path, is **off in the production image** (`--no-access-log`); a local `./dev.sh` still prints it in your terminal |
| Traces and metrics | API process memory (lost on restart), route templates only | until restart | not linked to content |
| Server backups | encrypted files, off the server once a schedule exists ([BACKUP.md](BACKUP.md)) | proposed: up to ~3 months | **not erased from older backups**: they age out. A restore must re-delete accounts deleted after that backup |
| Drafts in your browser (answers, code, notes, stories, whiteboards, reflections, drills, interviews) | this browser's storage | sent, or **cleared when you sign out** on this device (after a warning) | cleared on this device |
| Display, editor and voice preferences; public pages saved for offline | this browser | until you change or remove them | kept: device settings, not account data |
| Private pages and API responses | never cached: `Cache-Control: no-store` on every private response; only the public catalogue is cacheable (`tests/test_http_cache.py`) | — | — |

## Deletion, step by step

`DELETE /api/v1/auth/me` (Settings → Danger zone: your password plus typing DELETE):

1. The account row is deleted. Every owned row goes with it in the same transaction, including
   pending emails, shares (their links die at once), drafts saved to the account, AI feedback,
   restore imports and sign-in sessions. Every access token stops working.
2. The browser clears that account's private drafts.
3. Background work that was already running doesn't bring anything back:
   - An email job claimed before the deletion finds no account and sends nothing
     (`test_an_email_job_mid_send_when_the_account_is_deleted_recreates_nothing`).
   - A judge result that arrives after the deletion is discarded, not written back
     (`test_a_judge_result_after_deletion_recreates_nothing`; until this batch it crashed on the
     foreign key and logged an unexpected worker error).
4. **What deletion can't reach:**
   - emails already delivered;
   - the mail provider's and Anthropic's own records;
   - older server backups, until they expire;
   - files you downloaded.

## Diagnostics and test artifacts

What each place that collects diagnostics holds. "Synthetic" means test accounts and throwaway
keys that work nowhere else.

| Sink | Holds | Never holds | Kept | Checked by |
|---|---|---|---|---|
| App logs (production) | request id, trace id, method, route path, status, duration; job ids, Message-IDs, error classes | email or IP addresses, codes, links, bodies, cookies, answer text | the host's setting | `test_log_redaction.py`, `test_email_transport.py`; compose rehearsal step 2c (no visitor address in the API's logs) |
| Command output (`preflight`, `check-email`, `email-status`, `email-quarantine`, `backup-database`, `restore-database`, `prune`/`check-backups`) | setting names and presence, stages, file names, counts, the driver's first error line | setting values, database URLs, passwords, private keys | your terminal | `test_preflight.py`, `test_redaction_canaries.py` (canary passwords and values through the failure paths), `test_backup.py` (a wrong key's error never echoes either private key), `test_restore_quarantine.py` (held emails by domain only) |
| Backup manifests, the restore log | table names, row counts, role names, hashes, times | user data | with the backups | `test_backup.py` |
| e2e run records (`test-results/.e2e-owned`) | run id, server name, process group, start time | environment, command lines | until the run ends | `e2eRun.node.test.ts` (a canary in the environment never reaches them) |
| e2e failure diagnostics (`[diag]` lines) | API paths, statuses, request ids, headings and alerts on screen | request or response bodies, form values, cookies, headers | CI job log | `frontend/e2e/fixtures.ts` |
| Playwright traces and screenshots (CI artifact, **failures only**) | what the page showed and its network, including **synthetic** tokens and answers | real users' data: CI uses synthetic accounts and throwaway keys only | 7 days (`retention-days`), visible to people with access to the repository's Actions | the workflow file |
| The e2e email folder (`backend/e2e-outbox`) | codes and links for synthetic accounts, for the tests to read | anything real | local; gitignored; never uploaded | `.gitignore`, CI's artifact path (frontend only) |
| CI rehearsal output (compose, launch, CSP) | ok/FAIL lines, versions, counts | passwords, private keys | the CI job log | the rehearsal scripts fail if a password or `AGE-SECRET-KEY` appears in their output |

If a real secret ever shows up in one of these: stop the thing printing it, rotate the secret
(SECURITY.md), and remember that deleting a local file doesn't remove an uploaded artifact or a
log line already shipped elsewhere.

## Checks

| Claim | Test |
|---|---|
| Deletion removes every row of yours and nothing of anyone else's | `tests/test_account.py::test_delete_removes_every_row_and_nothing_else` |
| A deleted owner's share links stop working; feedback you gave stays anonymised | `tests/test_shares.py::test_export_and_account_deletion` |
| Exports contain only your records, and no keys, tokens or credentials | `tests/test_export_v2.py` (other accounts' ids absent; `password`, `refresh_token`, `access_token`, `token_version`, `client_request_id` absent) |
| Late email and judge work recreate nothing; expired sign-in material is purged | `tests/test_privacy_lifecycle.py` |
| Sign-out clears every draft key the code uses | `frontend/src/test/integration/offline.test.tsx` (scans the source) |
| Private responses aren't cached | `tests/test_http_cache.py` |
| Logs carry no addresses, codes or links | `tests/test_email_transport.py::test_logs_never_carry_the_address_subject_or_code` |
| The production image logs no visitor IP addresses | `backend/Dockerfile` (`--no-access-log`); compose rehearsal step 2c |
| Failure output carries no configured value, password or private key | `tests/test_redaction_canaries.py`, `tests/test_backup.py` |

## Limits

- Operators with database access can read what the database holds; row-level security restricts
  the app's role, not the database owner's.
- Retention of email-provider, AI-provider and host logs depends on choices not made yet. Once
  they are, add them to this map with their real retention.
- Nothing here has been audited or certified, and none of it is a claim of legal compliance.
