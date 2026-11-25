# Interview formats and simulated panels

Question rounds come in five formats. They all use the same engine (server-side session, deadline,
one answer per question, rubric grading, review and retries); a format only changes which
questions are picked, who asks them and whether a follow-up may be asked. Definitions live in
[`backend/app/careers/formats.py`](../backend/app/careers/formats.py).

| Format | Questions | Follow-ups |
| --- | --- | --- |
| Mixed (default) | one of each kind: why this work, knowledge, scenario, a time you did it, leading others | none (unchanged behavior) |
| Behavioral | five behavioral / leadership / motivation questions | up to 2: what you personally did, the result, a number, what you learned |
| Situational | five scenarios | up to 2: what first, who you'd inform, how you'd follow up, why |
| Technical / professional | five knowledge questions | up to 2: why that approach, an example, a number |
| Panel (simulated) | five questions asked in turn by three roles | up to 2, from the role that asked |

A format is offered only when the bank has five suitable questions at the chosen level
(`GET /api/v1/interviews/formats?track=&difficulty=` says why when it doesn't, e.g. no Easy
scenarios). The format is fixed when the round starts.

## Panels

A panel needs a reviewed role configuration for the career (`PANELS`). Today: **Software
Engineer** (engineering manager, senior engineer peer, product manager partner) and **Registered
Nurse** (nurse manager, charge nurse peer, physician colleague). Every other career shows the panel
as unavailable with that reason instead of falling back to generic questions.

Each role has a stable id (`hiring_manager`, `peer`, `partner`), a generic job title (never a real
employer, person or credential), an objective, the question kinds it asks and the details it
follows up on. The order is fixed: hiring manager, peer, partner, peer, hiring manager. Only one
role speaks at a time; the active role is named in text (the eyebrow, the turn cue and the roster),
never only by color or voice.

## Follow-ups

After an answer the server checks which details from the format's (or role's) list are missing,
using simple, disclosed patterns (`DETAIL_PATTERNS`). It asks about the first one that:

- the answer doesn't contain,
- no earlier answer or reply in this session supplied (shared context, so no role asks for
  something already given), and
- hasn't been asked about yet in this session.

At most one follow-up per question and two per session; no model is called. While a follow-up is
waiting, the next question can't be answered (`409 followup_pending`); the learner replies or
skips. The reply is stored on that question's turn (`meta.followup`) with whether it supplied the
detail; it doesn't change the question's score.

## Review

The review shows who asked each question, each follow-up and the reply, and a "Follow-up
questions" dimension. For panels it adds one perspective per role: the same rubric applied to
the questions that role asked. These are labelled as simulated and are not independent human
judgments or a hiring prediction. Simulated engagement stays an evidence-based signal that can be
hidden during the round.

## Adding a panel for a career

1. Add a tuple of three `Role`s to `PANELS` with generic titles appropriate to the career, an
   objective each, the question kinds each asks (in preference order) and the details each probes.
2. Check `GET /interviews/formats?track=<career>` shows the panel available at each level, and
   run `pytest tests/test_formats.py`.
3. Read a full round as a learner: do the roles' questions and follow-ups make sense together?
