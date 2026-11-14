"""Code-review practice (Volume 10, prompt 3; docs/CODE_REVIEW_PRACTICE.md): the learner reviews
someone else's code, writes findings first, then compares them with an authored review. The
comparison is by location, not wording; unsupported claims are named, never rewarded; an exercise
with no defect stays defect-free; an attempt keeps the version it reviewed; findings are the
learner's own. Synthetic content and accounts only."""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import shutil
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.content import validate
from app.models import CodeReviewAttempt, CodeReviewDraft
from app.reviews import BY_SLUG, REVIEWS_DIR

from .conftest import auth_headers, register

BACKEND = Path(__file__).resolve().parents[1]
java = pytest.mark.skipif(shutil.which("javac") is None, reason="needs a local JDK (CI installs one)")
SEEDS = {
    json.loads(p.read_text())["slug"]: json.loads(p.read_text()) for p in sorted(REVIEWS_DIR.glob("*.json"))
}
MINE = "/api/v1/me/code-reviews"


def finding(fid: str, start: int, end: int, problem: str, consequence: str = "", repair: str = "") -> dict:
    return {
        "id": fid,
        "start_line": start,
        "end_line": end,
        "problem": problem,
        "consequence": consequence,
        "repair": repair,
    }


def send(client, headers, slug: str, findings: list[dict], summary: str = ""):
    return client.post(
        f"{MINE}/{slug}/attempts", json={"findings": findings, "summary": summary}, headers=headers
    )


def test_the_exercise_shows_code_and_task_but_not_the_authored_review(client):
    listed = client.get("/api/v1/code-reviews").json()
    assert [e["slug"] for e in listed] == list(SEEDS)
    assert "defect" not in json.dumps(listed)  # nothing hints which exercise has none
    body = client.get("/api/v1/code-reviews/review-largest-number").json()
    seed = SEEDS["review-largest-number"]
    assert body["code"] == seed["code"] and body["line_count"] == 15 and body["version"] == 1
    assert body["problem_title"] == "Find Largest Number"
    assert body["public_tests"][1] == {"position": 2, "input": {"nums": [-5, -2, -11]}, "expected_output": -2}
    text = json.dumps(body)
    for f in seed["findings"]:
        assert f["title"] not in text and f["explanation"] not in text
    assert seed["debrief"] not in text
    assert client.get("/api/v1/code-reviews/no-such").status_code == 404
    assert client.get(f"{MINE}/review-largest-number/draft").status_code == 401


def test_a_correct_finding_and_the_same_point_in_other_words_both_line_up(client):
    h = auth_headers(register(client))
    first = send(
        client,
        h,
        "review-largest-number",
        [
            finding(
                "a",
                7,
                7,
                "largest starts at zero",
                "all-negative input returns 0, which isn't in the array",
                "start from nums[0]",
            )
        ],
    )
    assert first.status_code == 201, first.text
    fb = first.json()["feedback"]
    assert fb["findings"][0]["location"] == "defect" and fb["findings"][0]["matches"] == ["starts-at-zero"]
    assert fb["findings"][0]["consequence"] and fb["findings"][0]["repair"]
    assert (fb["defects_raised"], fb["defects_total"]) == (1, 1)
    assert "score" not in json.dumps(fb).lower()
    # Different words, pointing at where the defect shows (the comparison), still line up.
    other = send(
        client,
        h,
        "review-largest-number",
        [finding("b", 9, 10, "Negative numbers never beat the initial value, so they are ignored.")],
    ).json()["feedback"]
    assert other["findings"][0]["location"] == "defect"
    assert "Add what happens because of it" in " ".join(other["findings"][0]["notes"])
    assert "Add a next step" in " ".join(other["findings"][0]["notes"])


def test_an_unsupported_claim_is_named_and_a_longer_list_earns_nothing(client):
    h = auth_headers(register(client))
    claims = [
        finding("x1", 4, 6, "The empty check is wrong", "it throws", "return 0 instead"),
        finding("x2", 2, 2, "The comment is a bug", "misleads", "delete it"),
        finding("x3", 14, 15, "Braces are wrong", "unclear", "reformat it"),
    ]
    fb = send(client, h, "review-largest-number", claims).json()["feedback"]
    assert [f["location"] for f in fb["findings"]] == ["unsupported"] * 3
    assert "No authored finding covers lines 4–6" in fb["findings"][0]["notes"][0]
    assert fb["unsupported"] == 3 and fb["defects_raised"] == 0
    assert any("short review where each point has evidence" in line for line in fb["summary"])
    # Citing the whole file would line up with everything: a finding that broad isn't matched.
    everything = send(
        client, h, "review-largest-number", [finding("all", 1, 15, "Something here is wrong")]
    ).json()
    assert everything["feedback"]["findings"][0]["location"] == "broad"
    assert everything["feedback"]["defects_raised"] == 0
    assert (
        "Narrow it to where the problem is (6 lines at most)"
        in everything["feedback"]["findings"][0]["notes"][0]
    )


def test_no_defect_is_invented_for_correct_code(client):
    h = auth_headers(register(client))
    fb = send(
        client,
        h,
        "review-binary-search",
        [
            finding(
                "o", 6, 6, "(lo + hi) / 2 overflows", "wrong index on huge arrays", "use lo + (hi - lo) / 2"
            )
        ],
    ).json()["feedback"]
    assert fb["defects_total"] == 0
    assert fb["findings"][0]["location"] == "observation"
    assert "preference, not a defect" in fb["findings"][0]["notes"][0]
    assert fb["summary"][0].startswith("The authored review found no defect in this code")
    # Saying "no defect" with no findings is a complete review; an empty one isn't.
    ok = send(client, h, "review-binary-search", [], summary="Looks correct to me; nothing to change.")
    assert ok.status_code == 201
    assert "agrees there's no defect" in " ".join(ok.json()["feedback"]["summary"])
    empty = send(client, h, "review-binary-search", [])
    assert empty.status_code == 400 and empty.json()["error"]["code"] == "review_empty"
    half = send(client, h, "review-binary-search", [finding("h", 3, 3, "")])
    assert half.status_code == 400 and half.json()["error"]["code"] == "finding_incomplete"


def test_reveal_shows_the_evidence_and_later_reviews_say_they_came_after_it(client):
    h = auth_headers(register(client))
    first = send(
        client, h, "review-second-largest", [finding("d", 9, 10, "duplicates of the max slip in")]
    ).json()
    assert first["after_reveal"] is False
    ref = {f["id"]: f for f in first["reference"]["findings"]}
    assert ref["duplicate-of-largest"]["evidence"] == [
        {"public_test": 2, "input": {"nums": [5, 5, 3]}, "expected": 3, "actual": 5},
        {"public_test": 3, "input": {"nums": [8, 8]}, "expected": -1, "actual": 8},
    ]
    assert ref["duplicate-of-largest"]["excerpt"].strip().startswith("} else if (n > second) {")
    assert ref["minus-one-sentinel"]["kind"] == "observation" and ref["minus-one-sentinel"]["why_preference"]
    again = send(
        client, h, "review-second-largest", [finding("d", 9, 10, "duplicates of the max slip in")]
    ).json()
    assert again["after_reveal"] is True

    other = auth_headers(register(client, email="bea@example.com"))
    assert client.get(f"{MINE}/review-largest-number/draft", headers=other).json()["revealed"] is False
    shown = client.post(f"{MINE}/review-largest-number/reveal", headers=other)
    assert shown.status_code == 200
    assert shown.json()["findings"][0]["evidence"][0]["actual"] == 0
    assert client.get(f"{MINE}/review-largest-number/draft", headers=other).json()["revealed"] is True
    late = send(client, other, "review-largest-number", [finding("a", 7, 7, "starts at zero")]).json()
    assert late["after_reveal"] is True


def test_a_draft_comes_back_and_a_stale_save_is_a_conflict(client):
    h = auth_headers(register(client))
    url = f"{MINE}/review-largest-number/draft"
    assert client.get(url, headers=h).json()["revision"] == 0
    body = {"findings": [finding("a", 7, 7, "starts at zero")], "summary": "", "expected_revision": 0}
    saved = client.put(url, json={**body, "client_request_id": "review-draft-key-1"}, headers=h)
    assert saved.status_code == 200, saved.text
    assert saved.json()["revision"] == 1
    assert saved.json()["findings"][0]["excerpt"] == "        int largest = 0;"
    again = client.get(url, headers=h).json()
    assert again["findings"][0]["problem"] == "starts at zero" and again["exercise_version"] == 1
    # The same save sent again (its reply was lost) is told it went through.
    replay = client.put(url, json={**body, "client_request_id": "review-draft-key-1"}, headers=h).json()
    assert replay["save_replay"] == {"accepted_revision": 1, "current_revision": 1}
    stale = client.put(url, json={**body, "summary": "other tab"}, headers=h)
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "stale_revision"
    out_of_range = client.put(
        url, json={**body, "expected_revision": 1, "findings": [finding("a", 7, 99, "x")]}, headers=h
    )
    assert out_of_range.status_code == 400 and out_of_range.json()["error"]["code"] == "line_out_of_range"


def test_old_attempts_keep_their_version_and_draft_anchors_follow_the_text(client, monkeypatch):
    h = auth_headers(register(client))
    sent = send(client, h, "review-largest-number", [finding("a", 7, 7, "starts at zero")]).json()
    url = f"{MINE}/review-largest-number/draft"
    client.put(
        url,
        json={
            "findings": [finding("a", 7, 7, "starts at zero"), finding("b", 2, 2, "comment")],
            "expected_revision": 0,
        },
        headers=h,
    )
    # The exercise is corrected: a new version with two lines added at the top, one comment gone.
    old = BY_SLUG["review-largest-number"]
    code = "// Reviewed for practice.\n// Synthetic code.\n" + old.code.replace(
        "    /** Returns the largest value in nums. */\n", "    // (no comment)\n"
    )
    monkeypatch.setitem(BY_SLUG, old.slug, dataclasses.replace(old, version=2, code=code))

    kept = client.get(f"{MINE}/attempts/{sent['id']}", headers=h).json()
    assert kept["exercise_version"] == 1 and kept["current_version"] == 2
    assert kept["code"] == old.code and kept["findings"][0]["excerpt"] == "        int largest = 0;"
    draft = client.get(url, headers=h).json()
    assert draft["exercise_version"] == 1 and draft["current_version"] == 2 and draft["revealed"] is False
    a, b = draft["findings"]
    assert (a["anchor"], a["start_line"], a["end_line"]) == ("moved", 9, 9)
    assert b["anchor"] == "missing"  # the cited comment isn't in the new version


def test_another_account_can_not_read_your_findings(client):
    ada = auth_headers(register(client))
    bea = auth_headers(register(client, email="bea@example.com"))
    secret = "ADA-REVIEW-7781"
    made = send(client, ada, "review-largest-number", [finding("a", 7, 7, f"starts at zero {secret}")]).json()
    client.put(
        f"{MINE}/review-largest-number/draft",
        json={"findings": [finding("a", 7, 7, secret)], "expected_revision": 0},
        headers=ada,
    )
    assert client.get(f"{MINE}/attempts/{made['id']}", headers=bea).status_code == 404
    for path in ("/draft", "/attempts"):
        r = client.get(f"{MINE}/review-largest-number{path}", headers=bea)
        assert r.status_code == 200 and secret not in r.text and made["id"] not in r.text


def test_learner_text_is_kept_as_plain_text(client):
    h = auth_headers(register(client))
    hostile = '<img src=x onerror="alert(1)"> </code><script>alert(2)</script>'
    made = send(client, h, "review-largest-number", [finding("a", 7, 7, hostile + "\x00\x07", hostile)])
    assert made.status_code == 201
    f = made.json()["findings"][0]
    assert f["problem"] == hostile and f["consequence"] == hostile  # control characters removed, nothing else


def test_the_review_works_the_same_when_the_ai_coach_is_unavailable(client):
    class Down:
        name, model = "anthropic", "m"

        def __getattr__(self, _):
            raise AssertionError("code-review practice doesn't call the AI coach")

    client.app.state.ai_provider = Down()
    h = auth_headers(register(client))
    made = send(client, h, "review-largest-number", [finding("a", 7, 7, "starts at zero")])
    assert made.status_code == 201
    assert made.json()["feedback"]["method"].startswith("Fixed rules, not AI")
    assert made.json()["reference"]["debrief"] == SEEDS["review-largest-number"]["debrief"]


def test_export_includes_reviews_and_deleting_the_account_removes_them(client):
    data = register(client)
    h = auth_headers(data)
    send(client, h, "review-largest-number", [finding("a", 7, 7, "starts at zero")])
    client.put(
        f"{MINE}/review-binary-search/draft",
        json={"findings": [], "summary": "fine", "expected_revision": 0},
        headers=h,
    )
    exported = client.get("/api/v1/me/export", headers=h).json()["code_reviews"]
    # The binary-search draft, and the one sending a review made (it records the reveal).
    assert {d["exercise"] for d in exported["drafts"]} == {"review-binary-search", "review-largest-number"}
    assert exported["attempts"][0]["code_reviewed"] == SEEDS["review-largest-number"]["code"]
    assert exported["attempts"][0]["findings"][0]["problem"] == "starts at zero"
    deleted = client.request(
        "DELETE", "/api/v1/auth/me", headers=h, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    assert deleted.status_code == 204
    with client.app.state.session_factory() as db:
        for model in (CodeReviewAttempt, CodeReviewDraft):
            assert (
                db.scalar(select(func.count()).select_from(model).where(model.user_id == data["user"]["id"]))
                == 0
            )


def test_the_validator_rejects_a_malformed_exercise(tmp_path, monkeypatch):
    good = SEEDS["review-largest-number"]
    bad = json.loads(json.dumps(good))
    bad["slug"] = "review-broken-example"
    bad["findings"][0]["evidence"] = []  # a defect with no public test
    bad["findings"][1]["evidence"] = [{"public_test": 1, "actual": 9}]  # an observation with a failing test
    bad["findings"][1]["why_preference"] = ""
    bad["findings"][1]["lines"] = [8, 40]
    bad["repaired_code"] = None
    (tmp_path / "001-review-broken-example.json").write_text(json.dumps(bad))
    (tmp_path / "002-wrong-prefix.json").write_text(json.dumps({**good, "slug": "largest-number"}))
    monkeypatch.setattr(validate, "REVIEWS_DIR", tmp_path)
    errors = "\n".join(validate.run(None).errors)
    assert (
        "review review-broken-example finding starts-at-zero: a defect needs evidence from a public test"
        in errors
    )
    assert "finding index-loop: an observation has no failing test" in errors
    assert "finding index-loop: an observation says why it's a preference, not a defect" in errors
    assert "finding index-loop: lines must be [first, last] within the code's 15 lines" in errors
    assert "review review-broken-example: an exercise with a defect needs repaired_code" in errors
    assert "a review exercise's slug starts with 'review-'" in errors
    assert "at least one exercise must have no defect" in errors
    monkeypatch.setattr(validate, "REVIEWS_DIR", REVIEWS_DIR)
    assert not [e for e in validate.run(None).errors if "review" in e]


def _verifier():
    spec = importlib.util.spec_from_file_location(
        "verify_ref", BACKEND / "scripts" / "verify_reference_solutions.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@java
def test_each_authored_review_matches_what_the_code_does_on_the_tests():
    verify = _verifier()
    for path in sorted(REVIEWS_DIR.glob("*.json")):
        assert verify.check_review_exercise(path) == [], path.name


@java
def test_the_check_catches_a_review_that_doesnt_match_the_code(tmp_path):
    verify = _verifier()

    def check(data: dict) -> str:
        path = tmp_path / f"{data['slug']}.json"
        path.write_text(json.dumps(data))
        return "\n".join(verify.check_review_exercise(path))

    seed = SEEDS["review-largest-number"]
    wrong_actual = json.loads(json.dumps(seed))
    wrong_actual["findings"][0]["evidence"][0]["actual"] = -11
    assert "public test 2 returns 0, but the evidence says -11" in check(wrong_actual)
    wrong_test = json.loads(json.dumps(seed))
    wrong_test["findings"][0]["evidence"][0]["public_test"] = 1
    assert "fails public tests [2], but the defects cite [1]" in check(wrong_test)
    # A "correct" exercise whose code actually fails a test: the review can't call it defect-free.
    no_defect = {**seed, "findings": [seed["findings"][1]]}
    assert "has no defect in its review but fails" in check(no_defect)
    bad_repair = {**seed, "repaired_code": seed["code"]}
    assert "repaired_code fails" in check(bad_repair)
