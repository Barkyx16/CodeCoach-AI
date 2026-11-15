# Story freshness: when the story behind preparation moves on

A kit's chosen stories and a target's requirement links are prepared from a story. When the story
changes afterwards in a way that matters, the preparation says so, keeps what it was prepared from,
and changes only when the learner decides (Volume 12, prompt 8).

- The rules: `backend/app/services/story_freshness.py` (`assess`, `decide`, `CONTENT_FIELDS`).
- Kits: `backend/app/services/kits.py`; requirement links: `backend/app/services/roles.py`.
- Scope: stories, behind kits and requirement links (Volume 12, prompt 8); notes captured from a
  question, a lesson or a coding problem (Volume 13, prompt 6, "Notes" below:
  `backend/app/services/note_freshness.py`). Saved questions and collections come later.

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

## Notes

A note captured from a question, a lesson or a coding problem keeps the source's version it was
captured from (`notes.source_version`: a question's or lesson's version, a coding problem's test
version). When the source has a newer version that matters, the note says so; the note itself is
never changed, and its snapshot (the excerpt) is never refreshed.

| Source | A change that asks | What's shown |
|---|---|---|
| Question | A published correction marked significant. A typo fix is published as not significant and never asks ("Up to date: … only for typos or wording marked minor"). | Title and question side by side, as captured (or last reviewed) and now, with each correction's note. |
| Lesson | A new version that isn't marked minor. A typo fix isn't a new version at all (authors don't bump for typos); a wording fix kept on record can be published as a version marked minor (`Unit.minor`, Volume 15, prompt 5), which never asks, and a later version that matters still does. | The lesson's own note for each newer version, a minor one labelled "(minor)"; it doesn't keep its earlier wording, so the page says it can't be shown side by side. The lesson's version history labels minor versions too. |
| Coding problem | Any new test version. A problem's version changes only when its tests change (`app/db/seed.py`); a statement edit alone keeps the version, so it never asked. New tests are never minor: a verdict depends on them. | That it changed; there's no earlier wording to show. |
| Interview | Not versioned: no notice. | |

- **States.** `current`; `needs_review` ("The question changed since you captured this note
  (version 1, now 2). Review whether your note still fits."); `unknown` (captured before versions
  were recorded: "Whether the question changed since isn't known …", never "up to date"); `retired`
  (said with its reason; the note still opens); `unavailable` (it left the library).
- **Mark reviewed** records the version the learner was shown (`source_reviews`: holder_kind note,
  decision reviewed, from the version seen before, to the one shown, with a digest of that
  version's wording), once: a repeat or a second tab adds nothing, and two at once are one row
  (unique). It clears the notice until the source changes again in a way that asks. If the source
  changed again while the learner was looking, the review is for the version shown and the newer
  one is said ("changed again since you marked it reviewed at version 2 (now version 3)"). A note
  whose version isn't known can be marked reviewed too; later changes are then said.
- **The notebook** marks such notes "Source updated" and filters to them (`source_updated=true`;
  the page's "Source updated" checkbox, kept in the URL as `updated=1`). The note page shows the
  notice above the snapshot.
- **Data.** Reviews go with the note (removed when it's purged after its undo window; an Undo
  keeps them) and with the account; only the learner's own are read. The export carries each
  note's captured version and its reviews (`notes[].source_reviews`); the top-level
  `source_reviews` stays decisions about stories. A backup restore keeps a note's captured version
  and its reviews (Volume 14, prompt 7). Until then this page said a restore kept the captured
  version; the code in fact recorded the version the source had at restore time, so a restored note
  could read "up to date" past a change it never saw, and its reviews were dropped. Now the
  version comes from the file, only if the source has had it (otherwise "not known"), and each
  review of a version the source has had comes back, once.

## Saved items and collections

A saved question or coding problem, on the saved list (Saved → Bookmarks) and in each collection
and its practice queue, follows the notes' rule above: the same code
(`backend/app/services/note_freshness.py`, `SourceFreshness`) judges any holder of a versioned
source, with its own words and its own reviews. There is no second rule.

- **The version, when saved.** A bookmark records the source's version when it's saved
  (`bookmarks.content_version`; questions already did, coding problems now do too, as their test
  version). A collection item records the version it was added at (`collection_items.content_version`,
  migration `a9d2c4e6f813`): if the item is saved, the version the saved item was last seen at
  (saved or reviewed), so the badge means the same thing in both places; otherwise the version
  now. Items saved or added before versions were recorded read "not known", never "up to date",
  until marked reviewed.
- **The badge.** "Source updated" (a change that matters), "Version not known", or "Source retired",
  with what changed under "What changed": the server's text, a question's title and wording side
  by side as saved and now, and each version's change note. A source that left the library is
  said by the row's own banner, and the row stays. Drills have no versions: no badge.
- **Mark reviewed** records the version shown (`source_reviews`, holder_kind `bookmark` or
  `collection_item`), once, also from two tabs at once (the unique row), and clears the badge until
  a further change. A review on the saved list doesn't clear the collection's badge, or the other
  way round: each place is reviewed where it's shown. It isn't a bulk action yet; bulk add and
  remove keep working, and a bulk add takes the same versions as a single one.
- **Never changed.** A saved item isn't changed, moved, reordered or unsaved by any of this.
  Removing a saved item or a collection item takes its reviews with it; saving it again starts
  from the version then.
- **Filter.** The saved list's "Source updated (n)" checkbox, kept in the URL as `updated=1`, shows
  only the items whose source changed in a way that matters; one reviewed while filtered stays in
  view, with what it said, until the filter changes.
- **Data.** The export carries each saved item's and collection item's `version` and
  `source_reviews`. Restoring a backup brings saved items back with the version they were saved at
  (from the file, only if the source has had it; otherwise "not known") and their reviews.
  Collections aren't restored from a file yet, so their items' versions come back only with a
  collection that's still there; there's no way to share or copy a collection.
- **Limits.** A lesson's minor mark is reviewed content: a person marks it, and the content gate
  refuses one on version 1, beyond the lesson's version, or without a change note
  (`tests/test_minor_changes.py`; 6 negative controls, all caught). No lesson has a minor version
  yet: all six are at version 1. A coding problem's earlier statement isn't kept, so its change can't
  be shown side by side.

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
- Notes: `POST /api/v1/me/notes/{id}/source-review {reviewed_version}` → the note's `freshness`
  (docs/API.md, "Notebook"); `GET /me/notes?source_updated=true`.
- Saved items: each bookmark has `id`, `content_version` and `freshness` (the notes' shape);
  `POST /api/v1/me/bookmarks/review {item_type, track, ref_id, reviewed_version}` → that bookmark.
  Each collection item has `content_version` and `freshness`; `POST
  /api/v1/me/collections/{id}/items/{item}/review {reviewed_version}` → the collection.
