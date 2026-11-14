# Work samples

Volume 10, prompt 5. Practice the work, not only the interview: a short, realistic professional
artifact written from a **fictional brief**, with feedback on whether it covers what the brief asks
using only the facts the brief supplies. Different from "Tell me about a time": the learner writes
the incident update, the reply or the handoff note itself, for a named reader.

Nothing is sent anywhere: no email, no publishing, no employer submission, no sharing. Copying the
text is deliberate (a "Copy as text" button in the preview). A finished work sample is practice
evidence, not a credential or proof of workplace performance; the page says so before any input.

## Where it is

- `/work-samples` (signed in): briefs for the learner's career first, others below ("open to
  anyone curious"); the dashboard's "More ways to practice", the command palette ("Work samples")
  and Help ("Work samples").
- A brief: `/work-samples/<id>`.

## Careers and formats with content

| Brief | Format | Careers |
|---|---|---|
| Checkout errors: the first status update | Incident status update (4 sections) | software-engineer, it-support-specialist |
| A double charge, explained to the customer | Customer explanation (one message) | customer-service-representative |
| Handing over the office move | Project handoff note (4 sections) | project-manager, product-manager, construction-project-manager |

No other career has a brief yet. Regulated professions (nursing, finance) are deliberately not
covered: their content would need review by a practitioner before it could be offered.

## What a brief is made of

A file in `backend/app/seed/worksamples/` (loaded by `backend/app/worksamples/__init__.py`):

| Field | Meaning |
|---|---|
| `id`, `version`, `title`, `format`, `format_label`, `careers` | `ws-…`; the careers it's offered to first |
| `scenario`, `audience`, `purpose` | the situation, who reads the artifact, what it's for |
| `facts` | the only facts the learner may use (all made up) |
| `required` | the points the brief asks for: a label, matchers (several phrasings each) and the guidance shown when it's missing |
| `claims_to_avoid` | statements the facts contradict (e.g. "fixed" when it isn't), with why |
| `avoid` | words wrong for this audience (e.g. "5xx" in a non-engineering channel), with why |
| `sections` | the parts the format calls for; none means one plain message |
| `limits` | words, minimum and maximum |
| `reference` | one good approach, per section |
| `review_status`, `scope_note` | how it was checked; the practice-scope note shown before input |

### Checked before a learner sees it

`validate-content` refuses a brief whose own reference artifact fails its checks (a required point
not covered, a detail not in the facts, a claim it warns against, an audience-unfit word, outside its
limits), whose guidance mentions a detail that isn't among its facts, or whose careers aren't known.

## The editor

The brief (scenario, reader, purpose, facts, the points it asks for, limits) sits beside the editor
on wide screens and above it on narrow ones. One textarea per section (or one for the message), a
live word count against the limits, Preview (the artifact as a document, rendered as text, with
"Copy as text"), Save draft (revision-checked, with update receipts; a stale save shows both
versions), a copy on this device until saved (`work-sample-draft:<account>:<id>`, cleared at
sign-out) offered back after a reload, and the leave guard while unsaved.

## Feedback

Fixed checks (`app/worksamples/feedback.py`), not AI; every note points at the learner's own text or
at the brief:

- **Required parts** (deterministic): every section has text; the length is within limits.
- **Points**: covered when the text says it in any phrasing the brief accepts; a covered point quotes
  the learner's sentence ("What you covered"); a missing one shows the brief's guidance ("Missing").
- **Not supported by the brief**: every specific in the text (a time, amount, percentage, date,
  reference, phone number, any number of two or more digits) is compared with the specifics in the
  facts after normalising (6pm and 18:00 are the same time, $84.20 and 84.20 the same amount); one
  the facts don't contain is named with its sentence. Claims the facts contradict are named too,
  unless negated nearby ("not fixed yet" is fine). Invented details never count as evidence.
- **Audience and clarity**: the brief's audience-unfit words; sentences over 35 words.
- **One revision to try**: the most important thing to change (a contradicted claim, then an
  invented detail, then the first missing point, …).
- **One good approach**: shown only when asked, labelled as one way to do it; wording, order and
  style don't need to match.

Matching is by meaning-bearing phrases, with several alternatives per point, so different
structures and styles pass when they cover the points with the facts.

## Revisions, ownership, export

- Every send is an attempt (`work_sample_attempts`), with the text as sent, a snapshot of the brief
  it was written against, and the feedback. After the first, a send is a revision that names the
  attempt it revises; the original is never changed.
- Drafts and attempts are owner-only and under PostgreSQL row-level security (migration
  `c4a9e2f71b35`, listed in `rls.ADDED_TABLES`); another account gets 404, and can't name your
  attempt as the one theirs revises.
- In the data export as `work_samples`; deleted with the account; not restored from backups.
- Interview answers and coding verdicts are separate: nothing here changes a score, progress or a plan.

## Limits

- The checks can't judge tone beyond the brief's word lists, or whether a sentence is true in a way the
  facts don't settle. A point phrased in a way none of its matchers expects reads as missing; the
  guidance then says what was looked for.
- A number the facts don't contain is flagged even when harmless (a year, "24/7"); the note asks the
  learner to check it rather than calling it wrong.
- No AI: an unavailable or over-budget AI coach changes nothing here. If AI commentary is added later,
  it must be grounded in the brief's facts and kept apart from these checks.
- Three briefs, written for practice and checked for internal consistency, not reviewed by an outside
  practitioner. Plain text only; no rich formatting.
