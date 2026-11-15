"""What an interview's feedback read, recorded when it was scored (Volume 15, prompt 8;
docs/COACH_CONTEXT.md, "What the feedback read"): its labels, sizes and what was replaced, never a
second copy of the text; the fingerprint of what was read; how it ended; and whether the learner
checked it. A timed-out interview says it wasn't checked, a checked finish says it was, a stale check
is refused as before and the interview is then recorded as unchecked; a career round records its
own material; interviews scored before this say so. The export carries it by id. Synthetic data
only."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from app.models import PracticeSession
from tests.conftest import auth_headers, register
from tests.test_coach_context import CODE
from tests.test_coach_context_interviewer import feedback_preview, say, setup
from tests.test_question_rounds import NURSE_ANSWER, answer, start


def expire(client, iv_id):
    with client.app.state.session_factory() as db:
        s = db.get(PracticeSession, iv_id)
        s.deadline_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()


def get(client, h, iv_id):
    r = client.get(f"/api/v1/interviews/{iv_id}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def finish(client, h, iv_id, **body):
    return client.post(f"/api/v1/interviews/{iv_id}/finish", headers=h, json=body)


def test_while_it_runs_nothing_is_recorded_and_the_margin_is_said(client):
    h, rec, iv = setup(client)
    got = get(client, h, iv["id"])
    assert got["feedback_read"] is None and got["feedback_check_margin_seconds"] == 120


def test_a_timed_out_interview_lists_what_was_read_and_says_it_wasnt_checked(client):
    h, rec, iv = setup(client)
    assert say(client, h, iv, code=CODE).status_code == 200
    # A preview can't be asked for a time-out, so this is the finish's preview: the same material but for
    # how it ended, which reads "time_expired" there.
    shown = feedback_preview(client, h, iv, code=None).json()["items"]
    expected = {i["label"]: len(i["text"]) for i in shown}
    expected["How it ended"] = len("How it ended: time_expired.")
    expire(client, iv["id"])
    got = get(client, h, iv["id"])
    assert got["status"] == "expired" and got["evaluation"] is not None
    read = got["feedback_read"]
    assert read["recorded"] and read["ending"] == "time_expired" and read["checked"] is False
    assert read["text"] == "You didn't check this before it was scored: time ran out."
    assert {i["label"]: i["chars"] for i in read["items"]} == expected
    assert read["fingerprint"] and read["read_by"]
    code = next(i for i in read["items"] if i["label"] == "Your code")
    assert code["notes"] == ["1 secret-looking string replaced with [REDACTED]."]  # the redactions, said


def test_a_checked_finish_says_it_was_checked(client):
    h, rec, iv = setup(client)
    say(client, h, iv, code=CODE)
    f = feedback_preview(client, h, iv).json()
    r = finish(client, h, iv["id"], code=CODE, approved_context=f["context_fingerprint"])
    assert r.status_code == 200, r.text
    read = r.json()["feedback_read"]
    assert read["checked"] is True and read["ending"] == "finished"
    assert (
        read["text"] == "You checked this before it was scored."
        and read["fingerprint"] == f["context_fingerprint"]
    )
    # A finish without a check is recorded as such.
    h2, _, iv2 = setup(client, email="bea@example.com")
    say(client, h2, iv2, code=CODE)
    plain = finish(client, h2, iv2["id"], code=CODE).json()["feedback_read"]
    assert plain["checked"] is False and plain["text"] == "You didn't check this before it was scored."


def test_a_stale_check_is_refused_and_a_time_out_after_it_is_unchecked(client):
    h, rec, iv = setup(client)
    say(client, h, iv, code=CODE)
    f = feedback_preview(client, h, iv).json()
    say(client, h, iv, message="And then I'd sort first.", code=CODE)  # the conversation moved on
    r = finish(client, h, iv["id"], code=CODE, approved_context=f["context_fingerprint"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "context_changed"
    assert get(client, h, iv["id"])["feedback_read"] is None  # still running: nothing recorded
    expire(client, iv["id"])
    read = get(client, h, iv["id"])["feedback_read"]
    assert read["checked"] is False and read["ending"] == "time_expired"
    assert read["fingerprint"] != f["context_fingerprint"]


def test_the_record_holds_labels_and_sizes_never_a_second_copy_and_the_export_carries_it(client):
    h, rec, iv = setup(client)
    marker = "My unmistakable sentence about hash maps."
    say(client, h, iv, message=marker, code=CODE)
    finish(client, h, iv["id"], code=CODE)
    with client.app.state.session_factory() as db:
        stored = json.dumps(db.get(PracticeSession, iv["id"]).plan["feedback_read"])
    assert marker not in stored and "twoSum" not in stored
    doc = client.get("/api/v1/me/export", headers=h).json()
    [row] = [i for i in doc["interviews"] if i["id"] == iv["id"]]
    assert row["feedback_read"]["ending"] == "finished" and row["feedback_read"]["checked"] is False
    assert {i["label"] for i in row["feedback_read"]["items"]} >= {"The conversation so far", "Your code"}


def test_an_interview_scored_before_this_says_it_wasnt_recorded(client):
    h, rec, iv = setup(client)
    finish(client, h, iv["id"], code=CODE)
    with client.app.state.session_factory() as db:
        s = db.get(PracticeSession, iv["id"])
        s.plan = {k: v for k, v in (s.plan or {}).items() if k != "feedback_read"}
        db.commit()
    read = get(client, h, iv["id"])["feedback_read"]
    assert read == {
        "recorded": False,
        "ending": None,
        "checked": None,
        "items": [],
        "fingerprint": None,
        "read_by": None,
        "text": "What it read wasn't recorded then.",
    }


def test_a_career_round_that_runs_out_of_time_records_its_own_material(client):
    h = auth_headers(register(client, career_track="registered-nurse"))
    iv = start(client, h).json()
    assert answer(client, h, iv["id"], 0).status_code in (200, 201)
    expire(client, iv["id"])
    got = get(client, h, iv["id"])
    read = got["feedback_read"]
    assert got["status"] == "expired" and read["recorded"] and read["ending"] == "time_expired"
    assert read["checked"] is None and read["fingerprint"] is None
    assert [i["label"] for i in read["items"]] == ["Your answer to question 1"]
    assert read["items"][0]["chars"] == len(NURSE_ANSWER)
    assert read["text"].startswith("Time ran out, so it was scored from what you'd answered.")
    assert read["read_by"] == "CodeCoach's own fixed rules, on its server: nothing left it"
