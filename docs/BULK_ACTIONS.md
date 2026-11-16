# Several at once (Volume 11, prompt 5)

Organising saved material a few items at a time: add several bookmarks to a collection, or take
several items out of a collection, and see exactly what happened to each. Only collection
membership; nothing here deletes a bookmark, a question, an answer or a collection.

## Supported operations

| Where | Action | What changes | What doesn't |
|---|---|---|---|
| Saved → Bookmarks | **Add the selected to** a collection you choose | those items join the collection, at the end | the bookmarks stay; nothing about your answers |
| A collection | **Remove N from "…"** | those items leave this collection; positions close up; the practice queue stays on the item it was on (or the last one) | the questions stay in the library; your bookmarks and answers aren't touched |
| Saved → Bookmarks, and a collection | **Mark N reviewed** (Volume 15, prompt 6) | a "Mark reviewed" for each, at the version its row shows (docs/STORY_FRESHNESS.md) | the items themselves: nothing is moved, reordered, unsaved or removed; the saved list's reviews and a collection's are each their own |

Not offered as a bulk action (on purpose): deleting bookmarks, collections or anything else;
answers, scores, schedules, shares or account settings.

## Duplicate a collection

`POST /api/v1/me/collections/{id}/duplicate {name?, client_request_id?}` (Volume 16, prompt 8), from
**Duplicate** on a collection's page: a new collection, "… (copy)" by default (numbered, "… (copy
2)", when that's taken; within the 80-character limit) or the name given, with:

| Carried to the copy | Starts fresh | Never touched |
|---|---|---|
| every item, in the same order, as the original shows it (one whose content left the library or was retired is carried as unavailable, never swapped or dropped) | the queue: at the first item, not started, nothing marked done | the original: its items, order, queue, marks and reviews |
| each item's version as it was added (`content_version`) and when (`added_at`, so "practised since added" reads the same) | | the saved list: no bookmark is added, removed or reviewed |
| each item's "Mark reviewed", copied as the copy's own record (its own `collection_item` holder in `source_reviews`): reviewing in one never changes the other | | another account's collections: one isn't found (404, the same answer as for an id that never existed) |

- **The name** is checked like a restored collection's: not one you already have, compared with its
  spacing and letter case ignored (`409 name_taken`: "You already have a collection called “…”
  (names are compared in any letter case). Choose another name.").
- **The limit** (50 collections) applies: `400 too_many_collections` with `{limit, count}`. The form
  says it before it's reached ("You have 47 of 50 collections; the copy would make 48."), and at it
  says so and doesn't send ("You have 50 of 50 collections: delete one to make room for a copy.").
- **A retried request makes one copy**: the page sends one `client_request_id` per exact request
  (`useRequestKey`), and the same key returns the copy it made (200, not 201), also from two tabs at
  once (the unique `(user_id, client_request_id)` settles a race). A key used for another
  collection's copy is refused (`409 idempotency_key_reused`). A lost reply says "No reply came, so
  it isn't known whether the copy was made. Sending it again is safe: it makes one copy, not two."
- The copy remembers where it came from (`copied_from_id`, migration `e5b1c7d9a248`; no foreign key,
  so deleting the original leaves the copy) and its page says "A copy of “…”" (or "of a collection
  you've since deleted"). Removing an item from either collection takes only that item's reviews.

## Selection scope

- **Only rows on screen.** A checkbox per row ("Select: <title>") and **Select all shown (N)**, which
  means exactly the N rows listed: these lists aren't paged, and nothing hidden is ever selected.
- **Counted out loud:** "K of N selected".
- **Stable keys:** a bookmark by its kind, career and id; a collection item by its id. If a selected
  row disappears (removed here or elsewhere), it stops counting, so a selection can't turn into a
  different group of records. Signing out leaves the page, and the selection with it; and since a
  bookmark's key is the same in every account, the selection also starts again whenever a different
  account is signed in, so one account's picks never apply to another's rows.
- **At most 50 at a time** (the server's limit): with more selected, the page says so and the action
  waits until 50 or fewer are chosen. One request per action, never several in parallel.

## `POST /api/v1/me/collections/{id}/items/batch`

Body: `{"add": [{item_type, track, ref_id}, …]}` or `{"remove": [item_id, …]}`: exactly one, 1–50
entries. Answer: the collection as it is now, and one result per entry, in the order sent:

| Outcome | Meaning |
|---|---|
| `added` | Added at the end. |
| `already_there` | It was already in the collection (including after a lost reply that did add it). |
| `unavailable` | Not in the library any more; nothing added. |
| `full` | The collection already holds 200 items; nothing added. |
| `removed` | Taken out of this collection. |
| `not_there` | Not an item of this collection (already removed, never there, or an id from another account: the same answer for all three). |
| `repeated` | The same entry earlier in this request; counted once. |

- **Owner first:** the collection must be yours (404 otherwise, before any entry is looked at), and
  every entry is checked on its own.
- **Repeat-safe:** adding and removing are idempotent, so sending the same batch again after a lost
  reply changes nothing twice and reports `already_there` / `not_there` for what had been done. Two
  batches adding the same item at the same moment keep one copy (each add in its own savepoint; the
  unique constraint decides, tested on PostgreSQL).
- **200 doesn't mean all done:** the page reads each result.

## `POST /api/v1/me/bookmarks/review/batch` and `POST /api/v1/me/collections/{id}/items/review/batch`

Body: `{"items": [...]}`, 1–50 entries: a saved item by its kind, career and id with
`reviewed_version`, or a collection's item by `item_id` with `reviewed_version`, each the version
its row shows. Answer: the saved list (or the collection) as it is now, and one result per entry,
in the order sent. Each is decided by the same rule as one at a time:

| Outcome | Meaning |
|---|---|
| `reviewed` | Recorded at that version; the badge goes. |
| `already_reviewed` | Already reviewed at that version or later; nothing more recorded (also after a lost reply that did record it). |
| `newer_since` | Recorded at that version, but the source has a newer one since, so it still asks. Needs attention. |
| `not_versioned` | A drill: no versions to review. |
| `unavailable` | No longer in the library: nothing to review. Needs attention. |
| `invalid_version` | That version doesn't exist yet. Needs attention. |
| `not_there` | Not saved (or not an item of this collection, or another account's: the same answer). |
| `repeated` | The same entry earlier in this request; counted once. |

The collection must be yours (404 otherwise, before any entry is looked at). Sending the same batch
again records nothing twice.

## The results on the page

**What happened: adding to "…"** (or removing from "…") gets focus after the action (the rows that
held it may be gone): a summary ("2 added, 1 not available. 1 needs attention; the rest are done.")
and one line per item, the ones that need attention (not available, didn't fit) first. Those stay
selected so they can be dealt with; the done ones leave the selection. When no reply comes, the page
says it isn't known which went through and offers **Send again**, which is safe for the reason above.

## Tests

`tests/test_collection_batch.py` (each add outcome, positions, the same batch again; full; removals
with positions, a bookmark and an answer left alone, removing again; another account's collection
404 and its item "not there"; bounds; two batches at once keeping one copy), on SQLite and on
PostgreSQL as the app role; `src/test/integration/bulkActions.test.tsx` (select all shown, one
request, per-item outcomes with attention first, focus, the ones needing attention kept selected;
a lost reply sent again reporting "already there", once each; 51 rows and the limit, a row removed
leaving the selection; another account signing in starting with nothing selected; keyboard
selection, removal with one already gone elsewhere, bookmarks untouched); `e2e/bulk-actions.spec.ts`
(real API: a lost reply and "Send again", removal by keyboard, bookmarks intact, axe in both themes).

Duplicate: `tests/test_collection_copies.py` (order, versions and reviews kept, a fresh queue, the
original unchanged; marking done and moving the copy's queue; reviewing and removing in one leaving
the other and the saved list; a retry making one copy, a key reused for another refused; the name in
any letter case, numbered defaults, the length limit; the collection limit and its words; retired and
removed items carried unavailable; the order after a reload and on another device; another account's
404 with nothing said; on PostgreSQL, row-level security keeping another account's rows unreadable)
and `src/test/integration/collectionCopy.test.tsx` (what the copy keeps, a lost reply sent again with
the same key making one copy, the copy saying whose it is, the limit said before and at it, a taken
name refused in the server's words), and `e2e/collection-copy.spec.ts` (the real API: a lost reply
sent again making one copy; the order after a reload and in a second browser; axe in both themes).

## Limits

- Two lists so far (bookmarks → a collection; a collection's items → out). Moving between
  collections, archiving in bulk and selection across pages aren't built. A collection can be
  duplicated whole, not in part, and only within the account (never shared).
- No Undo: the result list says what changed; adding or removing again reverses it.
