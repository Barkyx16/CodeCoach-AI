# Learn mode content: authoring and review

Learn units are short lessons that teach a skill before it's assessed. They're plain Python data in
[`backend/app/learn/units.py`](../backend/app/learn/units.py), validated by
`backend/tests/test_learn.py`. No model is called to show or grade a unit.

## Coverage (honest)

| Career | Units |
| --- | --- |
| Software Engineer | Hash maps for fast lookup · Sliding windows (needs hash maps first) · Explaining how you debug |
| Registered Nurse | STAR answers · SBAR for handoffs and escalation · Prioritizing several patients (needs SBAR first) |

Every other career shows "no lessons yet" instead of borrowing another career's units.

## What a unit contains

`Unit` (see `backend/app/learn/__init__.py`): `id`, `track`, `version` and `changes`, `title`,
`skill` (one of the career's skills, which links it to the practice plan, or `None`), coding
`topics`, `minutes`, `objective`, `prerequisites` (unit ids, same career), `explanation`, one
worked `example` (optional code), `mistakes`, an `exercise` (prompt, the four guided steps:
a question to think about, the concept, an example, the fuller explanation; and a `solution`
kept hidden until requested), a multiple-choice `check` (answers never leave the server before an
attempt), a `practice` action (a real question or problem id), `references`, `review`, an
optional `scope_note` for regulated careers, and `question_ids` it prepares for.

## Rules

1. **Small and specific.** One skill, 5–10 minutes. Don't claim to cover a whole topic.
2. **Real references only.** Cite documents you have read. If you don't know a stable link, set
   `url=None` and say how to find it in `note`; never guess a URL. Repository references point at
   the code or data the unit relies on. A unit with no outside references says so on the page.
3. **Review status is a claim.** `author_reviewed` means someone checked the unit against its
   references. Anything drafted by a model and not yet checked must be `generated_draft`; the page
   shows a "Generated draft: not reviewed yet" badge. Don't invent reviewers or credentials.
4. **Regulated careers.** Nursing and similar units carry a `scope_note`: interview education, not
   clinical guidance, with jurisdiction and facility policy named. Keep patient details generic.
5. **Versioning.** Bump `version` and append to `changes` when the meaning changes (a fix, a new
   check question, a different example). Learner progress is stored per version, so history is
   kept and the page tells returning learners what changed. A page still showing an older version
   gets `409 unit_changed` instead of recording against the wrong version.
6. **Progress means something.** Events are `started`, `read`, `check_attempted`,
   `check_passed` (every answer right) and `practiced` (a real answer or submission to the linked
   practice after starting). Reading or passing the check never marks a problem solved or a skill
   validated; the practice plan only counts a lesson as done when its check is passed.

## Adding a unit

1. Write it in `units.py` and add it to `UNITS`.
2. Run `pytest tests/test_learn.py`: it checks every unit is complete, prerequisites exist in the
   same career, skills belong to the career, practice items exist, check answers are in range, and
   links are absent or `https://`.
3. Read it in the app on desktop and a 320px-wide screen; check keyboard access to the outline,
   code blocks, guided steps and the check.
4. Set `review` honestly and note what it was checked against.
