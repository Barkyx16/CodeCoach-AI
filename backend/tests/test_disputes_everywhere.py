"""A dispute counts wherever the advice is reused (Volume 14, prompt 9; docs/DISPUTES.md): an
interview summary counts a disputed point and says so, and doesn't suggest one missed only where
it's disputed; the review queue doesn't schedule an item whose only reason is disputed feedback,
and a disputed score doesn't move its ladder; withdrawing restores each place; the feedback itself
never changes; the export marks what was left out, by id. One rule (app/services/disputes.py).
Synthetic data only."""

from tests.test_disputes import flag
from tests.test_review import STRONG, WEAK, review
from tests.test_roadmap import answer

TRACK = "registered-nurse"
QUEUE = "/api/v1/me/reviews"


def nurse(client, email="ada@example.com"):
    from tests.conftest import auth_headers, register

    return auth_headers(register(client, email=email, career_track=TRACK))


QUESTIONS = ["e-good-0", "e-steps-0", "e-time-0", "e-mistake-0", "e-explain-0"]


def fixed_round(client, h, answers):
    """A round of these exact questions (so which points rank first is the same every run)."""
    iv = client.post(
        "/api/v1/interviews", headers=h, json={"kind": "questions", "track": TRACK, "question_ids": QUESTIONS}
    )
    assert iv.status_code in (200, 201), iv.text
    iv_id = iv.json()["id"]
    for i, a in enumerate(answers):
        if a is None:
            client.post(f"/api/v1/interviews/{iv_id}/skip", headers=h, json={"question_index": i})
        else:
            r = client.post(
                f"/api/v1/interviews/{iv_id}/answers",
                headers=h,
                json={"question_index": i, "answer": a, "source": "typed"},
            )
            assert r.status_code in (200, 201), r.text
    return iv_id


def a_round(client, h):
    iv = fixed_round(client, h, [STRONG, WEAK, WEAK, None, STRONG])
    r = review(client, h, iv)
    imp = r["improvements"][0]
    assert imp["key"].startswith("point:")
    label = imp["title"]
    missing = [
        i
        for i in r["items"]
        if i["feedback"] and any(not p["covered"] and p["label"] == label for p in i["feedback"]["points"])
    ]
    assert len(missing) >= 2
    return iv, r, label, missing


def reinstate(client, h, answer_id, flag_id):
    r = client.post(f"/api/v1/me/answers/{answer_id}/flags/{flag_id}/reinstate", headers=h)
    assert r.status_code == 200, r.text


def feedback_of(r):
    return [(i["key"], i["feedback"]) for i in r["items"]]


def test_a_summary_counts_a_disputed_point_says_so_and_stops_suggesting_it_when_all_are_disputed(client):
    h = nurse(client)
    iv, before, label, missing = a_round(client, h)
    answered = sum(1 for i in before["items"] if i["feedback"])
    n = len(missing)
    imp = next(i for i in before["improvements"] if i["title"] == label)
    assert imp["why"].endswith(f"Missing in {n} of {answered} answers.") and imp["dispute"] is None

    first = flag(client, h, missing[0]["feedback"]["id"], label)
    one = review(client, h, iv)
    imp = next(i for i in one["improvements"] if i["title"] == label)
    assert imp["why"].endswith(f"Missing in {n} of {answered} answers, one disputed.")
    assert imp["dispute"]["answer_id"] == missing[0]["feedback"]["id"]
    assert missing[0]["key"] not in [e["item_key"] for e in imp["evidence"]]  # not used as evidence
    assert imp["practice"]["retry_index"] != missing[0]["index"]  # nor to choose the retry
    assert feedback_of(one) == feedback_of(before)  # the feedback itself is unchanged

    flags = [first] + [flag(client, h, m["feedback"]["id"], label) for m in missing[1:]]
    allof = review(client, h, iv)
    assert label not in [i["title"] for i in allof["improvements"]]
    [left] = [d for d in allof["disputed_points"] if d["label"] == label]
    assert (left["missing"], left["disputed"]) == (n, n)
    assert left["text"] == (
        f"Not suggested: “{label}” (missing in {n} of {answered} answers, all disputed). Left out because of "
        "feedback you disputed, not because there's nothing to practise."
    )
    assert feedback_of(allof) == feedback_of(before)

    # Withdrawing one dispute restores it, counted and said.
    reinstate(client, h, missing[-1]["feedback"]["id"], flags[-1]["id"])
    back = review(client, h, iv)
    imp = next(i for i in back["improvements"] if i["title"] == label)
    disputed_now = n - 1
    words = {1: "one", 2: "two", 3: "three"}
    assert imp["why"].endswith(f"Missing in {n} of {answered} answers, {words[disputed_now]} disputed.")
    assert back["disputed_points"] == [d for d in back["disputed_points"] if d["label"] != label]


def test_an_improvement_already_accepted_stays_with_its_dispute_said(client):
    h = nurse(client)
    iv, _, label, missing = a_round(client, h)
    key = f"point:{label}"
    r = client.post("/api/v1/me/actions", headers=h, json={"source": {"interview_id": iv, "key": key}})
    assert r.status_code == 201, r.text
    for m in missing:
        flag(client, h, m["feedback"]["id"], label)
    after = review(client, h, iv)
    imp = next(i for i in after["improvements"] if i["key"] == key)
    assert imp["action_id"] == r.json()["id"] and imp["dispute"] is not None
    assert key not in [d["key"] for d in after["disputed_points"]]


def save_for_review(client, h, iv, question_id):
    r = client.post(QUEUE, headers=h, json={"track": TRACK, "question_id": question_id, "session_id": iv})
    assert r.status_code in (200, 201), r.text
    return r.json()


def all_items(q):
    return q["due"] + q["upcoming"] + q["disputed"]


def test_the_queue_doesn_t_schedule_an_item_whose_only_reason_is_disputed_feedback(client):
    h = nurse(client)
    iv, r, label, missing = a_round(client, h)
    weak = missing[0]
    qid = weak["question_id"]
    q = save_for_review(client, h, iv, qid)
    [item] = all_items(q)
    assert q["disputed"] == [] and item["dispute"] is None
    f = flag(client, h, weak["feedback"]["id"], "Overall")
    q = client.get(QUEUE, headers=h).json()
    assert q["due"] == q["upcoming"] == []
    [held] = q["disputed"]
    assert held["id"] == item["id"] and held["dispute"]["answer_id"] == weak["feedback"]["id"]
    assert held["why"].startswith(
        "Not scheduled: you saved it from an interview answer whose feedback you disputed"
    )
    # Nothing else offers it: the schedule's list of things to schedule follows the queue.
    offered = client.get("/api/v1/me/schedule/schedulable", headers=h).json()
    assert item["id"] not in [o["ref"] for o in offered if o["kind"] == "review_item"]
    # A dispute on one point doesn't dispute the score, so it doesn't hold the item.
    reinstate(client, h, weak["feedback"]["id"], f["id"])
    flag(client, h, weak["feedback"]["id"], label)
    q = client.get(QUEUE, headers=h).json()
    assert q["disputed"] == [] and len(q["due"] + q["upcoming"]) == 1
    offered = client.get("/api/v1/me/schedule/schedulable", headers=h).json()
    assert item["id"] in [o["ref"] for o in offered if o["kind"] == "review_item"]


def test_an_item_with_another_reason_keeps_its_schedule_and_a_disputed_score_doesn_t_move_the_ladder(client):
    h = nurse(client)
    iv, r, label, missing = a_round(client, h)
    weak = missing[0]
    qid = weak["question_id"]
    save_for_review(client, h, iv, qid)
    flag(client, h, weak["feedback"]["id"], "Overall")
    # Answered again (undisputed): another reason, so it's scheduled again and says which is disputed.
    again = answer(client, h, TRACK, qid, STRONG)
    q = client.get(QUEUE, headers=h).json()
    [item] = q["due"] + q["upcoming"]
    assert q["disputed"] == [] and item["reviews"] == 1 and item["last_score"] == again["score"]
    assert "One reason it's here is feedback you disputed" in item["why"]
    # A newer answer, disputed overall: its score doesn't move the ladder.
    later = answer(client, h, TRACK, qid, WEAK)
    f = flag(client, h, later["id"], "Overall")
    q = client.get(QUEUE, headers=h).json()
    [item] = q["due"] + q["upcoming"]
    assert item["reviews"] == 1 and item["last_score"] == again["score"]
    # Counted again: the next look uses it.
    reinstate(client, h, later["id"], f["id"])
    q = client.get(QUEUE, headers=h).json()
    [item] = q["due"] + q["upcoming"]
    assert item["reviews"] == 2 and item["last_score"] == later["score"]


def test_another_accounts_disputes_never_apply(client):
    a = nurse(client)
    iv, before, label, missing = a_round(client, a)
    save_for_review(client, a, iv, missing[0]["question_id"])
    b = nurse(client, "bea@example.com")
    r = client.post(
        f"/api/v1/me/answers/{missing[0]['feedback']['id']}/flags",
        headers=b,
        json={"criterion": label, "kind": "disagree", "note": "Not mine"},
    )
    assert r.status_code == 404
    iv_b, _, label_b, missing_b = a_round(client, b)
    for m in missing_b:
        flag(client, b, m["feedback"]["id"], label_b)
        flag(client, b, m["feedback"]["id"], "Overall")
    after = review(client, a, iv)
    assert after["improvements"] == before["improvements"] and after["disputed_points"] == []
    assert client.get(QUEUE, headers=a).json()["disputed"] == []


def test_the_export_marks_what_was_left_out_because_of_a_dispute_by_id(client):
    h = nurse(client)
    iv, _, label, missing = a_round(client, h)
    q = save_for_review(client, h, iv, missing[0]["question_id"])
    [item] = all_items(q)
    for m in missing:
        flag(client, h, m["feedback"]["id"], label)
    flag(client, h, missing[0]["feedback"]["id"], "Overall")
    doc = client.get("/api/v1/me/export", headers=h).json()
    [interview] = [i for i in doc["interviews"] if i["id"] == iv]
    # The summary's own list, by the same rule: disputing an answer overall also covers points missed
    # only there.
    shown = sorted(d["key"] for d in review(client, h, iv)["disputed_points"])
    assert interview["points_left_out_disputed"] == shown and f"point:{label}" in shown
    [row] = doc["review_queue"]
    assert row["left_out_disputed"] is True
    assert {x["question"] for x in doc["review_queue"]} == {missing[0]["question_id"]}
    assert item["id"]
