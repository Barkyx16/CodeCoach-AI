# Search your workspace (Volume 11, prompt 3)

Find your own saved notes, stories, interview-day kits and applications by the words in them. It's
separate from the question-bank search (public questions and problems) and from Go to… (the
command palette, which finds pages, not records).

## `POST /api/v1/me/search` (`app/services/workspace_search.py`)

Body: `{"q": "...", "kinds": ["notes", "stories", "kits", "applications"], "include_archived": false, "limit": 20}`.

A POST so the words travel in the body: they're kept out of URLs, browser history, proxy access
logs and the app's request log (which records the path only). Nothing typed is logged; a kind that
fails is logged by name only.

### What's searched

| Kind | Fields | Not searched |
|---|---|---|
| Notes | title, text, reflection, tags, the title of the question it's attached to (what the notebook's own search covers) | deleted notes (also during their undo window); archived ones unless asked |
| Stories | title, situation, task, action, result, reflection, private notes, evidence, short and long versions, tags (what the story bank's own search covers) | archived ones unless asked |
| Interview-day kits | the interview's title, the employer and role it's for | the kit's notes, interviewer names, location, links, checklist and questions |
| Applications | employer, role, next step | application notes, links; archived ones (and their kits) unless asked |

Never searched: drafts kept only in this browser (see [YOUR_DATA.md](YOUR_DATA.md)), answers and
transcripts, audio, shares, diagnostics, anything of another account.

### Matching, ranking, snippets

- **Every word must appear** somewhere in the record's searched fields (a word inside a longer one
  counts: "lact" finds "lactate"). Words are folded (Unicode NFKC, lower case); at most 8 words of
  at most 60 characters are used; `q` is 1–200 characters and needs at least 2 real characters.
- **Punctuation is literal.** `c++`, `100%` and `under_score` match those characters; `%` and `_`
  are escaped, so they're never LIKE wildcards. Every value is a bound parameter.
- **Ranking:** a word in the title counts 3, in a tag 2, in the text 1; ties go to the most recently
  saved. `matched` says where the words were found.
- **Snippet:** plain text, up to about 160 characters around the first word found (or the start of
  the text when only the title or a tag matched). The page shows it as text and marks the words
  itself: markup in a note comes back, and is shown, as the characters typed.
- **Counts** are per kind, among your own records only. A kind with more than 200 candidates says so
  (`capped`): use more words.

### Ownership and bounds

- **Owner first.** Every query has `user_id = :me` before anything is matched, counted, ranked or
  quoted (kits also require the application to be yours), and PostgreSQL row-level security applies
  on top for the app role. Another account's records never reach Python, so its words can't show up
  in results, counts or snippets, or be inferred from them (tested with the same words in two
  accounts).
- **No new index.** The database narrows each kind to the caller's rows through the existing
  owner index, then matches text on those few rows. Measured on a throwaway PostgreSQL 16 database
  with 20,000 notes across 100 accounts: a bitmap index scan on `ix_notes_user_id` (200 of 20,000
  rows), the text filter on those, 3.0 ms; the whole four-kind search 30 ms. A trigram or full-text
  index would only pay off for much larger per-account collections.
- **Bounded:** at most 200 candidates per kind, at most 50 results (default 20).
- **Rate limited:** 120 searches a minute per account (typing is debounced on the page), then 429
  with `Retry-After`; other accounts aren't affected.
- **One kind failing doesn't take the rest down:** each kind is read in its own savepoint; one that
  fails is named in `unavailable`.

## The page: `/search` (`features/search/WorkspaceSearchPage.tsx`)

Reached from **Go to…** ("Search your saved work"), the **Library** menu ("Search"), or a dashboard
shortcut once added. Signed-in only.

- **Words to find**, with **Look in** (notes, stories, interview-day kits, applications) and
  **Include archived** (off by default). With no kind chosen it says so and sends nothing; fewer
  than 2 characters, the same.
- **Typing** waits 300 ms after the last key before searching, so there's no request per keystroke.
  Each search is cached under its account and its exact words and filters: an older search's
  answer is never shown for a newer one, and a superseded request is cancelled (its abort signal).
  While a search is pending the results say "Searching…" rather than showing the previous words'
  results.
- **Results**: kind, title, a snippet, Archived or Pinned, the application's stage or the kit's
  employer and date, "saved … ago" (the record's last save to the account) and where the words were
  found. Words are marked with `<mark>` around React text: nothing from a record is ever rendered as
  HTML (`features/search/Highlight.tsx`), so markup shows as typed.
- **Opening a result** uses the record's own route (a kit: `/applications/<app>/events/<event>/kit`),
  so the leave guard and Back behave as anywhere else; a record deleted since opens its "no longer
  available" page, and the list is read again when the search shows.
- **Back from a result** brings the same words and filters back. They're kept in this tab's history
  entry (`history.state`), with the account's id, and never in the address: a copied link or a
  shared URL doesn't carry them, and another account signing in on this tab never gets them back.
- **Honest states**: nothing found ("Nothing saved to your account matches those words."), a kind
  that couldn't be searched (named; the rest are listed), too many candidates (add a word), too many
  searches in a minute (wait), and other failures with Try again; none invents a result.
- **Another account** never sees the first one's words or results: the page is keyed by the account,
  signing out clears the cache, and an answer arriving after the switch is dropped.
- Drafts kept only in this browser aren't searched; the page says so and links to Your data.

## Tests

`tests/test_workspace_search.py` (each kind by its own fields; every word required; tags; kinds
chosen; another account's identical text invisible in results, counts and snippets; archived only
when asked, deleted never; punctuation, wildcards, markup and SQL-looking text as plain text;
bounded input that isn't echoed back; the database step alone matching wildcards literally; a
failing kind named; the words not logged and never a GET; the rate limit per account), on SQLite and
on PostgreSQL as the app role. `src/test/integration/workspaceSearch.test.tsx` (each kind linked to
its page, the words only in the request body, debounce, an older answer never shown, another
account, markup as text, kinds and archived, Back restoring the search without the address, another
account's saved search not restored, too short, a failing kind, too many searches, Go to… and the
Library menu); `e2e/workspace-search.spec.ts` (real API: a saved story and a private note found while
another account's note with the same words stays invisible, the words in no address, keyboard only,
Back restoring the search, axe in dark and light) and `workspace-search-mobile.spec.ts` (fits a
phone).

Negative controls: 23, each caught, among them the owner filter removed, deleted or archived notes
searched, LIKE wildcards live, the words logged or in an address, a GET allowed, no rate limit, no
savepoint (PostgreSQL), no debounce, one cache entry for every search, a title rendered as HTML,
another account's search restored, archived by default. Two guards are layered on purpose and each
alone is redundant: every word is required both in SQL and in the exact check after it, and a kit
requires both the kit and its application to be the caller's.

## Limits

- Substring matching, not stemming or typo tolerance: "stories" doesn't find "story".
- On SQLite (development), upper/lower-case folding of non-ASCII letters and non-ASCII tags are
  matched only as typed; PostgreSQL folds them.
- Application notes and kit contents aren't searched yet.
- Go to… finds pages, not records: typing in it doesn't search your saved work (open "Search your
  saved work" from it instead).
