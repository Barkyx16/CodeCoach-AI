# Whiteboard practice

Practice explaining a design: sketch the parts of a system and how they connect, write down
assumptions, rough capacity numbers and tradeoffs, explain one decision in your own words, then
ask for feedback on what the design addresses. It's a small, purposeful canvas, not a drawing
tool, and the feedback never judges how the diagram looks.

## What's offered, and what isn't

- **System design prompts for careers that write code**, three to start: a URL shortener, an API
  rate limiter and a notification service. Each has a visible objective, a short brief and the
  points a good answer addresses.
- **Process maps for other careers aren't offered.** They'd need reviewed content first. The
  prompt list says so plainly for those careers, and the system-design prompts stay open to
  anyone curious; nothing claims to cover nursing, teaching or other professional domains.
- Prompts and the rubric are versioned in code (`app/whiteboard/__init__.py`), like Learn units.

## The diagram

A plain, bounded format (`codecoach-whiteboard`, version 1):

- **Components** (up to 40): an id, a name (60 characters), a kind (client, service, database,
  cache, queue, external system, other), a position on a 20-pixel grid and an optional group
  name (40 characters). Components sharing a group are drawn inside one dashed box.
- **Connections** (up to 80): from, to and a label (60 characters).
- **Notes**: requirements, assumptions, capacity estimates and tradeoffs (2,000 characters
  each).
- **No HTML, images or scripts.** Every string is plain text; control characters are removed;
  unknown fields are refused. Names are rendered as text, never as markup.

## Using it without a pointer

Everything on the canvas has an outline equivalent, and an assessed attempt can be completed
with the keyboard alone:

- Add a component (name and kind), rename it, change its kind or group, move it with Left /
  Right / Up / Down buttons (one grid step of 40 pixels each), and delete it.
- Add a connection by choosing **From** and **To** and typing what flows; relabel or delete it.
- **Undo** and **Redo** cover every change (deleting a component removes its connections in the
  same step, so one Undo brings both back). There's no confirmation dialog; Undo is the safety
  net.
- **The diagram in words** lists every component and connection with its id, for screen readers
  and as a plain summary. The canvas itself is one labelled image whose words are in the outline.
- Pointer users can also drag components on the canvas. Only a component captures touch, so a
  finger elsewhere on the canvas still scrolls the page.
- Zoom in, zoom out and **Fit to content** change only the view.

## Saving and recovery

- **Save draft** stores the diagram and explanation with a revision number. A save from a stale
  tab gets `409` and the page offers "Save mine as the newest" without losing anything.
- Unsaved changes are also kept on this device as you work. After a crash, a closed tab or a
  failed save, reopening the prompt offers **Restore them** or **Discard them**. Leaving with
  unsaved changes asks first.
- A failed save or a failed feedback request leaves the diagram exactly as it was.

## Feedback

Feedback is only given when asked, and only after you explain at least one decision in your own
words (15 words or more). A words-only answer with no diagram is accepted too.

The request sends a validated, bounded copy of the diagram. The feedback has separate parts:

1. **Checks of the diagram itself**: facts about the file, each with the ids it's about
   (connections pointing at a missing component, a component connected to itself, unnamed or
   unconnected components, duplicate ids, an empty diagram).
2. **What your design addresses**: each of the prompt's points, marked *Addressed* or *Not
   found*, with the exact evidence: which component, connection, note or the explanation
   mentions it. "Show on the diagram" highlights those components and connections.
3. **Your reasoning**: whether there are rough capacity numbers, and whether a choice is
   explained with what it costs or gives up.

It's built-in rules, not a reviewer and not an AI model: it finds whether your own words address
each point. It never says a design is correct, secure or ready for production, and it never
judges layout, colours or neatness.

## Attempts are frozen

Each attempt stores the diagram exactly as sent, a fingerprint of it, the explanation, the
prompt version, the rubric version and the feedback. Editing the draft afterwards never changes
an attempt; the page says "Your diagram has changed since this attempt" when what you see differs
from what was evaluated, and the draft API reports `differs_from_last_attempt`.

## Export and import

- **Export JSON…** shows a preview of exactly what the file will contain and its name
  (`codecoach-whiteboard-<prompt>.json`) before downloading. The explanation and feedback aren't
  in it. Image and PDF export aren't offered.
- **Import JSON…** reads a file of at most 200 KB and sends it to the server to be checked
  against the format first (`POST /api/v1/me/whiteboard/validate`, which saves nothing). A file
  with unknown fields, wrong ids, oversize text or too many items is refused and nothing on the
  page changes. An imported diagram is loaded as unsaved changes for you to check and save.

## Privacy

Drafts and attempts are owner-only (`404` for anyone else), in the data export (`whiteboard`)
and deleted with the account. There's no sharing of diagrams.

## Verified, and not

See the V2-06 entry in [RESUME_LIFTER.md](../RESUME_LIFTER.md) for the exact runs.

Not verified here: screen readers, Safari and Firefox, real touch screens (touch drag is
implemented but only exercised with a mouse in Chromium), and how the canvas reads in Windows
high-contrast mode (forced-colors styles exist but weren't checked on Windows).
