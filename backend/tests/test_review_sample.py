"""The human label review sample (Durable Saves brief 14): bounded, seeded, blind first, never
filled in by anyone but a person, and never editing a dataset. Synthetic ratings only: these tests
are not a review."""

from __future__ import annotations

import csv
import hashlib
import json

import pytest

from evals import review_sample as rs


@pytest.fixture
def sample(tmp_path):
    return rs.build("test-seed", per_set=1, disagreement=3, samples_dir=tmp_path / "samples")


def _fill(tmp_path, sample, name, label_for):
    out = rs.blind_packet(sample, out_root=tmp_path / "out")
    rows = list(csv.DictReader((out / "1-form.csv").open(encoding="utf-8")))
    for i, r in enumerate(rows):
        r["your_label"] = label_for(i, r)
        r["uncertainty"] = "low"
        r["rationale"] = "synthetic test rating"
    path = tmp_path / f"{name}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rs.FORM)
        w.writeheader()
        w.writerows(rows)
    return path


def test_the_sample_is_seeded_stratified_and_never_sealed(tmp_path, sample):
    again = rs.build("test-seed", per_set=1, disagreement=3, samples_dir=tmp_path / "again")
    assert [(i["dataset"], i["case"], i["stratum"]) for i in again["items"]] == [
        (i["dataset"], i["case"], i["stratum"]) for i in sample["items"]
    ]
    other = rs.build("another-seed", per_set=1, disagreement=3, samples_dir=tmp_path / "other")
    randoms = lambda s: {(i["dataset"], i["case"]) for i in s["items"] if i["stratum"] == "random"}  # noqa: E731
    assert randoms(other) != randoms(sample)
    sealed = {e["id"] for e in rs._manifest() if e.get("sealed")}
    assert (
        sealed
        and not sealed & set(sample["datasets"])
        and not any(i["dataset"] in sealed for i in sample["items"])
    )
    assert sample["strata"] == {"disagreement": 3, "random": len(sample["datasets"])}
    assert all(i["why"] for i in sample["items"] if i["stratum"] == "disagreement")
    assert "not representative" in sample["selection"]["rule"]
    assert sample["status"].startswith("prepared; human review pending") and sample["reviewers"] == []
    with pytest.raises(SystemExit, match="sealed"):
        rs._open(next(e for e in rs._manifest() if e.get("sealed")))


def test_the_first_pass_hides_labels_grader_and_case_ids(tmp_path, sample):
    out = rs.blind_packet(sample, out_root=tmp_path / "out")
    page = (out / "1-blind.html").read_text(encoding="utf-8")
    header = next(csv.reader((out / "1-form.csv").open(encoding="utf-8")))
    assert header == rs.FORM and "proposed" not in header and "case" not in header
    for it in sample["items"]:
        assert it["case"] not in page
    assert "labeller unsure" not in page and "says covered" not in page and "says missing" not in page
    assert "needs_expertise" in page and "Structure, not practice" in page


def test_only_a_person_can_be_recorded_and_agreement_needs_two(tmp_path, sample):
    sd = tmp_path / "samples"
    form = _fill(tmp_path, sample, "a", lambda i, r: "covered")
    with pytest.raises(SystemExit, match="--human"):
        rs.import_ratings(
            sample["sample_id"], form, "A. Reviewer, nurse educator", human=False, samples_dir=sd
        )
    with pytest.raises(SystemExit, match="--reviewer"):
        rs.import_ratings(sample["sample_id"], form, " ", human=True, samples_dir=sd)
    bad = _fill(tmp_path, sample, "bad", lambda i, r: "yes")
    with pytest.raises(SystemExit, match="your_label"):
        rs.import_ratings(sample["sample_id"], bad, "A. Reviewer", human=True, samples_dir=sd)
    rec = rs.import_ratings(
        sample["sample_id"], form, "A. Reviewer, nurse educator", human=True, samples_dir=sd
    )
    assert rec["points_rated"] == sample["points_to_rate"] and rec["reviewer_kind"].startswith("human")
    st = rs.status(sample["sample_id"], samples_dir=sd)
    assert st["status"].startswith("first pass by 1 person") and st["agreement"]["computed"] is False


def test_reveal_and_adjudication_record_decisions_without_touching_the_data(tmp_path, sample):
    sd = tmp_path / "samples"
    hashes = {
        e["id"]: hashlib.sha256((rs.EVAL_DIR / e["file"]).read_bytes()).hexdigest()
        for e in rs._manifest()
        if not e.get("sealed")
    }
    rs.import_ratings(
        sample["sample_id"],
        _fill(tmp_path, sample, "a", lambda i, r: "covered"),
        "A",
        human=True,
        samples_dir=sd,
    )
    rs.import_ratings(
        sample["sample_id"],
        _fill(tmp_path, sample, "b", lambda i, r: "covered" if i % 2 else "missing"),
        "B",
        human=True,
        samples_dir=sd,
    )
    pair = rs.status(sample["sample_id"], samples_dir=sd)["agreement"]["pairs"][0]
    assert pair["points"] == sample["points_to_rate"] and 0 < pair["agreement"] < 1
    out = rs.reveal(sample["sample_id"], samples_dir=sd, out_root=tmp_path / "out")
    rows = list(csv.DictReader((out / "2-adjudication.csv").open(encoding="utf-8")))
    assert rows and all(r["proposed"] and r["grader"] and "A:" in r["reviewers"] for r in rows)
    rows[0]["outcome"] = "change"
    with (tmp_path / "adj-bad.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rs.ADJ)
        w.writeheader()
        w.writerows(rows)
    with pytest.raises(SystemExit, match="adjudicated_label"):
        rs.adjudicate(sample["sample_id"], tmp_path / "adj-bad.csv", "C", human=True, samples_dir=sd)
    rows[0]["adjudicated_label"] = "missing"
    rows[1]["outcome"] = "keep"
    with (tmp_path / "adj.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rs.ADJ)
        w.writeheader()
        w.writerows(rows)
    with pytest.raises(SystemExit, match="--human"):
        rs.adjudicate(sample["sample_id"], tmp_path / "adj.csv", "C", human=False, samples_dir=sd)
    rec = rs.adjudicate(
        sample["sample_id"], tmp_path / "adj.csv", "C, adjudicator", human=True, samples_dir=sd
    )
    assert len(rec["decisions"]) == 2 and len(rec["label_changes_pending"]) == 1
    st = rs.status(sample["sample_id"], samples_dir=sd)
    assert "1 label change(s) to make in new dataset versions" in st["status"]
    assert hashes == {
        e["id"]: hashlib.sha256((rs.EVAL_DIR / e["file"]).read_bytes()).hexdigest()
        for e in rs._manifest()
        if not e.get("sealed")
    }


def test_a_changed_set_needs_a_new_sample(tmp_path, sample):
    path = tmp_path / "samples" / f"{sample['sample_id']}.json"
    rec = json.loads(path.read_text(encoding="utf-8"))
    first = next(iter(rec["datasets"]))
    rec["datasets"][first]["sha256"] = "0" * 64
    path.write_text(json.dumps(rec), encoding="utf-8")
    with pytest.raises(SystemExit, match="changed since the sample was drawn"):
        rs.blind_packet(rs.load_sample(sample["sample_id"], tmp_path / "samples"), out_root=tmp_path / "out")


def test_the_committed_sample_is_pending_and_current():
    rec = rs.load_sample("sample-2026-11-05")
    assert rec["status"].startswith("prepared; human review pending") and rec["reviewers"] == []
    assert not (rs.SAMPLES / "sample-2026-11-05.ratings.json").exists()  # no review has happened
    rs._cases(rec)  # every sampled set still has the hash it was drawn from


# --- ingestion checks (Verification brief 14) ---------------------------------------------------


def _write(tmp_path, name, rows, fields=None):
    path = tmp_path / name
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields or rs.FORM, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return path


def test_ingestion_refuses_duplicates_missing_columns_bad_labels_and_model_reviewers(tmp_path, sample):
    sd = tmp_path / "samples"
    first = sample["items"][0]
    row = {"item": first["item"], "point": first["points"][0], "your_label": "covered", "uncertainty": "low"}
    dup = _write(tmp_path, "dup.csv", [row, {**row, "your_label": "missing"}])
    with pytest.raises(SystemExit, match="rated twice"):
        rs.import_ratings(sample["sample_id"], dup, "A. Reviewer", human=True, samples_dir=sd)
    no_label = _write(tmp_path, "cols.csv", [row], fields=["item", "point", "uncertainty"])
    with pytest.raises(SystemExit, match="missing column"):
        rs.import_ratings(sample["sample_id"], no_label, "A. Reviewer", human=True, samples_dir=sd)
    bad = _write(tmp_path, "bad.csv", [{**row, "your_label": "mostly"}])
    with pytest.raises(SystemExit, match="your_label must be one of"):
        rs.import_ratings(sample["sample_id"], bad, "A. Reviewer", human=True, samples_dir=sd)
    unc = _write(tmp_path, "unc.csv", [{**row, "uncertainty": "very"}])
    with pytest.raises(SystemExit, match="uncertainty must be one of"):
        rs.import_ratings(sample["sample_id"], unc, "A. Reviewer", human=True, samples_dir=sd)
    good = _write(tmp_path, "good.csv", [row])
    for name in ("GPT-4 (labels)", "an LLM", "chatbot run 3"):
        with pytest.raises(SystemExit, match="reads as a model"):
            rs.import_ratings(sample["sample_id"], good, name, human=True, samples_dir=sd)
    # People's names that only look similar are accepted.
    for name in ("Claude Martin, nurse educator", "Ai Tanaka, RN", "Teaching assistant Kim"):
        rs.import_ratings(sample["sample_id"], good, name, human=True, samples_dir=sd)
    assert not (sd / f"{sample['sample_id']}.ratings.json").read_text().count("GPT")


def test_status_lists_unresolved_and_unadjudicated_differences(tmp_path, sample):
    sd = tmp_path / "samples"
    rs.import_ratings(
        sample["sample_id"],
        _fill(tmp_path, sample, "a", lambda i, r: "cant_tell"),
        "A",
        human=True,
        samples_dir=sd,
    )
    st = rs.status(sample["sample_id"], samples_dir=sd)
    assert st["not_adjudicated"] and st["unresolved"] == []  # every "can't tell" differs; none decided yet
    out = rs.reveal(sample["sample_id"], samples_dir=sd, out_root=tmp_path / "out")
    rows = list(csv.DictReader((out / "2-adjudication.csv").open(encoding="utf-8")))
    rows[0]["outcome"] = "unresolved"
    adj = _write(tmp_path, "adj.csv", rows[:1], fields=rs.ADJ)
    rs.adjudicate(sample["sample_id"], adj, "C", human=True, samples_dir=sd)
    st = rs.status(sample["sample_id"], samples_dir=sd)
    assert st["unresolved"] == [f"{rows[0]['item']} / {rows[0]['point']}"]
    assert f"{rows[0]['item']} / {rows[0]['point']}" not in st["not_adjudicated"]
    assert len(st["not_adjudicated"]) == len(rows) - 1
