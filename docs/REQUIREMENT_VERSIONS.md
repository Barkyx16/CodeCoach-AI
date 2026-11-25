# Requirement versions: changed requirements, kept history

A job target's requirements can be edited after they're found in the posting. Each edit has an
explicit meaning, and what was prepared earlier stays attached to the wording it was prepared
against (Volume 12, prompt 5).

## Identity and versions

A requirement keeps one id through its edits and has a version, starting at 1.

| What you do | What's recorded |
|---|---|
| Tidy the wording (spacing, capitals, punctuation) | Nothing new: the same requirement and the same version, no review needed |
| Change what it says, or move it to another group | The next version of the same requirement, with its new words |
| Add one | A new requirement, version 1 |
| Remove one | It's marked removed and stays readable with its history, shown under "Removed" |
| Restore one | It comes back at the version it had |

### What counts as cosmetic

An edit is cosmetic when the old and new wording are the same after:

- Unicode normalization (NFKC), so differently encoded characters compare the same;
- case-folding (a stronger lower-casing);
- replacing punctuation (anything that isn't a letter, digit, underscore or space) with a space;
- collapsing runs of spaces and trimming the ends.

Only within the same group: moving a requirement to another group is a change. So "current
RN license." and "Current  RN license" are the same version (and so are "RN-license" and "RN
license"); "Current RN license and BLS
certification" is version 2. There's no fuzzy matching here: a one-word change is a change.
The rule is `is_cosmetic` in `backend/app/services/requirement_versions.py`.

### History is only added to

Every recorded state is a row in `requirement_versions` (migration `a8e2c4f6b310`): the version,
what happened (`original`, `added`, `changed`, `removed`, `restored`), the words, the group and
the skills it mapped to then, and when. Rows are never edited or deleted (except with the target
or the account). A requirement gets an `original` row with its words at its first recorded
change; its earlier history isn't made up, and the page shows that row as "before the first
change" without a time (the row's time is when the change was made, not when the words were
written). Each requirement's History (on the target page, read when opened) lists them.

## Reviewing the whole set before saving

"Edit requirements" opens the whole set. Nothing is saved until you choose **Review changes**,
which asks the server what the edit would do (`POST …/requirements/revision/preview`, nothing
stored) and shows:

- a summary like "2 changed, 1 added, 1 removed, 5 unchanged" (a cosmetic edit counts as
  unchanged, and says "Wording tidied");
- for each change, its old and new words and versions, and the stories and accepted
  improvements it affects ("They stay linked to the earlier wording until you reuse them").

**Save these changes** sends the same set with the revision it was loaded at
(`PUT …/requirements`). If the set was saved somewhere else since (another tab), it's refused
(`409 stale_revision`) with the saved set in the reply: the page shows the saved requirements
beside yours, keeps your edits in the form, and offers "Keep mine and review again" or "Use the
saved ones".

A single requirement's **Correct** or **Remove** goes through the same rules: a cosmetic
correction saves at once; a change of meaning or a removal shows the same summary first, with
**Save this change**. (`PATCH …/requirements/{rid}` versions edits the same way for API callers.)

## Suggested, never silently equated

When a new requirement's wording looks like one being removed in the same edit (at least half of
their distinct words in common, leaving out small words like "a", "the" and "and"), the review
asks: "This looks like the earlier 'Current RN license'. Is it the
same requirement?" with **The same requirement: its next version** and **A different
requirement** (the default). Only the learner's answer links them, and choosing "the same"
needs a second review before saving. Declined, they stay two requirements: the old one removed
with its history, the new one at version 1. Accepted, the old requirement comes back as its next
version, with `same_as` recorded in its history.

## Evidence keeps its version

| Evidence | How it's linked | Its version |
|---|---|---|
| Stories | Chosen by the learner | Recorded when linked (`experience_entries.requirement_versions`) |
| Attempts (written answers) | The question practises a skill the requirement maps to | The version in effect when it was answered, read from the history |
| Accepted improvements | The question the improvement practises (its question link, or the interview question its retry is) | The version in effect when it was accepted, read from the history |

Attempts and accepted improvements are matched using the skills of **that** version, so
rewording a requirement so that it maps to other questions doesn't detach what was practised for
the earlier wording. Coverage ("Limited evidence", "Practised") is about the current wording: it
counts answers to the questions the current wording maps to.

A link says what it is about, never the learner:

- "Linked to the current wording (version 2)"
- "Linked to an earlier wording (version 1; now version 2)"
- "Linked before versions were kept: version not recorded" (a story linked before this existed)
- "Linked to a requirement you removed"
- "Reused for the current wording (version 2, first linked to version 1)"

An attempt answered against an earlier wording says so on the target page ("answered against an
earlier wording of '…' (version 1; now 2)").

**Use it for the current wording** (on a story or an accepted improvement linked to an earlier
wording) is the only way a link moves to a newer version. It's recorded as a reuse
(`reused_from`), and changes nothing else: no score is recalculated, the story's text and the
improvement's title, source and practice stay as they were. Nothing is re-scored or re-linked
automatically, and there are no bulk re-linking tools.

## Interviews in progress

An interview keeps the questions it started with: requirement edits never touch an interview's
plan, so a session started from the target's mock interview asks what it asked before the edit.

## Ownership, export and deletion

Every route checks the target is yours; another account's target, requirement, story or
accepted improvement ids read as not found, including an id from another account sent inside
your own set. `requirement_versions` is owner-only, under row-level security on PostgreSQL. The
data export includes each target's `requirements_revision`, each requirement's `version` and
`history`, each story's `requirement_versions` and each accepted improvement's
`requirement_reuse`; all of it is deleted with the target (history) or the account.

## Limits

- Wording similarity for suggestions is word overlap, not meaning: it may miss a rewording or
  suggest an unrelated one. It only ever asks.
- A requirement's skills changed through the API without changing its wording apply to the
  current version and aren't recorded as a version of their own.
- Backups restore none of this yet (the restore says what it doesn't restore).
