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
| A collection | **Copy N to…** / **Move N to…** another of your collections (Volume 17, prompt 6) | each joins the other at its end, in this collection's order, as it was; a move then takes it out of here | Duplicate; your bookmarks and answers; another account's collections |

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
- **The limit** (50 collections, served as `collections_per_account`) applies: `400
  too_many_collections` with `{limit, count}`. The form says it, in the served number, before it's
  reached ("You have 47 of 50 collections; the copy would make 48."), and at it
  says so and doesn't send ("You have 50 of 50 collections: delete one to make room for a copy.").
- **A retried request makes one copy**: the page sends one `client_request_id` per exact request
  (`useRequestKey`), and the same key returns the copy it made (200, not 201), also from two tabs at
  once (the unique `(user_id, client_request_id)` settles a race). A key used for another
  collection's copy is refused (`409 idempotency_key_reused`). A lost reply says "No reply came, so
  it isn't known whether the copy was made. Sending it again is safe: it makes one copy, not two."
- The copy remembers where it came from (`copied_from_id`, migration `e5b1c7d9a248`; no foreign key,
  so deleting the original leaves the copy) and its page says "A copy of “…”" (or "of a collection
  you've since deleted"). Removing an item from either collection takes only that item's reviews.

## Copy or move items

`POST /api/v1/me/collections/{id}/items/transfer {to, items: [{item_type, track, ref_id}], move}`
(Volume 17, prompt 6), from **Copy N to…** or **Move N to…** on a collection's page with some of its
items selected, then the collection they go to. Within one account; nothing is shared.

| Arrives with the item | Stays behind | Never happens |
|---|---|---|
| the version it was added at (`content_version`) and when (`added_at`) | its queue mark ("Done in queue" belongs to the collection it was marked in; a moved item's goes with nothing, and the form says so) | an item doubled: one the other collection already has reads "Already there" (a move then just takes it out of here: "Already in “…”; taken out of “…”.") |
| its "Mark reviewed": moved with it, or copied as the new item's own record (reviewing in one collection then never changes the other; docs/STORY_FRESHNESS.md) | for a copy, everything here: this collection doesn't change | a move taking an item out before it's in the other: past the other's limit (200 items) an item reads "Didn't fit" and stays here, review, place and all |
| its place: at the end of the other collection, in this collection's order, whatever order they were picked in | | a half-done request: it's one transaction, so a failure part way changes neither collection |

- **Outcomes**, one per item in the order sent: `copied | moved | already_there | full | not_there
  | repeated` ("Copied", "Moved", "Already there", "Didn't fit", "Wasn't there": no longer in this
  collection, "Listed twice"). The page lists the ones that need attention (didn't fit) first and
  keeps those selected.
- **Before sending**, once the other collection is chosen, the form says what it already has ("“Week
  2” already has 1 of these 3: it won't be doubled.") and its room ("It has room for 47 more.", or
  how many won't fit, or that it's full); what arrives with each; and for a move, what leaves ("Leaves
  “Week 1”, each once it's in “Week 2”: “…” and “…”.") and what its queue will skip ("Its queue (at
  item 2 of 4) will skip 1 not reached yet: “…”."; a done item's mark "isn't carried").
- **After it**, the page links to both collections with their counts ("Now: “Week 2” has 3 items,
  and “Week 1” has 1 item.").
- **Sent again**: the request names each item by what it is (type, track, id) and both collections,
  so nothing changes twice whatever happens. And it carries a request key (Volume 18, prompt 5):
  the first reply's outcomes are kept with what it did, in the same transaction (a
  `lifecycle_receipts` row, purged after a week like the others), so the same request sent again
  after a lost reply gets them back exactly ("Moved", not "Already there"), marked `replayed`, with
  both collections as they are now, and the page says so ("This was sent again after no reply came:
  these are what the first request did, and nothing was done twice."). The same key for another
  request (other items, another collection, a copy instead of a move) is refused, `409
  idempotency_key_reused`; another account's key is its own. Since Volume 19, prompt 1, the key is
  kept on this device before the request is sent (a `transfer` record among the device's pending
  records, docs/RECOVERY.md: the source collection, the key and a fingerprint of the other
  collection, copy or move and the items; never anything else). After a reload the page asks the
  server what that key made (`GET /me/requests/{key}`, a read; nothing is sent again) and shows the
  first reply's outcomes ("Your copy or move from 10:31 arrived. These are what it did, and nothing
  was done twice.", then "2 moved", with a link to the other collection); one that never arrived
  says so, and nothing was copied or moved. Since Volume 20, prompt 5, the record also keeps the
  request by ids only (the other collection's id, copy or move, and each item as the server names it
  in the library: never a title, a note or anything typed), so one that never arrived is offered
  again: the page names what it was for ("It was a move of 2 items to “Week 2”. All of them are
  still in this collection."), leaves out items removed since and says so ("1 item has been removed
  from it since, so it's left out"), and **Send again** sends the rest with the request's own key
  (the server never had it, so the key makes it once). Nothing is sent until it's pressed; when the
  other collection was deleted since, it says so and offers nothing to send. One that did arrive is
  shown, never sent again. The dashboard's "Waiting for a reply" checks it the same
  way. Answered, refused or checked, the record is forgotten. Where this browser can't keep it, the
  key lasts as long as the page, as before. Two tabs sending the same items at once: the unique `(collection, item)`
  settles it, and the request that meets it is worked out once more against what's now there; two
  copies of one keyed request meet the receipt's unique key instead, and the second is given the
  first's reply. Shown with two real PostgreSQL transactions (Volume 18, prompt 6;
  `test_collection_transfer_race.py`): both requests read the other collection and find the items
  missing before either inserts (a test hook holds them there), the second insert waits on the
  unique key until the first commits and is refused, and that request is worked out a third time:
  a copy is made once ("Copied" for one, "Already there" for the other), a move moves once.
- **Refused**: either collection another account's or missing, `404` before anything is looked at;
  the same collection on both sides, `409 same_collection`; 1–50 items.

## Selection scope

- **Only rows on screen.** A checkbox per row ("Select: <title>") and **Select all shown (N)**, which
  means exactly the N rows listed: these lists aren't paged, and nothing hidden is ever selected.
- **Counted out loud:** "K of N selected".
- **Stable keys:** a bookmark by its kind, career and id; a collection item by its id. If a selected
  row disappears (removed here or elsewhere), it stops counting, so a selection can't turn into a
  different group of records. Signing out leaves the page, and the selection with it; and since a
  bookmark's key is the same in every account, the selection also starts again whenever a different
  account is signed in, so one account's picks never apply to another's rows.
- **At most 50 at a time** (the server's limit, read from `GET /limits` as `items_per_batch`; Volume
  17, prompt 7): with more selected, the page says so and the action waits until that many or fewer
  are chosen; a collection's bulk bar does the same for removing, marking reviewed, copying and
  moving. If the limits can't be read, no number is stated and the server refuses past it (422). One
  request per action, never several in parallel.

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

Copy or move: `tests/test_collection_transfer.py` (9, on SQLite and on PostgreSQL as the app role: a
copy keeping each item's version and review in the source's order and leaving the source as it was;
a move taking the items out with their reviews, the queue mark left behind and positions closed up;
sent again after a lost reply changing nothing twice; an item already there not doubled; repeated,
missing and over-the-limit items each with their own outcome; a move taking out only what arrived;
both collections yours and different; a failure part way changing nothing; another tab's identical
move committed first, met as the constraint would be and worked out again);
`src/test/integration/collectionTransfer.test.tsx` (the form's words for a move, a copy, a full or
nearly full collection and a queue not started; the item's key; a move through a lost reply sent
again with the same items, both collections linked; a copy with mixed outcomes, the one needing
attention kept selected; no other collection; a refusal); `e2e/collection-transfer.spec.ts` (the real
API: two of three moved through a lost reply, the form's words, axe on the form in both themes, both
collections after a reload, the versions as added). Negative controls, all caught: a move taking an
item out before it's in the other (the ones that didn't fit too), a copy dropping the review, a move
leaving it behind, the queue mark carried, the order sent instead of the source's, the version not
kept, no second pass after a clash, a resent move reading "not there", the same collection allowed;
on the page, a done item counted as ahead in the queue, what's already there not counted, the room
ignoring the other's items, a problem's key keeping its track, Send again sending a copy, everything
left selected, no link to the other collection, sending with none chosen, a lost reply shown as an
error; in the browser, a move that leaves the items in the source.

## Limits

- Bookmarks → a collection; a collection's items out, or copied or moved to another collection
  (Volume 17, prompt 6). Archiving in bulk and selection across pages aren't built. Copying, moving
  and duplicating stay within the account (never shared).
- No Undo: the result list says what changed; adding or removing again reverses it.
