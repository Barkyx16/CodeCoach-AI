# Practice packet (Volume 11, prompt 8)

A readable study sheet of material you choose: questions you bookmarked (with your latest answer
and its automated feedback if you want them), notes and stories, in the order you choose. You
preview it, then save it as a text file or print it (or "Save as PDF" in the print dialog). It is
not an account backup (that's Your data → Export), a report, a certificate or a portfolio, and it
is never sent, emailed, published or attached to anything.

A synthetic example: [samples/practice-packet-sample.txt](samples/practice-packet-sample.txt).

## What you can put in

| Choice | Parts | Labelled |
|---|---|---|
| A question you bookmarked | The question and tips; your latest answer; the automated feedback on it | `[From the question library]` (with the question's version), `[Yours]` (with the date and the question version it answered), `[Automated feedback]` (coach, rubric version, date, "Not a grade from a person, and not a verification of anything", and the track's evaluation note) |
| A note | Note; reflection; the excerpt it quotes | `[Yours]` (revision, saved date); an excerpt is labelled as copied from its source when the note was made |
| A story | Situation, task, action, result, reflection, short and longer versions | `[Yours]` (revision, saved date) |

Up to 20 items. Each section says where it came from and when, as recorded. Nothing claims more:
no scores beyond what the coach recorded (and none for an answer too short to evaluate), no
endorsements, no certification.

## Never in a packet

- Meeting links, interview kits, applications, offer terms, recordings or audio, account details.
- From the question library, only what a question's page shows: the title, the prompt and the
  tips. Never the scoring rubric's internals, hidden tests, sealed evaluation cases or model
  instructions. Coding problems aren't offered.
- Email addresses and phone numbers in your own text are replaced with "[email address removed]"
  and "[phone number removed]" unless you tick "Keep email addresses and phone numbers in my own
  text". The preview says how many were removed.
- Anything you didn't choose. An empty choice is refused (422), never "everything".

## Exact preview

`POST /api/v1/me/packet/preview` assembles exactly the items and parts sent, in that order, owner
first item by item. The page shows it, and the text file and the printout are made **from that
preview** on your device: an edit made after previewing doesn't change the file. Change a choice
and the page hides "Save" until you preview again. Each preview has a fingerprint (in the preview
and the file) that changes when the content does.

A choice that can't be included is listed with its reason, in the preview and in the file, never
dropped silently:

| Reason | When |
|---|---|
| Not found: it may have been deleted. | A deleted note or story, or one that isn't yours (another account's id gets the same answer) |
| Not in the question library. | An unknown question or career |
| Retired from the library, so it isn't included. | A retired question |
| Already in the packet. | Chosen twice |
| Nothing to include from it with the parts chosen. | Only empty parts chosen |

A question you haven't answered says "You haven't answered this question, so there's no answer or
feedback to include." if you asked for those parts.

## Bounded

At most 20 items, 20,000 characters per section and 150,000 for the packet: past that, the text
ends with "[Shortened here: a packet holds a bounded amount of text.]" and the packet says some
text was shortened. 30 previews a minute per account (429 after). The server holds nothing: no file,
no job, no link, so there's nothing to guess, fetch or expire, and nothing to clean up.

## Safe text

Text is plain text everywhere: the preview renders it as text (`<script>`, `<img>` and Markdown
images are shown as characters, never run or fetched), and the file is a `.txt`. Long code wraps in
the preview and the printout (pre-wrapped, breaking long lines).

## Tests

`tests/test_packet.py` (exact order, parts and labels, the rubric's internals absent, the same
choice giving the same fingerprint and an edit changing it; each unavailable reason; another
account's note and story not found; empty and malformed choices refused without content; contact
details removed or kept, markup and URLs left as text; the bounds; the rate limit).
`src/test/integration/packet.test.tsx` (what's sent, the preview's labels, the file matching the
preview, a change hiding Save until previewed again, unavailable choices named in both, a failure
with nothing to save). `e2e/packet.spec.ts` (real API: a bookmarked question with an answer and its
feedback, a note with contact details and markup, a story, reordered; the file matching the preview
and unaffected by an edit after previewing; previewing again picking it up; axe in both themes).

## Limits

- Questions you've bookmarked, notes (the 50 most recent) and stories. Kits, reflections, coding
  problems and lessons aren't offered.
- PDF is the browser's print dialog ("Save as PDF"), not a file the server makes; the text file
  always works.
- Contact details are found by pattern (email addresses, phone-like digit runs); anything else
  personal in your own words stays as you wrote it.
