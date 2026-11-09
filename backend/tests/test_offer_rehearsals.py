"""Offer-conversation rehearsals (Volume 10, prompt 8; docs/OFFER_REHEARSAL.md): a complete text
journey with real arithmetic, unknown terms kept unknown, a declined offer, inaccurate and
unsupported claims, the same feedback for typed and dictated answers, no AI, interrupted sessions
(resends, stale tabs, phase limits, resume), a different approach that keeps the first, the
recorded card version, ownership, export and deletion, nothing sent anywhere, and the authoring
checks. Synthetic accounts and fictional cases only."""

from __future__ import annotations

import dataclasses
import re

import pytest
from sqlalchemy import func, select

from app import offers
from app.models import EmailJob, OfferRehearsal
from app.offers import BY_ID, check

from .conftest import auth_headers, register

MINE = "/api/v1/me/offer-rehearsals"
CASE = "offer-support-analyst"
HOURLY = "offer-warehouse-team-lead"


def start(client, h, case=CASE, **body):
    r = client.post(MINE, json={"case_id": case, **body}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def say(client, h, r, text, source="typed", key=None):
    body = {"text": text, "source": source, "after_seq": r["turns"][-1]["seq"], "client_request_id": key}
    return client.post(f"{MINE}/{r['id']}/turns", json=body, headers=h)


def ok(resp):
    assert resp.status_code == 200, resp.text
    return resp.json()


def advance(client, h, r):
    return ok(client.post(f"{MINE}/{r['id']}/phase", json={"from_phase": r["phase"]}, headers=h))


def last(r):
    return r["turns"][-1]["text"]


def card_numbers(case) -> set[float]:
    found: set[float] = set()
    for text in [t.value or "" for t in case.terms] + [case.counter.text]:
        found |= {float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}
    return found


def test_the_cards_are_fictional_and_unknown_terms_stay_unknown(client):
    listed = client.get("/api/v1/offer-rehearsals/cases").json()
    assert [c["id"] for c in listed] == [CASE, HOURLY]
    card = client.get(f"/api/v1/offer-rehearsals/cases/{CASE}").json()
    assert "(fictional)" in card["employer"] and "(fictional)" in card["counterpart"]
    assert {t["label"]: t["value"] for t in card["terms"]}["Bonus"] is None
    assert [p["id"] for p in card["phases"]] == ["clarify", "request", "respond"]
    assert "aren't market rates" in card["review_status"]
    assert client.get("/api/v1/offer-rehearsals/cases/nope").status_code == 404


def test_a_complete_text_journey_with_real_arithmetic_and_a_request_for_time(client):
    h = auth_headers(register(client))
    r = start(client, h, goals=["A higher base salary", "  ", "Time to decide\x07"])
    assert (
        r["goals"] == ["A higher base salary", "Time to decide"] and r["mode"] == "Authored responses (no AI)"
    )
    assert r["phase"] == "clarify" and r["turns"][0]["speaker"] == "counterpart"
    r = ok(say(client, h, r, "What's the base salary, and is there a bonus?"))
    assert last(r).startswith("Base salary: £31,000 per year.")
    assert "Bonus: That isn't set out in the offer you have" in last(r)  # never a guessed value
    r = advance(client, h, r)
    assert r["phase"] == "request" and "What would you like to discuss" in last(r)
    r = ok(
        say(
            client,
            h,
            r,
            "I'd like to ask for a base of £34,000, because I already hold the support certification the role asks for.",
        )
    )
    assert "can't agree" in last(r) and "£34,000" not in last(r)  # it agrees to nothing
    r = advance(client, h, r)
    assert r["phase"] == "respond" and "£32,500" in last(r)
    r = ok(say(client, h, r, "Thank you, I appreciate that. Could I have until Friday to think it over?"))
    assert r["status"] == "completed" and "come back to me by then" in last(r)
    d = r["debrief"]
    assert d["request"]["arithmetic"] == {
        "offered": "£31,000 per year",
        "requested": "£34,000 per year",
        "difference": "+£3,000 (+9.7%)",
        "per_week": None,
    }
    assert d["counteroffer"]["arithmetic"]["difference"] == "+£1,500 (+4.8%)"
    assert d["unresolved"] == [
        {"label": "Bonus", "asked": True},
        {"label": "Training budget", "asked": False},
    ]
    assert d["outcome"] == "time" and all(c["met"] for c in d["criteria"])
    assert d["goals"] == ["A higher base salary", "Time to decide"]
    assert {"label": "Base salary", "value": "£31,000 per year"} in d["facts_used"]
    assert "isn't evidence that a real employer would agree" in d["disclaimer"] and "tax" in d["no_tax"]


def test_an_hourly_offer_shows_a_weekly_difference_only_from_stated_hours(client):
    h = auth_headers(register(client))
    r = advance(client, h, start(client, h, HOURLY))
    r = ok(
        say(client, h, r, "Could you do $23 an hour, since I've led a shift of twelve people for two years?")
    )
    r = ok(client.post(f"{MINE}/{r['id']}/finish", headers=h))
    sums = r["debrief"]["request"]["arithmetic"]
    assert sums["difference"] == "+$1.50 (+7.0%)" and sums["per_week"] == "+$60 a week at the card's 40 hours"


def test_declining_is_a_complete_answer(client):
    h = auth_headers(register(client))
    r = advance(client, h, advance(client, h, start(client, h)))
    r = ok(
        say(client, h, r, "Thank you for checking. I've thought about it and I'm going to decline the offer.")
    )
    assert r["status"] == "completed" and "telling me directly" in last(r)
    d = r["debrief"]
    response = next(c for c in d["criteria"] if c["id"] == "response")
    assert (
        d["outcome"] == "decline" and response["met"] and "Declining is a complete answer" in response["note"]
    )
    assert d["request"] is None  # no request made: that's coached, not penalised as "wrong"
    assert d["improvement"].startswith("Say exactly what you're asking for")


def test_inaccurate_and_unsupported_claims_are_named_and_the_counterpart_stays_on_the_card(client):
    h = auth_headers(register(client))
    r = start(client, h)
    r = ok(say(client, h, r, "The salary is £30,000."))
    assert last(r) == "Just to check, the offer says base salary is £31,000 per year."
    r = advance(client, h, r)
    r = ok(say(client, h, r, "I have another offer at £40,000, so I'd like £38,000 or I walk."))
    assert "I understand this matters to you." in last(r) and "can't comment on other offers" in last(r)
    r = ok(client.post(f"{MINE}/{r['id']}/finish", headers=h))
    d = r["debrief"]
    kinds = [c["kind"] for c in d["claims"]]
    assert kinds == ["mismatch", "unsupported"] and d["pressure"] is True
    assert not next(c for c in d["criteria"] if c["id"] == "accurate")["met"]
    assert d["improvement"].startswith(
        "Stick to what the card says: The card says base salary is £31,000 per year."
    )
    # Every number the counterpart said is on the card (or in its authored counteroffer).
    said = {
        float(n.replace(",", ""))
        for t in r["turns"]
        if t["speaker"] == "counterpart"
        for n in re.findall(r"\d[\d,]*(?:\.\d+)?", t["text"])
    }
    assert said <= card_numbers(BY_ID[CASE])


def test_typed_and_dictated_answers_get_the_same_feedback(client):
    """The same conversation typed, and as speech-to-text gives it: lowercase, no punctuation, filler
    sounds (one inside "need some time"), "pounds" instead of £."""
    results = []
    for email, words, source in (
        (
            "ada@example.com",
            (
                "Is there a bonus?",
                "I'd like £34,000, because I hold the certification.",
                "Thank you. I need some time.",
            ),
            "typed",
        ),
        (
            "bea@example.com",
            (
                "um is there a bonus",
                "uh id like 34,000 pounds because i hold the certification",
                "thank you i need some um time",
            ),
            "voice",
        ),
    ):
        h = auth_headers(register(client, email=email))
        r = ok(say(client, h, start(client, h), words[0], source))
        r = ok(say(client, h, advance(client, h, r), words[1], source))
        r = ok(say(client, h, advance(client, h, r), words[2], source))
        assert last(r) == "Of course. When do you think you can let me know?"
        r = ok(client.post(f"{MINE}/{r['id']}/finish", headers=h))
        assert {t["source"] for t in r["turns"] if t["speaker"] == "learner"} == {source}
        d = r["debrief"]
        results.append(
            (
                [(c["id"], c["met"]) for c in d["criteria"]],
                d["request"]["term"],
                d["request"]["arithmetic"],
                d["outcome"],
                d["unresolved"],
            )
        )
    assert results[0] == results[1]
    assert results[0][1] == "Base salary" and results[0][3] == "time"


def test_it_runs_the_same_with_the_ai_coach_unavailable_and_sends_nothing(client):
    class Down:
        name, model = "anthropic", "m"

        def __getattr__(self, _):
            raise AssertionError("rehearsals don't call the AI coach")

    client.app.state.ai_provider = Down()
    h = auth_headers(register(client))
    with client.app.state.session_factory() as db:
        before = db.scalar(select(func.count()).select_from(EmailJob))
    r = ok(say(client, h, start(client, h), "What's the start date?"))
    assert last(r) == "Start date: Monday 2 March."
    r = ok(client.post(f"{MINE}/{r['id']}/finish", headers=h))
    assert r["mode"] == "Authored responses (no AI)"
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(EmailJob)) == before


def test_interrupted_sessions_resends_stale_tabs_limits_and_resume(client):
    h = auth_headers(register(client))
    r = start(client, h)
    first = ok(say(client, h, r, "Is there a training budget?", key="k-1"))
    again = ok(say(client, h, r, "Is there a training budget?", key="k-1"))  # the reply was lost; sent again
    assert len(again["turns"]) == len(first["turns"]) == 3
    reused = say(client, h, r, "Something else entirely", key="k-1")
    assert reused.status_code == 409
    stale = say(client, h, r, "A message from an old tab")  # after_seq is from before the first turn
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "rehearsal_advanced"
    r = first
    for text in ("What about probation?", "And holiday?"):
        r = ok(say(client, h, r, text))
    full = say(client, h, r, "One more question?")
    assert full.status_code == 409 and full.json()["error"]["code"] == "phase_full"
    assert start(client, h)["id"] == r["id"]  # starting again resumes it
    moved = advance(client, h, r)
    assert (
        ok(client.post(f"{MINE}/{r['id']}/phase", json={"from_phase": "clarify"}, headers=h))["turns"]
        == moved["turns"]
    )
    assert say(client, h, r, "   ").status_code in (400, 409)
    empty = say(client, h, moved, "   ")
    assert empty.status_code == 400 and empty.json()["error"]["code"] == "turn_empty"


def test_stopping_early_gives_a_debrief_of_what_happened(client):
    h = auth_headers(register(client))
    r = ok(say(client, h, start(client, h), "What's the base salary?"))
    r = ok(client.post(f"{MINE}/{r['id']}/finish", headers=h))
    d = r["debrief"]
    assert r["status"] == "completed" and d["phases_reached"] == ["Clarify the terms"]
    assert next(c for c in d["criteria"] if c["id"] == "request")["note"] == "You didn't reach the request."
    assert say(client, h, r, "More?").json()["error"]["code"] == "rehearsal_finished"
    assert ok(client.post(f"{MINE}/{r['id']}/finish", headers=h))["completed_at"] == r["completed_at"]


def test_a_different_approach_is_a_new_rehearsal_and_keeps_the_first(client):
    h = auth_headers(register(client))
    first = start(client, h)
    refused = client.post(MINE, json={"case_id": CASE, "parent_id": first["id"]}, headers=h)
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "parent_not_finished"
    first = ok(client.post(f"{MINE}/{first['id']}/finish", headers=h))
    other = start(client, h, parent_id=first["id"])
    assert (
        other["id"] != first["id"] and other["parent_id"] == first["id"] and other["status"] == "in_progress"
    )
    assert ok(client.get(f"{MINE}/{first['id']}", headers=h)) == first
    listed = ok(client.get(MINE, headers=h))
    assert [x["id"] for x in listed] == [other["id"], first["id"]]


def test_a_rehearsal_keeps_the_card_it_started_with(client, monkeypatch):
    h = auth_headers(register(client))
    r = ok(say(client, h, start(client, h), "What's the base salary?"))
    old = BY_ID[CASE]
    edited = dataclasses.replace(
        old,
        version=2,
        terms=(dataclasses.replace(old.terms[0], value="£99,999 per year", amount=99999), *old.terms[1:]),
        _index={},
    )
    monkeypatch.setitem(BY_ID, CASE, edited)
    again = ok(client.get(f"{MINE}/{r['id']}", headers=h))
    assert (again["case_version"], again["current_version"]) == (1, 2)
    assert again["card"]["terms"][0]["value"] == "£31,000 per year"
    again = ok(say(client, h, again, "So the salary is what exactly?"))
    assert "£31,000" in last(again) and "99,999" not in last(again)


def test_another_account_can_not_read_or_speak_and_deletion_removes_it(client):
    data = register(client)
    ada = auth_headers(data)
    bea = auth_headers(register(client, email="bea@example.com"))
    secret = "ADA-OFFER-5512"
    r = ok(say(client, ada, start(client, ada, goals=[f"goal {secret}"]), f"Is there a bonus? {secret}"))
    for method, path, body in (
        ("GET", f"{MINE}/{r['id']}", None),
        ("POST", f"{MINE}/{r['id']}/turns", {"text": "hi", "after_seq": 3}),
        ("POST", f"{MINE}/{r['id']}/phase", {"from_phase": "clarify"}),
        ("POST", f"{MINE}/{r['id']}/finish", None),
    ):
        assert client.request(method, path, json=body, headers=bea).status_code == 404
    assert client.post(MINE, json={"case_id": CASE, "parent_id": r["id"]}, headers=bea).status_code == 404
    assert secret not in client.get(MINE, headers=bea).text
    exported = client.get("/api/v1/me/export", headers=ada).json()["offer_rehearsals"]
    assert exported[0]["goals"] == [f"goal {secret}"] and secret in exported[0]["turns"][1]["text"]
    assert "client_request_id" not in exported[0]["turns"][1]
    gone = client.request(
        "DELETE", "/api/v1/auth/me", headers=ada, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    assert gone.status_code == 204
    with client.app.state.session_factory() as db:
        count = (
            select(func.count())
            .select_from(OfferRehearsal)
            .where(OfferRehearsal.user_id == data["user"]["id"])
        )
        assert db.scalar(count) == 0


def test_too_many_goals_are_refused(client):
    h = auth_headers(register(client))
    r = client.post(MINE, json={"case_id": CASE, "goals": ["a", "b", "c", "d"]}, headers=h)
    assert r.status_code == 422


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        (
            {"terms": tuple(t for t in BY_ID[CASE].terms if t.value is not None)},
            "at least one term must be unknown",
        ),
        (
            {"counter": offers.Counter("x", "start", None)},
            "the counteroffer must change a term with a stated amount",
        ),
        (
            {
                "terms": (
                    dataclasses.replace(BY_ID[CASE].terms[0], aliases=("Salary",)),
                    *BY_ID[CASE].terms[1:],
                )
            },
            "base: aliases must be lowercase without apostrophes",
        ),
    ],
)
def test_the_authoring_checks(change, problem):
    assert check(BY_ID[CASE]) == []
    found = check(dataclasses.replace(BY_ID[CASE], _index={}, **change))
    assert any(problem in p for p in found), found
