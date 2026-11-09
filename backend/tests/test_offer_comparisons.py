"""Private offer comparisons (Volume 10, prompt 9; docs/OFFER_COMPARISON.md): hourly against annual
with visible assumptions, monthly needing its payments, mixed currencies converted only with a dated
rate, missing fields unknown and not zero, a conditional bonus never added to guaranteed pay,
equity described and not valued, subjective factors with optional weights that explain every
contribution, conflicting edits, receipts, malicious text, another account's ids, an application
linked but never changed, the fictional example, export and deletion. Synthetic accounts only."""

from __future__ import annotations

import copy

from sqlalchemy import func, select

from app.models import OfferComparison
from app.offercompare.calc import derive

from .conftest import auth_headers, register

MINE = "/api/v1/me/offer-comparisons"


def offer(oid: str, **terms):
    base = {
        "id": oid,
        "label": f"Offer {oid.upper()}",
        "application_id": None,
        "source_note": "",
        "terms_as_of": None,
        "currency": None,
        "pay_amount": None,
        "pay_period": None,
        "months_paid": None,
        "hours_per_week": None,
        "weeks_per_year": None,
        "guaranteed_extra": None,
        "guaranteed_note": "",
        "bonus_amount": None,
        "bonus_note": "",
        "equity_note": "",
        "benefits_note": "",
    }
    return {**base, **terms}


def doc(*offers, **rest):
    return {
        "title": "Mine",
        "offers": list(offers),
        "factors": [],
        "conversions": [],
        "weights_on": False,
        "show_in": None,
        **rest,
    }


def new(client, h, **body):
    r = client.post(MINE, json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def put(client, h, c, d, key=None, base=None):
    return client.put(
        f"{MINE}/{c['id']}",
        json={
            "doc": d,
            "expected_revision": base if base is not None else c["revision"],
            "client_request_id": key,
        },
        headers=h,
    )


def test_hourly_and_annual_pay_show_their_basis_and_need_it_entered():
    hourly = offer("a", currency="USD", pay_amount=21.5, pay_period="hour", hours_per_week=40)
    salaried = offer("b", currency="USD", pay_amount=45000, pay_period="year")
    monthly = offer("c", currency="USD", pay_amount=3000, pay_period="month")
    d = derive(doc(hourly, salaried, monthly))
    a, b, c = (o["annual_pay"] for o in d["offers"])
    assert (
        a["value"] is None
        and a["unknown"] == "Enter the weeks paid a year to put hourly pay on a yearly basis."
    )
    assert b["value"] == 45000 and b["formula"] == "45,000 USD a year, as entered"
    assert c["value"] is None and "monthly payments a year" in c["unknown"]
    d = derive(doc({**hourly, "weeks_per_year": 52}, salaried, {**monthly, "months_paid": 13}))
    a, _, c = (o["annual_pay"] for o in d["offers"])
    assert a["value"] == 44720
    assert a["formula"] == "21.50 USD an hour × 40 hours a week × 52 weeks = 44,720 USD a year"
    assert a["assumptions"] == ["40 hours a week and 52 paid weeks a year (you entered these); no overtime"]
    assert (
        c["value"] == 39000 and c["formula"] == "3,000 USD a month × 13 payments a year = 39,000 USD a year"
    )


def test_missing_is_unknown_not_zero_and_a_conditional_bonus_is_never_guaranteed():
    nothing = offer("a", label="Gaps")
    zero_extra = offer(
        "b", currency="GBP", pay_amount=31000, pay_period="year", guaranteed_extra=0, bonus_amount=2000
    )
    unknown_extra = offer(
        "c", currency="GBP", pay_amount=31000, pay_period="year", equity_note="1,000 options, strike unknown"
    )
    a, b, c = derive(doc(nothing, zero_extra, unknown_extra))["offers"]
    assert (
        a["annual_pay"]["value"] is None
        and a["annual_pay"]["unknown"] == "No pay amount entered (unknown, not zero)."
    )
    assert a["conditional_bonus"]["text"] == "Not entered (unknown, not zero)"
    assert b["guaranteed_first_year"]["value"] == 31000  # the 2,000 bonus isn't added
    assert (
        b["guaranteed_first_year"]["formula"]
        == "31,000 GBP yearly pay + 0 GBP guaranteed one-off = 31,000 GBP"
    )
    assert b["conditional_bonus"]["text"] == "Up to 2,000 GBP, conditional: not counted in guaranteed pay"
    assert (
        c["guaranteed_first_year"]["value"] is None
        and "unknown, not zero" in c["guaranteed_first_year"]["unknown"]
    )
    assert c["equity"].startswith("Described, not valued")
    assert "tax" in derive(doc(nothing))["not_estimated"].lower()


def test_mixed_currencies_convert_only_with_a_dated_rate_you_entered():
    usd = offer("a", currency="USD", pay_amount=44720, pay_period="year")
    gbp = offer("b", currency="GBP", pay_amount=31000, pay_period="year")
    d = derive(doc(usd, gbp, show_in="GBP"))
    assert d["mixed_currencies"] and "only where you entered a dated rate" in d["currency_note"]
    assert (
        d["offers"][0]["annual_pay_converted"]["unknown"]
        == "No rate from USD to GBP entered, so it isn't converted."
    )
    assert d["offers"][1]["annual_pay_converted"] is None  # already in GBP
    rate = {"from_currency": "USD", "to_currency": "GBP", "rate": 0.8, "as_of": "2026-11-01", "note": ""}
    conv = derive(doc(usd, gbp, show_in="GBP", conversions=[rate]))["offers"][0]["annual_pay_converted"]
    assert conv["value"] == 35776 and conv["formula"] == "44,720 USD × 0.8 = 35,776 GBP"
    assert conv["assumptions"] == ["1 USD = 0.8 GBP (your rate for 2026-11-01)"]
    inverse = derive(doc(usd, gbp, show_in="USD", conversions=[rate]))["offers"][1]["annual_pay_converted"]
    assert inverse["value"] == 38750 and "used the other way" in inverse["assumptions"][0]
    assert (
        derive(doc(usd, gbp))["offers"][0]["annual_pay"]["currency"] == "USD"
    )  # never combined without asking


def test_weights_explain_every_contribution_and_never_name_a_best_offer():
    factors = [
        {
            "id": "schedule",
            "label": "Schedule",
            "weight": 3,
            "ratings": {
                "a": {"state": "rated", "value": 4, "note": ""},
                "b": {"state": "rated", "value": 2, "note": ""},
            },
        },
        {
            "id": "commute",
            "label": "Commute",
            "weight": 2,
            "ratings": {
                "a": {"state": "unknown", "value": None, "note": ""},
                "b": {"state": "rated", "value": 5, "note": ""},
            },
        },
        {
            "id": "scope",
            "label": "Role scope",
            "weight": 4,
            "ratings": {
                "a": {"state": "not_comparable", "value": None, "note": "Different roles"},
                "b": {"state": "rated", "value": 3, "note": ""},
            },
        },
        {
            "id": "learning",
            "label": "Learning",
            "weight": 0,
            "ratings": {
                "a": {"state": "rated", "value": 5, "note": ""},
                "b": {"state": "rated", "value": 1, "note": ""},
            },
        },
    ]
    d = doc(offer("a"), offer("b"), factors=factors)
    assert derive(d)["weighted"] is None  # off unless you turn it on
    w = derive({**d, "weights_on": True})["weighted"]
    a, b = w["rows"]
    assert a["contributions"] == [
        {
            "factor": "Schedule",
            "weight": 3,
            "rating": 4,
            "points": 12,
            "formula": "weight 3 × your rating 4 = 12",
        }
    ]
    assert {(n["factor"], n["reason"]) for n in a["not_counted"]} == {
        ("Commute", "unknown"),
        ("Role scope", "not comparable"),
        ("Learning", "no weight (or weight 0)"),
    }
    assert b["total"] == 6 + 10 + 12 and w["order"] == ["b", "a"]
    assert w["uneven"] and "not a recommendation" in w["label"] and "objectively best" in w["label"]
    lighter = copy.deepcopy(d)
    lighter["factors"][0]["weight"] = 5
    lighter["factors"][2]["weight"] = 0
    assert derive({**lighter, "weights_on": True})["weighted"]["order"] == [
        "a",
        "b",
    ]  # your weights, your order


def test_saves_are_revision_checked_with_receipts_and_ratings_stay_honest(client):
    h = auth_headers(register(client))
    c = new(client, h, title="Two offers")
    d = doc(offer("a", label="North"), offer("b", label="South"))
    d["factors"] = [
        {
            "id": "commute",
            "label": "Commute",
            "weight": None,
            "ratings": {"a": {"state": "unknown", "value": 4, "note": ""}},
        }
    ]
    saved = put(client, h, c, d, key="save-key-0001")
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert (
        body["revision"] == 2 and body["doc"]["factors"][0]["ratings"]["a"]["value"] is None
    )  # unknown has no number
    again = put(client, h, c, d, key="save-key-0001").json()  # the reply was lost; sent again
    assert again["save_replay"] == {"accepted_revision": 2, "current_revision": 2}
    reused = put(client, h, c, {**d, "title": "Other"}, key="save-key-0001")
    assert reused.status_code == 409
    stale = put(client, h, c, {**d, "title": "From an old tab"}, key="save-key-0002")
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "stale_revision"
    assert stale.json()["error"]["details"]["current"]["doc"]["title"] == "Mine"
    bad = copy.deepcopy(d)
    bad["factors"][0]["ratings"]["a"] = {"state": "rated", "value": None, "note": ""}
    assert put(client, h, body, bad).json()["error"]["code"] == "rating_value_required"
    bad["factors"][0]["ratings"] = {"zz": {"state": "rated", "value": 3, "note": ""}}
    assert put(client, h, body, bad).json()["error"]["code"] == "unknown_offer"
    same = {"from_currency": "GBP", "to_currency": "GBP", "rate": 1, "as_of": "2026-11-01", "note": ""}
    assert put(client, h, body, {**d, "conversions": [same]}).json()["error"]["code"] == "same_currency"


def test_malicious_text_is_text_and_control_characters_go(client):
    h = auth_headers(register(client))
    c = new(client, h)
    hostile = '<img src=x onerror="alert(1)"> Bigco'
    saved = put(
        client, h, c, doc(offer("a", label=hostile + "\x00\x07", source_note="<script>x</script>"))
    ).json()
    assert (
        saved["doc"]["offers"][0]["label"] == hostile
        and saved["doc"]["offers"][0]["source_note"] == "<script>x</script>"
    )


def test_another_accounts_ids_and_applications_are_refused_and_linking_changes_no_stage(client):
    ada = auth_headers(register(client))
    bea = auth_headers(register(client, email="bea@example.com"))
    mine = client.post(
        "/api/v1/me/applications",
        json={"employer": "Northfield", "role_title": "Support analyst", "stage": "offer"},
        headers=ada,
    ).json()
    theirs = client.post(
        "/api/v1/me/applications", json={"employer": "Elsewhere", "role_title": "Analyst"}, headers=bea
    ).json()
    c = new(client, ada)
    for method in ("GET", "DELETE"):
        assert client.request(method, f"{MINE}/{c['id']}", headers=bea).status_code == 404
    assert put(client, bea, c, doc(offer("a"))).status_code == 404
    assert put(client, ada, c, doc(offer("a", application_id=theirs["id"]))).status_code == 404
    linked = put(client, ada, c, doc(offer("a", application_id=mine["id"]))).json()
    assert linked["applications"] == {mine["id"]: "Support analyst at Northfield"}
    after = client.get(f"/api/v1/me/applications/{mine['id']}", headers=ada).json()
    assert after["stage"] == "offer" and len(after["history"]) == len(mine["history"]) >= 1
    assert after["history"] == mine["history"] and after["updated_at"] == mine["updated_at"]
    assert client.get(MINE, headers=bea).json() == []


def test_the_example_has_gaps_preview_stores_nothing_and_export_and_deletion_cover_it(client):
    data = register(client)
    h = auth_headers(data)
    ex = new(client, h, example=True)
    assert "Fictional" in ex["doc"]["title"]
    a, b = ex["derived"]["offers"]
    assert (
        a["annual_pay"]["value"] is None
        and b["annual_pay"]["value"] == 31000
        and ex["derived"]["mixed_currencies"]
    )
    with client.app.state.session_factory() as db:
        before = db.scalar(select(func.count()).select_from(OfferComparison))
    figures = client.post(
        f"{MINE}/preview", json=doc(offer("z", currency="EUR", pay_amount=10, pay_period="year")), headers=h
    )
    assert figures.status_code == 200 and figures.json()["derived"]["offers"][0]["annual_pay"]["value"] == 10
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(OfferComparison)) == before
    exported = client.get("/api/v1/me/export", headers=h).json()["offer_comparisons"]
    assert exported[0]["doc"]["offers"][1]["pay_amount"] == 31000
    gone = client.request(
        "DELETE", "/api/v1/auth/me", headers=h, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    assert gone.status_code == 204
    with client.app.state.session_factory() as db:
        count = (
            select(func.count())
            .select_from(OfferComparison)
            .where(OfferComparison.user_id == data["user"]["id"])
        )
        assert db.scalar(count) == 0
