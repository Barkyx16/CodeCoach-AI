"""Conditions for debugging exercises and the coding interviewer (Volume 16, prompt 2;
docs/ATTEMPT_CONDITIONS.md): a debugging exercise's attempt says the hints before it and whether its
explanation and repair were opened (recorded from 16 Nov 2026; before that it says it wasn't); a
coding interview lists the hints for its problem, in order, with the level in the hint panel's words
and whether each came before or during it, and its format: the time limit, how it ended and each
message and the feedback checked first (never help). One function decides each record for the
submission page, the interview's review, History and the export. Another account's rows never
count, and on PostgreSQL row-level security keeps them out even if a query forgot its owner filter.
Synthetic data only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import AIInteraction, LabReveal, PracticeSession, Problem, Submission
from app.services import conditions as conditions_service
from tests.conftest import auth_headers, register
from tests.test_coach_context import CODE
from tests.test_coach_context_interviewer import feedback_preview, preview, say
from tests.test_row_level_security import pytestmark_pg

LAB = "debug-coldest-day"
LAB_FIX = "class Solution { public int coldest(int[] temps) { return 0; } }"
BEFORE = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)  # before recording began for both


def coder(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track="software-engineer"))


def hint(client, h, level, slug=LAB):
    r = client.post(
        "/api/v1/ai/hint", headers=h, json={"problem_slug": slug, "level": level, "source_code": LAB_FIX}
    )
    assert r.status_code == 200, r.text
    return r.json()


def open_explanation(client, h, slug=LAB):
    r = client.post(f"/api/v1/problems/{slug}/lab/explanation", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def attempt(client, h, slug=LAB, mode="submit"):
    r = client.post(
        "/api/v1/submissions",
        headers=h,
        json={"problem_slug": slug, "language": "java", "source_code": LAB_FIX, "mode": mode},
    )
    assert r.status_code == 202, r.text
    return r.json()["id"]


def page(client, h, sub_id):
    r = client.get(f"/api/v1/submissions/{sub_id}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()["conditions"]


def review(client, h, iv_id):
    r = client.get(f"/api/v1/interviews/{iv_id}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()["conditions"]


def start_coding(client, h):
    r = client.post(
        "/api/v1/interviews",
        headers=h,
        json={"kind": "coding", "problem_slug": "two-sum", "duration_minutes": 15},
    )
    assert r.status_code == 201, r.text
    return r.json()


def setup(client, email="ada@example.com"):
    """A coding interview of Two Sum with the built-in coach (which also gives hints)."""
    h = coder(client, email)
    return h, None, start_coding(client, h)


def finish(client, h, iv_id, **body):
    r = client.post(f"/api/v1/interviews/{iv_id}/finish", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def bulk(client, h, **ids):
    r = client.post("/api/v1/me/attempt-conditions", headers=h, json=ids)
    assert r.status_code == 200, r.text
    return r.json()


# --- debugging exercises ------------------------------------------------------------------------------


def test_a_debugging_exercise_after_a_hint_says_so_and_the_next_one_says_none(client):
    h = coder(client)
    hint(client, h, 1)
    first = attempt(client, h)
    second = attempt(client, h)
    c = page(client, h, first)
    assert c["labels"] == ["Hint shown"] and [x["detail"] for x in c["help"]] == ["Level 1 hint (nudge)"]
    assert c["unrecorded"] is None
    assert page(client, h, second)["labels"] == ["No in-app help recorded"]


def test_opening_the_explanation_is_solution_revealed_for_the_next_attempt_only(client):
    h = coder(client)
    body = open_explanation(client, h)
    assert body["reference_repair"] and body["recorded_at"]
    # Asking again before the next attempt is the same opening, not a second one.
    assert open_explanation(client, h)["recorded_at"] == body["recorded_at"]
    first = attempt(client, h)
    c = page(client, h, first)
    assert c["labels"] == ["Solution revealed"]
    assert [x["detail"] for x in c["help"]] == ["The exercise's explanation and a correct repair (version 1)"]
    assert page(client, h, attempt(client, h))["labels"] == ["No in-app help recorded"]
    # Opened after an attempt: the next attempt's, never the earlier one's.
    later = open_explanation(client, h)["recorded_at"]
    assert later != body["recorded_at"]
    assert page(client, h, first)["labels"] == ["Solution revealed"]
    assert page(client, h, attempt(client, h))["labels"] == ["Solution revealed"]
    with client.app.state.session_factory() as db:
        assert db.query(LabReveal).count() == 2


def test_the_plain_read_records_nothing_and_an_ordinary_problem_has_no_explanation(client):
    h = coder(client)
    assert client.get(f"/api/v1/problems/{LAB}/lab/explanation").json()["recorded_at"] is None
    assert page(client, h, attempt(client, h))["labels"] == ["No in-app help recorded"]
    assert client.post("/api/v1/problems/two-sum/lab/explanation", headers=h).status_code == 404
    assert client.post(f"/api/v1/problems/{LAB}/lab/explanation").status_code == 401


def test_an_opening_at_another_version_of_the_exercise_doesnt_count(client):
    h = coder(client)
    open_explanation(client, h)
    with client.app.state.session_factory() as db:  # corrected after it was opened
        problem = db.scalar(select(Problem).where(Problem.slug == LAB))
        assert problem is not None
        problem.lab = {**(problem.lab or {}), "version": 2}
        db.commit()
    assert page(client, h, attempt(client, h))["labels"] == ["No in-app help recorded"]


def test_a_debugging_attempt_from_before_this_says_the_opening_wasnt_recorded(client):
    h = coder(client)
    bare = attempt(client, h)
    hint(client, h, 1)
    hinted = attempt(client, h)
    with client.app.state.session_factory() as db:
        db.get(Submission, bare).created_at = BEFORE
        db.get(Submission, hinted).created_at = BEFORE + timedelta(hours=2)
        for row in db.scalars(select(AIInteraction)):
            row.created_at = BEFORE + timedelta(hours=1)
        db.commit()
    c = page(client, h, bare)
    assert c["labels"] == ["Not recorded"] and "wasn't recorded before 16 Nov 2026" in c["unrecorded"]
    c = page(client, h, hinted)
    assert c["labels"] == ["Hint shown"] and "isn't known" in c["unrecorded"]
    # An ordinary problem's attempt from then has nothing of the kind to say.
    plain = page(client, h, attempt(client, h, slug="two-sum"))
    assert plain["unrecorded"] is None


def test_another_accounts_openings_and_hints_never_count(client):
    a = coder(client)
    b = coder(client, "bea@example.com")
    open_explanation(client, b)
    hint(client, b, 1)
    assert page(client, a, attempt(client, a))["labels"] == ["No in-app help recorded"]
    doc = client.get("/api/v1/me/export", headers=a).json()
    assert doc["lab_reveals"] == []


# --- coding interviews --------------------------------------------------------------------------------


def test_a_coding_interview_with_two_hints_lists_both_in_order(client):
    h = coder(client)
    hint(client, h, 1, slug="two-sum")  # before it started
    iv = start_coding(client, h)
    hint(client, h, 2, slug="two-sum")  # during it
    assert review(client, h, iv["id"]) is None  # nothing while it runs, here or in History
    assert bulk(client, h, interview_ids=[iv["id"]])["interviews"] == {}
    finish(client, h, iv["id"])
    c = review(client, h, iv["id"])
    assert c["labels"] == ["Hint shown"]
    assert [x["detail"] for x in c["help"]] == [
        "Level 1 hint, “Nudge”, on “Two Sum”, before the interview",
        "Level 2 hint, “Concept”, on “Two Sum”, during the interview",
    ]
    assert c["interview"]["ending"] == "finished" and c["interview"]["timed_minutes"] == 15
    # The next interview of the problem starts afresh; the next submission counts its own (modes apart).
    again = start_coding(client, h)
    finish(client, h, again["id"])
    assert review(client, h, again["id"])["labels"] == ["No in-app help recorded"]
    assert page(client, h, attempt(client, h, slug="two-sum"))["labels"] == ["Hint shown"]


def test_a_coding_interview_says_which_messages_and_the_feedback_were_checked(client):
    h, _rec, iv = setup(client)
    checked = preview(client, h, iv).json()["context_fingerprint"]
    assert say(client, h, iv, approved=checked).status_code == 200
    assert say(client, h, iv, message="And then I'd sort the pairs.").status_code == 200
    fp = feedback_preview(client, h, iv).json()["context_fingerprint"]
    finish(client, h, iv["id"], code=CODE, approved_context=fp)
    c = review(client, h, iv["id"])
    assert c["labels"] == ["No in-app help recorded"]  # checking is never help
    f = c["interview"]
    assert f["checks_recorded"] is True
    assert [(x["what"], x["detail"]) for x in f["checks"]] == [
        ("Message 1", "checked before it was sent"),
        ("The feedback's material", "checked before it was scored"),
    ]
    assert f["text"] == (
        "A 15-minute coding interview, finished; 1 of 2 messages checked before sending; "
        "the feedback's material checked before it was scored."
    )


def test_an_interview_ended_early_unchecked_says_so(client):
    h, _rec, iv = setup(client)
    assert say(client, h, iv).status_code == 200
    r = client.post(f"/api/v1/interviews/{iv['id']}/abandon", headers=h, json={})
    assert r.status_code == 200, r.text
    f = review(client, h, iv["id"])["interview"]
    assert f["ending"] == "ended_early" and f["checks"] == []
    assert f["text"] == (
        "A 15-minute coding interview, ended early; 0 of 1 message checked before sending; "
        "the feedback's material not checked."
    )


def test_an_interview_from_before_this_says_the_checks_werent_recorded(client):
    h, _rec, iv = setup(client)
    finish(client, h, iv["id"])
    with client.app.state.session_factory() as db:
        s = db.get(PracticeSession, iv["id"])
        s.started_at = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)  # before hints were recorded too
        s.ended_at = s.started_at + timedelta(minutes=15)
        s.plan = {k: v for k, v in (s.plan or {}).items() if k != "content_version"}
        db.commit()
    c = review(client, h, iv["id"])
    assert c["labels"] == ["Not recorded"]
    assert c["interview"]["checks_recorded"] is False
    assert (
        "whether messages were checked before they were sent wasn't recorded then" in c["interview"]["text"]
    )


def test_the_export_and_history_carry_both_records_by_id_and_match_the_pages(client):
    h, _rec, iv = setup(client)
    hint(client, h, 1, slug="two-sum")
    finish(client, h, iv["id"])
    open_explanation(client, h)
    sub = attempt(client, h)
    doc = client.get("/api/v1/me/export", headers=h).json()
    [row] = [i for i in doc["interviews"] if i["id"] == iv["id"]]
    assert row["conditions"] == review(client, h, iv["id"])
    [exported] = [s for s in doc["submissions"] if s["id"] == sub]
    assert exported["conditions"] == page(client, h, sub)
    assert [(r["exercise"], r["lab_version"]) for r in doc["lab_reveals"]] == [(LAB, 1)]
    found = bulk(client, h, submission_ids=[sub], interview_ids=[iv["id"], "no-such-id"])
    assert found["submissions"][sub] == page(client, h, sub)
    assert found["interviews"] == {iv["id"]: review(client, h, iv["id"])}
    # Another account asking for these ids gets nothing back.
    other = coder(client, "bea@example.com")
    assert bulk(client, other, submission_ids=[sub], interview_ids=[iv["id"]]) == {
        **bulk(client, other),
        "submissions": {},
        "interviews": {},
    }


def test_a_career_interview_isnt_described_as_a_coding_one(client):
    from tests.test_question_rounds import start

    h = auth_headers(register(client, email="nia@example.com", career_track="registered-nurse"))
    iv = start(client, h).json()
    client.post(f"/api/v1/interviews/{iv['id']}/abandon", headers=h, json={})
    assert review(client, h, iv["id"]) is None
    assert bulk(client, h, interview_ids=[iv["id"]])["interviews"] == {}


@pytestmark_pg
def test_on_postgresql_the_records_read_only_this_accounts_rows_even_without_their_owner_filter(
    client, monkeypatch
):
    """Row-level security keeps both records to this account's hints, openings and interviews, even
    if their queries lost the owner filter (the bug it exists for)."""
    b = coder(client, "bea@example.com")
    open_explanation(client, b)
    hint(client, b, 1)
    hint(client, b, 1, slug="two-sum")
    h, _rec, iv = setup(client, email="ada@example.com")

    def careless_hints(self, problem_ids):  # the real one also names the account
        out: dict = {}
        for row in self.db.scalars(
            select(AIInteraction)
            .where(AIInteraction.problem_id.in_(problem_ids))
            .order_by(AIInteraction.created_at)
        ):
            out.setdefault(row.problem_id, []).append(row)
        from collections import defaultdict

        return defaultdict(list, out)

    def careless_reveals(self, problem_ids):
        out: dict = {}
        for row in self.db.scalars(
            select(LabReveal).where(LabReveal.problem_id.in_(problem_ids)).order_by(LabReveal.created_at)
        ):
            out.setdefault(row.problem_id, []).append(row)
        from collections import defaultdict

        return defaultdict(list, out)

    monkeypatch.setattr(conditions_service.Conditions, "_hints", careless_hints)
    monkeypatch.setattr(conditions_service.Conditions, "_reveals", careless_reveals)
    finish(client, h, iv["id"])
    assert review(client, h, iv["id"])["labels"] == ["No in-app help recorded"]
    assert page(client, h, attempt(client, h))["labels"] == ["No in-app help recorded"]
