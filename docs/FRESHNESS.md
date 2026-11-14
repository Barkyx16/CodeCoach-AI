# Records changed elsewhere (Volume 11, prompt 9)

What a page does when the same account changes a record in another tab or on another device.
This slice covers **stories** (the story page, the stories list, "Where it's used" and Continue
your work). Other records keep their existing behaviour (listed below), described as it is.

## How a change reaches a page

| Where the change was made | How this page learns of it | When |
|---|---|---|
| Another tab of this browser | A hint over a `BroadcastChannel` (`codecoach-records`) | at once |
| Another device, or a tab that missed the hint | The story and the stories list are asked again when the tab is focused again or the connection comes back | on return / reconnect |
| Anywhere | Opening the page asks the server | on open |

A hint says only `{account, type: "story", id, change: saved | archived | unarchived | deleted,
revision}`, never the story's text. It is a hint: the page asks the server again, as this account,
through the usual requests, so it can't show anything the server wouldn't. A hint for another
account is ignored, and a malformed one is dropped. Hints are sent by the page that made the change
(saved, archived, unarchived, deleted, or created) to this browser's other tabs; the tab that sent
it doesn't act on it (it already has what it saved), so a save doesn't fetch the story again. The
listener closes with the page.

What a hint refreshes: the story (with where it's used and its versions), the stories list,
Continue your work and search results, fetched again only if on screen, and the counts in Your
data for a save or a deletion (an archived story is still counted, so an archive doesn't ask). Pages that show a story's title (an
application, a kit) are marked stale and fetched when next opened, so one change doesn't set off a
burst of requests. A list keeps showing what it has while it's asked again; it isn't emptied first.

## On the story page

| Situation | What happens |
|---|---|
| Nothing unsaved, a newer version saved elsewhere | The page shows it: "Updated to version N, saved in another tab or on another device." |
| Unsaved changes, a newer version saved elsewhere | Your text stays. "This story was saved somewhere else (version N) since you opened it. Your changes are still here, not saved." **Compare with the saved version** opens the usual comparison (keep yours as the newest version, saved over that version knowingly, or use the saved one). Saving without comparing meets the same comparison (the server refuses a stale save). |
| Archived or unarchived elsewhere | Only the flag changes ("Archived in another tab or on another device. It's kept, and hidden from your list."); your text stays. Saving the text afterwards doesn't unarchive it (a save never sends the flag). |
| Deleted elsewhere (or no longer available to this account) | The editor stays with your text: "This story was deleted, or isn't available to this account any more. Your text below is still on this page and kept on this device; it isn't saved anywhere else." **Copy my text**, or **Save it as a new story** (a new story with a new address). "Save changes", archive, delete, versions and "Where it's used" are hidden or disabled, and a comparison that was open is withdrawn, so nothing is sent to the deleted story, its last copy isn't offered, and it is never recreated. |
| An older reply arriving after a newer save | Ignored: only a higher revision than the page's is acted on. "Saved as version N" stays true for the save it describes. |

Opening a deleted story's address still shows "not available" as before; the editor only stays
when it was already open.

Nothing here restarts judge or AI work, signs anyone in or out, or moves data between accounts.

## Other records (unchanged)

Notes, interview kits, reflections, whiteboard drafts, code reviews, work samples and offer
comparisons already compare a stale save with the saved version (Volume 8) when you save, and
show a newer saved version when the page is opened or its own query is asked again. They don't
yet listen for hints or refresh on focus.

## Tests

`src/test/integration/freshness.test.tsx` (back in the tab, or back online, having missed the
change: a clean page showing the newer version; a dirty page keeping its text, the comparison with the real saved version, keeping yours saved
over the version seen; an archive elsewhere changing only the flag and a later save not undoing it;
a deletion keeping the text, Save disabled, Copy, and Save as a new story creating a new one with
nothing sent to the old; a comparison open at the time withdrawn by a deletion; an older reply ignored; another tab's hint updating a clean list at once,
another account's and a malformed hint ignored; a clean search showing the new title, its old
result kept on screen until the new answer arrives; Your data's counts asked again for a deletion
and not for an archive; a save telling other tabs the id and revision and none of the text, and
the tab that saved not fetching its own story again). `src/test/render.test.tsx`: tests run with
the app's own query defaults, so a query that should refresh on focus has to ask for it. `e2e/freshness.spec.ts` (real API, three tabs of one account: the list updating
without focus, the dirty editor keeping its text and comparing, then a deletion in the other tab
leaving the text with a new story made from it and the old one not revived; axe in both themes).

## Limits

- Stories only for hints and focus refresh; the rest as above.
- No hints between devices (no server push): another device catches up on focus or reconnect.
- A browser without `BroadcastChannel` gets no hints; focus and reconnect still work.
