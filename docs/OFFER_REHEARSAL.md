# Rehearse an offer conversation

Volume 10, prompt 8. A private rehearsal of the conversation after a job offer, in three parts:
**clarify the terms**, **make a reasoned request**, **respond to a counteroffer**. The offer and
the other person are fictional and labelled so. Nothing is sent to anyone, no employer is
contacted, and no application, stage or real offer changes.

## What it helps practise, and what it can't predict

It helps with how you say it: asking what an offer leaves unclear before negotiating, naming what
you want and why, keeping to facts you can back up, and answering a counteroffer clearly, which
includes asking for time or declining rather than only pushing a number up.

It can't predict what a real employer would offer, agree to or think of you. The counterpart is a
script, so a favourable reply is not evidence of anything. It gives no salary benchmarks, tax
calculations or legal conclusions.

## Where it is

- `/offers` (signed in): the cases and your rehearsals. Also reachable from the dashboard's "More ways to practice", the
  command palette ("Rehearse an offer conversation") and Help.
- `/offers/<case>`: the fact card and optional goals; `/offers/rehearsals/<id>`: the rehearsal.

## The fact card (`backend/app/offers/__init__.py`)

| Field | Meaning |
|---|---|
| `role`, `employer`, `counterpart` | fictional, each labelled "(fictional)" |
| `currency`, `hours_per_week` | the unit of every amount; hours only when the card states them |
| `terms` | label, aliases, `value` as the card states it, or **none: unknown stays unknown**; an `amount` and `unit` for arithmetic; the counterpart's authored reply to a request about it |
| `counter` | the counteroffer the last part brings (fictional), the term it changes and its amount |
| `review_status` | "its numbers aren't market rates, an employer's budget or what anyone is entitled to" |

Two cases: a salaried support analyst (GBP per year; bonus and training budget unknown) and an
hourly warehouse team lead (USD per hour at a stated 40 hours; parking and boots allowance
unknown). `validate-content` checks every card: unique terms, at least one unknown, a counteroffer
on a stated amount, aliases in the normalised form messages are matched in.

**Your goals** (up to three, optional) are what you write before starting. They're kept apart from
the card, shown back in the debrief, and used for nothing else. This slice doesn't take real offer
terms: the counterpart could only be grounded in a card it knows.

## The counterpart (`backend/app/offers/talk.py`): authored, never AI

The page shows the mode that ran: **Authored responses (no AI)**. There's no AI role-play here, so
an unavailable or over-budget AI coach changes nothing and no provider budget is used.

- **Clarify:** a term you ask about gets the card's own words ("Base salary: £31,000 per year."); an
  unknown term gets "That isn't set out in the offer you have. I don't want to guess, so I'll check
  and confirm it in writing." A stated amount said differently gets "Just to check, the offer says…".
- **Request:** the authored reply for that term, which agrees to nothing ("I can't agree a different
  salary on this call…"). A message about money is matched to the pay term even when it doesn't
  name it; with no term, it asks what you'd like to change and why.
- **Respond:** the card's counteroffer, then a reply to whether you accept, ask for time (it asks by
  when if you don't say), decline, or counter. Accepting reminds you to get real terms in writing.
- Pressure ("or I walk") gets a calm "I understand this matters to you", and claims the card can't
  back ("another offer", "market rate") get "I can only go on what's in this offer". Neither is
  rewarded. Every number the counterpart says is on the card (a test checks this).

## How it runs (`backend/app/services/offers.py`)

- One row per rehearsal (`offer_rehearsals`, migration `f2c8a6d4b913`): a snapshot of the card, your
  goals, the phase, every turn (who, which part, the text, typed or spoken) and the debrief.
- The server owns the conversation. A turn carries the last turn the page saw (`after_seq`) and a
  request key: a resend after a lost reply returns the rehearsal unchanged, the same key with other
  text is refused, and a turn from an older tab is refused (`rehearsal_advanced`) rather than
  talking over the newer one. Three turns per part (`phase_full`); moving on is idempotent.
- Starting again resumes an unfinished rehearsal of the same case. **Stop and see the debrief** works
  at any point. **Try a different approach** starts a new rehearsal naming the finished one; the
  first is never changed.
- The answer box is the interviews' `VoiceComposer`: always typeable; the microphone starts only on
  a click, never on resume, and stops when the turn is sent or the page is left. Spoken turns are
  recorded as spoken. Unsent text stays on this device per part
  (`offer-rehearsal-draft:<account>:<rehearsal>:<part>`, cleared at sign-out).

## The debrief

Kept in four clearly separate parts:

1. **The request you made**: quoted, with arithmetic only on amounts the card states, in their own
   unit (difference and percentage; per week only when the card states the hours). The scripted
   counteroffer's own difference is shown beside it. Amounts are before tax; nothing is annualised,
   taxed or judged legally.
2. **From the card (fictional)**: the facts you used, and every unknown term, marked as asked about
   or not, to get in writing.
3. **Things the card doesn't support**: a stated amount said differently, or a fact the card doesn't
   have.
4. **Coaching (qualitative)**: whether what you said matches the card, a clear request, a reason for
   it, questions about what the offer leaves open, and a clear answer to the counteroffer (declining
   or asking for time count fully). Then **one thing to try next**, the first of those not done.

The same rules read typed and dictated text after the same normalisation the interview rubric
uses (lowercase, apostrophes and filler sounds out); a test sends one conversation typed and the
same one as dictation and gets the same results. Tone, accent and personality aren't judged.

## Ownership and data

Owner-only, under PostgreSQL row-level security (listed in `rls.ADDED_TABLES`); another account
gets 404, including as the rehearsal a different approach follows. In the export as
`offer_rehearsals` (request keys left out), deleted with the account, not restored from backups.
Text is shown as text; control characters are removed.

## Limits

- Fixed keyword and number rules. A request phrased in a way they don't recognise reads as not
  naming a term, and a reason is any "because / since / given…", not a judgement of whether it's good.
- Two fictional cases, author-checked, not reviewed by a recruiter or an employment adviser.
- No transfer to an offer comparison yet; when one exists it will be a deliberate, reviewable step.
