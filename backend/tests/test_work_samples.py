"""Work-sample practice (Volume 10, prompt 5; docs/WORK_SAMPLES.md): a short professional artifact
from a fictional brief, checked against the facts the brief supplies. Two formats complete, a
revision that keeps the original, a recovered draft, missing points, an invented detail and claim,
equivalent wording, no AI, hostile text, another account's ids, and briefs that fail their own
checks. Synthetic content and accounts only."""

from __future__ import annotations

import json

from sqlalchemy import func, select

from app.content import validate
from app.models import WorkSampleAttempt, WorkSampleDraft
from app.worksamples import BY_ID, SEED_DIR
from app.worksamples.feedback import specifics

from .conftest import auth_headers, register

MINE = "/api/v1/me/work-samples"
INCIDENT = "ws-incident-update"
BILLING = "ws-billing-explanation"


def send(client, h, brief: str, sections: dict, revision_of: str | None = None):
    body = {"sections": sections, **({"revision_of": revision_of} if revision_of else {})}
    return client.post(f"{MINE}/{brief}/attempts", json=body, headers=h)


GOOD_INCIDENT = {
    "happening": "Since 09:12 UTC some card payments at checkout have been failing.",
    "affected": "About 30% of checkout attempts fail. Browsing, search and gift-card payments still work.",
    "doing": "Engineers are comparing failed and successful payments and have contacted the payment provider. "
    "We don't know the cause yet. Customers can retry or pay with a gift card.",
    "next": "Next update at 10:30 UTC.",
}


def test_the_brief_supplies_the_facts_but_not_the_reference(client):
    listed = client.get("/api/v1/work-samples").json()
    assert {b["id"] for b in listed} == set(BY_ID)
    assert {b["format_label"] for b in listed} >= {"Incident status update", "Customer explanation"}
    body = client.get(f"/api/v1/work-samples/{INCIDENT}").json()
    assert body["facts"][0] == "Card payments at checkout began failing at 09:12 UTC."
    assert [s["label"] for s in body["sections"]] == [
        "What's happening",
        "Who is affected",
        "What we're doing",
        "Next update",
    ]
    assert "Fictional" in body["review_status"] and "Don't paste real" in body["scope_note"]
    text = json.dumps(body)
    for value in BY_ID[INCIDENT].reference.values():
        assert value not in text
    assert client.get("/api/v1/work-samples/ws-nope").status_code == 404


def test_two_formats_complete_with_feedback_quoting_the_learners_own_sentences(client):
    h = auth_headers(register(client))
    incident = send(client, h, INCIDENT, GOOD_INCIDENT)
    assert incident.status_code == 201, incident.text
    fb = incident.json()["feedback"]
    assert (fb["covered"], fb["total"]) == (6, 6) and fb["unsupported"] == [] and fb["claims"] == []
    who = next(p for p in fb["points"] if p["id"] == "who")
    assert who["quote"] == "About 30% of checkout attempts fail."
    assert all(c["ok"] for c in fb["checks"])

    message = (
        "Dear Ms Okafor, I'm sorry we charged you twice for March. A payment retry ran after your first payment. "
        "We refunded the extra $84.20 on 6 April; it takes 3 to 5 business days to reach your account. "
        "Your account is up to date. If you need anything, reply to this email or call 0800 555 0199 and quote TW-48213."
    )
    billing = send(client, h, BILLING, {"message": message}).json()
    assert (billing["feedback"]["covered"], billing["feedback"]["total"]) == (6, 6)
    assert billing["section_labels"] == {"message": "Message"}
    assert billing["reference"]["message"].startswith("Dear Ms Okafor")  # one good approach, after an attempt


def test_missing_points_an_invented_detail_and_an_unsupported_claim_are_named(client):
    h = auth_headers(register(client))
    fb = send(
        client,
        h,
        INCIDENT,
        {
            "happening": "Payments are failing at checkout. It is fixed now.",
            "affected": "Some customers since 14:00.",
            "doing": "We are investigating; it is not resolved yet.",
            "next": "",
        },
    ).json()["feedback"]
    missing = {p["id"] for p in fb["points"] if not p["covered"]}
    assert {"who", "next", "workaround"} <= missing
    who = next(p for p in fb["points"] if p["id"] == "who")
    assert who["quote"] is None and "30%" in who["guidance"]
    assert [u["text"] for u in fb["unsupported"]] == ["14:00"]
    assert fb["unsupported"][0]["sentence"] == "Some customers since 14:00."
    assert [(c["phrase"], c["sentence"]) for c in fb["claims"]] == [
        ("fixed", "It is fixed now.")
    ]  # "not resolved yet" is fine
    # A negated claim on its own is fine: "not resolved", "haven't fixed".
    negated = send(
        client,
        h,
        INCIDENT,
        {
            **GOOD_INCIDENT,
            "doing": "It is not resolved yet, and we haven't fixed the cause. " + GOOD_INCIDENT["doing"],
        },
    ).json()["feedback"]
    assert negated["claims"] == []
    assert fb["revision"].startswith("Change “fixed”")
    assert next(c for c in fb["checks"] if c["id"] == "sections") == {
        "id": "sections",
        "ok": False,
        "text": "Empty: Next update.",
    }


def test_equivalent_wording_counts_and_a_different_order_is_fine(client):
    h = auth_headers(register(client))
    fb = send(
        client,
        h,
        INCIDENT,
        {
            "next": "We'll post again at 10:30 UTC.",
            "happening": "From 9:12 UTC, card payments at checkout are not going through for some people.",
            "affected": "Roughly three in ten checkout attempts. Search and browsing are fine.",
            "doing": "We're looking into it with our payment provider. Anyone affected can try again or use a gift card.",
        },
    ).json()["feedback"]
    assert (fb["covered"], fb["total"]) == (6, 6) and fb["unsupported"] == []  # 9:12 is 09:12


def test_a_revision_is_a_new_attempt_and_the_original_is_kept(client):
    h = auth_headers(register(client))
    first = send(client, h, INCIDENT, {**GOOD_INCIDENT, "next": "We'll update you later."}).json()
    assert first["feedback"]["covered"] == 5
    second = send(client, h, INCIDENT, GOOD_INCIDENT, revision_of=first["id"]).json()
    assert second["revision_of"] == first["id"] and second["feedback"]["covered"] == 6
    again = client.get(f"{MINE}/attempts/{first['id']}", headers=h).json()
    assert again["sections"]["next"] == "We'll update you later." and again["feedback"]["covered"] == 5
    listed = client.get(f"{MINE}/{INCIDENT}/attempts", headers=h).json()
    assert [a["id"] for a in listed] == [second["id"], first["id"]]


def test_a_draft_comes_back_and_a_stale_save_is_a_conflict(client):
    h = auth_headers(register(client))
    url = f"{MINE}/{BILLING}/draft"
    assert client.get(url, headers=h).json() == {
        "save_replay": None,
        "brief_id": BILLING,
        "sections": {"message": ""},
        "revision": 0,
        "updated_at": None,
    }
    body = {
        "sections": {"message": "Dear Ms Okafor,"},
        "expected_revision": 0,
        "client_request_id": "ws-draft-key-01",
    }
    assert client.put(url, json=body, headers=h).json()["revision"] == 1
    assert client.get(url, headers=h).json()["sections"] == {"message": "Dear Ms Okafor,"}
    replay = client.put(url, json=body, headers=h).json()
    assert replay["save_replay"] == {"accepted_revision": 1, "current_revision": 1}
    stale = client.put(
        url, json={**body, "client_request_id": None, "sections": {"message": "other tab"}}, headers=h
    )
    assert (
        stale.status_code == 409
        and stale.json()["error"]["details"]["current"]["sections"]["message"] == "Dear Ms Okafor,"
    )
    odd = client.put(url, json={"sections": {"subject": "x"}, "expected_revision": 1}, headers=h)
    assert odd.status_code == 400 and odd.json()["error"]["code"] == "unknown_section"
    long = client.put(url, json={"sections": {"message": "x" * 4001}, "expected_revision": 1}, headers=h)
    assert long.status_code == 400 and long.json()["error"]["code"] == "section_too_long"


def test_it_works_the_same_when_the_ai_coach_is_unavailable(client):
    class Down:
        name, model = "anthropic", "m"

        def __getattr__(self, _):
            raise AssertionError("work samples don't call the AI coach")

    client.app.state.ai_provider = Down()
    h = auth_headers(register(client))
    made = send(client, h, INCIDENT, GOOD_INCIDENT)
    assert made.status_code == 201 and made.json()["feedback"]["method"].startswith(
        "Fixed checks against this brief, not AI"
    )


def test_hostile_text_is_kept_as_text(client):
    h = auth_headers(register(client))
    hostile = (
        '<img src=x onerror="alert(1)"> payments are failing at checkout </textarea><script>alert(2)</script>'
    )
    made = send(client, h, INCIDENT, {**GOOD_INCIDENT, "happening": hostile + "\x00\x07"}).json()
    assert made["sections"]["happening"] == hostile


def test_another_account_can_not_read_or_build_on_your_attempts(client):
    ada = auth_headers(register(client))
    bea = auth_headers(register(client, email="bea@example.com"))
    secret = "ADA-WORK-5521"
    mine = send(
        client, ada, INCIDENT, {**GOOD_INCIDENT, "next": f"Next update at 10:30 UTC. {secret}"}
    ).json()
    assert client.get(f"{MINE}/attempts/{mine['id']}", headers=bea).status_code == 404
    theirs = send(client, bea, INCIDENT, GOOD_INCIDENT, revision_of=mine["id"])
    assert theirs.status_code == 404  # can't name someone else's attempt as the one revised
    for path in ("/draft", "/attempts"):
        r = client.get(f"{MINE}/{INCIDENT}{path}", headers=bea)
        assert r.status_code == 200 and secret not in r.text and mine["id"] not in r.text


def test_export_includes_work_samples_and_deleting_the_account_removes_them(client):
    data = register(client)
    h = auth_headers(data)
    send(client, h, INCIDENT, GOOD_INCIDENT)
    client.put(
        f"{MINE}/{BILLING}/draft", json={"sections": {"message": "Dear"}, "expected_revision": 0}, headers=h
    )
    exported = client.get("/api/v1/me/export", headers=h).json()["work_samples"]
    assert exported["drafts"] == [{"brief": BILLING, "sections": {"message": "Dear"}, "revision": 1}]
    assert exported["attempts"][0]["sections"] == GOOD_INCIDENT
    gone = client.request(
        "DELETE", "/api/v1/auth/me", headers=h, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    assert gone.status_code == 204
    with client.app.state.session_factory() as db:
        for model in (WorkSampleAttempt, WorkSampleDraft):
            assert (
                db.scalar(select(func.count()).select_from(model).where(model.user_id == data["user"]["id"]))
                == 0
            )


def test_every_brief_mentions_only_its_own_facts_in_its_guidance():
    for brief in BY_ID.values():
        allowed = {k for f in brief.facts for k, _ in specifics(f["text"])}
        for point in brief.required:
            assert {k for k, _ in specifics(point["guidance"])} <= allowed, (brief.id, point["id"])


def test_the_validator_refuses_a_brief_that_fails_its_own_checks(tmp_path, monkeypatch):
    good = json.loads((SEED_DIR / "001-ws-incident-update.json").read_text())
    bad = json.loads(json.dumps(good))
    bad["id"] = "ws-broken"
    bad["reference"]["next"] = "Next update at 11:00 UTC."  # an invented time in the "good" example
    bad["required"][0]["guidance"] = "Say it started at 08:00."  # guidance with a detail the facts lack
    bad["careers"] = ["software-engineer", "astronaut"]
    (tmp_path / "001-ws-broken.json").write_text(json.dumps(bad))
    monkeypatch.setattr(validate, "WORK_SAMPLES_DIR", tmp_path)
    errors = "\n".join(validate.run(None).errors)
    assert "work sample ws-broken: careers must be known career slugs (unknown: ['astronaut'])" in errors
    assert "its guidance mentions details that aren't in its facts: ['08:00']" in errors
    assert (
        "its reference artifact fails its own checks: point next not covered; detail '11:00' not in the facts"
        in errors
    )
    monkeypatch.setattr(validate, "WORK_SAMPLES_DIR", SEED_DIR)
    assert not [e for e in validate.run(None).errors if "work sample" in e]
