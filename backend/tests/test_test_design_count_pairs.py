"""A third test-design exercise, labelled as what it is (Volume 20, prompt 9; docs/TEST_DESIGN.md):
Count Pairs, in the existing input shape (int[] and one int), with four faulty versions. Drafted with
an AI coding assistant and machine-checked here: the JDK check shows each faulty version differs
from the reference on its own witness, none throws on any seeded input, and the reference gives
each example's expected output. Its note says its review is owed, and the content review report
lists it as owed, naming the check that backs its machine check; nobody is named as its reviewer.
The list, its page, runs, History and Continue take it as they take the others. Synthetic data."""

from __future__ import annotations

import json
import re

import pytest

from app.content import review_status as rs
from app.testdesign import BY_SLUG, EXERCISES, SEED_DIR, supported_signature
from tests.conftest import auth_headers, register
from tests.test_test_design import _verifier, java

SLUG = "tests-count-pairs"
FILE = SEED_DIR / "003-tests-count-pairs.json"
PUBLIC = "/api/v1/test-design"
MINE = "/api/v1/me/test-design"


def coder(client):
    return auth_headers(register(client, career_track="software-engineer"))


def test_it_follows_the_others_pattern_in_the_existing_shape():
    ex = BY_SLUG[SLUG]
    assert (ex.version, ex.title, len(ex.variants)) == (1, "Test design: Count Pairs", 4)
    assert ex.slug.startswith("tests-") and ex.title.startswith("Test design: ")
    assert supported_signature(ex.signature) and ex.returns == "int"
    for v in ex.variants:
        assert v.defect.count(". ") == 0 and v.defect.endswith("."), v.id  # one plain sentence
        assert v.code != ex.reference and v.title and v.gap and v.witness
    # The two that were there are unchanged: same versions, same faulty versions.
    assert [(e.slug, e.version, len(e.variants)) for e in EXERCISES] == [
        ("tests-count-in-range", 1, 4),
        ("tests-longest-run", 1, 3),
        (SLUG, 1, 4),
    ]


def test_its_note_says_drafted_machine_checked_and_owed_and_names_no_reviewer():
    note = json.loads(FILE.read_text())["review_status"]
    assert "AI coding assistant" in note and "machine-checked" in note and "review is owed" in note
    # "reviewed by" appears only as "not yet reviewed by": nobody is named as having reviewed it.
    assert re.findall(r"(?<!not yet )reviewed by", note) == []


def test_the_review_report_lists_it_as_owed_with_its_check():
    [item] = [i for i in rs.report() if i.id == SLUG]
    assert item.group == "owed" and item.kind == "drafted, its review owed; machine-checked"
    assert item.check and item.check["test"] == rs.MACHINE_CHECKS["test-design exercise"].test
    assert SLUG in rs.render(rs.report(), owed_only=True)
    # The other two are still reviewed, machine-checked.
    others = [i for i in rs.report() if i.format == "test-design exercise" and i.id != SLUG]
    assert [i.group for i in others] == ["reviewed", "reviewed"]


def test_the_list_page_and_runs_take_it_as_they_take_the_others(client):
    listed = {e["slug"]: e for e in client.get(PUBLIC).json()}
    assert listed[SLUG]["variant_count"] == 4 and listed[SLUG]["title"] == "Test design: Count Pairs"
    one = client.get(f"{PUBLIC}/{SLUG}").json()
    text = json.dumps([listed, one])
    for v in BY_SLUG[SLUG].variants:  # shown only once the showing is recorded
        assert v.defect not in text and v.title not in text
    assert "review is owed" in one["review_status"]
    h = coder(client)
    made = client.post(
        f"{MINE}/{SLUG}/runs",
        headers=h,
        json={"cases": [{"input": {"nums": [3, 1], "target": 6}, "expected": 0}]},
    )
    assert made.status_code == 202, made.text
    history = client.get("/api/v1/me/activity", headers=h, params={"type": "test_design_run"}).json()
    assert [i["title"] for i in history["items"]] == ["Test design: Count Pairs"]
    recent = client.get("/api/v1/me/recent-work", headers=h, params={"limit": 12}).json()["items"]
    assert [i["parent_id"] for i in recent if i["type"] == "test_design_run"] == [SLUG]


@java
def test_the_jdk_check_passes_it_and_refuses_a_version_that_isnt_faulty_or_crashes(tmp_path):
    verify = _verifier()
    assert verify.check_test_design_exercise(FILE) == []
    good = json.loads(FILE.read_text())

    def check(data: dict) -> str:
        path = tmp_path / "x.json"
        path.write_text(json.dumps(data))
        return "\n".join(verify.check_test_design_exercise(path))

    same = json.loads(json.dumps(good))
    same["variants"][1]["code"] = good["reference"]
    assert "faulty version stops-at-first gives the reference's answer on its own witness" in check(same)
    crashes = json.loads(json.dumps(good))
    crashes["variants"][3]["code"] = good["variants"][3]["code"].replace(
        "int count = 0;", "int count = 0;\n        if (nums.length == 0) { return nums[0]; }"
    )
    assert "faulty version never-pairs-the-last throws ArrayIndexOutOfBoundsException" in check(crashes)


@pytest.mark.parametrize("variant", range(4))
def test_each_witness_is_within_the_limits_and_the_examples_alone_tell_none_apart(variant):
    from app.testdesign import case_errors

    ex = BY_SLUG[SLUG]
    assert case_errors(ex, ex.variants[variant].witness, 0) == []
    assert all(case_errors(ex, e["input"], e["expected"]) == [] for e in ex.examples)


@java
def test_a_run_of_its_examples_tells_none_apart_and_its_witnesses_all_four(make_client):
    """The same runs as the real-judge test in test_judge_sandbox.py, with a local JDK standing in."""
    from tests.test_test_design import LocalJavaRunner, client_with, run_cases

    c, worker, h = client_with(make_client, LocalJavaRunner())
    examples = run_cases(c, worker, h, [dict(e, label=None) for e in BY_SLUG[SLUG].examples], slug=SLUG)
    assert examples["status"] == "done" and (examples["report"]["caught"], examples["report"]["total"]) == (
        0,
        4,
    )
    witnesses = [
        ({"nums": [3, 1], "target": 6}, 0, ["A"]),
        ({"nums": [1, 5, 2, 4], "target": 6}, 2, ["B", "D"]),
        ({"nums": [2, 2, 2], "target": 4}, 3, ["A", "B", "C", "D"]),
        ({"nums": [4, 7, 2], "target": 6}, 1, ["D"]),
    ]
    rep = run_cases(c, worker, h, [{"input": i, "expected": e} for i, e, _ in witnesses], slug=SLUG)["report"]
    assert (rep["caught"], rep["total"]) == (4, 4)
    assert [row["distinguishes"] for row in rep["cases"]] == [d for _, _, d in witnesses]
    assert "4 of the 4" in " ".join(rep["summary"])
