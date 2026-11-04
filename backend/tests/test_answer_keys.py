"""Keyed career-answer saves and explicit revision links (Durable Saves briefs 04, 06 and 09).

The contract: a career answer sent with `client_request_id` is saved at most once per account and
key. A resend of the same request (same key, same question, answer text, story and revised answer)
returns the saved answer, exactly as it was graded then, with 200 and `Idempotent-Replayed: true`;
the same key with a different request is refused (409); another account's identical key is a
different key. Grading itself is local and deterministic (the built-in coach); two concurrent
duplicates may both grade, but only one row is ever saved. Synthetic data only.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.careers import answers as answers_module
from app.careers.questions import questions_for
from app.models import PracticeAnswer
from tests.conftest import auth_headers, register

TRACK = "registered-nurse"
TEXT = (
    "Last winter on a busy ward I noticed a patient's breathing change during my night round. I checked his "
    "observations again, raised the bed, started oxygen as prescribed and called the doctor using SBAR. Within "
    "the hour his saturation was back to 96%, and I learned to escalate early rather than wait to be certain."
)


def _qid(i: int = 0) -> str:
    return questions_for(TRACK)[i].id


def _url(qid: str | None = None) -> str:
    return f"/api/v1/careers/{TRACK}/questions/{qid or _qid()}/answers"


def _rows(c) -> list[PracticeAnswer]:
    db = c.app.state.session_factory()
    try:
        return list(db.query(PracticeAnswer).order_by(PracticeAnswer.created_at).all())
    finally:
        db.close()


def test_a_resent_request_returns_the_saved_answer_instead_of_saving_another(client):
    h = auth_headers(register(client))
    body = {"answer": TEXT, "client_request_id": "op-0123456789abcdef"}
    first = client.post(_url(), headers=h, json=body)
    assert first.status_code == 201 and "Idempotent-Replayed" not in first.headers
    again = client.post(_url(), headers=h, json=body)  # the first reply was lost; the client resends
    assert again.status_code == 200 and again.headers["Idempotent-Replayed"] == "true"
    assert again.json() == first.json()
    assert len(_rows(client)) == 1
    # A deliberate new try (a new key, even with the same text) is a new answer.
    third = client.post(_url(), headers=h, json={**body, "client_request_id": "op-another-try-0001"})
    assert third.status_code == 201 and third.json()["id"] != first.json()["id"]
    assert len(_rows(client)) == 2


def test_unkeyed_answers_behave_as_before(client):
    h = auth_headers(register(client))
    a = client.post(_url(), headers=h, json={"answer": TEXT})
    b = client.post(_url(), headers=h, json={"answer": TEXT})
    assert a.status_code == b.status_code == 201 and a.json()["id"] != b.json()["id"]
    assert [r.client_request_id for r in _rows(client)] == [None, None]


@pytest.mark.parametrize(
    "change",
    [
        {"answer": TEXT + " Then I documented it."},  # the text changed
        {"answer": TEXT.replace("96%", "95%")},  # one character
        {"answer": TEXT + " "},  # whitespace counts: the stored answer is exactly what was sent
    ],
)
def test_the_same_key_with_a_different_request_is_refused(client, change):
    h = auth_headers(register(client))
    key = "op-conflict-000001"
    client.post(_url(), headers=h, json={"answer": TEXT, "client_request_id": key})
    r = client.post(_url(), headers=h, json={**change, "client_request_id": key})
    assert r.status_code == 409 and r.json()["error"]["code"] == "idempotency_key_reused"
    assert len(_rows(client)) == 1


def test_the_same_key_for_another_question_is_refused(client):
    h = auth_headers(register(client))
    key = "op-other-question-1"
    client.post(_url(_qid(0)), headers=h, json={"answer": TEXT, "client_request_id": key})
    r = client.post(_url(_qid(1)), headers=h, json={"answer": TEXT, "client_request_id": key})
    assert r.status_code == 409 and r.json()["error"]["code"] == "idempotency_key_reused"


def test_keys_belong_to_their_account(client):
    alice = auth_headers(register(client, email="alice@example.com"))
    bob = auth_headers(register(client, email="bob@example.com"))
    body = {"answer": TEXT, "client_request_id": "op-shared-raw-key-1"}
    a = client.post(_url(), headers=alice, json=body)
    b = client.post(_url(), headers=bob, json=body)
    assert a.status_code == b.status_code == 201
    assert a.json()["id"] != b.json()["id"]  # never Alice's answer in Bob's reply
    assert b.json()["answer"] == TEXT and len(_rows(client)) == 2


def test_a_replay_is_never_regraded(client, monkeypatch):
    h = auth_headers(register(client))
    body = {"answer": TEXT, "client_request_id": "op-no-regrade-0001"}
    first = client.post(_url(), headers=h, json=body).json()

    def boom(*args, **kwargs):  # any grading now would be a regrade
        raise AssertionError("graded again")

    monkeypatch.setattr("app.api.routes.careers.graded_answer", boom)
    again = client.post(_url(), headers=h, json=body)
    assert again.status_code == 200
    assert (
        again.json()["score"] == first["score"] and again.json()["rubric_version"] == first["rubric_version"]
    )


def test_a_replay_is_answered_before_the_rate_limit_and_after_retirement(make_client, monkeypatch):
    c = make_client(practice_answers_per_hour=1)
    h = auth_headers(register(c))
    body = {"answer": TEXT, "client_request_id": "op-limit-00000001"}
    assert c.post(_url(), headers=h, json=body).status_code == 201
    # The hour's allowance is used up: a new answer is refused, the resend still gets its answer.
    assert c.post(_url(), headers=h, json={"answer": TEXT}).status_code == 429
    assert c.post(_url(), headers=h, json=body).status_code == 200
    # Retired since: the saved answer is still returned for its own resend; a new one is refused.
    monkeypatch.setattr("app.api.routes.careers.is_retired", lambda *_: True)
    assert c.post(_url(), headers=h, json=body).status_code == 200


def test_a_fingerprint_from_an_unknown_version_is_not_taken_for_a_match(client):
    h = auth_headers(register(client))
    body = {"answer": TEXT, "client_request_id": "op-unknown-version"}
    client.post(_url(), headers=h, json=body)
    db = client.app.state.session_factory()
    row = db.query(PracticeAnswer).one()
    row.request_fingerprint = "v9:" + "0" * 64  # written by some other version of the server
    db.commit()
    db.close()
    r = client.post(_url(), headers=h, json=body)
    assert r.status_code == 409 and r.json()["error"]["code"] == "idempotency_key_unverifiable"
    assert len(_rows(client)) == 1


def test_fingerprints_are_versioned_and_cover_the_whole_request():
    f = answers_module.request_fingerprint
    base = f(TRACK, "q1", TEXT, None, None)
    assert base.startswith("v1:") and len(base) == 3 + 64
    assert f(TRACK, "q1", TEXT, None, None) == base
    assert (
        len(
            {
                base,
                f(TRACK, "q2", TEXT, None, None),
                f("barista", "q1", TEXT, None, None),
                f(TRACK, "q1", TEXT + ".", None, None),
                f(TRACK, "q1", TEXT, "story-1", None),
                f(TRACK, "q1", TEXT, None, "parent-1"),
            }
        )
        == 6
    )
    assert answers_module.same_request(base, base) is True
    assert answers_module.same_request(base, f(TRACK, "q2", TEXT, None, None)) is False
    assert answers_module.same_request(None, base) is None
    assert answers_module.same_request("v2:abc", base) is None


def test_concurrent_resends_save_one_answer(make_client):
    c = make_client()
    h = auth_headers(register(c))
    body = {"answer": TEXT, "client_request_id": "op-race-0123456789"}
    with ThreadPoolExecutor(4) as pool:
        replies = list(pool.map(lambda _: c.post(_url(), headers=h, json=body), range(4)))
    assert {r.status_code for r in replies} <= {200, 201}
    assert sum(r.status_code == 201 for r in replies) == 1
    assert len({r.json()["id"] for r in replies}) == 1
    assert len(_rows(c)) == 1


def test_two_requests_past_the_lookup_at_once_still_save_one(make_client, monkeypatch):
    """Deterministic: both requests pass the "already saved?" lookup before either inserts (a
    barrier inside grading), so the database's (owner, key) uniqueness has to decide."""
    c = make_client()
    h = auth_headers(register(c))
    barrier = threading.Barrier(2, timeout=10)
    real = answers_module.graded_answer

    def graded_after_both_arrive(*args, **kwargs):
        barrier.wait()
        return real(*args, **kwargs)

    monkeypatch.setattr("app.api.routes.careers.graded_answer", graded_after_both_arrive)
    body = {"answer": TEXT, "client_request_id": "op-barrier-00000001"}
    with ThreadPoolExecutor(2) as pool:
        replies = list(pool.map(lambda _: c.post(_url(), headers=h, json=body), range(2)))
    assert sorted(r.status_code for r in replies) == [200, 201]
    assert replies[0].json()["id"] == replies[1].json()["id"]
    assert len(_rows(c)) == 1


def test_a_conflicting_request_racing_the_original_is_refused_not_saved(make_client, monkeypatch):
    c = make_client()
    h = auth_headers(register(c))
    barrier = threading.Barrier(2, timeout=10)
    real = answers_module.graded_answer

    def graded_after_both_arrive(*args, **kwargs):
        barrier.wait()
        return real(*args, **kwargs)

    monkeypatch.setattr("app.api.routes.careers.graded_answer", graded_after_both_arrive)
    key = "op-barrier-conflict1"
    bodies = [
        {"answer": TEXT, "client_request_id": key},
        {"answer": TEXT + " Changed.", "client_request_id": key},
    ]
    with ThreadPoolExecutor(2) as pool:
        replies = list(pool.map(lambda b: c.post(_url(), headers=h, json=b), bodies))
    assert sorted(r.status_code for r in replies) == [201, 409]
    assert len(_rows(c)) == 1


def test_a_failure_before_commit_leaves_nothing_and_the_retry_saves_once(make_client, monkeypatch):
    c = make_client()
    h = auth_headers(register(c))
    body = {"answer": TEXT, "client_request_id": "op-fails-before-commit"}
    real = answers_module.graded_answer
    calls = {"n": 0}

    def fails_once(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("grading crashed")
        return real(*args, **kwargs)

    monkeypatch.setattr("app.api.routes.careers.graded_answer", fails_once)
    with pytest.raises(RuntimeError):
        c.post(_url(), headers=h, json=body)
    assert _rows(c) == []  # nothing half-saved, no key left behind
    assert c.post(_url(), headers=h, json=body).status_code == 201
    assert c.post(_url(), headers=h, json=body).status_code == 200
    assert len(_rows(c)) == 1


def test_a_reply_lost_after_commit_is_recovered_by_the_resend(make_client, monkeypatch):
    c = make_client()
    h = auth_headers(register(c))
    body = {"answer": TEXT, "client_request_id": "op-lost-after-commit"}
    real = answers_module.answer_out
    calls = {"n": 0}

    def fails_once(row):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("the reply was lost after the answer was saved")
        return real(row)

    monkeypatch.setattr("app.api.routes.careers.answer_out", fails_once)
    with pytest.raises(RuntimeError):
        c.post(_url(), headers=h, json=body)
    assert len(_rows(c)) == 1  # it was saved
    again = c.post(_url(), headers=h, json=body)
    assert again.status_code == 200 and again.json()["id"] == _rows(c)[0].id
    assert len(_rows(c)) == 1


@pytest.mark.parametrize(
    "bad",
    ["short", "has spaces in it", "x" * 65, "semi;colon-0001", "üñíçødé-00001", 12345678, ["op-in-a-list"]],
)
def test_keys_are_validated_and_a_refused_key_saves_nothing(client, bad):
    h = auth_headers(register(client))
    r = client.post(_url(), headers=h, json={"answer": TEXT, "client_request_id": bad})
    assert r.status_code == 422
    assert _rows(client) == []


def test_keys_at_the_size_limits_and_many_distinct_keys(make_client):
    c = make_client(practice_answers_per_hour=100)
    h = auth_headers(register(c))
    for key in ("k" * 8, "K" * 64):
        assert c.post(_url(), headers=h, json={"answer": TEXT, "client_request_id": key}).status_code == 201
    for i in range(30):
        r = c.post(_url(), headers=h, json={"answer": TEXT, "client_request_id": f"op-many-{i:08d}"})
        assert r.status_code == 201
    assert len(_rows(c)) == 32 and len({r.client_request_id for r in _rows(c)}) == 32


# --- explicit revision links (brief 09) -----------------------------------------------------


def test_a_revision_links_to_the_learners_own_earlier_answer(client):
    h = auth_headers(register(client))
    first = client.post(_url(), headers=h, json={"answer": TEXT}).json()
    assert first["revises_answer_id"] is None
    rev = client.post(
        _url(), headers=h, json={"answer": TEXT + " Then I documented it.", "revises_answer_id": first["id"]}
    )
    assert rev.status_code == 201 and rev.json()["revises_answer_id"] == first["id"]
    listed = client.get(_url(), headers=h).json()
    assert [a["revises_answer_id"] for a in listed] == [first["id"], None]  # newest first


def test_a_revision_link_must_be_yours_and_to_the_same_question(client):
    alice = auth_headers(register(client, email="alice@example.com"))
    bob = auth_headers(register(client, email="bob@example.com"))
    alices = client.post(_url(), headers=alice, json={"answer": TEXT}).json()
    # Another account's answer: 404 (it isn't confirmed to exist), and nothing is saved.
    r = client.post(_url(), headers=bob, json={"answer": TEXT, "revises_answer_id": alices["id"]})
    assert r.status_code == 404 and "Alice" not in r.text and TEXT not in r.text
    assert (
        client.post(
            _url(), headers=bob, json={"answer": TEXT, "revises_answer_id": "no-such-answer"}
        ).status_code
        == 404
    )
    # Your own answer to a different question.
    r = client.post(_url(_qid(1)), headers=alice, json={"answer": TEXT, "revises_answer_id": alices["id"]})
    assert r.status_code == 400 and r.json()["error"]["code"] == "revision_other_question"
    assert len(_rows(client)) == 1


def test_a_replay_cant_change_a_revision_link(client):
    h = auth_headers(register(client))
    a = client.post(_url(), headers=h, json={"answer": TEXT}).json()
    b = client.post(_url(), headers=h, json={"answer": TEXT}).json()
    key = "op-revision-replay-1"
    client.post(
        _url(), headers=h, json={"answer": TEXT, "revises_answer_id": a["id"], "client_request_id": key}
    )
    r = client.post(
        _url(), headers=h, json={"answer": TEXT, "revises_answer_id": b["id"], "client_request_id": key}
    )
    assert r.status_code == 409


def test_deleting_an_earlier_answer_leaves_its_revision_unlinked(client):
    h = auth_headers(register(client))
    first = client.post(_url(), headers=h, json={"answer": TEXT}).json()
    rev = client.post(
        _url(), headers=h, json={"answer": TEXT + " More.", "revises_answer_id": first["id"]}
    ).json()
    db = client.app.state.session_factory()
    db.delete(db.get(PracticeAnswer, first["id"]))
    db.commit()
    kept = db.get(PracticeAnswer, rev["id"])
    assert kept is not None and kept.revises_answer_id is None  # the revision stays, unlinked
    db.close()


def test_the_server_says_it_honours_keys_and_the_export_keeps_links_but_not_keys(client):
    assert client.get("/api/v1/capabilities").json()["answer_request_keys"] is True
    h = auth_headers(register(client))
    first = client.post(
        _url(), headers=h, json={"answer": TEXT, "client_request_id": "op-export-000001"}
    ).json()
    client.post(_url(), headers=h, json={"answer": TEXT, "revises_answer_id": first["id"]})
    exported = client.get("/api/v1/me/export", headers=h)
    assert exported.status_code == 200
    answers = exported.json()["interview_answers"]
    assert [a["revises"] for a in answers] == [None, first["id"]]
    assert "op-export-000001" not in exported.text
