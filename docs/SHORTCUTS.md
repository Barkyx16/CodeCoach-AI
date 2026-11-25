# Your shortcuts (Volume 11, prompt 2)

The dashboard's **Your shortcuts** (`features/dashboard/ShortcutsCard.tsx`, on both the career and
the coding dashboard, after "Continue your work") keeps a few pages one click away. It sits
alongside the command palette (Ctrl+K), which finds any page by typing; shortcuts are the pages you
use often, always in view.

## Making a tool one click away

1. On the dashboard, **Edit shortcuts**.
2. **Add a shortcut**: choose a page (grouped as in the palette) and **Add**. It goes last.
3. **Move up** / **Move down** to put it where you want it; **Remove** to take one off.
4. **Done**. The links are there next time you open the dashboard.

Nothing else is set up: no widgets, no layout designer, no custom links.

## What can be a shortcut

The palette's own commands (`app/commands.ts`): the router's real pages with their real labels,
following the same career and server rules. Not offered: the dashboard itself, admin tools (even to
an admin; a home page isn't the place, and access is decided by the server anyway) and signed-out
pages. The practice library is a single shortcut whatever it's called for the career ("Coding
problems", "Interview questions").

- **Only opens a page.** A shortcut is a link: it doesn't submit, record, delete or spend AI budget,
  and the page it opens still asks before it does anything (and an unsaved-work warning on the page
  you're leaving still applies). "Write a new story" opens an empty story; nothing is saved until
  you save it.
- **Arranging changes nothing on the account.** Adding, moving, removing and resetting don't touch
  your career, plan, applications or practice history; no request is sent (tested in the browser).
- **A page the career doesn't offer** (say the whiteboard after changing from Software Engineer to
  Registered Nurse) stays in the list, shown as "Not part of Registered Nurse practice." and not as
  a link, until you remove it. It isn't offered to add.
- **A page the server can't fully serve** says so on the shortcut (for example "Code isn't run on
  this server: attempts are saved, not judged.") and still opens.

## Defaults

Practice library, Notes, Stories, Applications and My plan. **Reset to defaults** puts these back
and says so; it only changes this list.

## Where it's kept, and what

- **In this browser, for your account**: `codecoach.shortcuts.v1.<user id>` holds `{"v": 1, "ids":
  [...]}` and nothing else. Your other devices, and other accounts on this browser, have their own
  lists. It isn't synced to your account.
- **Page ids only**, from a fixed set: never a URL, a record's title, a token or anything typed. Ids
  are checked when read; an id the app doesn't offer (an old one, an admin tool, a stored URL, a
  repeat) is left out and counted ("2 saved shortcuts are no longer offered…"), and at most eight are
  kept. Something unreadable shows the defaults and says so. Only known ids are ever written.
- **No list stored means the defaults**: showing them stores nothing, and Reset removes the list.
- **When the browser won't store it** (private mode, full storage) the change still applies on the
  page and the dashboard says it lasts only until you leave the page; it never claims it was saved.
- **Another tab** of this browser changing the list updates this one.
- **Signing out keeps it**, like display settings: it names pages, not your work. "Your data" lists
  it among the device settings.
- **Not the same as pinned notes.** Pinning a note (Notes) is saved to your account and keeps that
  note at the top of your notebook; shortcuts are pages on the dashboard, kept in this browser.

## Accessibility

Every control is a button (keyboard and touch; at least 44 px tall on touch screens). After a move,
focus stays on the same item's button in its new place and the new position is announced ("Notes
moved to position 2 of 5."); at the top or bottom the button stays focusable and says "already
first/last" instead of disappearing. Removing moves focus to the next item. Done returns focus to
Edit shortcuts. Each button's name starts with its visible label ("Move up: Notes"). The list wraps
on a phone; no sideways scrolling, no icon-only targets.

## Tests

`src/features/dashboard/shortcuts.test.ts` (at most eight known ids, no repeats, unknown formats
unreadable, only known ids written, the career's own library, no excluded pages);
`src/test/integration/shortcuts.test.tsx` (defaults as real pages, opening one sends nothing and
Back comes home, add/move/remove by keyboard and pointer with focus and announcements, a reload,
Reset, invalid stored ids and unreadable storage, admin tools not offered, storage refusing, a page
the career doesn't offer, another tab, another account); `e2e/shortcuts.spec.ts` (real API: keyboard
arranging, a reload, open and Back, no requests sent, a career change, axe in dark and light) and
`e2e/shortcuts-mobile.spec.ts` (fits a phone, 44 px targets, taps to move and remove stick).

## Limits

- Per browser, not per account: a new device starts with the defaults.
- No dragging; the buttons do the moving.
- At most eight shortcuts; pages only, not individual records (use bookmarks, collections or
  pinned notes for those).
