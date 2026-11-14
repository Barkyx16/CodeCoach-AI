"""Query budgets for the main learner journeys (docs/PERFORMANCE.md, "Real journeys").

Stable checks, not timings: the number of SQL statements a request makes must not grow with
the learner's history (no N+1), must stay within a recorded budget, and the history-heavy
dashboard endpoints must not load whole answers (text and feedback JSON) just to count them.
"""

import random
import re
from contextlib import contextmanager

from sqlalchemy import event

from app.careers.answers import graded_answer
from app.careers.questions import questions_for
from app.content import state as content_state
from tests.conftest import auth_headers, register

TRACK = "registered-nurse"
# (name, method, path, statement budget). Budgets are today's counts plus a little headroom.
JOURNEYS = [
    ("search", "GET", f"/api/v1/careers/{TRACK}/questions?q=patient&page_size=20", 4),
    ("career progress", "GET", f"/api/v1/careers/{TRACK}/progress", 4),
    ("career analytics", "GET", f"/api/v1/me/careers/{TRACK}/analytics", 5),
    ("history", "GET", "/api/v1/me/activity?page=1&page_size=20", 10),
    ("history facets", "GET", "/api/v1/me/activity/facets", 8),
    ("plan", "GET", "/api/v1/me/plan", 24),
    ("reviews", "GET", "/api/v1/me/reviews", 4),
    ("resume", "GET", "/api/v1/me/resume", 6),
]
FEEDBACK = re.compile(r"practice_answers\.feedback")


def loads_whole_feedback(statement: str) -> bool:
    """Does this SELECT return answers' whole feedback JSON (rather than one field of it)?"""
    if not statement.lstrip().upper().startswith("SELECT"):
        return False
    columns = re.split(r"\sFROM\s", statement, maxsplit=1, flags=re.I)[0]
    for m in FEEDBACK.finditer(columns):
        inside_json_extract = "JSON_EXTRACT(" in columns[max(0, m.start() - 14) : m.start()].upper()
        json_operator = columns[m.end() :].lstrip().startswith("->")
        if not (inside_json_extract or json_operator):
            return True
    return False


@contextmanager
def statements(client):
    seen: list[str] = []

    def record(_conn, _cursor, statement, *_args):
        seen.append(statement)

    event.listen(client.app.state.engine, "before_cursor_execute", record)
    try:
        yield seen
    finally:
        event.remove(client.app.state.engine, "before_cursor_execute", record)


def learner(client, email, answers):
    tokens = register(client, email=email, career_track=TRACK)
    headers = auth_headers(tokens)
    uid = client.get("/api/v1/auth/me", headers=headers).json()["id"]
    rng = random.Random(1)
    qs = questions_for(TRACK)
    with client.app.state.session_factory() as db:
        for i in range(answers):
            db.add(
                graded_answer(
                    uid,
                    qs[rng.randrange(len(qs))],
                    ["We handled it.", "I assessed him and escalated; he was stable."][i % 2],
                )
            )
        db.commit()
    return headers


def fresh_content(client):
    """The process-wide snapshot of corrections and retirements reloads when it's over
    content_state.MAX_AGE_S old: two statements, once per 5 s per process, not per request. Fresh
    now, so a measurement counts only its own request. (Without this the count depended on timing:
    on a slow runner the reload fell inside one measurement and not the other; CI run 276.)"""
    with client.app.state.session_factory() as db:
        content_state.refresh(db, force=True)


def measure(client, headers, method, path):
    client.request(method, path, headers=headers)  # first view may create things (a plan)
    fresh_content(client)
    with statements(client) as seen:
        r = client.request(method, path, headers=headers)
    assert r.status_code == 200, r.text
    return seen


def test_statements_per_request_do_not_grow_with_history_and_stay_in_budget(client):
    small = learner(client, "small@example.com", 0)
    large = learner(client, "large@example.com", 300)
    for name, method, path, budget in JOURNEYS:
        few = measure(client, small, method, path)
        many = measure(client, large, method, path)
        assert len(many) <= len(few) + 2, (
            f"{name}: {len(few)} statements with no history, {len(many)} with 300 answers"
        )
        assert len(many) <= budget, f"{name}: {len(many)} statements, budget {budget}"


def test_the_check_recognises_whole_rows_and_single_fields():
    assert loads_whole_feedback(
        "SELECT practice_answers.id, practice_answers.feedback, practice_answers.provider FROM x"
    )
    assert not loads_whole_feedback(
        "SELECT JSON_QUOTE(JSON_EXTRACT(practice_answers.feedback, ?)) AS evaluator FROM x"
    )
    assert not loads_whole_feedback(
        "SELECT (practice_answers.feedback ->> %(feedback_1)s) AS evaluator FROM x"
    )
    assert not loads_whole_feedback("UPDATE practice_answers SET feedback = ?")


def test_dashboard_statistics_never_load_whole_answers(client):
    h = learner(client, "heavy@example.com", 300)
    analytics = measure(client, h, "GET", f"/api/v1/me/careers/{TRACK}/analytics")
    assert not [s for s in analytics if loads_whole_feedback(s)]
    plan = measure(client, h, "GET", "/api/v1/me/plan")
    # The plan reads whole answers only one at a time: the weak answers whose feedback it quotes
    # (by id) and each plan item's latest evidence (LIMIT 1). Never every answer at once.
    whole = [s for s in plan if loads_whole_feedback(s)]
    unbounded = [s for s in whole if not re.search(r"\bLIMIT\b|practice_answers\.id = ", s, re.I)]
    assert not unbounded, unbounded


def test_submitting_an_answer_is_a_bounded_number_of_statements(client):
    h = learner(client, "writer@example.com", 300)
    qid = questions_for(TRACK)[0].id
    fresh_content(client)
    with statements(client) as seen:
        r = client.post(
            f"/api/v1/careers/{TRACK}/questions/{qid}/answers",
            headers=h,
            json={"answer": "I escalated early."},
        )
    assert r.status_code == 201, r.text
    assert len(seen) <= 8, len(seen)
