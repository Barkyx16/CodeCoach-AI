"""What content is still waiting for its review (Volume 19, prompt 7; docs/LEARN_CONTENT.md): every
generated_draft lesson is listed as owed and no author_reviewed one is; every format appears; --owed
prints only what's owed and --json the same report; the exit code is 0 either way (a report, not a
gate); statuses are the content's own words; each line says where its note lives. A fixture with one
item per format checks the grouping, so a renamed field fails loudly instead of dropping a format.
The content gate refuses an author_reviewed lesson that names a drafting tool as its reviewer."""

from __future__ import annotations

import dataclasses
import json

import pytest

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
