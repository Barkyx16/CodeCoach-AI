# Where a story is used (Volume 11, prompt 6)

Your stories are already linked from three places: an application's **Linked preparation**, an
interview kit's examples, and a reflection's "preparation I used". Those links were one-way: from
a story you couldn't see where it was used. Now you can, and linking a story to an application is
safer.

Nothing new is stored: the links are the story ids those records already hold. Nothing is copied
either: a backlink shows titles and dates, never notes, answers or the story's text.

## Supported relationships

| From | To a story | Chosen where | Shown on the story |
|---|---|---|---|
| An application | `story_ids` (up to 20) | the application's Linked preparation | Applications (n) |
| An interview kit | `story_ids` | the kit's examples (saved with the kit's revision) | Interview kits (n) |
| A reflection | `story_ids` | the reflection's form (revision-checked) | Reflections (n) |
| A practice answer | `story_id` | the question page ("Practise with one of your stories") | Practised with this story (already shown) |

Not linked: notes (a note keeps the question, problem or lesson it was written from), job targets
(a story has one target, chosen on the story), offer comparisons.

## `GET /api/v1/me/stories/{id}/used-in`

- **Yours only, both ends.** The story must be yours (404 otherwise, the same as a missing one), and
  only your applications, kits and reflections are read, so nothing of another account is ever
  listed or counted.
- **One level, bounded.** It lists what points at this story and stops there: nothing follows
  those records' own links. Each list holds the newest 20 (`limit`) with a count of all
  (`applications_total`, `kits_total`, `reflections_total`). An account's records are capped (300
  applications), so reading them is bounded too.
- **Titles and dates only.** An application: role, employer, stage, archived. A kit: the interview's
  title and date, the role and employer, and whether the application is archived. A reflection: the
  interview, role and employer *as the reflection recorded them* (a reflection is a record of that
  day; renaming the application later doesn't rewrite it).

## Changes to linked records

| Change | What the story shows |
|---|---|
| Rename an application | the new name (kits too); reflections keep what they recorded |
| Archive an application | still listed, marked "archived" (kits: "application archived") |
| Delete an application | gone, with its kits and reflections (they're deleted with it) |
| Rename or archive the story | every link stays; the application shows the story marked "(archived)" |
| Delete the story | its page is gone (404); applications drop it, a kit and a reflection say an example was deleted (as before); nothing is revived |

## Linking a story to an application

`PUT /api/v1/me/applications/{id}/stories/{story_id}` links one story; `DELETE` unlinks it. Both
return the application.

- **One at a time.** The page used to save the whole list of story ids, so a page showing an older
  list could undo a link made elsewhere. Now each checkbox sends only its own story.
- **Repeat-safe.** Linking a linked story or unlinking one that isn't linked changes nothing (not
  even the saved time), so after a lost reply the page says it isn't known whether it went through
  and offers **Try again**.
- **Both ends must be yours.** Another account's application or story is not found. Unlinking needs
  no story, so an id left behind by a deleted story can still be taken out.
- **Two at once both stay.** The write is conditional on the list it was worked out from (`UPDATE
  … WHERE story_ids = <as read>`); if another change got there first it reads again and retries, on
  SQLite and PostgreSQL alike. (A plain read-then-write lost one of four links made at the same
  moment on SQLite in testing.)
- **Up to 20.** The 21st is refused (409 `too_many_stories`); the page disables the remaining boxes
  and says why. A linked one can always be unlinked.
- The old way (`PATCH` with `story_ids`) still works for older pages.

On the page: one list in a fixed order (checking a box doesn't move it, so keyboard focus stays),
"Linked (n): …" with links to the stories, an archived story that's still linked shown "(archived)"
so it can be unlinked, competencies for context, and a **Find a story** box once there are more than
eight.

## Returning

Every backlink carries `{from: "/stories/<id>", fromLabel: "Back to your story"}`, so the kit,
application or reflection shows **Back to your story**. Nothing is guessed: a page opened another
way shows its usual way back (a story linked to several applications never assumes which one you
came from).

## Tests

`tests/test_story_links.py` (what each list holds and that nothing private is copied; renamed,
archived and deleted records; a deleted story's page and its id unlinked; another account's story
and application not found, nothing of theirs counted, signed-out refused; repeat-safe linking and a
stale page not undoing a link; the limit of 20; the newest 20 with a count of all; four links at once
all kept; an older application with no list), on SQLite and on PostgreSQL as the app role.
`src/test/integration/storyLinks.test.tsx` (the three lists, a title with markup shown as text, the
way back; "the newest 20 of 23" and the empty state; a failed read retried; linking by keyboard with
focus kept and the archived one unlinked, one story per request; a lost reply and Try again linking
once; the filter and the limit). `e2e/story-links.spec.ts` (real API: link by keyboard, choose in a
kit, find the kit from the story, open it, Back to your story, nothing copied, axe in both themes).

## Limits

- Stories only. Notes, targets and offer comparisons have no backlinks.
- Kits and reflections still choose stories in their own forms (they save with their own revision
  checks); only the application's chooser changed.
- The used-in lists are read from your records each time (no index): fine at the account caps, and
  the first thing to revisit if those caps grow.
