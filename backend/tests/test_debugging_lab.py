"""The debugging lab (Volume 10, prompt 2; docs/DEBUGGING_LAB.md): exercises whose starter is
deliberately faulty. They're kept apart from the coding library, say up front what the code should
do and which public cases show the defect, keep the explanation and repair until asked, and record
the code each attempt started from so a later correction doesn't rewrite it. The judge decides:
any repair that passes is accepted."""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest
from sqlalchemy import select

from app.content import validate
from app.db.seed import DEBUGGING_DIR
from app.models import Problem, Submission

from .conftest import auth_headers, register

EXERCISES = {
    json.loads(p.read_text())["slug"]: json.loads(p.read_text()) for p in sorted(DEBUGGING_DIR.glob("*.json"))
}
BACKEND = Path(__file__).resolve().parents[1]
java = pytest.mark.skipif(shutil.which("javac") is None, reason="needs a local JDK (CI installs one)")


def _verifier():
    spec = importlib.util.spec_from_file_location(
        "verify_ref", BACKEND / "scripts" / "verify_reference_solutions.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_lab_is_separate_from_the_library(client):
    library = client.get("/api/v1/problems", params={"page_size": 200}).json()
    assert not any(i["slug"].startswith("debug-") for i in library["items"])
    lab = client.get("/api/v1/problems", params={"kind": "debug", "page_size": 50}).json()
    assert [i["slug"] for i in lab["items"]] == list(EXERCISES)
    counts = client.get("/api/v1/problems/counts", params={"kind": "debug"}).json()
    assert counts == {"easy": 2, "medium": 1, "hard": 0}
    library_counts = client.get("/api/v1/problems/counts").json()
    assert sum(library_counts.values()) == library["total"]
    assert "debugging" not in {t["topic"] for t in client.get("/api/v1/topics").json()}


def test_the_brief_names_the_failing_public_cases_and_keeps_the_answer_back(client):
    body = client.get("/api/v1/problems/debug-palindrome-sentence").json()
    seed = EXERCISES["debug-palindrome-sentence"]
    assert body["kind"] == "debug"
    assert body["starter_code"] == seed["starter_code"]  # the faulty code is the starting point
    assert body["lab"]["version"] == 1
    assert body["lab"]["intended_behavior"] == seed["lab"]["intended_behavior"]
    failing = [t for t in body["public_tests"] if t["id"] in body["lab"]["reproduction_test_ids"]]
    assert [t["input"] for t in failing] == [{"s": "Racecar"}, {"s": "1a2"}]
    text = json.dumps(body)
    assert seed["lab"]["defect"]["explanation"] not in text
    assert "isLetterOrDigit" not in text  # the reference repair isn't sent up front
    assert "Panama" not in text  # nor any hidden test
    assert client.get("/api/v1/problems/two-sum").json()["lab"] is None


def test_the_explanation_is_there_when_asked_and_only_for_lab_exercises(client):
    body = client.get("/api/v1/problems/debug-count-at-most/lab/explanation").json()
    seed = EXERCISES["debug-count-at-most"]["lab"]
    assert body["explanation"] == seed["defect"]["explanation"]
    assert body["why_missed"] == seed["defect"]["why_missed"]
    assert "i < nums.length; i++" in body["reference_repair"]
    assert "[7]" not in json.dumps(body)  # no hidden test input
    assert client.get("/api/v1/problems/two-sum/lab/explanation").status_code == 404
    assert client.get("/api/v1/problems/no-such/lab/explanation").status_code == 404


def test_an_attempt_keeps_the_code_it_started_from_through_a_later_correction(make_client):
    client = make_client()
    headers = auth_headers(register(client, "lab@example.com"))
    original = EXERCISES["debug-coldest-day"]["starter_code"]
    fix = original.replace("int coldest = 0;", "int coldest = temps[0];")
    made = client.post(
        "/api/v1/submissions",
        json={"problem_slug": "debug-coldest-day", "language": "java", "source_code": fix, "mode": "submit"},
        headers=headers,
    )
    assert made.status_code == 202, made.text
    sub = made.json()
    assert sub["starting_code"] == original and sub["lab_version"] == 1 and sub["source_code"] == fix

    # The exercise is corrected later: a new version with a different starter.
    with client.app.state.session_factory() as db:
        problem = db.scalar(select(Problem).where(Problem.slug == "debug-coldest-day"))
        assert problem is not None
        problem.starter_code = original.replace("coldest", "lowest")
        problem.lab = {**(problem.lab or {}), "version": 2}
        db.commit()
    again = client.get(f"/api/v1/submissions/{sub['id']}", headers=headers).json()
    assert again["starting_code"] == original and again["lab_version"] == 1

    # Another account can't see it; an ordinary problem's attempt has no starting code.
    stranger = auth_headers(register(client, "stranger@example.com"))
    assert client.get(f"/api/v1/submissions/{sub['id']}", headers=stranger).status_code == 404
    plain = client.post(
        "/api/v1/submissions",
        json={
            "problem_slug": "two-sum",
            "language": "java",
            "source_code": "class Solution {}",
            "mode": "submit",
        },
        headers=headers,
    ).json()
    assert plain["starting_code"] is None and plain["lab_version"] is None
    with client.app.state.session_factory() as db:
        assert db.scalar(select(Submission.starting_code).where(Submission.id == sub["id"])) == original


def test_the_validator_rejects_a_malformed_exercise(tmp_path, monkeypatch):
    good = EXERCISES["debug-count-at-most"]
    bad = json.loads(json.dumps(good))
    bad["slug"] = "debug-broken-example"
    bad["lab"]["reproduction"] = [4]  # a hidden test: the reproduction must be public
    bad["lab"]["defect"]["why_missed"] = " "
    bad["hints"] = ["only one"]
    (tmp_path / "001-debug-broken-example.json").write_text(json.dumps(bad))
    (tmp_path / "002-wrong-prefix.json").write_text(json.dumps({**good, "slug": "count-at-most"}))
    monkeypatch.setattr(validate, "DEBUGGING_DIR", tmp_path)
    report = validate.run(None)
    errors = "\n".join(report.errors)
    assert "debugging debug-broken-example: lab.reproduction must list public test positions" in errors
    assert "lab is missing ['defect.why_missed']" in errors
    assert "needs at least two staged hints" in errors
    assert "no reference repair" in errors
    assert "a debugging exercise's slug starts with 'debug-'" in errors
    monkeypatch.setattr(validate, "DEBUGGING_DIR", DEBUGGING_DIR)
    assert not [e for e in validate.run(None).errors if "debugging" in e]


@java
def test_each_starter_shows_its_defect_and_each_repair_passes():
    verify = _verifier()
    for path in sorted(DEBUGGING_DIR.glob("*.json")):
        assert verify.check_debug_exercise(path) == [], path.name


@java
def test_the_check_catches_an_exercise_that_doesnt_show_its_defect(tmp_path):
    verify = _verifier()
    seed = EXERCISES["debug-count-at-most"]
    (tmp_path / "alternatives").mkdir()

    def check(data: dict, alternative: str | None = None) -> str:
        path = tmp_path / f"{data['slug']}.json"
        path.write_text(json.dumps(data))
        for old in (tmp_path / "alternatives").glob("*.java"):
            old.unlink()
        if alternative:
            (tmp_path / "alternatives" / f"{data['slug']}.1.java").write_text(alternative)
        return "\n".join(verify.check_debug_exercise(path))

    wrong_repro = {**seed, "lab": {**seed["lab"], "reproduction": [1]}}
    assert "fails public tests [2], but lab.reproduction says [1]" in check(wrong_repro)
    fixed_starter = {**seed, "starter_code": seed["starter_code"].replace("nums.length - 1", "nums.length")}
    assert "but lab.reproduction says [2]" in check(fixed_starter)  # the "faulty" code isn't faulty
    no_compile = {**seed, "starter_code": seed["starter_code"].replace("int count = 0;", "int count = 0")}
    assert "the faulty starter doesn't compile" in check(no_compile)
    crashing = {
        **seed,
        "starter_code": seed["starter_code"].replace("nums[i] <= limit", "nums[i + 2] <= limit"),
    }
    assert "crashes instead of failing" in check(crashing)
    wrong_alternative = seed["starter_code"]  # "an alternative repair" that's still the bug
    assert "alternative debug-count-at-most.1.java" in check(seed, wrong_alternative)


def test_unchanged_faulty_code_isnt_called_a_placeholder():
    from app.services.ai.static_analysis import analyze

    starter = EXERCISES["debug-count-at-most"]["starter_code"]
    found = analyze(starter, starter_code=starter)
    assert found.is_unchanged_starter
    assert "the code as given, defect included" in found.findings[0].detail
    assert "placeholder" not in found.findings[0].detail
    stub = "class Solution {\n    public int f() {\n        // TODO: write your solution here\n        return 0;\n    }\n}\n"
    assert "placeholder" in analyze(stub, starter_code=stub).findings[0].detail
