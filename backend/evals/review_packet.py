"""A review packet for a labelled set, and the record of a reviewer's decisions.

    python -m evals.review_packet career-rn-families-dev            # writes evals/reviews/out/<id>/
    python -m evals.review_packet career-rn-families-dev --import decisions.csv --reviewer "Name, role"

The packet is a printable page (question, rubric points with their advice, the answer, each
proposed label) and a CSV with one row per (case, point) to fill in: agree, disagree or unsure,
with the label the reviewer would give and a note. Importing a filled CSV writes
evals/reviews/<dataset id>.json. Labels are never changed by a review: disagreements are
recorded, and a corrected label needs a new dataset version. A sealed set's packet is only for a
reviewer who isn't tuning the coach, so it needs --reviewer-not-tuning.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.careers.questions import get_question

EVAL_DIR = Path(__file__).resolve().parent
REVIEWS = EVAL_DIR / "reviews"
DECISIONS = {"agree", "disagree", "unsure"}
COLUMNS = ["case", "point", "proposed", "decision", "reviewer_label", "note"]


def dataset(dataset_id: str) -> tuple[dict, dict]:
    manifest = json.loads((EVAL_DIR / "datasets.json").read_text(encoding="utf-8"))
    entry = next((d for d in manifest["datasets"] if d["id"] == dataset_id), None)
    if entry is None or entry["domain"] != "career-answer":
        raise SystemExit(f"{dataset_id}: not a career-answer set in evals/datasets.json")
    return entry, json.loads((EVAL_DIR / entry["file"]).read_text(encoding="utf-8"))


def rows(data: dict) -> list[dict]:
    out = []
    for c in data["cases"]:
        for point, covered in c["labels"]["points"].items():
            unsure = point in c["labels"].get("uncertain", [])
            out.append(
                {
                    "case": c["id"],
                    "point": point,
                    "proposed": ("covered" if covered else "missing")
                    + (" (labeller unsure)" if unsure else ""),
                    "decision": "",
                    "reviewer_label": "",
                    "note": "",
                }
            )
    return out


def packet_html(data: dict) -> str:
    parts = [
        "<!doctype html><meta charset='utf-8'><title>Label review</title>",
        "<style>body{font:15px/1.5 system-ui;max-width:52rem;margin:2rem auto;padding:0 1rem}"
        "section{border-top:1px solid #999;padding:1rem 0;break-inside:avoid}blockquote{background:#f4f4f4;padding:.75rem;white-space:pre-wrap}"
        "td,th{border:1px solid #ccc;padding:.3rem .5rem;text-align:left;vertical-align:top}table{border-collapse:collapse;width:100%}</style>",
        f"<h1>Label review: {html.escape(data['id'])} v{data['version']}</h1>",
        "<p>For each answer, read the question and the rubric points, then mark every proposed label: agree, disagree "
        "or unsure, with your own label and a note. Judge whether the answer does what the point describes "
        "(its structure and evidence), not whether the nursing practice is correct. Record your decisions in the "
        "CSV next to this page. Proposed labels were written by: "
        f"{html.escape(str(data.get('labeler', 'unknown')))}</p>",
    ]
    for c in data["cases"]:
        q = get_question(data["track"], c["question_id"], c["question_version"])
        advice = {r.label: r.advice for r in q.rubric} if q else {}
        trs = "".join(
            f"<tr><td>{html.escape(p)}<br><small>{html.escape(advice.get(p, ''))}</small></td>"
            f"<td>{'covered' if v else 'missing'}{' (unsure)' if p in c['labels'].get('uncertain', []) else ''}</td>"
            "<td>agree / disagree / unsure</td></tr>"
            for p, v in c["labels"]["points"].items()
        )
        meta = ", ".join(x for x in (c.get("variant"), c.get("kind")) if x)
        parts.append(
            f"<section><h2>{html.escape(c['id'])}</h2><p><b>Question:</b> {html.escape(q.prompt if q else c['question_id'])}"
            f"{' <small>(' + html.escape(meta) + ')</small>' if meta else ''}</p>"
            f"<blockquote>{html.escape(c['answer'])}</blockquote>"
            f"<table><tr><th>Rubric point</th><th>Proposed</th><th>Your decision</th></tr>{trs}</table></section>"
        )
    return "\n".join(parts)


def write_packet(dataset_id: str, out_root: Path | None = None, reviewer_not_tuning: bool = False) -> Path:
    out_root = out_root or REVIEWS / "out"
    entry, data = dataset(dataset_id)
    if entry.get("sealed") and not reviewer_not_tuning:
        raise SystemExit(
            "This set is sealed: its packet is only for a reviewer who isn't tuning the coach (--reviewer-not-tuning)."
        )
    out = out_root / dataset_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "packet.html").write_text(packet_html(data), encoding="utf-8")
    with (out / "decisions.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows(data))
    return out


def import_decisions(dataset_id: str, csv_path: Path, reviewer: str, reviews_dir: Path | None = None) -> dict:
    reviews_dir = reviews_dir or REVIEWS
    if not reviewer.strip():
        raise SystemExit("--reviewer is required: who reviewed, and in what capacity")
    entry, data = dataset(dataset_id)
    expected = {(r["case"], r["point"]) for r in rows(data)}
    decisions = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (r["case"], r["point"]) not in expected:
                raise SystemExit(f"unknown case/point in the decisions: {r['case']} / {r['point']}")
            d = r["decision"].strip().lower()
            if d == "":
                continue  # not reviewed
            if d not in DECISIONS:
                raise SystemExit(f"{r['case']} / {r['point']}: decision must be one of {sorted(DECISIONS)}")
            decisions.append(
                {
                    "case": r["case"],
                    "point": r["point"],
                    "decision": d,
                    "reviewer_label": r.get("reviewer_label", "").strip() or None,
                    "note": r.get("note", "").strip() or None,
                }
            )
    record = {
        "dataset": dataset_id,
        "dataset_version": data["version"],
        "dataset_sha256": entry["sha256"],
        "reviewer": reviewer,
        "imported": datetime.now(UTC).isoformat(timespec="seconds"),
        "points_in_set": len(expected),
        "points_reviewed": len(decisions),
        "agree": sum(d["decision"] == "agree" for d in decisions),
        "disagree": sum(d["decision"] == "disagree" for d in decisions),
        "unsure": sum(d["decision"] == "unsure" for d in decisions),
        "decisions": decisions,
    }
    reviews_dir.mkdir(exist_ok=True)
    path = reviews_dir / f"{dataset_id}.json"
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"reviews": []}
    existing["reviews"].append(record)
    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return record


def review_status(dataset_id: str, reviews_dir: Path | None = None) -> str:
    """What may be said about a set's labels: never more than its review records support."""
    reviews_dir = reviews_dir or REVIEWS
    path = reviews_dir / f"{dataset_id}.json"
    if not path.exists():
        return "unreviewed"
    recs = json.loads(path.read_text(encoding="utf-8"))["reviews"]
    reviewed = max((r["points_reviewed"] for r in recs), default=0)
    total = recs[-1]["points_in_set"] if recs else 0
    return "reviewed" if reviewed and reviewed == total else f"partly reviewed ({reviewed} of {total} points)"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("dataset")
    parser.add_argument("--import", dest="decisions", type=Path)
    parser.add_argument("--reviewer", default="")
    parser.add_argument("--reviewer-not-tuning", action="store_true")
    args = parser.parse_args()
    if args.decisions:
        rec = import_decisions(args.dataset, args.decisions, args.reviewer)
        print(
            f"recorded {rec['points_reviewed']} of {rec['points_in_set']} points: {rec['agree']} agree, {rec['disagree']} disagree, {rec['unsure']} unsure"
        )
        return
    out = write_packet(args.dataset, reviewer_not_tuning=args.reviewer_not_tuning)
    print(f"wrote {out / 'packet.html'} and {out / 'decisions.csv'}")
    sys.exit(0)


if __name__ == "__main__":
    main()
