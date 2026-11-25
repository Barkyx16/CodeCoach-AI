"""Disputed feedback stops shaping automatic plans (Volume 12, prompt 7; docs/DISPUTES.md): a
dispute changes what's recommended, not what happened. Timing cases (before planning, after, while
a version is being worked out, a version built before it), reinstating, commitments kept and
labelled, scores untouched, other accounts refused. Synthetic data only."""

from app.services import roadmap as roadmap_module
from tests.conftest import auth_headers, register
from tests.test_roadmap import answer, plan

TRACK = "registered-nurse"
WEAK_Q = "e-good-0"
# Long enough to score; scores 52 and misses "Backs it up with a concrete example" and "Lays out
# clear steps or habits".
WEAK = (
    "Patient assessment is something every nurse does on the ward. It is part of the job and it is "
    "important to do it well because patients depend on nurses. I do it on my shifts like everyone else "
    "on the team and I think it is a key skill to have in this job."
)
EXAMPLE = "Backs it up with a concrete example"
STEPS = "Lays out clear steps or habits"


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track=TRACK))


def setup(client, h):
    """One weak answer: the plan retries its question (and offers a baseline beside it)."""
    weak = answer(client, h, TRACK, WEAK_Q, WEAK)
    assert weak["score"] < 70 and weak["evidence_level"] == "sufficient"
    return weak


def flag(client, h, answer_id, criterion, kind="disagree", note="I did give an example"):
    r = client.post(
        f"/api/v1/me/answers/{answer_id}/flags",
        headers=h,
        json={"criterion": criterion, "kind": kind, "note": note},
    )
    assert r.status_code == 200, r.text
    return next(f for f in r.json()["flags"] if f["criterion"] == criterion)


def retry_of(p):
    return next(i for i in p["items"] if i["kind"] == "retry" and i["href"].endswith(f"/{WEAK_Q}"))


def review_of(p):
    return next(i for i in p["items"] if i["kind"] == "review" and f"/{WEAK_Q}?" in i["href"])


def new_version(client, h):
    """Something that makes the next version (here: goals saved)."""
    client.put("/api/v1/me/goals", headers=h, json={"setup_skipped": True})
    return plan(client, h)


def test_without_disputes_the_retry_names_the_missed_points(client):
    h = nurse(client)
    setup(client, h)
    p = plan(client, h)
    assert retry_of(p)["reason"].endswith(f"it missed {EXAMPLE.lower()}, {STEPS.lower()}.")
    assert p["withheld"] == [] and retry_of(p)["disputed"] is None


def test_a_point_disputed_before_planning_never_shapes_a_recommendation(client):
    h = nurse(client)
    weak = setup(client, h)
    f = flag(client, h, weak["id"], EXAMPLE)
    assert f["disputed"] and f["disputed_at"] and f["reinstated_at"] is None
    p = plan(client, h)
    retry = retry_of(p)
    assert EXAMPLE.lower() not in retry["reason"] and retry["reason"].endswith(f"it missed {STEPS.lower()}.")
    assert retry["disputed"] is None  # it no longer comes from the disputed point
    [w] = p["withheld"]
    assert w["text"].startswith(f"Not suggested: adding “{EXAMPLE}” to “")
    assert "you disputed this point on " in w["text"] and w["href"].endswith(f"?answer={weak['id']}")
    # The retry itself still comes from the score, which is evidence the dispute doesn't touch.
    assert retry["reason"].startswith("Your best score is 52/100")


def test_disputing_after_suggestions_exist_labels_exactly_the_derived_ones(client):
    h = nurse(client)
    weak = setup(client, h)
    before = plan(client, h)
    flag(client, h, weak["id"], EXAMPLE)
    after = plan(client, h)
    assert after["version"] == before["version"]  # nothing regenerated, nothing removed
    assert [i["id"] for i in after["items"]] == [i["id"] for i in before["items"]]
    labelled = {i["id"]: i["disputed"] for i in after["items"] if i["disputed"]}
    assert list(labelled) == [retry_of(after)["id"]]  # only the retry cites that point
    note = labelled[retry_of(after)["id"]]
    assert note["text"].startswith("Based on feedback you disputed on ") and note["text"].endswith(
        f": “{EXAMPLE}”."
    )
    assert note["href"].endswith(f"?answer={weak['id']}")
    assert review_of(after)["disputed"] is None  # the feedback as a whole isn't disputed


def test_disputing_the_feedback_overall_withholds_what_only_it_supported(client):
    h = nurse(client)
    weak = setup(client, h)
    flag(client, h, weak["id"], "Overall")
    p = plan(client, h)
    assert not any(i["kind"] in ("retry", "review") and WEAK_Q in (i["href"] or "") for i in p["items"])
    assert any(
        w["text"].startswith("Not suggested: retrying “") and "you disputed that feedback on" in w["text"]
        for w in p["withheld"]
    )


def test_independent_evidence_still_counts(client):
    h = nurse(client)
    weak = setup(client, h)
    other = answer(client, h, TRACK, WEAK_Q, WEAK + " It matters.")  # another weak answer, not disputed
    flag(client, h, weak["id"], "Overall")
    p = plan(client, h)
    retry = retry_of(p)
    assert retry["reason"].startswith(f"Your best score is {other['score']}/100")
    assert retry["disputed"] is None and review_of(p)["href"].endswith(f"?answer={other['id']}")


def test_a_dispute_is_about_one_answer_not_every_answer_that_missed_the_point(client):
    h = nurse(client)
    weak = setup(client, h)
    flag(client, h, weak["id"], EXAMPLE)
    latest = answer(client, h, TRACK, WEAK_Q, WEAK + " It matters.")  # misses it too; not disputed
    assert any(p["label"] == EXAMPLE and not p["covered"] for p in latest["points"])
    p = plan(client, h)
    assert EXAMPLE.lower() in retry_of(p)["reason"] and retry_of(p)["disputed"] is None
    assert not any(EXAMPLE in w["text"] for w in p["withheld"])


def test_editing_a_disputes_note_keeps_it_standing_from_when_it_was_made(client):
    h = nurse(client)
    weak = setup(client, h)
    first = flag(client, h, weak["id"], EXAMPLE)
    again = flag(client, h, weak["id"], EXAMPLE, note="I named the patient and what I did")
    assert again["id"] == first["id"] and again["disputed"] and again["reinstated_at"] is None
    assert (
        again["disputed_at"] == first["disputed_at"] and again["note"] == "I named the patient and what I did"
    )
    assert EXAMPLE.lower() not in retry_of(plan(client, h))["reason"]


def test_unclear_is_not_a_dispute(client):
    h = nurse(client)
    weak = setup(client, h)
    f = flag(client, h, weak["id"], EXAMPLE, kind="unclear")
    assert f["disputed"] is False and f["disputed_at"] is None
    p = plan(client, h)
    assert EXAMPLE.lower() in retry_of(p)["reason"] and p["withheld"] == []


def test_a_dispute_made_while_a_version_is_worked_out_is_respected_when_it_is_published(client, monkeypatch):
    h = nurse(client)
    weak = setup(client, h)
    real = roadmap_module.Roadmap._generate
    calls = {"n": 0}

    def disputed_meanwhile(self, user, track, goal, ev, avoid):
        specs = real(self, user, track, goal, ev, avoid)
        calls["n"] += 1
        if calls["n"] == 1:  # another tab disputes the point while this one is working the plan out
            flag(client, h, weak["id"], EXAMPLE)
        return specs

    monkeypatch.setattr(roadmap_module.Roadmap, "_generate", disputed_meanwhile)
    p = plan(client, h)
    assert calls["n"] == 2  # worked out again before publishing
    assert EXAMPLE.lower() not in retry_of(p)["reason"] and retry_of(p)["disputed"] is None
    assert any(w["text"].startswith(f"Not suggested: adding “{EXAMPLE}”") for w in p["withheld"])


def test_a_version_built_before_a_dispute_is_not_reused_for_the_next(client):
    h = nurse(client)
    weak = setup(client, h)
    v1 = plan(client, h)
    assert EXAMPLE.lower() in retry_of(v1)["reason"]
    flag(client, h, weak["id"], EXAMPLE)
    v2 = new_version(client, h)
    assert v2["version"] == v1["version"] + 1
    assert EXAMPLE.lower() not in retry_of(v2)["reason"] and retry_of(v2)["disputed"] is None
    # The earlier version's words are kept as they were.
    exported = client.get("/api/v1/me/export", headers=h).json()["practice_plans"]
    first = next(x for x in exported if x["version"] == v1["version"])
    assert any(a["kind"] == "retry" for a in first["activities"])


def test_the_same_state_after_a_reload_and_on_a_second_device(client):
    h = nurse(client)
    weak = setup(client, h)
    plan(client, h)
    flag(client, h, weak["id"], EXAMPLE)
    second = auth_headers(
        client.post(
            "/api/v1/auth/login", json={"email": "ada@example.com", "password": "CorrectHorse42"}
        ).json()
    )
    a, b = plan(client, h), plan(client, second)
    assert retry_of(a)["disputed"] == retry_of(b)["disputed"] is not None
    assert a["withheld"] == b["withheld"]


def test_reinstating_is_deliberate_and_nothing_restores_by_itself(client):
    h = nurse(client)
    weak = setup(client, h)
    f = flag(client, h, weak["id"], EXAMPLE)
    v1 = plan(client, h)
    # New practice and new versions don't reinstate it.
    answer(client, h, TRACK, "e-good-3")
    v2 = new_version(client, h)
    assert v2["version"] > v1["version"] and EXAMPLE.lower() not in retry_of(v2)["reason"]
    review = client.get(f"/api/v1/me/answers/{weak['id']}/review", headers=h).json()
    assert next(x for x in review["flags"] if x["id"] == f["id"])["disputed"] is True
    # Reinstated: recorded, the flag and its note kept; the plan's line says it can come back.
    r = client.post(f"/api/v1/me/answers/{weak['id']}/flags/{f['id']}/reinstate", headers=h)
    kept = next(x for x in r.json()["flags"] if x["id"] == f["id"])
    assert kept["disputed"] is False and kept["reinstated_at"] and kept["note"] == "I did give an example"
    again = client.post(f"/api/v1/me/answers/{weak['id']}/flags/{f['id']}/reinstate", headers=h)
    assert (
        next(x for x in again.json()["flags"] if x["id"] == f["id"])["reinstated_at"] == kept["reinstated_at"]
    )
    now = plan(client, h)
    assert now["withheld"] and all(w["reinstated"] for w in now["withheld"])
    # At the plan's next update it can be suggested again.
    client.put("/api/v1/me/goals", headers=h, json={"setup_skipped": False, "focus_areas": ["triage"]})
    v3 = plan(client, h)
    assert (
        v3["version"] > now["version"] and EXAMPLE.lower() in retry_of(v3)["reason"] and v3["withheld"] == []
    )


def test_scores_feedback_and_verdicts_stay_as_they_were(client):
    h = nurse(client)
    weak = setup(client, h)
    before = client.get(f"/api/v1/careers/{TRACK}/questions/{WEAK_Q}/answers", headers=h).json()
    flag(client, h, weak["id"], EXAMPLE)
    flag(client, h, weak["id"], "Overall")
    plan(client, h)
    after = client.get(f"/api/v1/careers/{TRACK}/questions/{WEAK_Q}/answers", headers=h).json()
    keys = ("id", "answer", "score", "rating", "summary", "points", "evidence_level", "rubric_version")
    assert [{k: a[k] for k in keys} for a in after] == [{k: a[k] for k in keys} for a in before]


def test_accepted_actions_and_scheduled_entries_stay_and_are_labelled(client):
    from tests.test_actions import BASE, accept
    from tests.test_review import STRONG as RSTRONG
    from tests.test_review import WEAK as RWEAK
    from tests.test_review import review, round_with

    h = nurse(client)
    iv = round_with(client, h, [RSTRONG, RWEAK, RWEAK, None, RSTRONG])
    rv = review(client, h, iv)
    imp = next(i for i in rv["improvements"] if i["key"].startswith("point:"))
    label = imp["key"].removeprefix("point:")
    action = accept(client, h, iv, imp["key"]).json()
    client.post(f"{BASE}/{action['id']}/occurrences", headers=h, json={"on_date": "2026-11-20"})
    # A plan step on the schedule too.
    setup(client, h)
    step = retry_of(plan(client, h))
    entry = client.post(
        "/api/v1/me/schedule",
        headers=h,
        json={"kind": "plan_item", "ref": step["id"], "on_date": "2026-11-21", "all_day": True},
    )
    assert entry.status_code in (200, 201), entry.text
    # Dispute the improvement's point on one of the round's answers, and the plan step's point.
    answered = next(
        it["feedback"]["id"]
        for it in rv["items"]
        if it.get("feedback")
        and any(p["label"] == label and not p["covered"] for p in it["feedback"]["points"])
    )
    flag(client, h, answered, label)
    weak_answer = client.get(f"/api/v1/careers/{TRACK}/questions/{WEAK_Q}/answers", headers=h).json()[0]
    flag(client, h, weak_answer["id"], EXAMPLE)
    got = client.get(f"{BASE}/{action['id']}", headers=h).json()
    assert got["status"] == "open" and len(got["occurrences"]) == 1  # nothing deleted or cancelled
    assert (
        got["disputed"]["text"].startswith("Based on feedback you disputed on ")
        and label in got["disputed"]["text"]
    )
    entries = client.get(
        "/api/v1/me/schedule", headers=h, params={"from": "2026-11-15", "to": "2026-12-01"}
    ).json()
    by_kind = {e["kind"]: e for e in entries}
    assert by_kind["accepted_action"]["status"] == "scheduled" and by_kind["accepted_action"]["disputed"]
    assert by_kind["plan_item"]["status"] == "scheduled" and by_kind["plan_item"]["disputed"]


def test_another_accounts_feedback_and_disputes_are_refused(client):
    h = nurse(client)
    weak = setup(client, h)
    f = flag(client, h, weak["id"], EXAMPLE)
    other = nurse(client, email="grace@example.com")
    assert (
        client.post(
            f"/api/v1/me/answers/{weak['id']}/flags",
            headers=other,
            json={"criterion": STEPS, "kind": "disagree"},
        ).status_code
        == 404
    )
    assert (
        client.post(f"/api/v1/me/answers/{weak['id']}/flags/{f['id']}/reinstate", headers=other).status_code
        == 404
    )
    mine = client.get(f"/api/v1/me/answers/{weak['id']}/review", headers=h).json()["flags"]
    assert [(x["kind"], x["disputed"], x["reinstated_at"]) for x in mine] == [
        ("disagree", True, None)
    ]  # nothing changed
    # Their own plan is untouched by my dispute.
    setup(client, other)
    assert EXAMPLE.lower() in retry_of(plan(client, other))["reason"]


def test_the_export_keeps_disputes_and_derivations(client):
    h = nurse(client)
    weak = setup(client, h)
    flag(client, h, weak["id"], EXAMPLE)
    plan(client, h)
    doc = client.get("/api/v1/me/export", headers=h).json()
    [f] = doc["answer_reviews"]["flags"]
    assert f["kind"] == "disagree" and f["disputed_at"] and f["reinstated_at"] is None
    [p] = doc["practice_plans"]
    retry = next(a for a in p["activities"] if a["kind"] == "retry")
    assert {"answer_id": weak["id"], "criterion": STEPS} in retry["derived_from"]
    assert {"answer_id": weak["id"], "criterion": EXAMPLE} not in retry["derived_from"]
    assert p["withheld"] and p["withheld"][0].startswith(f"Not suggested: adding “{EXAMPLE}”")
