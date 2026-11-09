# Back, deep links and returning to the right place (Volume 7, prompt 7)

A learner who opens something from a list, a plan or Settings comes back to where they were: the
same filters, rows, scroll position and focused item. A page opened directly (a bookmark, a new
tab, a copied link) shows its permitted view and a useful way on, never a "Back" that leads
nowhere or to another career.

## Before and after

| Journey | Before | After |
|---|---|---|
| Interview results opened from History, then an item clicked | "Back to History" vanished on the first click (choosing an item replaced the URL without the page's state) | it stays; opened directly, the page offers **All your interviews** (`/history?type=interview`) |
| Practice queue → next item → "Back to the queue" | went to the *previous item* (the link stepped back in history) | opens the queue; finishing lands on the queue, whose own Back leads to the collection |
| A nurse's breadcrumb "Registered Nurse questions" while signed in as another career | opened the signed-in career's library (`?career=` was ignored when signed in) | a known `?career=` wins; an unknown one falls back to the learner's own |
| Coding list, "View more", scrolled, a problem opened, then back | five rows, top of the page, focus at the top | the same rows (`?shown=` in the URL, capped at 200), the same scroll, focus on that problem |
| A problem's breadcrumb | "All problems" → `/problems`, which shows a nurse the nursing library | "Coding problems" → `/problems?career=software-engineer`; opened from the list, "Back to coding problems" first |
| Landing page, signed in as a nurse | "Open a problem" → a Java problem | "Practise your questions" → their questions; coding careers still open a problem |
| Learn page with no lessons for a career | "Practice questions instead" → no career | that career's questions |
| History, stories, applications: open an item, come back | filters kept (URL), but scroll lost (History, stories) and the item page's Back lost the filters (applications, stories) | scroll and focus come back; rows carry the list's address |
| A new note or story, first save | "Back to your notebook" became the unfiltered notebook (the replace dropped the page's state) | the state is kept |
| A new story saved while this browser can't keep a local copy | asked "changes that aren't saved yet" after saving; cancelling then made a duplicate on the next Save | no question: the save is done |
| Goals opened from the plan | Save and Cancel went to the dashboard | back to the plan |
| Settings → confirm email | two copies of Settings in history, so Back seemed to do nothing | the confirmation goes back to Settings |

## What survives what

| State | Where it lives | Survives reload | Survives a copied link |
|---|---|---|---|
| List filters, search, sort, tab, page; coding list's "View more" (`shown`) | the URL query | yes | yes |
| Career being browsed (`?career=`) | the URL query | yes | yes; access is still checked: it only chooses a public library |
| "Back to …" (where a page was opened from) | the router's history state | yes, in the same tab (browsers keep it) | no: a copied link shows the page's fallback instead |
| Scroll position and the item to refocus | this tab's sessionStorage, per history entry | yes, in the same tab | no |
| Where the learner was going before signing in or confirming an email | router state; for a link opened in a new tab, this browser's storage, per account (see VERIFICATION_JOURNEY.md) | yes | no |

Private text (answers, notes, drafts) is never put in a URL.

## Rules the code follows

- **One way back.** `BackLink` steps back in history when the page that linked here is the previous
  entry. That restores the list exactly. A sender that moves forward through several pages (the
  queue) marks its state `backVia: "link"`, and the link then opens the list itself.
- **No dead ends.** A page opened directly shows a fallback where one is useful, or nothing. It never
  calls `history.back()`, which could leave the app.
- **Validated targets.** Return targets from router state or storage go through `appPath` or
  `safeReturnPath`. Both accept only in-app paths: not `//host`, `/\host`, control characters, or the
  sign-in pages (a loop). The destination checks access as usual: a target is never permission.
- **Leaving asks only when it would lose something.** Pages that ask:
  - a written scenario response that hasn't been sent;
  - a note neither saved nor kept in this browser, or in a conflict;
  - the existing pages (answers, stories, kits, reflections, diagrams) on their own rules;
  - goals, a new target job, the job posting editor, and an application's details (Volume 9,
    prompt 1), below.

  A navigation that follows a successful save doesn't ask (`allowLeaveAfterSave`): one move,
  within a second, and only the one that save makes. A failed save allows nothing.

  The question names what would be discarded when the page says ("Your changes to the job posting
  aren't saved, and leaving would discard them. Leave anyway? (Cancel stays here with everything as
  it is.)"). It's the browser's own confirm, so the buttons are its OK and Cancel. Cancel keeps every
  field as it was. Reload and closing the tab get the browser's generic warning instead: browsers
  don't show custom text there, and a phone that ends the app's process may show nothing at all.

### The forms added in Volume 9, prompt 1

| Form | Unsaved means | After a successful save | Typed while the save was on its way |
|---|---|---|---|
| Goals (`/plan/goals`) | the form differs from what was loaded or last saved; typing and putting it back isn't a change | goes back where the goals were opened from, without asking | stays on the page: "Saved what you had when you pressed Save. You changed more since: save again to keep those changes." Leaving asks |
| New target job (`/targets`, Add a target role) | anything typed in its fields (the job chosen by default isn't typing) | opens the new target without asking | — (creating isn't repeated) |
| The job posting editor (`/targets/:id`, The posting, Edit) | the open editor differs from the posting as saved | the editor closes | the editor stays open with the newer text; leaving asks. Cancel discards on purpose and asks nothing |
| An application's details (`/applications/:id`) | any detail differs from what was loaded or last accepted, or the private notes differ from the saved notes | "Saved."; leaving doesn't ask | the newer text stays and still counts as unsaved |

### Unfinished forms kept in this browser (Volume 9, prompt 2)

The same four forms also keep a copy of what's typed in this browser (`hooks/useFormDraft.ts`),
so a reload, a closed tab or a crash of the page doesn't lose it:

- **What's stored:** only the form's own fields, its base (the posting's or application's
  `updated_at` when the copy was made; goals and new targets have none), the time, a schema
  version and a per-page id. Under `form-draft:<account>:<form>:<target>`, at most 60,000
  characters, written a moment after typing stops, removed when the form matches the saved
  values again. Never in a URL, a cache, or a support report.
- **Offered, never applied:** "You have unsaved changes to your goals from 9 Nov, 04:12, kept on
  this device. They aren't saved to your account." with **Restore them** and **Discard them**.
  Nothing replaces the loaded values until one is pressed, and nothing is written over the copy
  meanwhile. Discard removes that copy only. When the posting or application was saved again
  after the copy was made, the offer says so; restoring puts the copy in the form, and saving it
  replaces what's saved (these records are last write wins, PERSISTENCE.md).
- **Wording:** "Unsaved changes, kept on this device." Never "saved". When the browser refuses the
  copy (private mode, full): "Unsaved changes, and this browser can't keep a copy: save them, or
  copy your work", with **Copy your work**.
- **Bounds and identity:** a copy older than 14 days, malformed, or of another format is ignored
  and removed. Another account never sees it: copies are per account, and they're deleted with
  that account's other local work when it signs out here (a session that ends by itself keeps
  them, RECOVERY.md). Another tab's newer copy is never overwritten: this page then says its
  changes are on this page only.
- **After a save:** the copy goes only if nothing was typed since; newer text keeps its copy.

Found on the way: two places compared with the form as it was when Save was pressed instead of
as it is when the reply arrives, so text typed while saving lost its browser copy until the next
keystroke. One was the application's private notes (Volume 8, prompt 5); both now read the
current form. And the notes' browser copy (`codecoach.appnotes.v1.…`) wasn't deleted at sign-out:
it is now, and the test that scans the source for private keys now looks for "notes" too.

## Tests

- `frontend/src/test/integration/returnPaths.test.tsx` (12):
  - results keep "Back to History" after an item is chosen, and offer All your interviews when
    opened directly;
  - a career link opens that career's library when signed in; an unknown one falls back;
  - the landing page for a nurse;
  - "View more" in the URL, its rows' way back, and a bounded `shown`;
  - an unsent scenario response asks;
  - a story saved without local storage doesn't ask;
  - goals return to the plan;
  - confirming from Settings goes back;
  - focus returns to the item.
- `explore.test.tsx`: "Back to the queue" opens the queue.
- `formDrafts.test.tsx` (9): type, reload, the offer, restore, save; discard; malformed, older-format
  and expired copies; a refused write with Copy your work; another account; another tab's newer
  copy; a posting saved again since; details and notes typed while saving keep their copy.
  6 negative controls, each caught (one test strengthened after its control was missed).
- `leaveWarnings.test.tsx` (8): for goals, a new target job, the posting editor and an
  application's details: an in-app exit asks and names what would be discarded; staying keeps
  every field; putting a field back asks nothing; a successful save moves on without asking; a
  failed save still asks; typing during a save stays and asks; a second edit after saving asks
  again; Cancel discards without asking; browser Back asks too. 4 negative controls, each caught.
- Negative control: with the source as it was (366449b), 11 of these checks fail.
- Browser, `frontend/e2e/navigation.spec.ts`, against the real API:
  - a medium-difficulty coding list, View more, scrolled, a problem opened from row 13;
  - back by the breadcrumb, with the same rows, scroll and focus;
  - browser Forward and Back;
  - the same problem opened in a new tab offers the coding library and no "Back to …".
- The existing `explore.spec.ts` and `progress.spec.ts` journeys still pass.

## Limits

- **Back needs the tab's history.** "Back to …" relies on it; a copied link or a new tab gets the
  fallback, not the original list's scroll position.
- **Focus is restored only when the item is still in the list.** If it was removed or filtered out
  since, focus starts at the top of the page.
- **Leave warnings are not everywhere.** Inventoried here: the forms listed above ask. Still
  without one: the application message composer. The one-line form for adding a requirement to a
  target doesn't ask; what it would lose is one line.
- **An unexplained hang, seen once.** One run of the related browser specs hung two API reads for
  63 s, and then the next navigation was aborted. It didn't reproduce in four more runs of that test
  (two alone, two with the same specs), and the server logged nothing. It's recorded here, not explained.
