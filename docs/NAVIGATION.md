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
| Career being browsed (`?career=`) | the URL query | yes | yes; access is still checked: it only chooses public content |
| The learner's own career (plan, goals, dashboard, analytics) | the account (changed only in Settings) | yes | no: a link never changes it |
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

### Field errors (Volume 9, prompt 3)

When the server refuses a save of these four forms with a validation error (422
`validation_error`), each error is shown beside the field it names (`hooks/useFieldErrors.ts`,
`components/FieldErrors.tsx`):

- **Beside the field:** the control gets `aria-invalid` and the message's id in
  `aria-describedby`; the message is outside the label, so it's the control's description, not
  part of its name. A group of choices (experience, formats, focus areas, confidence) carries its
  message after its legend. Text says what's wrong and what to do: "Too long: use at most 2,000
  characters.", "Not a date: choose a day, or leave it empty.", "This is required: fill it in.",
  or the server's own sentence for a rule only it knows ("Links must start with https:// or
  http://"). Colour isn't the only sign.
- **Summary on the longer forms:** goals, a new target job and the posting editor show "This
  wasn't saved. Check 2 fields:" with a link to each field (a link to a group of choices focuses
  its first choice; one inside a closed section opens it). An error the server didn't tie to one
  of the form's fields is listed there too. The application's details, a short form, put focus in
  the first field in error instead, with untied errors in one line under the form.
- **Focus:** the summary (or the first field) takes focus only while the form still holds exactly
  what was sent. A refusal that arrives after the learner carried on typing doesn't pull them out
  of their field.
- **Only while it's still true:** an error is shown only while its field holds the value that was
  refused. Edit the field and its error and its summary line go; the next save checks the new
  value. Nothing typed is lost or replaced, before or during the save, and a retry sends what the
  form holds now, never the refused copy.
- **Not a field error:** offline, not allowed, a conflict, the server unavailable: shown as before
  (one message, the recovery choices of RECOVERY.md), with no field marked. The vaguer "Request
  validation failed" isn't shown next to field errors. The form stays unsaved: its browser copy
  and its leave warning are unchanged.

### Browsing a career, and the learner's own career (Volume 9, prompt 4)

Two different things, kept apart:

- **The career being browsed** decides what a public page shows: the library (questions or coding
  problems), lessons, scenarios and the mock interview setup. It's `?career=` in the URL when it
  names a known career, for anyone, signed in or not; otherwise the learner's own career;
  otherwise Software Engineer. One resolver reads it (`useBrowseCareer`,
  `features/careers/practiceTrack.ts`): trimmed and lower-cased (`?career=Barista` is barista),
  and anything that can't be a career slug (`../admin`, 65 characters) is treated as unknown. An
  unknown or removed career falls back to the learner's own and says so in one line ("There's no
  career called “not-a-job” here, so these are Registered Nurse interview questions."); nothing is
  requested from the server for it. The parameter only chooses public content: it gives no access
  to anyone's records, and the server checks access as before.
- **The learner's own career** is what their plan, goals, dashboard and analytics follow. It
  changes only in Settings (Career, Save career), which then updates the pages that depend on it.
  Opening a link, choosing a career in the library, copying a URL or pressing Back never changes
  it. Until this prompt, choosing a career in the library's selector saved it to the profile;
  that selector ("Show practice for") now only browses (the URL changes; choosing your own career
  goes back to your own library).

When a signed-in learner is shown another career, one line under the page's heading says so:
"Viewing Software Engineer coding problems. Your plan and progress follow your own career,
Registered Nurse. Back to Registered Nurse interview questions · Change my career". The mock
interview pages add what a round started there is saved as ("…saved to your history as a
Registered Nurse interview."). Nothing is shown on the learner's own career, and nothing for a
signed-out visitor, whose page heading already names the career.

Links within a browse context keep it: the library's coding/questions switch, the coding library's
"Try a mock interview", the lessons' and interview page's "branching scenario", the interview
page's "Browse all … questions", an empty scenarios list's "Try a mock interview". The breadcrumbs
fixed earlier (a question's "Registered Nurse questions", a problem's "Coding problems") are
unchanged. Personal pages (History, Analytics, Notes) have their own `career` filter over the
learner's own records; it isn't a browse context.

### Links that lead nowhere (Volume 9, prompt 5)

A copied link or bookmark opened directly uses the page's normal way back (its fallback); that
isn't a broken link. When the record itself can't be shown, the page says so calmly: a short
heading, one sentence, and a few working destinations (`components/Unavailable.tsx`;
`isGone` in `lib/errors.ts` decides).

| What the server said | What the learner sees | Can it be told apart safely? |
|---|---|---|
| A private record (note, application, story, interview, its kit or reflection, a retry, a submission, saved feedback, a scenario attempt): 404, or 403 | "This note isn't available. It may have been deleted, the link may be mistyped, or it may belong to a different account. Nothing was changed." The learner's own list of that kind (Your notebook, Your applications, All your interviews…) and the dashboard. No Try again | no, on purpose: the server answers 404 for a deleted record, one that never existed and another account's alike, and the page uses the same words for all three (a 403 too). No id, title or server wording is shown |
| Public content removed from the library (a question, coding problem, scenario, lesson): 404 | "This question isn't available", with that career's questions; a problem leads to coding problems (`/problems?career=software-engineer`, coding even for a nurse); a scenario or lesson to its library, saying a lesson has no direct replacement and a scenario's attempts stay in history | yes: public content isn't private |
| A retired question (still in the library, marked retired) | the question itself, readable, with why it was retired; it isn't graded any more; past answers keep their recorded version and scores; the breadcrumb leads to its career's questions | yes |
| A scenario attempt whose scenario changed or was retired | the attempt, with its recorded scenario and debrief, marked retired | yes |
| Offline, busy, a server error | the page's error with Try again, which loads the record when the server answers; never "isn't available" | – |
| Signed out (or the session ended) | sign in first, back to the same link afterwards, where access is checked again for that account: a different account sees the generic words above, not a loop | – |

Examples. A bookmarked interview that's no longer there: "This interview isn't available", with
All your interviews (History, interviews only) and Dashboard. A retired nursing question: the
question, "This question is retired, so it isn't graded any more", the reason, past answers as
they were, and the breadcrumb "Registered Nurse questions".

### Coming back to a list that changed (Volume 9, prompt 6)

`hooks/useScrollMemory.ts` puts a list back when the learner returns to it with Back/Forward, a
breadcrumb that goes back, or a reload. It restores by the item, not by pixels:

- **The item that was opened** is remembered with its neighbours and where it sat on screen. On
  return, once the list's fresh data has arrived (not the cached copy shown while it refetches),
  it's found again by its link and put where it was, with keyboard focus (no activation, no
  animated scroll). Notes added above it or a new order don't land the learner on another item.
- **Gone** (deleted, filtered out, moved to a page that isn't loaded): the nearest neighbour still
  shown (the next one, else the previous one) gets focus at that place, and a screen reader hears
  "The item you opened isn't in this list any more." With no neighbour either (an empty list),
  focus goes to the page's main region at the remembered position, with the same announcement.
  A hidden row is never focused; nothing pretends the item still exists.
- **Once, and only if wanted:** a return is restored once. If the learner scrolls, presses a
  navigation key or clicks while the list is still loading, they've taken over and nothing moves.
  Later background refetches, late layout and window focus never snap back.
- **New contexts start at the top:** following a link, changing a filter or search (a new history
  entry), and opening a page directly (a link, a bookmark, a typed address). The router gives a
  document's first entry the same key every time, so `lib/documentEntry.ts` tells the first page
  of a freshly opened document (top) from a return to it or a reload (restored).
- **Per tab, per entry, per account:** positions live in this tab's sessionStorage, per history
  entry; a copied URL carries only the public filters. Signing out here clears them
  (`clearListMemory`), so the next account's Back starts at the top.

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
- `listRestore.test.tsx` (5): the opened note focused again after one was added; a deleted one's
  neighbour focused, with the announcement, and the note not shown; an emptied list focuses the
  main region; scrolling during the reload leaves the page alone; signing out clears this tab's list
  memory and nothing else. `returnPaths.test.tsx`: the focus test stubs layout (hidden rows aren't
  focused). Browser, `e2e/list-restore.spec.ts`, real API, 30 synthetic notes: three added above the
  opened one (same note, same place within 40 px, focused); a background refetch after the
  learner scrolled away doesn't pull them back; Forward then Back restores again; the opened note
  deleted (its neighbour focused, announced); scrolling while the reload is held (left alone); a
  direct visit at the top. `navigation.spec.ts` (the filtered coding list) unchanged and passing.
  7 negative controls, each caught (one rerun with both of its checks removed: the hook checks a
  takeover twice).
- `deadLinks.test.tsx` (7): a bookmarked interview that isn't there (generic words, All your
  interviews, Dashboard, no retry, no id, no server wording); deleted, never there, another
  account's and a 403 read exactly the same; each kind's own list (applications, stories,
  reflections); a temporary failure keeps Try again, which loads it; a removed scenario and lesson
  lead to their library; a retired question stays readable and leads to its career's questions;
  a signed-out visitor signs in and the link is rechecked, with no loop. Updated to the new
  behaviour: notes, kit, workspace and learner-journey tests. 4 negative controls, each caught.
- Browser, `e2e/dead-links.spec.ts`, real API, fresh browser contexts: another account's note and a
  mistyped id read the same and show nothing of the owner's; a signed-out visitor is sent to sign
  in; a bookmarked interview leads to All your interviews; a busy read keeps Try again, which then
  loads; a removed scenario, lesson and problem lead to their libraries. The stranger checks in
  applications, kit, notes, persistence and stories now expect the generic heading.
- `browseCareer.test.tsx` (8): the parameter read the same way (case, spaces, malformed); a
  nurse browsing coding (the line, Change my career, the switch and interview links keeping the
  career, back to their own questions, nothing saved); choosing careers in the library (URL only,
  never the profile or the goals); unknown, differently cased and malformed values; signed out
  (a copied link, an unknown value); lessons for another career and an unknown one (no request
  for it); a mock interview for another career; a deliberate change in Settings. `careers.test.tsx`:
  choosing a job in the library no longer saves it. 6 negative controls, each caught.
- `fieldErrors.test.tsx` (8): the wording of each common refusal and the server's own sentence;
  errors tied to the form's fields, the first per field, the rest in the summary; a refused goals
  save (errors beside two fields, linked by `aria-describedby`, the summary focused, the field's
  name without the error, nothing lost, still unsaved and kept), a summary link by keyboard,
  editing a field clears its error, the retry sends the edited value; a link to a group of choices
  focuses its first choice; a new target job's refusal arriving after the title was edited again
  (no old error on the title, focus stays, the other field's error shown, both edits kept); a 403
  and a dropped connection mark no field; the posting editor stays open with its text and a
  focused summary; an application's link that only the server refuses (`ftp://`), corrected and
  saved. 6 negative controls, each caught.
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
- **Restoration is checked on the lists named below.** The notebook (in the browser, with records
  added, deleted, and scrolled during the reload) and the coding list (navigation.spec.ts); the
  same hook serves History, stories, applications and the question library, which share the
  behaviour but weren't driven through every changed-data case in a browser. An item moved to a
  page that isn't loaded counts as gone. Stale browser state from before this change (an older
  memory entry) is read as "just the link".
- **Leave warnings are not everywhere.** Inventoried here: the forms listed above ask. Still
  without one: the application message composer. The one-line form for adding a requirement to a
  target doesn't ask; what it would lose is one line.
- **Field errors are on these four forms.** The account forms (sign in, create account, password
  reset, Settings) keep their older helper (`features/auth/fieldErrors.ts`): errors beside their
  fields in the server's wording, without a summary or the "only while the field holds the refused
  value" rule. Other forms (stories, the application's events and messages) still show one
  message for a refused save. Messages are in English, and a
  rule the app hasn't worded is shown in the server's own words, made readable.
- **The browser checks some values first.** Required fields, lengths, link and date formats stop
  a save before it's sent, with the browser's own message; field errors cover what only the
  server checks, and what reaches it anyway.
- **The browse line is on the public pages listed.** A single question or problem page names its
  career in its heading and breadcrumb instead. Drills, the plan and Today follow the learner's
  own career only and take no `?career=`.
- **An unexplained hang, seen once.** One run of the related browser specs hung two API reads for
  63 s, and then the next navigation was aborted. It didn't reproduce in four more runs of that test
  (two alone, two with the same specs), and the server logged nothing. It's recorded here, not explained.
