# Sharing an answer for feedback

A learner can share one of their graded answers (a practice answer, or an answer from a finished
mock interview) with a mentor or practice partner, and get structured feedback back. This page
is the security, privacy and retention model. Endpoints are in [API.md](API.md#sharing-an-answer-for-feedback);
tables in [DATABASE.md](DATABASE.md#shared-answers).

## The reviewer model: an unlisted link

Sharing works with an **unlisted capability link**, not reviewer accounts: the people a learner
asks are often not CodeCoach users. The trade-off is stated on the page before a link is made,
and the learner has to tick it: **anyone who has the link can see what was selected** until it
expires or is turned off. A reviewer who happens to be signed in is named as such; everyone else
is a guest whose name (optional) is shown as unverified.

## What is shared

The learner chooses, and sees the reviewer's view before creating anything (the preview is the
server's own rendering of the snapshot, not a client-side imitation):

- the question (title, prompt, career, kind, difficulty);
- the sentences of the answer they tick (the reviewer sees where something was left out, never
  what);
- optionally the follow-up question and their reply (interviews);
- optionally CodeCoach's automated feedback (score, rating, summary, which rubric points were
  covered), always labelled as automated;
- an optional note to the reviewer (500 characters).

Never included: name, email, account id, other answers or history, scores over time, goals,
plans, notes, target roles, hidden tests, or audio (CodeCoach never stores audio, so there is
nothing to share; no audio option exists).

What the reviewer sees is a **snapshot** taken when the link is made. Editing or deleting the
original later never changes it; the owner's page says when the original changed or is gone.

## The link and its secret

- The secret is 256 bits from `secrets.token_urlsafe(32)`. Record ids are never used as keys.
- The link is `https://<site>/shared#t=<secret>`. The secret is in the URL **fragment**, which
  browsers don't send to servers or in `Referer` headers, so it doesn't appear in server or
  proxy access logs, analytics, or other sites' logs. The page sends it in a POST body; the API's
  access log records the path only (a test checks the secret never appears in it).
- Only the secret's SHA-256 is stored. A database copy can't be turned back into working links,
  and the owner can't see a link again: "Make a new link" replaces it and the old one dies.
- Shared pages and API responses carry `Cache-Control: no-store`, `X-Robots-Tag: noindex,
  nofollow` and `Referrer-Policy: no-referrer`; the page adds `noindex` and `no-referrer` meta
  tags; `robots.txt` disallows `/shared`. There is no sitemap. The reviewer's page never keeps
  the snapshot in the app's cache (`gcTime: 0`), so a revoked link can't be shown from memory.
- Unknown or replaced links answer `404`; revoked or expired links answer `410` with no content.
  Opening and feedback are rate-limited per client IP, and creation per user; the secret's
  length is what makes guessing infeasible, the limits bound load and abuse.

## Expiry, closing, revoking, deleting

| Action | The link | The snapshot and feedback |
| --- | --- | --- |
| Expires (1, 7 or 30 days) | stops working (`410`) | kept for the owner |
| Stop taking feedback (close) | still opens, read-only; can be reopened | kept |
| Turn the link off (revoke) | stops working for everyone, at once, for good | kept for the owner |
| Make a new link | old link `404`, new one works | unchanged |
| Delete | stops working | deleted, with all its feedback |

**Retention:** after expiry or revocation the snapshot and feedback stay visible **only to the
owner**, until the owner deletes the share or the account. Nothing is purged automatically.

## Feedback

- Three prompts ("What was clear?", "What needs more evidence?", "One useful next step") and up
  to 8 comments, each anchored to a shared sentence by its index in the snapshot (stable because
  the snapshot never changes). Bounded sizes; at least one box must be filled.
- Stored and shown as **plain text** (control characters removed, rendered by React as text,
  never HTML or Markdown), so markup in feedback is inert.
- A retry with the same `client_request_id` returns the original instead of a duplicate.
- Feedback is labelled as a person's opinion, shown on its own page section, apart from the
  automated feedback and judge verdicts. It never changes the answer, its score, the practice
  plan or progress, and is not a correctness verdict, professional validation or hiring decision.
- The owner can mark feedback useful or delete it. The owner can't review their own share.
- There is no moderation team, so there is no "report" button: the owner controls who has the
  link, and can delete feedback, turn the link off or delete the share.

## Notifications

None. CodeCoach doesn't email, message or notify anyone about shares or feedback. The learner
copies the link and sends it themselves; they see new feedback when they open the share.

## Export and deletion

- The owner's data export includes each share's snapshot, status, dates and feedback received
  (no link secrets: none are stored).
- A reviewer's export includes feedback they wrote while signed in (their words and the
  question's title, not the learner's answer).
- Deleting the owner's account deletes their shares and all feedback on them (cascade).
- Deleting a reviewer's account keeps the feedback with the learner it was written for, labelled
  "A former CodeCoach user (account deleted)".

## Limits

- Coding submissions and whole transcripts can't be shared yet; one written answer (plus its
  follow-up) per share.
- A capability link can be forwarded; the page asks reviewers not to, and the owner can turn it
  off, but nothing technical stops forwarding while it works.
- Rate limits are per client IP; behind a proxy, `FORWARDED_ALLOW_IPS` must be set so the real
  client IP is used.
