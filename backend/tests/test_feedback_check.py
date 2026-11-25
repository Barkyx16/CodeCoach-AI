"""A check made before time ran out (Volume 16, prompt 3; docs/COACH_CONTEXT.md, "A check before
time ran out"): "I've checked this" keeps the feedback preview's fingerprint, its time and a digest of
each part by label, never the text, replacing any earlier one. When time runs out, the review says
"You checked this before time ran out" if what it read is what was checked, or names what changed
after. Confirming sends nothing, scores nothing and doesn't stop the clock; a stale confirmation is
refused as a stale finish is; another account can't confirm; a career interview has nothing to check.
The export carries the check's time and fingerprint by id. Synthetic data only."""

from __future__ import annotations

import json

from sqlalchemy import func, select

from app.models import AIInteraction, PracticeSession
from tests.conftest import auth_headers, register
from tests.test_coach_context import CODE
from tests.test_coach_context_interviewer import feedback_preview, say, setup
from tests.test_feedback_read import expire, get
from tests.test_question_rounds import start

CONFIRM = "/api/v1/interviews/{}/feedback/confirm"


def same_time(a: str, b: str) -> bool:
    """The export keeps the stored ISO time; the API writes the same instant with "Z"."""
    from datetime import datetime

    return datetime.fromisoformat(a.replace("Z", "+00:00")) == datetime.fromisoformat(
        b.replace("Z", "+00:00")
    )


def confirm(client, h, iv, fingerprint, code=CODE, ending="finished"):
    body = {"ending": ending, "approved_context": fingerprint}
    if code is not None:
        body["code"] = code
    return client.post(CONFIRM.format(iv["id"]), headers=h, json=body)


def checked(client, h, iv, code=CODE):
    fp = feedback_preview(client, h, iv, code=code).json()["context_fingerprint"]
    r = confirm(client, h, iv, fp, code=code)
    assert r.status_code == 200, r.text
    return r.json()


def test_check_then_time_out_is_recorded_as_checked_with_the_time(client):
    h, _rec, iv = setup(client)
    assert say(client, h, iv, code=CODE).status_code == 200
    kept = checked(client, h, iv)
    assert kept["text"].startswith("Checked. If time runs out before you finish")
    assert "Your code" in kept["labels"] and "How it ended" not in kept["labels"]
    expire(client, iv["id"])
    got = get(client, h, iv["id"])
    read = got["feedback_read"]
    assert read["ending"] == "time_expired" and read["checked"] is False  # not a checked finish
    assert read["text"] == "You checked this before time ran out."
    assert read["confirmed"]["matched"] is True and read["confirmed"]["at"] == kept["at"]
    assert read["confirmed"]["fingerprint"] == kept["fingerprint"]
    # The interview's conditions say the same, as part of how it was given.
    f = got["conditions"]["interview"]
    assert "the feedback's material checked before time ran out" in f["text"]
    assert [c["what"] for c in f["checks"]] == ["The feedback's material"]


def test_check_add_a_message_time_out_names_what_changed(client):
    h, _rec, iv = setup(client)
    assert say(client, h, iv, code=CODE).status_code == 200
    checked(client, h, iv)
    assert say(client, h, iv, message="And then I'd sort the pairs first.", code=CODE).status_code == 200
    expire(client, iv["id"])
    read = get(client, h, iv["id"])["feedback_read"]
    assert read["confirmed"]["matched"] is False
    assert read["confirmed"]["changed"] == ["The conversation so far"]
    assert read["text"] == (
        "You checked an earlier version before time ran out; it changed after: The conversation so far."
    )


def test_no_check_is_unchanged(client):
    h, _rec, iv = setup(client)
    say(client, h, iv, code=CODE)
    expire(client, iv["id"])
    read = get(client, h, iv["id"])["feedback_read"]
    assert read["confirmed"] is None
    assert read["text"] == "You didn't check this before it was scored: time ran out."


def test_code_checked_in_the_editor_but_never_sent_is_said(client):
    h, _rec, iv = setup(client)
    say(client, h, iv, code=CODE)
    checked(client, h, iv, code=CODE + "\n// a last edit, never sent")
    expire(client, iv["id"])
    read = get(client, h, iv["id"])["feedback_read"]
    assert read["confirmed"]["changed"] == ["Your code"] and read["confirmed"]["code_unsent"] is True
    assert read["text"].endswith(
        "The code you checked was still in your editor, not sent, so it read the code last sent."
    )


def test_a_confirmation_from_another_tab_after_the_conversation_moved_on_is_refused(client):
    h, _rec, iv = setup(client)
    say(client, h, iv, code=CODE)
    fp = feedback_preview(client, h, iv).json()["context_fingerprint"]
    say(client, h, iv, message="Sent from the other tab.", code=CODE)  # moved on
    r = confirm(client, h, iv, fp)
    assert r.status_code == 409 and r.json()["error"]["code"] == "context_changed"
    assert "a message was sent or your code changed, perhaps in another tab" in r.json()["error"]["message"]
    assert r.json()["error"]["details"]["preview"]["context_fingerprint"] != fp
    with client.app.state.session_factory() as db:
        assert "feedback_check" not in (db.get(PracticeSession, iv["id"]).plan or {})


def test_each_confirmation_replaces_the_last(client):
    h, _rec, iv = setup(client)
    say(client, h, iv, code=CODE)
    first = checked(client, h, iv)
    say(client, h, iv, message="One more thought on the hash map.", code=CODE)
    second = checked(client, h, iv)
    assert second["fingerprint"] != first["fingerprint"]
    expire(client, iv["id"])
    read = get(client, h, iv["id"])["feedback_read"]
    assert read["confirmed"]["matched"] is True and read["confirmed"]["at"] == second["at"]


def test_confirming_sends_nothing_scores_nothing_and_keeps_the_clock(client):
    h, rec, iv = setup(client)
    say(client, h, iv, code=CODE)
    before = get(client, h, iv["id"])
    with client.app.state.session_factory() as db:
        calls = db.scalar(select(func.count()).select_from(AIInteraction))
    asked = (len(rec.turns), len(rec.evaluations))
    checked(client, h, iv)
    after = get(client, h, iv["id"])
    assert after["deadline_at"] == before["deadline_at"] and after["status"] == "in_progress"
    assert after["turns"] == before["turns"] and after["evaluation"] is None
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(AIInteraction)) == calls
        plan = db.get(PracticeSession, iv["id"]).plan
    assert (len(rec.turns), len(rec.evaluations)) == asked  # nothing sent to the interviewer
    # Never the text: only labels, digests, the fingerprint and the time.
    stored = json.dumps(plan["feedback_check"])
    assert "twoSum" not in stored and "hash map" not in stored
    # (Since Volume 17, prompt 1, also how many turns there were, and each part's line digests.)
    assert set(plan["feedback_check"]) == {"v", "fingerprint", "at", "parts", "code_sent", "turns"}


def test_another_account_cant_confirm_or_read_a_check(client):
    h, _rec, iv = setup(client)
    say(client, h, iv, code=CODE)
    fp = feedback_preview(client, h, iv).json()["context_fingerprint"]
    other = auth_headers(register(client, email="bea@example.com"))
    assert confirm(client, other, iv, fp).status_code == 404
    assert client.get(f"/api/v1/interviews/{iv['id']}", headers=other).status_code == 404


def test_a_career_interview_has_nothing_to_check(client):
    h = auth_headers(register(client, email="nia@example.com", career_track="registered-nurse"))
    iv = start(client, h).json()
    r = client.post(CONFIRM.format(iv["id"]), headers=h, json={"approved_context": "v1:x"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "wrong_interview_kind"


def test_the_export_carries_the_checks_time_and_fingerprint_never_the_text(client):
    h, _rec, iv = setup(client)
    marker = "My unmistakable sentence about two pointers."
    say(client, h, iv, message=marker, code=CODE)
    kept = checked(client, h, iv)
    doc = client.get("/api/v1/me/export", headers=h).json()
    [row] = [i for i in doc["interviews"] if i["id"] == iv["id"]]
    check = row["feedback_check"]
    assert same_time(check["at"], kept["at"]) and check["fingerprint"] == kept["fingerprint"]
    assert check["labels"] == kept["labels"]
    expire(client, iv["id"])
    get(client, h, iv["id"])  # past its time, it's closed (and scored) when it's next read
    doc = client.get("/api/v1/me/export", headers=h).json()
    [row] = [i for i in doc["interviews"] if i["id"] == iv["id"]]
    confirmed = row["feedback_read"]["confirmed"]
    assert same_time(confirmed["at"], kept["at"]) and confirmed["fingerprint"] == kept["fingerprint"]
    assert marker not in json.dumps(row["feedback_read"]) and marker not in json.dumps(row["feedback_check"])
