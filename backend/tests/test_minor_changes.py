"""A lesson change marked minor (Volume 15, prompt 5; docs/STORY_FRESHNESS.md): a note taken from
the lesson isn't asked to be reviewed for it, a later change that matters still asks (the minor one
between doesn't hide it), the notes list both with the minor one labelled, the lesson says which
versions were minor, and the content gate refuses a minor mark on version 1, beyond the lesson's
version, or without a note. A coding problem's versions are its tests, which always ask. Synthetic
data only."""

from __future__ import annotations

import dataclasses

from app.content.validate import Report, _learn
from app.learn import UNIT_INDEX
from app.services import note_freshness
from tests.test_note_freshness import NOTES, note, nurse

UNIT = "rn-sbar-handoff"


def lesson_note(client, h):
    r = client.post(NOTES, headers=h, json={"title": "SBAR", "source": {"type": "lesson", "id": UNIT}})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def revise(monkeypatch, *changes: str, minor: tuple[int, ...] = ()):
    real = note_freshness.get_unit

    def revised(unit_id):
        u = real(unit_id)
        if u is None or unit_id != UNIT:
            return u
        return dataclasses.replace(u, version=1 + len(changes), changes=(*u.changes, *changes), minor=minor)

    monkeypatch.setattr(note_freshness, "get_unit", revised)


def test_a_minor_change_doesnt_ask(client, monkeypatch):
    h = nurse(client)
    nid = lesson_note(client, h)
    revise(monkeypatch, "Fixed the spelling of “assessment”.", minor=(2,))
    f = note(client, h, nid)["freshness"]
    assert f["state"] == "current"
    assert "only for typos or wording marked minor" in f["text"]


def test_a_later_change_that_matters_still_asks_and_both_are_listed(client, monkeypatch):
    h = nurse(client)
    nid = lesson_note(client, h)
    revise(monkeypatch, "Fixed the spelling of “assessment”.", "A new worked example.", minor=(2,))
    f = note(client, h, nid)["freshness"]
    assert f["state"] == "needs_review"
    assert f["change_notes"] == [
        "Version 2: Fixed the spelling of “assessment”. (minor)",
        "Version 3: A new worked example.",
    ]


def test_an_unmarked_change_asks_as_before(client, monkeypatch):
    h = nurse(client)
    nid = lesson_note(client, h)
    revise(monkeypatch, "Reworded the SBAR example.")
    f = note(client, h, nid)["freshness"]
    assert f["state"] == "needs_review" and f["change_notes"] == ["Version 2: Reworded the SBAR example."]


def test_the_lesson_says_which_versions_were_minor(client):
    body = client.get(f"/api/v1/learn/units/{UNIT}").json()
    assert body["minor_versions"] == [] and body["changes"] == ["First version."]


def test_the_content_gate_refuses_a_minor_mark_it_cant_check(monkeypatch):
    u = UNIT_INDEX[UNIT]
    bad = {
        "a": dataclasses.replace(u, id="a", minor=(1,)),
        "b": dataclasses.replace(u, id="b", minor=(3,)),
        "c": dataclasses.replace(u, id="c", version=2, changes=(*u.changes, "  "), minor=(2,)),
        "ok": dataclasses.replace(u, id="ok", version=2, changes=(*u.changes, "Typo."), minor=(2,)),
    }
    monkeypatch.setattr("app.content.validate.UNIT_INDEX", bad)
    report = Report()
    _learn(report, set(), set())
    errors = [e for e in report.errors if "minor" in e]
    assert "lesson a: version 1 is marked minor but isn't a later version" in errors
    assert "lesson b: version 3 is marked minor but isn't a later version" in errors
    assert "lesson c: version 2 is marked minor without a change note" in errors
    assert not any(e.startswith("lesson ok:") for e in errors)


def test_a_coding_problems_versions_are_its_tests_and_are_never_minor():
    now = note_freshness.source_now(note_freshness.SourceRef("problem", "two-sum", None, 1), {"two-sum": 3})
    assert now.history == {2: ("", True), 3: ("", True)}
