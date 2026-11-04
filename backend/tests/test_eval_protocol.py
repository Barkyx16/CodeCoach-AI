"""The evaluation protocol (docs/EVAL_PROTOCOL.md): duplicates across splits, case validation,
review records, sealed sets, the known-defect register and reference text."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.careers.grading import grade
from evals import career, meta, overlap, review_packet
from evals import run as runner
from evals.contracts import check_reference_leak
from evals.validate_cases import validate

EVALS = Path(__file__).resolve().parents[1] / "evals"


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """A copy of evals/ data files, with every module pointed at it."""
    for f in EVALS.glob("*.json"):
        shutil.copy(f, tmp_path / f.name)
    shutil.copytree(EVALS / "sealed", tmp_path / "sealed")  # read by the id-only checks, never graded here
    for module in (meta, career, overlap, review_packet):
        monkeypatch.setattr(module, "EVAL_DIR", tmp_path)
    monkeypatch.setattr(meta, "MANIFEST", tmp_path / "datasets.json")
    monkeypatch.setattr(overlap, "REVIEW_FILE", tmp_path / "overlap_review.json")
    monkeypatch.setattr(review_packet, "REVIEWS", tmp_path / "reviews")
    monkeypatch.setattr(runner, "SEALED_DIR", tmp_path / "sealed")
    return tmp_path


def _register(ws: Path, data: dict, file: str, **extra) -> None:
    (ws / file).parent.mkdir(exist_ok=True)
    (ws / file).write_text(json.dumps(data))
    manifest = json.loads((ws / "datasets.json").read_text())
    manifest["datasets"].append(
        {
            "id": data["id"],
            "file": file,
            "version": data["version"],
            "split": data["split"],
            "domain": "career-answer",
            "sha256": meta.sha256_file(ws / file),
            "provenance": "test",
            "labels": "test",
            "used_for": "test",
            **extra,
        }
    )
    (ws / "datasets.json").write_text(json.dumps(manifest))


# --- the protocol itself ----------------------------------------------------------------------


def test_the_protocol_is_frozen_before_measurement_with_metrics_and_release_rules():
    p = json.loads((EVALS / "protocol.json").read_text())
    assert p["protocol_version"] >= 1 and p["frozen"]
    assert set(p["family_plan_per_question"]) == {"A", "B", "probe"}
    for m in (
        "item_precision",
        "item_recall",
        "unsupported_credit_rate",
        "keyword_false_award",
        "attack_credit",
        "benign_false_exclusion",
        "dictated_parity",
        "contradiction_full_credit",
        "uncertainty",
    ):
        assert m in p["metrics"], m
    assert p["release"]["must_pass"] and p["release"]["non_inferiority"]
    assert "never opens" in p["sealed_access"]["tuning_session"]


def test_every_dataset_records_its_role_and_exposure():
    for d in meta.manifest()["datasets"]:
        assert d["role"] in {"development", "exposed historical benchmark", "sealed final evaluation"}, d[
            "id"
        ]
        assert d["exposure"], d["id"]
    held = {d["id"]: d for d in meta.manifest()["datasets"]}["career-rn-holdout"]
    assert held["role"] == "exposed historical benchmark"


# --- duplicates ---------------------------------------------------------------------------------


def test_exact_normalized_and_near_duplicates_are_detected():
    a = overlap.Item("x/1", "dev", "x/1", "I checked the chart, then I called the doctor about the new rash.")
    assert overlap.compare(a, overlap.Item("y/1", "holdout", "y/1", a.text))["kind"] == "exact"
    assert (
        overlap.compare(
            a,
            overlap.Item(
                "y/2", "holdout", "y/2", "i checked the chart then i called the DOCTOR about the new rash"
            ),
        )["kind"]
        == "normalized"
    )
    near = "I checked the chart, then I called the doctor about the new rash on her arm."
    assert overlap.compare(a, overlap.Item("y/3", "holdout", "y/3", near))["kind"] == "near"
    assert (
        overlap.compare(
            a, overlap.Item("y/4", "holdout", "y/4", "We planned the week's rota around two new starters.")
        )
        is None
    )
    # Code keeps its operators: a one-character bug is not "the same after normalisation".
    c1 = overlap.Item("c/1", "dev", "c/1", "for (int i = 0; i < n; i++)", code=True)
    c2 = overlap.Item("c/2", "holdout", "c/2", "for (int i = 0; i <= n; i++)", code=True)
    assert overlap.compare(c1, c2) is None or overlap.compare(c1, c2)["kind"] == "near"


def test_a_new_cross_split_duplicate_fails_while_the_known_one_stays_disclosed(workspace):
    dev = career.load("career_dev.json")
    copied = {**dev, "id": "career-rn-copy", "split": "holdout", "cases": [dict(dev["cases"][0], id="cp-1")]}
    _register(workspace, copied, "career_copy.json", role="development", exposure="test")
    pairs = overlap.flagged_pairs(overlap.all_items())
    missing = overlap.unreviewed(pairs)
    assert [(p["a"], p["b"], p["kind"]) for p in missing] == [
        ("career-rn-dev/rn-dev-01", "career-rn-copy/cp-1", "exact")
    ]
    known = [p for p in pairs if "md-rotated-linear" in p["b"]]
    assert known and known[0] not in missing  # the pre-existing overlap is reviewed and disclosed
    report = {"data_checks": runner.data_checks()}
    failures = next(g for g in runner.evaluate_gates(report) if g["id"] == "data.integrity")["failures"]
    assert any("career-rn-copy/cp-1" in f for f in failures)


def test_the_real_sets_have_no_unreviewed_cross_split_overlap():
    pairs = overlap.flagged_pairs(overlap.all_items())
    assert overlap.unreviewed(pairs) == []
    assert any(p["b"].endswith("md-rotated-linear") for p in pairs)


# --- validating cases -----------------------------------------------------------------------------


def _family_case(**over) -> dict:
    labels = {
        "Lays out clear steps or habits": True,
        "Uses the specifics of the job": True,
        "Explains why it matters": False,
        "Follows up, documents and prevents a repeat": False,
    }
    base = {
        "id": "t-1-A-typed",
        "family": "t-1-A",
        "variant": "typed",
        "question_id": "e-accuracy-0",
        "question_version": 1,
        "tags": ["typed"],
        "answer": " ".join(["word"] * 60),
        "labels": {"points": labels, "uncertain": []},
        "expected": {"evidence_level": "sufficient"},
    }
    return {**base, **over}


def _set(cases: list[dict], **over) -> dict:
    return {
        "id": "test-set",
        "version": 1,
        "split": "dev",
        "track": "registered-nurse",
        "domain": "career-answer",
        "provenance": "Synthetic",
        "labeling": "test",
        "labeler": "test",
        "review_status": "unreviewed",
        "cases": cases,
        **over,
    }


def test_the_validator_catches_missing_uncertain_and_inconsistent_labels():
    typed = _family_case()
    bad = [
        _family_case(
            id="t-1-A-dictated",
            variant="dictated",
            tags=["dictated"],
            pair_of="t-1-A-typed",
            labels={
                "points": {**typed["labels"]["points"], "Explains why it matters": True},
                "uncertain": [],
            },
        ),
        _family_case(
            id="t-2", labels={"points": {"Lays out clear steps or habits": True}, "uncertain": ["Nope"]}
        ),
        _family_case(id="t-3", expected={"evidence_level": "insufficient"}),
        _family_case(
            id="t-4",
            variant="grader_directed",
            kind="score_request",
            tags=["grader_directed"],
            expected={"evidence_level": "sufficient", "rating_at_most": "Good"},
        ),
        _family_case(
            id="t-5",
            variant="contradiction",
            kind="did_and_did_not",
            tags=["contradiction"],
            contradicted_points=["Lays out clear steps or habits"],
            expected={"evidence_level": "sufficient", "rating_at_most": "Good"},
        ),
    ]
    errors, _ = validate(_set([typed, *bad]))
    text = "\n".join(errors)
    assert "t-1-A-dictated: a meaning-preserving dictated must have its typed pair's point labels" in text
    assert "t-2: labels must name exactly the question's rubric points" in text
    assert "t-2: uncertain names a point that isn't labelled" in text
    assert "t-3: evidence_level must be 'sufficient'" in text
    assert (
        "t-4: grader_directed needs `injection`" in text
        and "t-4: grader_directed needs forbidden_evidence" in text
    )
    assert "t-5: contradiction needs contradicted_points, each labelled not covered" in text
    assert "no family with exactly the variants of plan probe" in text


def test_a_set_cannot_claim_review_it_did_not_get():
    errors, _ = validate(_set([_family_case()], review_status="validated by a clinical expert"))
    assert any("review_status must start with" in e for e in errors)
    assert any("claims validation or expert review without review records" in e for e in errors)


# --- review records -------------------------------------------------------------------------------


def test_review_status_never_says_more_than_the_records(workspace, tmp_path):
    assert review_packet.review_status("career-rn-dev") == "unreviewed"
    out = review_packet.write_packet("career-rn-dev", out_root=tmp_path / "out")
    assert "Judge whether the answer does what the point describes" in (out / "packet.html").read_text()
    rows = list((out / "decisions.csv").read_text().splitlines())
    head, first, second = rows[0], rows[1], rows[2]
    filled = tmp_path / "filled.csv"
    filled.write_text(
        "\n".join(
            [head, first.replace(",,,", ",agree,,"), second.replace(",,,", ",disagree,missing,too vague")]
        )
        + "\n"
    )
    with pytest.raises(SystemExit, match="reviewer"):
        review_packet.import_decisions("career-rn-dev", filled, "")
    before = (workspace / "career_dev.json").read_text()
    rec = review_packet.import_decisions("career-rn-dev", filled, "A. Reviewer, nursing educator")
    assert (rec["agree"], rec["disagree"], rec["points_reviewed"]) == (1, 1, 2)
    assert review_packet.review_status("career-rn-dev").startswith("partly reviewed (2 of ")
    assert (workspace / "career_dev.json").read_text() == before  # a review never edits labels
    bad = tmp_path / "bad.csv"
    bad.write_text("\n".join([head, first.replace(",,,", ",maybe,,")]) + "\n")
    with pytest.raises(SystemExit, match="decision must be one of"):
        review_packet.import_decisions("career-rn-dev", bad, "A. Reviewer")


def test_a_sealed_packet_needs_a_reviewer_who_is_not_tuning(workspace, tmp_path):
    dev = career.load("career_dev.json")
    _register(
        workspace,
        {**dev, "id": "career-rn-fake-sealed", "split": "holdout"},
        "sealed/fake.json",
        sealed=True,
        role="sealed final evaluation",
        exposure="test",
    )
    with pytest.raises(SystemExit, match="sealed"):
        review_packet.write_packet("career-rn-fake-sealed", out_root=tmp_path / "out")
    assert review_packet.write_packet(
        "career-rn-fake-sealed", out_root=tmp_path / "out", reviewer_not_tuning=True
    )


# --- sealed runs ----------------------------------------------------------------------------------


def test_sealed_sets_are_only_graded_by_a_sealed_run_whose_report_holds_aggregates(workspace, tmp_path):
    # The real sealed set is graded once, for the frozen candidate: never in a test.
    manifest = json.loads((workspace / "datasets.json").read_text())
    manifest["datasets"] = [d for d in manifest["datasets"] if not d.get("sealed")]
    (workspace / "datasets.json").write_text(json.dumps(manifest))
    dev = career.load("career_dev.json")
    fake = {**dev, "id": "career-rn-fake-sealed", "split": "holdout", "cases": dev["cases"][:4]}
    _register(
        workspace, fake, "sealed/fake.json", sealed=True, role="sealed final evaluation", exposure="test"
    )
    (workspace / "sealed" / "ACCESS.md").write_text("| When | What | Who |\n|---|---|---|\n")
    normal = runner.run(sections=("career",))
    assert "career-rn-fake-sealed" not in normal["career"]
    sealed = runner.run(sealed=True)
    assert list(sealed["career"]) == ["career-rn-fake-sealed"] and sealed["kind"] == "sealed"
    path = runner.write_report(sealed, "final-test", out=tmp_path / "results")
    md, js = path.with_suffix(".md").read_text(), path.read_text()
    for c in fake["cases"]:
        assert c["id"] not in md and c["id"] not in js and c["answer"][:40] not in js
    cases = json.loads((workspace / "sealed" / "results" / "final-test.cases.json").read_text())
    assert len(cases["career"]["career-rn-fake-sealed"]["cases"]) == 4
    assert "graded" in (workspace / "sealed" / "ACCESS.md").read_text()


# --- the known-defect register and reference text --------------------------------------------------


def test_the_defect_register_matches_what_is_measured():
    for d in career.evaluate_regression(grade):
        assert d["still_shows"] == (d["status_recorded"] == "open"), d["id"]


def test_reference_text_never_reaches_the_prompt_and_a_leak_is_caught():
    assert check_reference_leak()["reference_leak"] == []
    sample = json.loads((EVALS / "review_set.json").read_text())["samples"][0]
    leaky = {**sample, "code": f"// {sample['note']}\n{sample['code']}"}
    assert check_reference_leak(sample_sets={"planted": [leaky]})["reference_leak"]


def test_a_keyword_list_awarded_a_point_fails_its_gate():
    report = {
        "career": {
            "career-rn-families-dev": {
                "cases": [
                    {
                        "id": "fd-1-P-keyword_list",
                        "tags": ["keyword_list"],
                        "observed": {"covered": ["Uses the specifics of the job"]},
                    },
                    {
                        "id": "fd-1-A-typed",
                        "tags": ["typed"],
                        "observed": {"covered": ["Uses the specifics of the job"]},
                    },
                ]
            }
        }
    }
    gate = next(g for g in runner.evaluate_gates(report) if g["id"] == "career.keyword_lists")
    assert (
        gate["status"] == "failed"
        and len(gate["failures"]) == 1
        and "fd-1-P-keyword_list" in gate["failures"][0]
    )
