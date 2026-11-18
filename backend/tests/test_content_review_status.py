"""What content is still waiting for its review (Volume 19, prompt 7; docs/LEARN_CONTENT.md): every
generated_draft lesson is listed as owed and no author_reviewed one is; every format appears; --owed
prints only what's owed and --json the same report; the exit code is 0 either way (a report, not a
gate); statuses are the content's own words; each line says where its note lives. A fixture with one
item per format checks the grouping, so a renamed field fails loudly instead of dropping a format.
The content gate refuses an author_reviewed lesson that names a drafting tool as its reviewer."""

from __future__ import annotations

import ast
import dataclasses
import json
from pathlib import Path

import pytest
import yaml

import app.careers
import app.drills
import app.learn
import app.offers
import app.scenarios
import app.whiteboard
from app import cli
from app.careers import followups
from app.content import problem_followups, validate
from app.content import review_status as rs

FORMATS = {
    "lesson",
    "scenario",
    "sample-answer lesson",
    "work sample",
    "code-review exercise",
    "test-design exercise",
    "debugging exercise",
    "offer case",
    "question follow-up",
    "problem follow-up",
    "drill",
    "whiteboard prompt",
    "career questions",
    "coding problems",
}


def test_every_draft_lesson_is_owed_and_no_reviewed_one_is():
    items = {(i.format, i.id): i for i in rs.report()}
    for unit in app.learn.UNIT_INDEX.values():
        item = items[("lesson", unit.id)]
        assert item.group == ("owed" if unit.review.status == "generated_draft" else "reviewed"), unit.id
        assert unit.review.status in item.status and unit.review.by in item.status  # its own words
        assert item.where == "backend/app/learn/units.py: review"
        assert (item.title, item.version) == (unit.title, unit.version)
    assert any(i.group == "owed" for i in items.values())  # today: se-failing-test


def test_every_format_appears_and_each_line_says_where_its_note_lives():
    items = rs.report()
    assert {i.format for i in items} == FORMATS
    for i in items:
        assert i.where.startswith("backend/"), i
        path = i.where.split(":")[0].split(" (")[0]
        assert (rs.BACKEND.parent / path).exists(), i.where
    # The question bank is counted per career, by the status its labels record.
    questions = [i for i in items if i.format == "career questions"]
    assert len(questions) == len(app.careers.CATALOG)
    assert all(i.count and i.status == rs.QUESTION_STATUS and i.group == "none" for i in questions)


def test_owed_filters_json_says_the_same_and_the_exit_code_is_zero(capsys):
    assert cli.main(["app.cli", "content", "review-status", "--owed"]) == 0
    owed = capsys.readouterr().out
    assert owed.startswith("Review owed (drafted and not yet checked): ")
    assert "\nReviewed: " not in owed and "No review recorded" not in owed
    assert "se-failing-test" in owed and "se-hash-map-lookup" not in owed
    assert cli.main(["app.cli", "content", "review-status"]) == 0
    full = capsys.readouterr().out
    assert "\nReviewed: " in full and "\nNo review recorded: " in full and "se-hash-map-lookup" in full
    assert cli.main(["app.cli", "content", "review-status", "--owed", "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["owed"] == len(doc["items"]) and {i["group"] for i in doc["items"]} == {"owed"}
    assert {"format", "id", "title", "version", "group", "kind", "status", "where"} <= set(doc["items"][0])


def test_an_unknown_note_is_owed_never_upgraded():
    assert rs._text_kind("Looks fine to me.") == ("owed", "its note names no check")
    assert rs._text_kind("Written for practice and machine-checked: ran every test.")[0] == "reviewed"
    assert rs._structured("something_else", "x", "2026-01-01", "")[0] == "owed"


def _fixture(tmp_path, monkeypatch, *, rename: str | None = None):
    """One item per format: seeded formats from files written here, the rest from one real item."""
    seed = tmp_path / "seed"
    files = {
        "comparisons": {
            "id": "cmp-x",
            "title": "C",
            "version": 1,
            "review_status": "checked for consistency.",
        },
        "worksamples": {"id": "ws-x", "title": "W", "version": 1, "review_status": "Looks fine."},
        "reviews": {"slug": "rv-x", "title": "R", "version": 2, "review_status": "machine-checked."},
        "testdesign": {"slug": "td-x", "title": "T", "version": 1, "review_status": "machine-checked."},
        "debugging": {
            "slug": "db-x",
            "title": "D",
            "lab": {"version": 3, "review_status": "machine-checked."},
        },
        "problems": {"slug": "p-x"},
    }
    for folder, data in files.items():
        (seed / folder).mkdir(parents=True)
        if rename and folder == rename:
            block = data.get("lab", data)
            block["status_of_review"] = block.pop("review_status")
        (seed / folder / "001.json").write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(rs, "SEED", seed)
    draft = next(u for u in app.learn.UNIT_INDEX.values() if u.review.status == "generated_draft")
    monkeypatch.setattr(app.learn, "UNIT_INDEX", {draft.id: draft})
    first = next(iter(app.scenarios.SCENARIO_INDEX.values()))
    monkeypatch.setattr(app.scenarios, "SCENARIO_INDEX", {first.id: first})
    monkeypatch.setattr(app.offers, "CASES", app.offers.CASES[:1])
    monkeypatch.setattr(followups, "RELATIONSHIPS", followups.RELATIONSHIPS[:1])
    monkeypatch.setattr(problem_followups, "PAIRS", problem_followups.PAIRS[:1])
    monkeypatch.setattr(app.drills, "DRILLS", app.drills.DRILLS[:1])
    monkeypatch.setattr(app.whiteboard, "PROMPTS", app.whiteboard.PROMPTS[:1])
    track = "registered-nurse"
    monkeypatch.setattr(app.careers, "CATALOG", {track: app.careers.CATALOG[track]})


def test_a_fixture_with_one_item_per_format_lands_in_its_group(tmp_path, monkeypatch):
    _fixture(tmp_path, monkeypatch)
    got = {i.format: (i.id, i.version, i.group, i.kind.split(";")[0]) for i in rs.report()}
    assert set(got) == FORMATS
    assert got["sample-answer lesson"] == ("cmp-x", 1, "reviewed", "checked for consistency")
    assert got["work sample"] == ("ws-x", 1, "owed", "its note names no check")  # never upgraded
    assert got["code-review exercise"] == ("rv-x", 2, "reviewed", "machine-checked")
    assert got["debugging exercise"] == ("db-x", 3, "reviewed", "machine-checked")
    assert got["lesson"][2] == "owed" and got["scenario"][2] == "reviewed"
    assert got["drill"][2] == got["whiteboard prompt"][2] == got["career questions"][2] == "none"
    assert got["coding problems"][:3] == ("problem-bank", None, "none")


@pytest.mark.parametrize("folder", ["comparisons", "worksamples", "reviews", "testdesign", "debugging"])
def test_a_renamed_review_field_fails_loudly(tmp_path, monkeypatch, folder):
    _fixture(tmp_path, monkeypatch, rename=folder)
    with pytest.raises(KeyError):
        rs.report()


def test_the_gate_refuses_an_author_reviewed_lesson_that_names_a_drafting_tool(monkeypatch):
    unit = next(iter(app.learn.UNIT_INDEX.values()))
    review = dataclasses.replace(
        unit.review, status="author_reviewed", by="Drafted with an AI coding assistant"
    )
    monkeypatch.setitem(validate.UNIT_INDEX, unit.id, dataclasses.replace(unit, review=review))
    report = validate.Report()
    validate._learn(report, set(), set())
    assert any(
        e.startswith(f"lesson {unit.id}: its review says author_reviewed but names a drafting tool")
        for e in report.errors
    )
    # A draft that says so, or the author's own review, is fine.
    for ok in (
        dataclasses.replace(review, status="generated_draft"),
        dataclasses.replace(review, by="CodeCoach project author"),
    ):
        monkeypatch.setitem(validate.UNIT_INDEX, unit.id, dataclasses.replace(unit, review=ok))
        report = validate.Report()
        validate._learn(report, set(), set())
        assert not [e for e in report.errors if "drafting tool" in e]


# --- a claim names its check (Volume 20, prompt 8) -------------------------------------------------


REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"


def stale(checks: dict[str, rs.Check], workflow: str) -> list[str]:
    """What a mapped check names that isn't there: a test, a command's script, or a CI step that runs it."""
    problems: list[str] = []
    jobs = {job.get("name", key): job for key, job in yaml.safe_load(workflow)["jobs"].items()}
    for fmt, c in checks.items():
        path, _, func = c.test.partition("::")
        file = REPO / path
        if not file.exists():
            problems.append(f"{fmt}: {path} doesn't exist")
        elif func not in {
            n.name for n in ast.walk(ast.parse(file.read_text())) if isinstance(n, ast.FunctionDef)
        }:
            problems.append(f"{fmt}: {path} has no test {func}")
        script = c.command.split()[1]
        if not (REPO / "backend" / script).exists():
            problems.append(f"{fmt}: {script} doesn't exist")
        runs = {"pytest": False, "command": False}
        for job_name, step_name in c.ci:
            job = jobs.get(job_name)
            step = next((s for s in (job or {}).get("steps", []) if s.get("name") == step_name), None)
            if step is None:
                problems.append(f"{fmt}: no CI step {job_name!r} › {step_name!r}")
                continue
            if any("setup-java" in str(s.get("uses", "")) for s in job["steps"]) is False:
                problems.append(f"{fmt}: {job_name!r} installs no JDK, so the check would be skipped")
            run = str(step.get("run", "")).strip()
            runs["pytest"] |= run.split()[:1] == ["pytest"]
            runs["command"] |= run == c.command
        if not runs["pytest"]:
            problems.append(f"{fmt}: no mapped CI step runs pytest (the test)")
        if not runs["command"]:
            problems.append(f"{fmt}: no mapped CI step runs `{c.command}`")
    return problems


def test_every_mapped_check_exists_and_ci_runs_it():
    assert stale(rs.MACHINE_CHECKS, WORKFLOW.read_text()) == []


def test_a_renamed_ci_step_or_test_fails_the_tables_test():
    renamed = WORKFLOW.read_text().replace(
        "- name: Reference solutions pass every seeded test", "- name: Reference solutions pass"
    )
    assert any("Reference solutions pass every seeded test" in p for p in stale(rs.MACHINE_CHECKS, renamed))
    gone = {
        "debugging exercise": dataclasses.replace(
            rs.MACHINE_CHECKS["debugging exercise"], test="backend/tests/test_debugging_lab.py::test_renamed"
        )
    }
    assert stale(gone, WORKFLOW.read_text()) == [
        "debugging exercise: backend/tests/test_debugging_lab.py has no test test_renamed"
    ]


def test_every_format_is_mapped_or_named_as_having_no_machine_check():
    assert set(rs.MACHINE_CHECKS) | set(rs.NO_MACHINE_CHECK) == FORMATS
    assert not set(rs.MACHINE_CHECKS) & set(rs.NO_MACHINE_CHECK)
    assert all(rs.NO_MACHINE_CHECK.values()) and all(c.proves for c in rs.MACHINE_CHECKS.values())


def test_every_machine_checked_item_today_names_its_existing_check():
    claimed = [i for i in rs.report() if i.kind.startswith("machine-checked")]
    assert {i.format for i in claimed} == set(rs.MACHINE_CHECKS)
    for i in claimed:
        assert i.group == "reviewed" and i.check is not None, i.id
        c = rs.MACHINE_CHECKS[i.format]
        assert i.check == {
            "proves": c.proves,
            "test": c.test,
            "command": c.command,
            "ci": [f"{j} › {s}" for j, s in c.ci],
        }
    assert not [i for i in rs.report() if i.group == "unverified"]
    assert not [i for i in rs.report() if i.check and not i.kind.startswith("machine-checked")]


def test_a_claim_with_no_check_here_is_listed_apart_never_as_reviewed(tmp_path, monkeypatch):
    _fixture(tmp_path, monkeypatch)
    sample = tmp_path / "seed" / "worksamples" / "001.json"
    sample.write_text(
        json.dumps(
            {"id": "ws-x", "title": "W", "version": 1, "review_status": "Machine-checked by a script."}
        ),
        encoding="utf-8",
    )
    got = {i.format: i for i in rs.report()}
    claim = got["work sample"]
    assert claim.group == "unverified" and claim.check is None
    assert claim.kind == "machine-checked: claimed, no check found here"
    assert got["code-review exercise"].group == "reviewed" and got["code-review exercise"].check
    text = rs.render(rs.report(), owed_only=True)  # what CI's content gate prints
    assert "Claimed machine-checked, no check found here: 1" in text and "ws-x" in text
    assert "rv-x" not in text  # a backed claim isn't among what's owed


def test_an_authors_review_is_never_reported_as_machine_checked(monkeypatch):
    reviewed = next(u for u in app.learn.UNIT_INDEX.values() if u.review.status == "author_reviewed")
    said = dataclasses.replace(reviewed.review, note="Machine-checked against every case.")
    monkeypatch.setattr(app.learn, "UNIT_INDEX", {reviewed.id: dataclasses.replace(reviewed, review=said)})
    [lesson] = [i for i in rs.report() if i.format == "lesson"]
    assert (lesson.group, lesson.kind.split(";")[0], lesson.check) == (
        "reviewed",
        "the author's review",
        None,
    )


def test_the_report_prints_the_check_and_json_carries_it(capsys):
    assert cli.main(["app.cli", "content", "review-status"]) == 0
    out = capsys.readouterr().out
    c = rs.MACHINE_CHECKS["test-design exercise"]
    assert f"check: {c.proves}" in out and f"by {c.test} and `{c.command}`" in out
    assert "run in CI: Backend (lint, types, SQLite tests, reference solutions) › Tests (SQLite)" in out
    assert cli.main(["app.cli", "content", "review-status", "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    designs = [i for i in doc["items"] if i["format"] == "test-design exercise"]
    assert designs and all(i["check"]["test"] == c.test for i in designs) and doc["unverified"] == 0


def test_cis_content_gate_prints_what_isnt_backed():
    gate = next(
        s
        for j in yaml.safe_load(WORKFLOW.read_text())["jobs"].values()
        for s in j.get("steps", [])
        if str(s.get("name", "")).startswith("Content quality gates")
    )
    assert "python -m app.cli content review-status --owed" in gate["run"]
