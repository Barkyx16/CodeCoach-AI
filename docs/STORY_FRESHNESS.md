# Story freshness: when the story behind preparation moves on

A kit's chosen stories and a target's requirement links are prepared from a story. When the story
changes afterwards in a way that matters, the preparation says so, keeps what it was prepared from,
and changes only when the learner decides (Volume 12, prompt 8).

- The rules: `backend/app/services/story_freshness.py` (`assess`, `decide`, `CONTENT_FIELDS`).
- Kits: `backend/app/services/kits.py`; requirement links: `backend/app/services/roles.py`.
- Scope: stories, behind kits and requirement links. Notes and question content come later, one at
  a time.

## Two kinds of version, kept apart

- **The story's revision**: every save of a story is a new revision, kept in `story_revisions`
  (docs/STORIES.md). This is what freshness is about.
- **A requirement's version** (docs/REQUIREMENT_VERSIONS.md): a requirement's own wording. A
  requirement link shows both, separately: "Linked to the current wording (version 1)" is about the
  requirement; "The story changed since you linked it (version 1, now 3)" is about the story.

## What counts as a relevant change

Preparation relies on the story's words: its **title, situation, task, action, result,
reflection, evidence, short version and long version**. A change to any of them asks for a review.

A change only to the rest doesn't, even though it's a new revision: **tags, competencies, private
notes, career, context, question links, the target it belongs to, archiving**. Nor does spacing
alone. The preparation says "Up to date: the story changed since (version 1, now 2), but only in
details this doesn't use, like tags or notes."

What changed is compared through a digest of those words, recorded when the preparation was made,
so it still works after the earlier revision itself is pruned (only the latest 100 are kept).

## What the learner sees

| State | What it says | Choices |
|---|---|---|
| Up to date | "Up to date with the story (version 3)." Nothing is shown on the kit or the card. | none |
| Needs review | "The story changed since you chose it for this kit (version 3, now 5). Review whether it still fits." (for a link: "since you linked it"), with what changed side by side, as prepared and now | "Use version 5" (refresh), "Keep version 3" |
| Kept | "You kept version 3 on 14 November; version 5 was the latest then. You'll be asked again only if the story changes again." | "Use version 5" |
| Unknown | "Whether the story changed since isn't known: this was prepared before story versions were recorded." | "Use version 5" (records a starting point) |
| No longer available | "This story is no longer available. What the kit prepared from it is kept here." (kits) | "Remove it from this kit" |

If the earlier revision was pruned, the change is said without the side by side: "The earlier
version isn't kept any more, so what changed can't be shown."

A changed source can need review without the earlier evidence having been wrong; the wording never
says otherwise.

## Refresh and keep

- **Deliberate.** Nothing refreshes by itself: reading the kit, saving it for another reason, or
  editing the story elsewhere never moves what a kit or a link was prepared from.
- **Bound to what was reviewed.** The request names the revision the learner reviewed. Access is
  checked again; if the story has moved on meanwhile, the answer is 409 `source_changed` ("The story
  changed again while you were reviewing it (now version 6; you reviewed version 5). Nothing was
  changed: review version 6.") and the page reloads to show version 6. A newer revision is never used
  silently.
- **Recorded** (`source_reviews`): who decided (the learner), what (refreshed or kept), from which
  revision to which, and when. "Refreshed from version 3 to version 5 on 14 November, by you."
- **Once.** Refreshing to the same revision again, or the same decision from two tabs at once,
  gives one result (a unique constraint, and the kit's own revision check).
- **All or nothing.** A refresh is one transaction: a failure leaves the kit or link exactly as it
  was.
- **Keeping is a valid decision.** It's recorded, and the question isn't asked again until the
  story's words change again.

On a kit, a review is its own save: with unsaved kit edits, the choices wait ("Save the kit first: a
review is saved on its own."). A refresh changes the kit, so another tab with unsaved kit edits gets
the usual stale-save choice when it saves.

## What's kept

- **Kits** keep each chosen story as prepared (`interview_kits.story_snapshots`: revision, digest,
  title and short version). The kit page's summary and the printed pack show the story as
  prepared when it changed since ("version 3; the story has changed since") or was kept. If the
  story is deleted, the kit keeps what it prepared from it until the learner removes it ("Remove it
  from this kit"); kits saved before this was recorded just count it, as before.
- **Requirement links** record the story's revision and digest when the link is made (inside
  `experience_entries.requirement_versions`, beside the requirement's version). A refresh is
  recorded in `source_reviews`; the link itself isn't rewritten. Deleting a story removes its links
  with it (the story holds them), so there is nothing left to label.
- Snapshots follow the existing retention rules: they go with the kit, the account, or when the
  learner removes them. Nothing is rewritten.
- Decisions go with what they were about: a kit's with its interview event (or its application),
  or when the learner removes what the kit kept from a deleted story; a requirement link's with its
  requirement's target or its story. All go with the account.

## What it never does

- Re-judge or re-score anything, or call an AI provider because a story changed.
- Rewrite a story, a kit's other content, or the history of decisions.
- Guess: preparation from before revisions were recorded stays "unknown" until the learner chooses.

## API and data

- `POST /api/v1/me/applications/{app}/events/{event}/kit/stories/{story}/review`
  `{reviewed_revision, decision: refresh|keep}` → the kit. `DELETE …/kit/stories/{story}/kept`
  removes what was kept from a deleted story.
- `POST /api/v1/targets/{target}/experience/{story}/review`
  `{reviewed_revision, decision, requirement_ids}` → the target.
- Each kit story has `prepared` and `freshness`; the kit has `kept_stories`; each requirement link
  has `story_freshness`. `freshness` = `{state, text, prepared_revision, current_revision, changes:
  [{field, before, after}], lineage: [{decision, from_revision, to_revision, at, text}]}`.
- The export carries each kit's `stories_as_prepared`, each link's story revision, and every
  decision (`source_reviews`). They aren't restored from a backup file (kits and targets aren't yet).
