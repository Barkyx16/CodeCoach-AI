"""Comparing authored sample answers (Volume 10, prompt 6; docs/COMPARE_ANSWERS.md): excerpts
marked with reasons, compared with an authored explanation tied to the rubric. A clearly supported
choice, a different reasoned choice, a both-have-tradeoffs lesson, an early reveal, quotes anchored
to the version reviewed, no AI, hostile text, ownership, and the sealed evaluation set kept out.
Synthetic content and accounts only."""

from __future__ import annotations

import dataclasses
import json

from sqlalchemy import func, select

from app.comparisons import BY_ID, SEED_DIR
from app.content import validate
from app.models import ComparisonAttempt

from .conftest import auth_headers, register

MINE = "/api/v1/me/comparisons"
SPECIFIC = "cmp-specific-evidence"
TRADEOFF = "cmp-tradeoffs"


def pick(sample: str, sentence: str, kind: str, reason: str) -> dict:
    return {"sample": sample, "sentence": sentence, "kind": kind, "reason": reason}


def send(client, h, lesson: str, selections: list[dict], choice: str | None = None, early: bool = False):
    body = {"selections": selections, "choice": choice, "revealed_early": early}
    return client.post(f"{MINE}/{lesson}/attempts", json=body, headers=h)


def test_the_lesson_shows_samples_but_not_the_explanation_until_asked(client):
    listed = client.get("/api/v1/comparisons").json()
    assert [item["id"] for item in listed] == list(BY_ID)
    body = client.get(f"/api/v1/comparisons/{SPECIFIC}").json()
    assert [s["label"] for s in body["samples"]] == ["Answer A", "Answer B"]  # neutral labels
    assert body["samples"][0]["sentences"][0] == {
        "id": "a1",
        "text": BY_ID[SPECIFIC].samples[0]["sentences"][0]["text"],
    }
    text = json.dumps(body)
    assert "explanation" not in body and BY_ID[SPECIFIC].explanation["summary"] not in text
    shown = client.get(f"/api/v1/comparisons/{SPECIFIC}/explanation").json()  # the deliberate reveal
    assert shown["preferred"] == "B"
    assert client.get("/api/v1/comparisons/cmp-nope").status_code == 404


def test_a_clearly_supported_choice_with_matching_reasons(client):
    h = auth_headers(register(client))
    made = send(
        client,
        h,
        SPECIFIC,
        [
            pick("B", "b3", "strength", "It says exactly what they did: asked for time, brought examples."),
            pick("A", "a1", "gap", "A claim about yourself is not evidence of anything."),
        ],
        choice="B",
    )
    assert made.status_code == 201, made.text
    out = made.json()
    sel = out["feedback"]["selections"]
    assert [s["status"] for s in sel] == ["matches", "matches"]
    assert sel[0]["quote"] == BY_ID[SPECIFIC].sentence("B", "b3")  # the quote is the reviewed sample's text
    assert "What you did, step by step" in sel[0]["note"]
    assert "as the explanation does" in out["feedback"]["choice_note"]
    assert "Check that your reasons match its reasons, not just its choice" in out["feedback"]["choice_note"]
    assert out["explanation"]["summary"].startswith("Answer B lets an interviewer see")
    assert "score" not in json.dumps(out["feedback"]).lower()


def test_a_different_reasoned_choice_is_explained_not_marked_wrong(client):
    h = auth_headers(register(client))
    fb = send(
        client,
        h,
        SPECIFIC,
        [
            pick(
                "A", "a3", "strength", "Listening first and explaining your side is a sound way to handle it."
            ),
            pick("A", "a1", "strength", "Knowing your strengths shows self-awareness."),
            pick("B", "b2", "gap", "Doubting a colleague's plan could come across as negative."),
        ],
        choice="A",
    ).json()["feedback"]
    assert [s["status"] for s in fb["selections"]] == ["matches", "differs", "differs"]
    assert "both can have a point" in fb["selections"][1]["note"]
    assert fb["selections"][1]["explanation_why"].startswith("A claim about yourself isn't evidence")
    assert fb["choice_note"].startswith("You chose Answer A; the explanation prefers Answer B")
    assert "may still be worth keeping" in fb["choice_note"]


def test_a_tradeoff_lesson_has_no_best_answer_to_choose(client):
    h = auth_headers(register(client))
    refused = send(
        client, h, TRADEOFF, [pick("A", "a1", "strength", "Lets the customer be heard first.")], choice="A"
    )
    assert refused.status_code == 400 and refused.json()["error"]["code"] == "invalid_choice"
    fb = send(
        client,
        h,
        TRADEOFF,
        [
            pick("A", "a1", "strength", "Lets the customer be heard first."),
            pick("B", "b3", "strength", "Gives a real choice with timing."),
            pick("A", "a4", "gap", "A callback is another wait for an angry customer."),
        ],
    ).json()["feedback"]
    assert [s["status"] for s in fb["selections"]] == ["matches", "matches", "matches"]
    assert fb["choice_note"].startswith("This lesson has no single best answer")


def test_reasons_are_required_and_excerpts_must_exist_in_this_version(client):
    h = auth_headers(register(client))
    short = send(client, h, SPECIFIC, [pick("B", "b3", "strength", "good")])
    assert short.status_code == 400 and short.json()["error"]["code"] == "reason_required"
    missing = send(client, h, SPECIFIC, [pick("B", "b9", "strength", "this does not exist anywhere")])
    assert missing.status_code == 400 and missing.json()["error"]["code"] == "unknown_excerpt"
    twice = send(client, h, SPECIFIC, [pick("B", "b3", "strength", "one two three")] * 2)
    assert twice.status_code == 400 and twice.json()["error"]["code"] == "duplicate_excerpt"
    assert send(client, h, SPECIFIC, []).status_code == 422


def test_an_early_reveal_is_recorded_and_an_old_attempt_keeps_its_version(client, monkeypatch):
    h = auth_headers(register(client))
    made = send(
        client, h, SPECIFIC, [pick("B", "b4", "strength", "A result that can be checked.")], early=True
    ).json()
    assert made["revealed_early"] is True
    old = BY_ID[SPECIFIC]
    edited = [dict(s) for s in old.samples]
    edited[1] = {**edited[1], "sentences": [{"id": "b1", "text": "A rewritten sample."}]}
    monkeypatch.setitem(BY_ID, SPECIFIC, dataclasses.replace(old, version=2, samples=tuple(edited)))
    again = client.get(f"{MINE}/attempts/{made['id']}", headers=h).json()
    assert (again["lesson_version"], again["current_version"]) == (1, 2)
    assert again["selections"][0]["quote"] == old.sentence("B", "b4")
    assert again["samples"][1]["sentences"][3]["text"] == old.sentence("B", "b4")
    assert again["explanation"] == old.explanation
    stale = send(client, h, SPECIFIC, [pick("B", "b4", "strength", "A result that can be checked.")])
    assert stale.status_code == 400 and stale.json()["error"]["code"] == "unknown_excerpt"  # not in version 2


def test_it_works_the_same_when_the_ai_coach_is_unavailable(client):
    class Down:
        name, model = "anthropic", "m"

        def __getattr__(self, _):
            raise AssertionError("comparisons don't call the AI coach")

    client.app.state.ai_provider = Down()
    h = auth_headers(register(client))
    made = send(client, h, SPECIFIC, [pick("B", "b3", "strength", "Specific actions are named.")], choice="B")
    assert made.status_code == 201 and made.json()["feedback"]["method"].startswith("Fixed rules, not AI")


def test_reasons_are_kept_as_plain_text(client):
    h = auth_headers(register(client))
    hostile = '<img src=x onerror="alert(1)"> specific actions </b><script>alert(2)</script>'
    made = send(client, h, SPECIFIC, [pick("B", "b3", "strength", hostile + "\x00\x07")]).json()
    assert made["selections"][0]["reason"] == hostile


def test_another_account_can_not_read_your_reading_and_deletion_removes_it(client):
    data = register(client)
    ada = auth_headers(data)
    bea = auth_headers(register(client, email="bea@example.com"))
    secret = "ADA-CMP-4410"
    made = send(client, ada, SPECIFIC, [pick("B", "b3", "strength", f"specific actions {secret}")]).json()
    assert client.get(f"{MINE}/attempts/{made['id']}", headers=bea).status_code == 404
    r = client.get(f"{MINE}/{SPECIFIC}/attempts", headers=bea)
    assert r.status_code == 200 and r.json() == [] and secret not in r.text
    exported = client.get("/api/v1/me/export", headers=ada).json()["comparisons"]
    assert exported[0]["selections"][0]["reason"].endswith(secret)
    gone = client.request(
        "DELETE", "/api/v1/auth/me", headers=ada, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    assert gone.status_code == 204
    with client.app.state.session_factory() as db:
        count = (
            select(func.count())
            .select_from(ComparisonAttempt)
            .where(ComparisonAttempt.user_id == data["user"]["id"])
        )
        assert db.scalar(count) == 0


def test_only_the_authored_lessons_are_served_never_evaluation_data(client):
    """Lessons come only from app/seed/comparisons; an id can't reach any other file (the sealed
    evaluation set included, which this test doesn't open)."""
    assert all(lesson_id.startswith("cmp-") for lesson_id in BY_ID)
    for probe in (
        "..%2F..%2Fevals%2Fsealed%2Fcareer_rn_sealed",
        "career_rn_sealed",
        "cmp-specific-evidence.json",
    ):
        assert client.get(f"/api/v1/comparisons/{probe}").status_code == 404
        assert client.get(f"/api/v1/comparisons/{probe}/explanation").status_code == 404


def test_the_validator_refuses_a_lesson_whose_explanation_cites_missing_text(tmp_path, monkeypatch):
    good = json.loads((SEED_DIR / "001-cmp-specific-evidence.json").read_text())
    bad = json.loads(json.dumps(good))
    bad["id"] = "cmp-broken"
    bad["explanation"]["samples"]["B"]["strengths"][0]["sentences"] = ["b9"]
    bad["explanation"]["samples"]["A"]["gaps"][0]["criterion"] = "charisma"
    bad["samples"][0]["label"] = "The weak answer"
    (tmp_path / "001-cmp-broken.json").write_text(json.dumps(bad))
    tradeoff = {**good, "id": "cmp-tradeoff-bad", "kind": "tradeoff"}  # a tradeoff lesson can't prefer one
    (tmp_path / "002-cmp-tradeoff-bad.json").write_text(json.dumps(tradeoff))
    monkeypatch.setattr(validate, "COMPARISONS_DIR", tmp_path)
    errors = "\n".join(validate.run(None).errors)
    assert (
        "comparison cmp-broken: the explanation cites sentences that aren't in the samples: ['B/b9']"
        in errors
    )
    assert "comparison cmp-broken: unknown rubric criteria in the explanation: ['charisma']" in errors
    assert "comparison cmp-broken: sample labels must be neutral ('Answer A', 'Answer B', ...)" in errors
    assert "comparison cmp-tradeoff-bad: a tradeoff lesson has no preferred answer" in errors
    monkeypatch.setattr(validate, "COMPARISONS_DIR", SEED_DIR)
    assert not [e for e in validate.run(None).errors if "comparison" in e]
