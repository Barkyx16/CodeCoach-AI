# Story bank: your own STAR stories

A private place to write real experiences once, in Situation / Task / Action / Result form with
an optional Reflection, and use them to prepare for behavioral questions. It's a preparation
tool: separate from scored attempts and from the general notebook.

## One model, shared with job targets

Job targets already had "Your examples" (title, situation, what you did, result, linked
requirements). The story bank **extends that same table** (`experience_entries`), so an example
written in a target *is* a story in the bank and editing it in either place edits the one copy.
The bank adds: career, where it happened (work, study, volunteering, a personal project), Task,
Reflection, competencies, skill tags, private notes, optional evidence of the outcome, rehearsal
versions, linked questions, archiving and a revision number.

- A story links to **one job target** (and that target's requirements) by id, and to **questions**
  by their stable `track/question_id`. A link never copies text, so it can't drift apart.
- **Deleting a target no longer deletes its examples**: they stay in the bank, unlinked.
  (Before this change, deleting a target deleted its examples.)
- **Existing data** (migration `178db0129ee0`): every existing example became a story with
  every original word kept, got the career of its target, and a first saved version holding its
  text exactly as it was.

## Writing and retrieving

- Neutral prompts under each section ("What did you do? Say 'I' for your part"), none suggesting
  achievements, employers, qualifications or numbers. A story can be saved unfinished; missing
  sections are listed as "Not written yet", never as a judgment.
- Competencies (teamwork, conflict, leadership, prioritising, handling a mistake, communication,
  problem solving, adapting to change, patient or customer care, taking initiative); one story
  can show several. Free-text skill tags too.
- **Search** runs on the server over everything you wrote in your own stories (every word must
  match), with a competency filter and an archived view; filters live in the URL.
- **Privacy**: a note asks for de-identified stories ("a patient", "my manager"). After saving,
  possible identifiers are pointed out (an honorific with a name, a long ID number, a date like a
  date of birth, an email address or phone number) for the learner to review; nothing is blocked
  or changed automatically.

## Every save is kept

- Each save is a new **version** (`story_revisions`, a full snapshot); saving with nothing
  changed creates none. The editor sends only the fields that changed, with the version it
  started from: if the story was saved elsewhere since, the save is refused (`409
  stale_revision`) and the learner chooses "Save mine as the newest version" or "Discard mine and
  load the saved version". Nothing is lost silently.
- **Restoring** an old version saves it as a new version; history is never rewritten. Up to 100
  versions are kept per story (the first one always).
- **Unsaved edits** are kept on the device as you type and offered back ("Restore them" /
  "Discard them") when you return, including after a reload. They're cleared with the account's
  other drafts on sign-out.

## Writing help: rules, not AI

"Check for missing parts", "Suggest a shorter version" and "Suggest clearer wording" are a
**built-in rule-based check**. No model is involved and **story text is never sent anywhere**,
so no provider consent, budget or redaction is needed, and nothing can be invented.

- It works on the text in the form now, saved or not, and **saves nothing**.
- *Check* asks questions only: a missing Situation, Task, Action or Result; an Action that only
  says "we" ("Which parts did you do yourself?"); very long sections; an optional reflection. It
  never asks for numbers ("A number isn't required").
- *Shorter* and *clearer* can only **remove** words (filler such as "basically", hedges such as
  "I think", repeated sentences). Every proposal is checked to contain only words that were
  already in the learner's text; one that fails is dropped. Vague phrases ("helped with", "worked
  on") and very long sentences become questions, not rewrites.
- Proposals appear **side by side** with the original. "Use this version" puts it in the form;
  "Keep mine" leaves it. It's saved only when the learner saves, as a version marked "edited
  with the writing check".
- **Not built:** model-based rewriting. If added, it would have to go through the AI coach's
  budget and redaction, with an explicit warning before any story text is sent.

## Practising a story

On a question page, "Practise with one of your stories" lets the learner pick a story, start the
answer from it (after confirming if there's already a draft), and optionally link the question
to the story. The answer is an ordinary graded answer that **points at** the story
(`practice_answers.story_id`): the story itself is never changed by practising. The story lists
"Practised with this story". Deleting a story keeps those answers and their scores. Rehearsal
versions (short and longer) are the learner's own words, labelled as rehearsals, not scripts.

Voice is in mock interviews; the question page is typed, so practising a story there is typed
too.

## Privacy and data

- Private to the owner: every endpoint is scoped to the signed-in account (404 for anyone else).
- Text is stored as written (control characters removed) and shown only as plain text.
- Sharing an answer for feedback shares only the sentences chosen from the answer: nothing from
  the story (title, notes, evidence) is included (tested).
- The data export includes every story with all its versions, and which story each answer
  rehearsed. Account deletion removes stories and versions.

## Verified, and not

- Backend: 11 tests on SQLite and PostgreSQL, plus a migration run on PostgreSQL with seeded
  existing examples (text kept, first version created, target deletion unlinks).
- Frontend: 7 integration tests. Playwright (Chromium): a target example becomes a story, is
  edited, checked, accepted, restored after a reload, practised, linked, restored to version 1,
  hidden from another account and deleted while its answer is kept; the editor at 320px in the
  light theme; axe scans.
- Not verified: screen readers, Safari/Firefox.
