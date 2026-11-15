# Practice packet (Volume 11, prompt 8)

A readable study sheet of material you choose: questions you bookmarked (with your latest answer
and its automated feedback if you want them), notes and stories, the improvements you accepted and
one interview's kit (Volume 13, prompt 7), in the order you choose. You
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
| An improvement you accepted | What you planned (its title, why, from the automated feedback when you accepted it, and its practice); your schedule for it (each week or the one-off date, and whether you marked it done); your notes on it | `[Your plan]`: "Accepted improvement, from your practice interview on 12 November 2026 (Registered Nurse interview); read 15 November 2026: weekly, 1 of 3 weeks marked done. A plan you made, not a measure of improvement." |
| One interview's kit | Its checklist (ticked or not; each accepted improvement on it by id, read now, with its weeks marked done) and its questions to ask (not the ones you excluded). Only if you choose them, one by one: the meeting link, the interviewers' names, your private notes | `[Yours]`: "Your interview-day kit for Panel interview (Ward nurse at Mercy General, 20 November 2026), revision 3; read 15 November 2026" |

Up to 20 items (so at most 20 improvements; the page offers the 20 most recent and says how many
more there are) and one kit. Each section says where it came from and when, as recorded, and for
an improvement or a kit the state it was read in. Nothing claims more: no scores beyond what the
coach recorded (and none for an answer too short to evaluate), no endorsements, no certification;
an improvement is a plan you made, never an achievement.

Improvements and kits are read from the same records as their pages (the plan page and the kit),
when the preview is made: mark a week done, or rename the improvement, and the next preview says
so. A file you already saved keeps what its preview showed.

## Never in a packet

- Applications, offer terms, recordings or audio, account details.
- A kit's meeting link, interviewers' names and private notes, unless you choose that part: the kit
  is in the packet without them, and the packet says which were left out ("The meeting link isn't
  included: choose “Meeting link” to add it.").
- From the question library, only what a question's page shows: the title, the prompt and the
  tips. Never the scoring rubric's internals, hidden tests, sealed evaluation cases or model
  instructions. Coding problems aren't offered.
- Email addresses and phone numbers in your own text are replaced with "[email address removed]"
  and "[phone number removed]" unless you tick "Keep email addresses and phone numbers in my own
  text". The preview says how many were removed.
- Anything you didn't choose. An empty choice is refused (422), never "everything".

## Exact preview

`GET /api/v1/me/packet/kits` lists the saved kits you can choose (with whether each has a meeting
link, interviewers or private notes, never what they are). `POST /api/v1/me/packet/preview`
assembles exactly the items and parts sent, in that order, owner
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
| This interview has no saved kit yet. | A kit you've never saved |
| A packet holds one interview's kit, so this one isn't included. | A second kit |

A deleted improvement, or another account's improvement or kit, is "Not found: it may have been
deleted." An improvement deleted since a kit chose it stays on the kit's checklist as "An
improvement that's no longer available", as the kit page shows it.

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

`tests/test_packet_plans.py` (an improvement's weeks marked done as the plan page reads them; a
rename read by the next preview; a kit's checklist and questions, its private parts only when chosen
and said otherwise; contact details removed from a kit; one kit; unsaved, deleted and another
account's improvements and kits). `src/test/integration/packetPlans.test.tsx` (both offered, private
parts sent only when chosen, one kit, at most 20 improvements, the saved file keeping its preview
after a rename). `e2e/packet-plans.spec.ts` (real API: weeks marked done read live, a synthetic secret
in a kit's notes and its meeting link left out of the preview and the file, no sideways scroll at
phone width). `tests/test_packet.py` (exact order, parts and labels, the rubric's internals absent, the same
choice giving the same fingerprint and an edit changing it; each unavailable reason; another
account's note and story not found; empty and malformed choices refused without content; contact
details removed or kept, markup and URLs left as text; the bounds; the rate limit).
`src/test/integration/packet.test.tsx` (what's sent, the preview's labels, the file matching the
preview, a change hiding Save until previewed again, unavailable choices named in both, a failure
with nothing to save). `e2e/packet.spec.ts` (real API: a bookmarked question with an answer and its
feedback, a note with contact details and markup, a story, reordered; the file matching the preview
and unaffected by an edit after previewing; previewing again picking it up; axe in both themes).

## Limits

- Questions you've bookmarked, notes (the 50 most recent), stories, accepted improvements (the 20
  most recent) and saved kits (the 50 most recent interviews). Reflections, coding problems and
  lessons aren't offered.
- PDF is the browser's print dialog ("Save as PDF"), not a file the server makes; the text file
  always works.
- Contact details are found by pattern (email addresses, phone-like digit runs); anything else
  personal in your own words stays as you wrote it.
