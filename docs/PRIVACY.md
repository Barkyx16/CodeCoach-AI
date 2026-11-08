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
| Server logs | the host's log storage | the host's setting | not linked: logs carry request ids, paths, job ids and SMTP codes, never addresses, codes, links or content (`tests/test_email_transport.py`) |
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

## Limits

- Operators with database access can read what the database holds; row-level security restricts
  the app's role, not the database owner's.
- Retention of email-provider, AI-provider and host logs depends on choices not made yet. Once
  they are, add them to this map with their real retention.
- Nothing here has been audited or certified, and none of it is a claim of legal compliance.
