# What's new (Volume 11, prompt 10)

A small page, **What's new** (`/whats-new`, in the header beside Help and in Go to…), listing the
changes this version of CodeCoach ships, written for the learner: what got better, where to find
it, what it doesn't do yet, and a link to the page when this learner can use it there. It is not a
roadmap, a tour or a notification: nothing opens by itself, and nothing is sent or emailed.

## What's shown, and when

| | |
|---|---|
| The build's release | `frontend/release.json` `release`, read by `vite.config.ts` into the bundle at build time. Missing or not a whole number from 1: the page lists nothing. |
| The entries | `frontend/src/features/whatsnew/releases.ts`. Each has a `release`. |
| Shown | A well-formed entry whose `release` is at most the build's. An entry for a later release (written ahead, or planned) never shows on a build that doesn't ship it. |
| Malformed | An entry with an unknown page, a URL or a path instead of a page id, missing or overlong text (400 characters), an odd field value, or a repeated id isn't shown. A unit test fails if any real entry is malformed. |

Each entry opens a page through `opens`, a command id from the command palette (`app/commands.ts`),
so the link is one of the router's real pages with the palette's own rules:

| Learner | What the entry shows |
|---|---|
| Can use the page | **Open** *page name* |
| A coding-only change (`audience: "coding"`), a career without coding practice | "For careers with coding practice: not part of *career* practice." No link. |
| `needs: "code-runner"`, on a server that doesn't run code | the link, and "Code isn't run on this server right now: attempts are saved, not judged." |
| Signed out, a page that needs an account | "Sign in to use it." No link. |
| A page the server can't serve (the palette's `unavailable`) | the palette's reason. No link. |

The page and the route guards still decide access: an entry's link only goes where the router
already goes.

## New, and seen

- Per account, in this browser: `codecoach.whatsnew.v1.<user id>` holds `{v: 1, seen: <release>}`,
  the newest release this account has looked at here, and nothing else (no per-entry reading, no
  times). Listed in Your data under "Also on this device". Kept when you sign out; another account
  signing in on the same browser has its own.
- Nothing stored yet: this release's changes are new and the earlier ones aren't.
- New for this learner: entries in a later release than the one seen that their career can use
  (a coding-only change isn't counted for a career without coding practice).
- The header's **What's new** link shows a small dot when there's something new, and its name says
  how many ("What's new, 9 new"). It doesn't move, open, take focus, announce itself or open the
  microphone, so an interview or an answer in progress carries on. The careers list is asked for
  only when a coding-only change is among the unseen ones.
- Opening the page marks everything up to this release as seen (the dot goes); what was new when it
  opened stays marked **New** for that visit. A value written by a newer build isn't lowered.
- Storage that refuses: no dot, nothing marked new, and the page says the browser isn't letting it
  keep track. Everything is still listed.
- Signed out: the list, with "Sign in to see which of these are new to you and to open them."

## Adding a truthful entry

1. Only for a change that's in the build and works there: check it in the app, not from a plan or a
   prompt. Never for a capability because its code was proposed.
2. Add it to `ENTRIES` with the **next** release number (`release.json` + 1) if this change starts
   a release, or the current one if the release hasn't been built and published yet.
3. Write for the learner: the concrete improvement, where to find it (the words on screen), and what
   it doesn't do yet. No test counts, migrations, job names, hostnames, account data or screenshots.
4. `opens`: the palette command for the page. If the page has no command, add one there first (the
   palette and shortcuts will offer it too). Set `audience: "coding"` for coding-only changes and
   `needs: "code-runner"` when the page runs code.
5. Raise `release.json` in the change that ships the release (and add the release's title to
   `RELEASES`).
6. `npx vitest run src/features/whatsnew src/test/integration/whatsNew*.test.tsx`: the content test
   checks every entry is well formed and opens a real route.

Plain text only. There is no markup, Markdown or link syntax: anything like it is shown as typed.

## Drafts (not in the app)

Drafts live here, never in `releases.ts`, until the change ships:

- *(none yet)*

## Tests

`src/features/whatsnew/whatsNew.test.ts` (every real entry well formed, each once, each release
named, each opening a route the router has for each career; this build's release is release.json's;
later releases and a build without a release show nothing; malformed entries dropped; what an entry
opens for a coding and a non-coding career, a server that doesn't run code and a visitor; the seen
value per account, malformed values, storage that refuses).
`src/test/integration/whatsNew.test.tsx` (a fresh account, already seen, a newer release, a value
from a newer build, the careers list asked for only when needed, coding-only changes by career with
the server's note, storage that refuses, another account signing in on the same browser, an answer
in progress not interrupted and still there after a look, a visitor).
`src/test/integration/whatsNewContent.test.tsx` (markup shown as text and never run; entries
pointing at a script, a URL or a later release not shown). `e2e/whats-new.spec.ts` (real app: a
nurse mid-answer, the dot, What's new opened from the keyboard, a coding-only change without a
link, a page opened from an entry, back to the answer still there, the dot gone; axe in both themes).

## Limits

- Per browser: another device shows its own New marks.
- On a phone the link is inside Menu (and in Go to…); the Menu button itself shows no dot.
- On a narrow desktop window a long account name in the header is shortened sooner, to make room for the link.
- Two releases so far, both in this build; nothing has been published anywhere yet, so "Earlier"
  means earlier in this version's history, not a version anyone necessarily had.
- The build's release is set by hand in release.json; nothing checks it against a deployment.
