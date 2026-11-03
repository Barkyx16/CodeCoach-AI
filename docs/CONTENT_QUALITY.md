# Content quality: labels, reports, corrections and retirement

How CodeCoach tells learners what its content is, how learners report problems, how reports are
triaged, and how corrections and retirements are made without rewriting anyone's history.

## What the content actually is

Be precise about this; the labels are.

| Content | How it was made | What has been checked | Expert review |
| --- | --- | --- | --- |
| Career interview questions (33,000 across all careers) | **Generated** by CodeCoach's question templates from structured career profiles (`backend/app/careers`) | `validate-content` checks fields, levels, kinds, ids and career mapping | **None recorded** |
| Coding problems (300) | **Generated** for the problem bank (statement, tests, reference solution) | Schemas and test shapes; with `--run-reference`, a trusted reference solution is compiled and run against every test, and the result is recorded | **None recorded** |
| Learn lessons (6) | Authored; each states its own review status and sources (docs/LEARN_CONTENT.md) | References and links between lessons, questions and problems | As stated per lesson; nursing lessons are not clinically validated |
| Branching scenarios (2) | Authored, fictional | The graph validator | As stated per scenario; not clinically validated |

Nothing in CodeCoach claims expert, clinical or employer review, reviewer credentials, citations
it doesn't have, or employer associations. Passing the validation command is **automated
validation, not expert review**.

## Labels learners see

"About this question / problem" on each question and coding problem shows career, topic, level,
version and labels built only from recorded facts (`ContentService.meta`):

- **Generated** (always, today): "Generated from the {career} career profile by CodeCoach's
  question templates" or "Generated for CodeCoach's coding problem bank".
- **Not reviewed by a subject-matter expert** (always, today).
- **Reference solution passed all N tests (checked {date})**: only when a passing
  `reference_solution` check is recorded in `content_checks` for the problem's **current** test
  version. Otherwise: "Tests haven't been checked against a reference solution on this server".
- **Corrected N times**: when corrections have been published, with each change note.

One label never implies another: "generated" says nothing about review, a passing reference run
says nothing about how well the problem teaches, and a correction isn't a review.

## Reporting an issue

"Report an issue" on every question and coding problem, and "Report a problem with this feedback"
under the feedback on an answer.

- Categories: ambiguous wording, incorrect example or answer, outdated guidance, wrong career or
  topic, accessibility problem, technical bug, something else. Details are optional (2,000
  characters).
- Sent automatically: the content id and **the version on screen**. Nothing else. Feedback
  reports also name the learner's own answer (the server checks it's theirs); the answer text is
  attached only if the learner ticks "Attach part of my answer" and reviews (and can edit) the
  excerpt. Transcripts, recordings and other account data are never attached.
- Rate-limited (10 per user per hour, `CONTENT_REPORTS_PER_HOUR`). The same person can't file
  the same open report twice; a different person's report on the same content and category is
  grouped under the first as a likely duplicate. Nothing is merged or deleted.
- Stored and shown as plain text (control characters removed; never rendered as HTML).
- A report never changes a score, an answer, a plan or progress.
- Learners see their own reports, status and the public resolution in **Your reports**
  (Settings → Privacy & data, or `/reports`). They never see other reporters or internal notes.
  Nothing is emailed, and no resolution time is promised.

## Triage (admins)

- Admin is a flag on a registered account, **granted only from the command line** on the server:
  `python -m app.cli grant-admin EMAIL` (and `revoke-admin`). No API or page can grant it.
- Every admin route answers **404** to anyone who isn't an admin, signed in or not; the admin pages
  show "Page not found". There's no public maintenance route.
- **Triage** (`/admin/reports`): reports grouped by content, likely duplicates nested; filters for
  open (incl. investigating), resolved, not actionable and all. A report shows the learner's text
  and chosen excerpt as plain text, the reporter's display name (never an email), the version
  they saw and the current one, the content's labels, and the audit trail.
- **Statuses**: open → investigating → resolved or not actionable (can be reopened). Resolved and
  not actionable need a plain-language explanation for the reporter. Changing a group's first
  report updates its duplicates too.
- **Grouping**: an admin can group a report under another about the same content, or ungroup it.
- **Audit**: every report, grouping, status change, correction, retirement and restore is written
  to `content_audit` with who, when, what and an optional internal note. Internal notes are
  admin-only.

## Corrections are new versions

- "Publish a correction" (career questions) changes the title, prompt, tips or outline, with a
  short change note for learners and a "significant" flag. It creates the next version
  (`content_versions`); version 1 is the generated original and versions only grow.
- Answers record the version they were written against (`practice_answers.content_version`) and
  are never re-graded or rewritten. A past answer on an older version says so and offers the
  wording that was answered (`GET /careers/{slug}/questions/{id}/versions/{n}`).
- A learner who answered or saved the question before a significant change sees what changed
  when they come back. Saved items remember the version they were saved at.
- Linked reports, and their grouped duplicates, are resolved with "Corrected in version N: …".
- Coding problems are corrected in their seed files (statement, tests and reference solution
  together), which bumps the test version. Existing submissions keep the test version they were
  judged against. **There is no re-evaluation of old submissions**: if one were ever justified it
  would have to be a separate, authorized, audited job, not an automatic score rewrite.

## Retirement

- An admin can retire a question or problem that's unsuitable for assessment, with a reason
  learners see. Retired content is left out of lists, interview rounds, plans, recommendations
  and role preparation, and can't be answered or submitted (`409 content_retired`).
- It stays readable: History, past answers and submissions keep it, and saved items and
  collections link to it with "Retired: {reason}". It can be restored.

Corrections, retirements and restores take effect at once on the API process that made them;
other API replicas pick them up within a few seconds (each keeps a snapshot of corrections and
retirements that it reloads at most every 5 seconds).

## Quality gates: `python -m app.cli validate-content`

Runs in CI after migrations. Checks career questions (required fields, levels, kinds, unique ids,
career mapping, bank size), published corrections (existing content, correctable fields only,
versions 2, 3, … without gaps, a change note), retirements (existing content), lessons
(prerequisites, linked and practice questions/problems exist; retired links warned), scenarios
(the graph validator) and coding problems (required keys, unique slugs, difficulty, signature,
public and hidden tests, a reference solution file).

- `--run-reference` compiles and runs each trusted reference solution against every test with a
  local JDK (`scripts/verify_reference_solutions.py`; never user code). `--record` stores the
  results in `content_checks`, the only source of the "reference solution passed" label. In this
  environment all 300 passed.

## Review process (for content changes)

1. Triage reports at `/admin/reports`; set "investigating" and note what you checked.
2. Fix the content: a correction for a career question, or a seed-file change (with its
   reference solution) for a coding problem. Run `validate-content --run-reference`.
3. Explain the outcome in plain language; it's what the reporter reads.
4. If something can't be fixed soon and shouldn't be used for assessment, retire it with a reason.
5. Only describe content as reviewed by an expert after a named, qualified review has actually
   happened and been recorded. There is no such record today, and no label for it.
