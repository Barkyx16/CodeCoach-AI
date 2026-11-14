"""Reviewed follow-up questions (Volume 12, prompt 4; docs/FOLLOW_UPS.md): offered after repeated
practice, worded conservatively, linked to the answer they follow and never merged with it.
Synthetic data only."""

from sqlalchemy import select

from app.careers.followups import RELATIONSHIPS, FollowUp, problems
from app.careers.questions import get_question
from app.models import User
from tests.conftest import auth_headers, register

NURSE = "registered-nurse"
A, B = "e-inform-0", "e-inform-2"  # patients, then patients' families
ANSWER = (
    "Every morning on my unit I tell each patient the plan for the day: the tests, the times and who "
    "they will see. I explain each medication before I give it and check they understood by asking "
    "them to say it back. After rounds I come back to say what changed and why. Last week a patient "
    "was anxious about a delayed scan, so I checked with radiology, told him the new time and the "
    "reason, and he settled. Keeping people informed builds trust and catches confusion early."
)


def nurse(client, email="nia@example.com"):
    return auth_headers(register(client, email=email, career_track=NURSE))


def answer(client, h, qid, text=ANSWER, **extra):
    r = client.post(
        f"/api/v1/careers/{NURSE}/questions/{qid}/answers", headers=h, json={"answer": text, **extra}
    )
    return r


def offer(client, h, qid=A):
    r = client.get(f"/api/v1/careers/{NURSE}/questions/{qid}/follow-up", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def admin(client):
    h = nurse(client, email="root@example.com")
    with client.app.state.session_factory() as db:
        db.scalar(select(User).where(User.email == "root@example.com")).is_admin = True
        db.commit()
    return h


def test_offered_after_two_scored_answers_with_the_stated_difference(client):
    h = nurse(client)
    assert answer(client, h, A).status_code == 201
    first = offer(client, h)
    assert first["status"] == "not_yet" and first["offers"] == [] and first["scored_answers"] == 1
    assert "After 2 answers" in first["message"]
    assert answer(client, h, A).status_code == 201
    got = offer(client, h)
    assert got["status"] == "offered"
    [o] = got["offers"]
    assert (o["track"], o["question_id"]) == (NURSE, B)
    assert "families" in o["difference"] and o["objective"]
    assert o["exposure"] == "Not previously attempted in this app" and o["attempts"] == 0
    assert "new to you" not in str(got).lower() and "never seen" not in str(got).lower()


def test_answers_too_short_to_score_dont_count_toward_the_offer(client):
    h = nurse(client)
    for _ in range(3):
        answer(client, h, A, text="I tell them things.")
    assert offer(client, h)["status"] == "not_yet"


def test_a_follow_up_already_answered_isnt_called_new(client):
    h = nurse(client)
    answer(client, h, B)
    answer(client, h, A)
    answer(client, h, A)
    [o] = offer(client, h)["offers"]
    assert o["exposure"] == "Answered 1 time before in this app" and o["attempts"] == 1


def test_no_reviewed_relationship_is_one_plain_sentence(client):
    h = nurse(client)
    answer(client, h, "m-pressure-0")
    answer(client, h, "m-pressure-0")
    got = offer(client, h, "m-pressure-0")
    assert got["status"] == "none" and got["offers"] == []
    assert got["message"] == "No reviewed related question is linked to this one yet."


def test_a_retired_follow_up_isnt_offered(client):
    h = nurse(client)
    answer(client, h, A)
    answer(client, h, A)
    root = admin(client)
    r = client.post(
        f"/api/v1/admin/content/question/{NURSE}/{B}/retire",
        headers=root,
        json={"reason": "Broken question."},
    )
    assert r.status_code in (200, 201), r.text
    got = offer(client, h)
    assert got["status"] == "none" and got["offers"] == []


def test_a_revised_follow_up_shows_its_version_and_old_answers_keep_theirs(client):
    h = nurse(client)
    old = answer(client, h, B).json()
    root = admin(client)
    r = client.post(
        f"/api/v1/admin/content/question/{NURSE}/{B}/corrections",
        headers=root,
        json={
            "prompt": "How do you keep a patient's family informed during an ordinary shift?",
            "change_note": "Clearer.",
        },
    )
    assert r.status_code in (200, 201), r.text
    answer(client, h, A)
    answer(client, h, A)
    [o] = offer(client, h)["offers"]
    assert o["version"] == 2
    kept = client.get(f"/api/v1/careers/{NURSE}/questions/{B}/answers", headers=h).json()
    assert [a["content_version"] for a in kept] == [1] and kept[0]["id"] == old["id"]


def test_the_follow_up_is_its_own_answer_kept_beside_the_original(client):
    h = nurse(client)
    answer(client, h, A)
    original = answer(client, h, A).json()
    follow = answer(client, h, B, follows_up_answer_id=original["id"])
    assert follow.status_code == 201, follow.text
    f = follow.json()
    assert f["follows_up_answer_id"] == original["id"] and f["id"] != original["id"]
    assert f["conditions"]["labels"]  # its own conditions (prompt 3)
    beside = offer(client, h)["answered"]
    assert [(x["answer_id"], x["score"], x["follows_up_answer_id"]) for x in beside] == [
        (f["id"], f["score"], original["id"])
    ]
    # The original is unchanged: its own score, nothing merged or averaged.
    mine = client.get(f"/api/v1/careers/{NURSE}/questions/{A}/answers", headers=h).json()
    assert {a["id"]: a["score"] for a in mine}[original["id"]] == original["score"]
    assert "average" not in str(offer(client, h)).lower()


def test_a_link_without_a_reviewed_relationship_or_to_another_account_is_refused(client):
    h = nurse(client)
    unrelated = answer(client, h, "m-pressure-0").json()
    r = answer(client, h, B, follows_up_answer_id=unrelated["id"])
    assert r.status_code == 400 and r.json()["error"]["code"] == "not_a_follow_up"
    other = nurse(client, email="ola@example.com")
    theirs = answer(client, other, A).json()
    assert answer(client, h, B, follows_up_answer_id=theirs["id"]).status_code == 404
    assert answer(client, h, B, follows_up_answer_id="no-such-answer").status_code == 404


def test_another_accounts_answers_dont_decide_this_accounts_offer(client):
    mine = nurse(client)
    theirs = nurse(client, email="ola@example.com")
    answer(client, theirs, A)
    answer(client, theirs, A)
    answer(client, theirs, B)
    got = offer(client, mine)
    assert got["status"] == "not_yet" and got["scored_answers"] == 0
    answer(client, mine, A)
    answer(client, mine, A)
    [o] = offer(client, mine)["offers"]
    assert o["attempts"] == 0 and o["exposure"] == "Not previously attempted in this app"


def test_offers_stay_in_the_career_and_the_gate_refuses_bad_relationships(client):
    # Every shipped relationship stays in its career; none names another.
    assert all(r.to_track is None for r in RELATIONSHIPS)
    h = nurse(client)
    answer(client, h, A)
    answer(client, h, A)
    assert {o["track"] for o in offer(client, h)["offers"]} == {NURSE}

    def exists(track, qid):
        return get_question(track, qid) is not None

    good = FollowUp(NURSE, A, B, "Keeping people informed", "A different audience", "Reviewed.")
    assert problems((good,), exists) == []
    missing = FollowUp(NURSE, A, "no-such-question", "x", "y", "Reviewed.")
    unreviewed = FollowUp(NURSE, A, B, "x", "y", "  ")
    self_link = FollowUp(NURSE, A, A, "x", "y", "Reviewed.")
    found = problems((missing, unreviewed, self_link), exists)
    assert any("isn't in the registered-nurse bank" in p for p in found)
    assert any("not reviewed" in p for p in found)
    assert any("can't follow up itself" in p for p in found)
