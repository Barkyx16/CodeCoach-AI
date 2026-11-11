# Archive (Volume 11, prompt 4)

Archiving takes a record out of the active views so the lists you use stay short. It doesn't
delete, complete, submit or cancel anything, and a restored record is the same record: the same id,
content, revision and links, not a copy.

## What can be archived

| Kind | Archive / restore | Where archived ones are |
|---|---|---|
| Notes | `PATCH /me/notes/{id}` `{"archived": true/false}` (existing) | Notebook status filter "Archived" |
| Stories | `POST /me/stories/{id}/archive` / `unarchive` (existing) | "Show archived stories" |
| Applications | `POST /me/applications/{id}/archive` / `unarchive` (existing) | "Show archived" on the board |
| Target roles | `PATCH /targets/{id}` `{"archived": …}` (existing; an archived target can't be the active one) | the targets list, last |
| Offer comparisons | `POST /me/offer-comparisons/{id}/archive` / `unarchive` (new; migration `b8e4c2a7d915`) | "Archived (n)" on Compare offers |

Not archivable on purpose: interview-day kits (they belong to an application's event: archiving
the application takes its kits out of active views), interviews, answers, attempts and reflections
(history: they're never hidden or changed by tidying a list).

## The rules

- **Only the flag changes.** Archiving sets one flag. It doesn't touch the text, the revision or
  anything else, so it can't overwrite an edit made on another device, and an edit made elsewhere
  keeps the record archived. Asking twice is the same as asking once. (For offer comparisons the
  "saved" time doesn't change either; the older kinds set their last-changed time, as before.)
- **Owner only.** Archive and restore look the record up by its owner first: another account's id
  is "not found" and nothing changes. Archiving never makes anything public or shared.
- **History and stages stay.** An application keeps its stage and stage history (archived isn't a
  stage); its events, kits and reflections are kept. Evaluations, attempts and answers are never
  changed.
- **Links stay.** An archived story stays linked from interview-day kits (labelled archived there) and
  from answers that used it; an archived application stays linked from offer comparisons.
- **Active views leave archived records out**: lists, "Continue your work" (including the kits of an
  archived application) and search (unless "Include archived" is ticked).
- **Something still to come.** Archiving an application with an interview not yet over asks first and
  says what happens: it leaves the board and the upcoming list; the interview isn't cancelled, the
  stage doesn't change, and anything already on your schedule stays.
- **Deleting is different.** Delete is separate, can't be undone, and follows the account's retention
  rules: archive doesn't revive or keep anything deleted. Restoring a deleted record isn't possible.
- **Exports** say which records are archived (`archived` on notes, stories, applications, targets and
  offer comparisons). Restoring from a backup file keeps the flag where that kind is restored
  (offer comparisons aren't restored from files, as before).

## Offer comparisons (`features/offerCompare/OfferCompareList.tsx`)

**Active (n)** and **Archived (n)** switch the list (the choice is in the address, `?archived=1`).
Each row has **Archive** or **Restore** ("Archive: <title>"). After one leaves the list, focus moves
to the next row's button (or the list's heading when none is left), and the page says what happened
("… archived. It's under Archived; nothing was deleted.") with a button to the other view. An
archived comparison still opens, with a banner and **Restore**; it can still be edited.

## Tests

`tests/test_archive_lifecycle.py` (archive and restore unchanged, twice is once, an archive never
overwrites a save elsewhere and the revision check still refuses a stale save, owner only, deleting
stays deleting, the export flag, "Continue your work" without archived notes, stories,
applications, their kits and comparisons, an archived application's stage and events, an archived
story still linked from a kit), on SQLite and PostgreSQL; `src/test/integration/archive.test.tsx`
(counts, archive with focus and message, restore from Archived, the last one, the banner and Restore
sending only the flag, the question before archiving an application with an interview coming and
"Keep it active" sending nothing); `e2e/archive.spec.ts` (real API, keyboard, Continue your work,
restore unchanged, the application's stage kept, axe in both themes).

## Limits

- Counts are shown for offer comparisons; the older lists keep their own filters without counts.
- There's no Undo button: Restore is the undo, from the Archived view or the record's own page.
