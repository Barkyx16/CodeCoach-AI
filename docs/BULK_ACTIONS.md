# Several at once (Volume 11, prompt 5)

Organising saved material a few items at a time: add several bookmarks to a collection, or take
several items out of a collection, and see exactly what happened to each. Only collection
membership; nothing here deletes a bookmark, a question, an answer or a collection.

## Supported operations

| Where | Action | What changes | What doesn't |
|---|---|---|---|
| Saved → Bookmarks | **Add the selected to** a collection you choose | those items join the collection, at the end | the bookmarks stay; nothing about your answers |
| A collection | **Remove N from "…"** | those items leave this collection; positions close up; the practice queue stays on the item it was on (or the last one) | the questions stay in the library; your bookmarks and answers aren't touched |

Not offered as a bulk action (on purpose): deleting bookmarks, collections or anything else;
answers, scores, schedules, shares or account settings.

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

## Limits

- Two lists so far (bookmarks → a collection; a collection's items → out). Moving between
  collections, archiving in bulk and selection across pages aren't built.
- No Undo: the result list says what changed; adding or removing again reverses it.
