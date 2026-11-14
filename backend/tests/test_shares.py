"""Sharing an answer with a reviewer: exact snapshot, link security, revocation, structured
feedback, owner controls, privacy across accounts, logs, export and deletion."""

import logging
import secrets
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import PracticeAnswer, Share, ShareFeedback
from app.services import shares as shares_service
from tests.conftest import auth_headers, register

NURSE = "registered-nurse"
ANSWER = (
    "Last winter I was the night nurse for five patients. One of them suddenly became confused. "
    "I checked his vital signs and called the rapid response team. As a result he was stable within 30 minutes."
)
VAGUE = "We handled it together as a team and everything was fine in the end."
OWNED_NO_RESULT = "I checked his vital signs and I called the doctor straight away while the team helped."


def nurse(client, email="ada@example.com", name="Ada"):
    return auth_headers(register(client, email=email, display_name=name, career_track=NURSE))


def answer_question(client, h, text=ANSWER, qid="m-pressure-0") -> dict:
    r = client.post(f"/api/v1/careers/{NURSE}/questions/{qid}/answers", headers=h, json={"answer": text})
    assert r.status_code == 201, r.text
    return r.json()


def share(client, h, answer_id, **body) -> dict:
    payload = {"answer_id": answer_id, "acknowledge_link_access": True, **body}
    r = client.post("/api/v1/me/shares", headers=h, json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def open_link(client, token, headers=None):
    return client.post("/api/v1/shared/open", json={"token": token}, headers=headers or {})


def feedback(client, token, headers=None, **body):
    payload = {
        "token": token,
        "client_request_id": secrets.token_hex(8),
        "clear": "The situation was clear.",
        **body,
    }
    return client.post("/api/v1/shared/feedback", json=payload, headers=headers or {})


def test_the_reviewer_sees_exactly_the_preview_and_nothing_else(client):
    h = nurse(client)
    a = answer_question(client, h)
    p = client.post(
        "/api/v1/me/shares/preview",
        headers=h,
        json={"answer_id": a["id"], "sentences": [0, 2], "note": "Be blunt."},
    )
    assert p.status_code == 200, p.text
    preview = p.json()
    assert [s["text"] for s in preview["source_sentences"]] == [
        "Last winter I was the night nurse for five patients.",
        "One of them suddenly became confused.",
        "I checked his vital signs and called the rapid response team.",
        "As a result he was stable within 30 minutes.",
    ]
    view = preview["view"]
    assert [s["index"] for s in view["excerpt"]] == [0, 2] and view["omitted_sentences"] == 2
    assert view["ai_feedback"] is None and view["followup"] is None and view["note"] == "Be blunt."
    assert view["prompts"] == ["What was clear?", "What needs more evidence?", "One useful next step"]
    assert view["kind"] == "practice_answer" and view["career_title"] == "Registered Nurse"

    created = share(client, h, a["id"], sentences=[0, 2], note="Be blunt.")
    token = created["token"]
    assert created["path"] == f"/shared#t={token}" and len(token) >= 43
    r = open_link(client, token)  # anyone holding the link, not signed in
    assert r.status_code == 200
    assert r.json()["view"] == view and r.json()["status"] == "active" and r.json()["reviewer"] is None
    # Private and uncachable.
    assert r.headers["cache-control"] == "no-store" and r.headers["x-robots-tag"] == "noindex, nofollow"
    assert r.headers["referrer-policy"] == "no-referrer"
    # Nothing else from the account: no email, name, ids, omitted sentences or score.
    body = r.text
    for secret in (
        "ada@example.com",
        "Ada",
        a["id"],
        created["share"]["id"],
        "suddenly became confused",
        "stable within",
    ):
        assert secret not in body, secret
    assert '"score"' not in body


def test_ai_feedback_and_a_follow_up_are_included_only_when_chosen(client):
    h = nurse(client)
    iv = client.post(
        "/api/v1/interviews",
        headers=h,
        json={"kind": "questions", "format": "behavioral", "difficulty": "medium"},
    ).json()
    r = client.post(
        f"/api/v1/interviews/{iv['id']}/answers",
        headers=h,
        json={"question_index": 0, "answer": VAGUE, "source": "typed"},
    ).json()
    answer_id = r["questions"][0]["answer"]["id"]
    # Not while the round is still running.
    early = client.post("/api/v1/me/shares/preview", headers=h, json={"answer_id": answer_id})
    assert early.status_code == 409 and early.json()["error"]["code"] == "interview_in_progress"
    client.post(
        f"/api/v1/interviews/{iv['id']}/followup",
        headers=h,
        json={"answer": OWNED_NO_RESULT, "source": "typed"},
    )
    client.post(f"/api/v1/interviews/{iv['id']}/abandon", headers=h)

    plain = client.post(
        "/api/v1/me/shares/preview", headers=h, json={"answer_id": answer_id, "include_followup": False}
    ).json()
    assert (
        plain["has_followup"] is True
        and plain["view"]["followup"] is None
        and plain["view"]["ai_feedback"] is None
    )
    full = client.post(
        "/api/v1/me/shares/preview", headers=h, json={"answer_id": answer_id, "include_ai_feedback": True}
    ).json()["view"]
    assert full["kind"] == "interview_answer"
    assert full["followup"] == {
        "asked_by": "Interviewer",
        "question": full["followup"]["question"],
        "answer": OWNED_NO_RESULT,
    }
    assert full["ai_feedback"]["coach"] == "built-in (offline)" and isinstance(
        full["ai_feedback"]["score"], int
    )
    assert set(full["ai_feedback"]["points"][0]) == {"label", "covered"}  # no rubric advice or outline


def test_creating_requires_a_deliberate_valid_choice(client):
    h = nurse(client)
    a = answer_question(client, h)
    base = {"answer_id": a["id"]}
    r = client.post("/api/v1/me/shares", headers=h, json={**base, "acknowledge_link_access": False})
    assert r.status_code == 400 and r.json()["error"]["code"] == "acknowledgement_required"
    assert client.post("/api/v1/me/shares", headers=h, json=base).status_code == 422  # must be stated
    r = client.post("/api/v1/me/shares/preview", headers=h, json={**base, "sentences": []})
    assert r.json()["error"]["code"] == "empty_selection"
    r = client.post("/api/v1/me/shares/preview", headers=h, json={**base, "sentences": [0, 9]})
    assert r.json()["error"]["code"] == "unknown_sentence"
    r = client.post(
        "/api/v1/me/shares", headers=h, json={**base, "acknowledge_link_access": True, "expires_in_days": 365}
    )
    assert r.status_code == 422
    other = nurse(client, "bea@example.com", "Bea")
    assert client.post("/api/v1/me/shares/preview", headers=other, json=base).status_code == 404
    assert client.post("/api/v1/me/shares/preview", json=base).status_code == 401


def test_links_are_unguessable_and_only_their_hash_is_stored(client):
    h = nurse(client)
    created = share(client, h, answer_question(client, h)["id"])
    token = created["token"]
    with client.app.state.session_factory() as db:
        row = db.scalars(select(Share)).one()
        stored = " ".join(str(getattr(row, c.name)) for c in Share.__table__.columns)
    assert token not in stored and row.token_hash == shares_service.hash_token(token)
    for guess in (
        created["share"]["id"] + "0" * 8,
        secrets.token_urlsafe(32),
        token[:-1] + ("A" if token[-1] != "A" else "B"),
    ):
        r = open_link(client, guess)
        assert r.status_code == 404 and r.json()["error"]["code"] == "share_not_found"
    assert open_link(client, "short").status_code == 422
    assert client.post("/api/v1/shared/open", json={"token": row.id}).status_code in (
        404,
        422,
    )  # an id is not a key


def test_revoked_expired_and_replaced_links_stop_working_everywhere(client):
    h = nurse(client)
    created = share(client, h, answer_question(client, h)["id"])
    sid, token = created["share"]["id"], created["token"]
    assert open_link(client, token).status_code == 200

    replaced = client.post(f"/api/v1/me/shares/{sid}/link", headers=h).json()
    assert open_link(client, token).status_code == 404  # the old link died
    token = replaced["token"]
    assert open_link(client, token).status_code == 200

    revoked = client.post(f"/api/v1/me/shares/{sid}/revoke", headers=h).json()
    assert revoked["status"] == "revoked"
    for r in (open_link(client, token), feedback(client, token)):
        assert r.status_code == 410 and r.json()["error"]["code"] == "share_revoked"
        assert "Last winter" not in r.text
    assert (
        client.post(f"/api/v1/me/shares/{sid}/reopen", headers=h).json()["error"]["code"] == "share_revoked"
    )
    assert client.post(f"/api/v1/me/shares/{sid}/link", headers=h).json()["error"]["code"] == "share_inactive"
    # The owner keeps the snapshot and feedback until they delete it.
    assert client.get(f"/api/v1/me/shares/{sid}", headers=h).json()["view"]["excerpt"]

    second = share(client, h, answer_question(client, h)["id"], expires_in_days=1)
    with client.app.state.session_factory() as db:
        db.get(Share, second["share"]["id"]).expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    r = open_link(client, second["token"])
    assert r.status_code == 410 and r.json()["error"]["code"] == "share_expired"
    assert client.get("/api/v1/me/shares", headers=h).json()[0]["status"] == "expired"


def test_closing_keeps_the_snapshot_readable_but_stops_feedback(client):
    h = nurse(client)
    created = share(client, h, answer_question(client, h)["id"])
    sid, token = created["share"]["id"], created["token"]
    client.post(f"/api/v1/me/shares/{sid}/close", headers=h)
    assert open_link(client, token).json()["status"] == "closed"
    r = feedback(client, token)
    assert r.status_code == 409 and r.json()["error"]["code"] == "share_closed"
    client.post(f"/api/v1/me/shares/{sid}/reopen", headers=h)
    assert feedback(client, token).status_code == 201


def test_feedback_is_structured_attributed_honestly_and_rendered_as_text(client):
    h = nurse(client)
    created = share(client, h, answer_question(client, h)["id"], sentences=[0, 2])
    sid, token = created["share"]["id"], created["token"]
    evil = '<img src=x onerror=alert(1)><script>alert("x")</script>'
    r = feedback(
        client,
        token,
        clear=evil + "\x00\x07",
        needs_evidence="What did the vitals show?",
        next_step="Name the result first.",
        comments=[{"sentence": 2, "text": "Who did you call first?"}],
        guest_name="Sam",
    )
    assert r.status_code == 201, r.text
    item = r.json()["feedback"]
    assert item["clear"] == evil  # stored as plain text (control characters removed); never rendered as HTML
    assert item["reviewer"] == {"kind": "guest", "label": "Sam (guest, name not verified)"}
    assert item["comments"] == [
        {
            "sentence": 2,
            "text": "Who did you call first?",
            "quote": "I checked his vital signs and called the rapid response team.",
        }
    ]

    bea = nurse(client, "bea@example.com", "Bea")
    assert open_link(client, token, bea).json()["reviewer"] == {
        "kind": "account",
        "label": "Bea (signed-in CodeCoach user)",
    }
    r = feedback(client, token, bea, guest_name="Not used")
    assert r.json()["feedback"]["reviewer"]["label"] == "Bea (signed-in CodeCoach user)"
    anon = feedback(client, token).json()["feedback"]["reviewer"]
    assert anon == {"kind": "guest", "label": "Guest (no name given)"}

    # Comments only on sentences that were shared; something must be said; sizes are bounded.
    bad = feedback(client, token, comments=[{"sentence": 1, "text": "hidden one"}])
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "unknown_sentence"
    empty = feedback(client, token, clear="   ", needs_evidence="", next_step="")
    assert empty.status_code == 400 and empty.json()["error"]["code"] == "empty_feedback"
    assert feedback(client, token, clear="x" * 1501).status_code == 422
    assert feedback(client, token, comments=[{"sentence": 0, "text": "c"}] * 9).status_code == 422
    # The owner can't review their own answer.
    own = feedback(client, token, h)
    assert own.status_code == 409 and own.json()["error"]["code"] == "own_share"

    detail = client.get(f"/api/v1/me/shares/{sid}", headers=h).json()
    assert detail["feedback_count"] == 3 and [f["reviewer"]["kind"] for f in detail["feedback"]] == [
        "guest",
        "account",
        "guest",
    ]


def test_retries_are_saved_once_and_volume_is_bounded(client, monkeypatch):
    h = nurse(client)
    token = share(client, h, answer_question(client, h)["id"])["token"]
    once = feedback(client, token, client_request_id="retry-0001")
    again = feedback(client, token, client_request_id="retry-0001")
    assert once.status_code == 201 and again.status_code == 200 and again.json()["duplicate"] is True
    assert again.json()["feedback"]["id"] == once.json()["feedback"]["id"]
    # The same key with other words isn't the same feedback: refused, not taken as already sent
    # (Volume 8, prompt 2). Before, it came back as "duplicate" and the new words were dropped.
    changed = feedback(client, token, client_request_id="retry-0001", clear="a changed retry")
    assert changed.status_code == 409 and changed.json()["error"]["code"] == "idempotency_key_reused"
    with client.app.state.session_factory() as db:
        assert len(db.scalars(select(ShareFeedback)).all()) == 1

    monkeypatch.setattr(shares_service, "MAX_FEEDBACK_PER_SHARE", 2)
    assert feedback(client, token).status_code == 201
    r = feedback(client, token)
    assert r.status_code == 409 and r.json()["error"]["code"] == "feedback_limit"


def test_opening_and_feedback_are_rate_limited_per_client(make_client):
    # A fresh app whose counters start at zero (they're kept in the shared database).
    limited = make_client(share_feedback_per_hour=2, share_opens_per_10_minutes=3)
    h2 = nurse(limited, "cy@example.com", "Cy")
    t2 = share(limited, h2, answer_question(limited, h2)["id"])["token"]
    assert [feedback(limited, t2).status_code for _ in range(3)] == [201, 201, 429]
    assert [open_link(limited, secrets.token_urlsafe(32)).status_code for _ in range(4)] == [
        404,
        404,
        404,
        429,
    ]


def test_owner_controls_and_human_feedback_never_touches_scores(client):
    h = nurse(client)
    a = answer_question(client, h)
    created = share(client, h, a["id"])
    sid, token = created["share"]["id"], created["token"]
    fid = feedback(client, token, guest_name="Sam").json()["feedback"]["id"]
    before = client.get(f"/api/v1/careers/{NURSE}/questions/m-pressure-0/answers", headers=h).json()

    listing = client.get("/api/v1/me/shares", headers=h).json()
    assert len(listing) == 1 and listing[0]["feedback_count"] == 1 and listing[0]["question_title"]
    assert client.get(f"/api/v1/me/shares?answer_id={a['id']}", headers=h).json()[0]["id"] == sid
    marked = client.put(
        f"/api/v1/me/shares/{sid}/feedback/{fid}/useful", headers=h, json={"useful": True}
    ).json()
    assert marked["feedback"][0]["useful"] is True
    after = client.get(f"/api/v1/careers/{NURSE}/questions/m-pressure-0/answers", headers=h).json()
    assert after == before  # the answer and its score are untouched
    removed = client.delete(f"/api/v1/me/shares/{sid}/feedback/{fid}", headers=h).json()
    assert removed["feedback"] == []
    assert client.delete(f"/api/v1/me/shares/{sid}", headers=h).status_code == 204
    assert client.get(f"/api/v1/me/shares/{sid}", headers=h).status_code == 404
    assert open_link(client, token).status_code == 404


def test_other_accounts_cannot_see_or_change_a_share(client):
    h = nurse(client)
    created = share(client, h, answer_question(client, h)["id"])
    sid = created["share"]["id"]
    fid = feedback(client, created["token"]).json()["feedback"]["id"]
    other = nurse(client, "bea@example.com", "Bea")
    assert client.get("/api/v1/me/shares", headers=other).json() == []
    for method, path, body in (
        ("GET", f"/api/v1/me/shares/{sid}", None),
        ("POST", f"/api/v1/me/shares/{sid}/revoke", None),
        ("POST", f"/api/v1/me/shares/{sid}/close", None),
        ("POST", f"/api/v1/me/shares/{sid}/link", None),
        ("PUT", f"/api/v1/me/shares/{sid}/feedback/{fid}/useful", {"useful": True}),
        ("DELETE", f"/api/v1/me/shares/{sid}/feedback/{fid}", None),
        ("DELETE", f"/api/v1/me/shares/{sid}", None),
    ):
        r = client.request(method, path, headers=other, json=body)
        assert r.status_code == 404, (method, path, r.status_code)
    assert client.get(f"/api/v1/me/shares/{sid}", headers=h).json()["status"] == "active"


def test_changing_the_source_later_never_changes_what_was_shared(client):
    h = nurse(client)
    a = answer_question(client, h)
    created = share(client, h, a["id"])
    sid, token = created["share"]["id"], created["token"]
    shared = open_link(client, token).json()["view"]
    with client.app.state.session_factory() as db:
        db.get(PracticeAnswer, a["id"]).answer = "Something completely different."
        db.commit()
    assert open_link(client, token).json()["view"] == shared
    detail = client.get(f"/api/v1/me/shares/{sid}", headers=h).json()
    assert detail["source_changed"] is True and detail["source_missing"] is False and detail["view"] == shared
    with client.app.state.session_factory() as db:
        db.delete(db.get(PracticeAnswer, a["id"]))
        db.commit()
    detail = client.get(f"/api/v1/me/shares/{sid}", headers=h).json()
    assert detail["source_missing"] is True and open_link(client, token).json()["view"] == shared


def test_link_secrets_never_reach_the_access_log(client, caplog):
    h = nurse(client)
    token = share(client, h, answer_question(client, h)["id"])["token"]
    with caplog.at_level(logging.INFO, logger="codecoach.access"):
        open_link(client, token)
        feedback(client, token)
    paths = [getattr(r, "path", "") for r in caplog.records]
    assert "/api/v1/shared/open" in paths and "/api/v1/shared/feedback" in paths
    assert all(token not in (r.getMessage() + str(getattr(r, "path", ""))) for r in caplog.records)


@pytest.mark.filterwarnings("ignore")
def test_export_and_account_deletion(client):
    h = nurse(client)
    created = share(client, h, answer_question(client, h)["id"], sentences=[0])
    bea_tokens = register(client, email="bea@example.com", display_name="Bea", career_track=NURSE)
    bea = auth_headers(bea_tokens)
    feedback(client, created["token"], bea, next_step="Lead with the outcome.")

    mine = client.get("/api/v1/me/export", headers=h).json()
    assert mine["shares"][0]["snapshot"]["excerpt"] == [
        {"index": 0, "text": "Last winter I was the night nurse for five patients."}
    ]
    assert mine["shares"][0]["feedback"][0]["next_step"] == "Lead with the outcome."
    assert created["token"] not in str(mine)
    given = client.get("/api/v1/me/export", headers=bea).json()["feedback_given"]
    assert given[0]["next_step"] == "Lead with the outcome." and given[0]["question"]

    # The reviewer deletes their account: the feedback stays with the owner, anonymised.
    r = client.request(
        "DELETE", "/api/v1/auth/me", headers=bea, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    assert r.status_code == 204
    item = client.get(f"/api/v1/me/shares/{created['share']['id']}", headers=h).json()["feedback"][0]
    assert item["reviewer"] == {
        "kind": "former_account",
        "label": "A former CodeCoach user (account deleted)",
    }

    # The owner deletes theirs: the share, its snapshot and feedback go, and the link dies.
    r = client.request(
        "DELETE", "/api/v1/auth/me", headers=h, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    assert r.status_code == 204
    with client.app.state.session_factory() as db:
        assert db.scalars(select(Share)).all() == [] and db.scalars(select(ShareFeedback)).all() == []
    assert open_link(client, created["token"]).status_code == 404
