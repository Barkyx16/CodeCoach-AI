"""Practice related to an accepted improvement (Volume 13, prompt 4; docs/ACCEPTED_ACTIONS.md):
retries of the question it came from and follow-ups to it, found by stored links only, each with its
own score and comparison, never marking the action done or claiming it worked. Synthetic data."""

from sqlalchemy import delete

from app.models import PracticeAnswer
from tests.conftest import auth_headers, register
from tests.test_journey_canary import STRONG

TRACK = "registered-nurse"
Q = "e-accuracy-0"  # "Checking your patient assessment work"
FOLLOW = "e-accuracy-1"  # its reviewed follow-up
SHORT = "I would check it again."
MIDDLING = (
    "I checked the patient and looked at the chart. I asked a colleague and we talked about it, then I wrote "
    "it down for the next shift so everyone knew what had happened on the ward that night. It was a busy "
    "shift and there were a lot of patients, so we did our best as a team and kept going until the morning."
)


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track=TRACK))


def accepted(client, h):
    """A one-question round, its review's first improvement accepted (its practice: retry question 0)."""
    iv = client.post(
        "/api/v1/interviews",
        headers=h,
        json={"kind": "questions", "question_ids": [Q], "duration_minutes": 15},
    ).json()
    r = client.post(
        f"/api/v1/interviews/{iv['id']}/answers",
        headers=h,
        json={"question_index": 0, "answer": STRONG, "source": "typed"},
    )
    assert r.status_code == 200, r.text
    imp = client.get(f"/api/v1/interviews/{iv['id']}/review", headers=h).json()["improvements"][0]
    assert imp["practice"]["retry_index"] == 0
    action = client.post(
        "/api/v1/me/actions", headers=h, json={"source": {"interview_id": iv["id"], "key": imp["key"]}}
    ).json()
    return iv["id"], action


def retry(client, h, iv, text=STRONG):
    r = client.post(f"/api/v1/interviews/{iv}/questions/0/retries", headers=h, json={"answer": text})
    assert r.status_code in (200, 201), r.text
    return r.json()["latest"]


def follow_up(client, h, parent_id, text=MIDDLING):
    r = client.post(
        f"/api/v1/careers/{TRACK}/questions/{FOLLOW}/answers",
        headers=h,
        json={"answer": text, "follows_up_answer_id": parent_id},
    )
    assert r.status_code == 201, r.text
    return r.json()


def practice(client, h, action_id):
    r = client.get(f"/api/v1/me/actions/{action_id}/practice", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_a_retry_then_a_follow_up_are_both_listed_in_order_with_their_own_scores(client):
    h = nurse(client)
    iv, action = accepted(client, h)
    first = retry(client, h, iv)
    second = follow_up(client, h, first["id"])
    p = practice(client, h, action["id"])
    assert p["linked"] and p["count"] == 2
    assert [i["kind"] for i in p["items"]] == ["retry", "follow_up"]
    assert [i["answer_id"] for i in p["items"]] == [first["id"], second["id"]]
    r, f = p["items"]
    assert r["score"] == first["score"] and f["score"] == second["score"]
    assert r["question_id"] == Q and f["question_id"] == FOLLOW
    assert f["question_title"] == "Checking your medication administration work"
    assert f["note"].startswith("A different question about the same thing: not a retry")
    assert r["comparison"]["outcome"] == "partially_comparable"  # the conditions differed (a timed round)
    assert f["comparison"]["outcome"] == "incompatible"  # a different question: scores aren't compared
    assert p["origin"]["score"] is not None
    # Never a claim it worked; nothing averaged.
    assert "worked" not in p["note"] and "average" not in str(p).lower()


def test_a_lower_follow_up_is_shown_as_lower_and_nothing_is_averaged(client):
    h = nurse(client)
    iv, action = accepted(client, h)
    origin = practice(client, h, action["id"])["origin"]
    low = follow_up(client, h, origin["answer_id"])
    p = practice(client, h, action["id"])
    [item] = p["items"]
    assert item["score"] == low["score"] < origin["score"]
    assert set(p) == {"action_id", "count", "items", "submissions", "origin", "linked", "note", "disputed"}


def test_unrelated_answers_and_earlier_practice_never_count(client):
    h = nurse(client)
    iv = client.post(
        "/api/v1/interviews",
        headers=h,
        json={"kind": "questions", "question_ids": [Q], "duration_minutes": 15},
    ).json()
    client.post(
        f"/api/v1/interviews/{iv['id']}/answers", headers=h, json={"question_index": 0, "answer": STRONG}
    )
    before = retry(client, h, iv["id"])  # practised before accepting it: not practice of the action
    imp = client.get(f"/api/v1/interviews/{iv['id']}/review", headers=h).json()["improvements"][0]
    action = client.post(
        "/api/v1/me/actions", headers=h, json={"source": {"interview_id": iv["id"], "key": imp["key"]}}
    ).json()
    # The same question answered on its own, and another question: no stored link to the action.
    client.post(f"/api/v1/careers/{TRACK}/questions/{Q}/answers", headers=h, json={"answer": STRONG})
    client.post(f"/api/v1/careers/{TRACK}/questions/e-good-0/answers", headers=h, json={"answer": STRONG})
    p = practice(client, h, action["id"])
    assert p["count"] == 0 and p["items"] == []
    # A follow-up after accepting, to the retry made before it, is practice since accepting.
    f = follow_up(client, h, before["id"])
    assert [i["answer_id"] for i in practice(client, h, action["id"])["items"]] == [f["id"]]


def test_the_action_is_never_marked_done_or_moved_by_its_practice(client):
    h = nurse(client)
    iv, action = accepted(client, h)
    sched = client.post(
        f"/api/v1/me/actions/{action['id']}/occurrences", headers=h, json={"on_date": "2026-12-01"}
    )
    assert sched.status_code in (200, 201), sched.text
    before = client.get(f"/api/v1/me/actions/{action['id']}", headers=h).json()
    retry(client, h, iv)
    follow_up(client, h, practice(client, h, action["id"])["origin"]["answer_id"])
    after = client.get(f"/api/v1/me/actions/{action['id']}", headers=h).json()
    assert after["status"] == before["status"] == "open" and after["done_at"] is None
    assert after["occurrences"] == before["occurrences"]
    assert after["revision"] == before["revision"]


def test_deleting_a_related_answer_drops_it_and_says_one_fewer(client):
    h = nurse(client)
    iv, action = accepted(client, h)
    first = retry(client, h, iv)
    origin = practice(client, h, action["id"])["origin"]["answer_id"]
    to_origin = follow_up(client, h, origin)
    to_retry = follow_up(client, h, first["id"])
    assert practice(client, h, action["id"])["count"] == 3
    with client.app.state.session_factory() as db:
        db.execute(delete(PracticeAnswer).where(PracticeAnswer.id == first["id"]))
        db.commit()
    p = practice(client, h, action["id"])
    # The retry is gone, and the follow-up that pointed at it is unlinked (its stored link is
    # cleared), so it's no longer related either; the one to the original stays.
    assert p["count"] == 1 and [i["answer_id"] for i in p["items"]] == [to_origin["id"]]
    assert to_retry["id"] not in {i["answer_id"] for i in p["items"]}
    assert client.get(f"/api/v1/me/actions/{action['id']}", headers=h).json()["status"] == "open"


def test_another_accounts_answers_and_actions_never_show(client):
    h = nurse(client)
    iv, action = accepted(client, h)
    other = nurse(client, email="bea@example.com")
    client.post(f"/api/v1/careers/{TRACK}/questions/{Q}/answers", headers=other, json={"answer": STRONG})
    client.post(
        f"/api/v1/careers/{TRACK}/questions/{FOLLOW}/answers", headers=other, json={"answer": MIDDLING}
    )
    origin = practice(client, h, action["id"])["origin"]["answer_id"]
    refused = client.post(
        f"/api/v1/careers/{TRACK}/questions/{FOLLOW}/answers",
        headers=other,
        json={"answer": MIDDLING, "follows_up_answer_id": origin},
    )
    assert refused.status_code == 404  # they can't link to this account's answer
    assert practice(client, h, action["id"])["count"] == 0
    assert client.get(f"/api/v1/me/actions/{action['id']}/practice", headers=other).status_code == 404


def test_an_answer_too_short_to_score_is_listed_as_such_not_as_zero(client):
    h = nurse(client)
    iv, action = accepted(client, h)
    retry(client, h, iv, SHORT)
    [item] = practice(client, h, action["id"])["items"]
    assert item["scoring"] == "too_short" and item["score"] is None


def test_a_disputed_points_action_still_shows_its_practice_labelled(client):
    h = nurse(client)
    iv, action = accepted(client, h)
    first = retry(client, h, iv)
    origin = practice(client, h, action["id"])["origin"]["answer_id"]
    r = client.post(
        f"/api/v1/me/answers/{origin}/flags", headers=h, json={"criterion": "Overall", "kind": "disagree"}
    )
    assert r.status_code == 200, r.text
    p = practice(client, h, action["id"])
    assert p["disputed"] is not None and [i["answer_id"] for i in p["items"]] == [first["id"]]


def test_the_export_carries_each_actions_related_attempts_by_id(client):
    h = nurse(client)
    iv, action = accepted(client, h)
    first = retry(client, h, iv)
    second = follow_up(client, h, first["id"])
    v2 = client.get("/api/v1/me/export", headers=h, params={"version": 2}).json()
    [exported] = v2["accepted_actions"] if "accepted_actions" in v2 else v2["data"]["accepted_actions"]
    assert exported["related_attempts"] == [first["id"], second["id"]]
    v1 = client.get("/api/v1/me/export", headers=h).json()
    assert (v1.get("accepted_actions") or v1["data"]["accepted_actions"])[0]["related_practice"] == 2


def test_an_improvement_without_a_practice_link_says_so(client):
    h = nurse(client)
    iv, action = accepted(client, h)
    with client.app.state.session_factory() as db:
        from app.models import AcceptedAction

        row = db.get(AcceptedAction, action["id"])
        row.practice_href = None
        db.commit()
    p = practice(client, h, action["id"])
    assert p["linked"] is False and p["count"] == 0 and "no practice linked" in p["note"]
