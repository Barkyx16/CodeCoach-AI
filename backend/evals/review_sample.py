"""A bounded sample of labelled answers for people to review, blind first, then adjudicated.

    python -m evals.review_sample build                      # evals/reviews/samples/<id>.json (the sample)
    python -m evals.review_sample packet <id>                # evals/reviews/out/<id>/1-blind.html + 1-form.csv
    python -m evals.review_sample import <id> form.csv --reviewer "Name, role" --human
    python -m evals.review_sample reveal <id>                # 2-reveal.html + 2-adjudication.csv
    python -m evals.review_sample adjudicate <id> adjudication.csv --adjudicator "Name, role" --human
    python -m evals.review_sample status <id>

Only development sets and the exposed historical set are sampled: a sealed set is never opened
here (its packet is `evals.review_packet --reviewer-not-tuning`, for someone who isn't tuning the
coach). The selection rule is fixed and seeded, and it is not a random sample of everything: it
has two strata, recorded on every item.

- ``disagreement``: cases where the current rubric and the proposed label differ on a point, or
  the labeller marked a point unsure. Chosen on purpose because they are where labels are most
  likely to be wrong; figures from them say nothing about the sets as a whole.
- ``random``: per set, the first cases in the order of sha256(seed:set:case), skipping ones already
  in the other stratum.

The first pass hides the proposed labels and the grader's decisions; the reveal shows them next
to each reviewer's label, and the adjudication records what to do about each difference. Nothing
here edits a dataset: an accepted label change is made as a new dataset version (see
docs/EVAL_PROTOCOL.md, "Review by people"). Ratings can only be imported as a person's
(``--human``): another model's labels are not a review. Agreement between reviewers is reported
only when at least two people rated the same points.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from app.careers.grading import RUBRIC_VERSION, grade
from app.careers.questions import get_question
from app.careers.support import scope_note

EVAL_DIR = Path(__file__).resolve().parent
SAMPLES = EVAL_DIR / "reviews" / "samples"
OUT = EVAL_DIR / "reviews" / "out"
LABELS = {"covered", "missing", "cant_tell"}
UNCERTAINTY = {"low", "medium", "high"}
OUTCOMES = {"keep", "change", "unresolved"}
FORM = ["item", "point", "domain_flag", "your_label", "uncertainty", "needs_expertise", "rationale"]
ADJ = [
    "item",
    "case",
    "point",
    "proposed",
    "grader",
    "reviewers",
    "outcome",
    "adjudicated_label",
    "rationale",
]
PENDING = "prepared; human review pending (no person has reviewed any item)"
# A backstop, not the control (the --human declaration is): a reviewer named as a model or tool is
# refused. Only names no person carries ("Claude" is also a person's name, so it isn't listed).
_MODEL_NAME = re.compile(r"\b(?:chatgpt|gpt-?\d+\w*|llm|language model|chatbot|copilot)\b", re.IGNORECASE)


def _manifest() -> list[dict]:
    m = json.loads((EVAL_DIR / "datasets.json").read_text(encoding="utf-8"))
    return [d for d in m["datasets"] if d["domain"] == "career-answer"]


def _open(entry: dict) -> dict:
    if entry.get("sealed"):  # never opened by the tuning session
        raise SystemExit(f"{entry['id']} is sealed: it is not sampled here")
    return json.loads((EVAL_DIR / entry["file"]).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _order(seed: str, set_id: str, case_id: str) -> str:
    return hashlib.sha256(f"{seed}:{set_id}:{case_id}".encode()).hexdigest()


def _commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=EVAL_DIR, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _differences(track: str, case: dict) -> list[str]:
    """Why a case is disagreement-prone: the current rubric differs from a label, or it's unsure."""
    q = get_question(track, case["question_id"], case["question_version"])
    if q is None:
        return []
    labels = case["labels"]["points"]
    unsure = set(case["labels"].get("uncertain", []))
    covered = {p.label: p.covered for p in grade(q, case["answer"]).points}
    out = [f"labeller unsure: {p}" for p in labels if p in unsure]
    out += [
        f"rubric {RUBRIC_VERSION} says {'covered' if covered[p] else 'missing'}, label says "
        f"{'covered' if v else 'missing'}: {p}"
        for p, v in labels.items()
        if p in covered and p not in unsure and covered[p] != v
    ]
    return out


def build(seed: str, per_set: int = 2, disagreement: int = 10, samples_dir: Path | None = None) -> dict:
    samples_dir = samples_dir or SAMPLES
    sets = [(e, _open(e)) for e in _manifest() if not e.get("sealed")]
    candidates: list[tuple[str, str, dict, list[str]]] = []
    for e, data in sets:
        for c in data["cases"]:
            reasons = _differences(data["track"], c)
            if reasons:
                candidates.append((e["id"], _order(seed, e["id"], c["id"]), c, reasons))
    # Spread across sets: round-robin by set, most differences first, then the seeded order.
    by_set: dict[str, list] = {}
    for item in sorted(candidates, key=lambda x: (-len(x[3]), x[1])):
        by_set.setdefault(item[0], []).append(item)
    picked: list[tuple[str, dict, str, list[str]]] = []
    while len(picked) < disagreement and any(by_set.values()):
        for set_id in sorted(by_set):
            if by_set[set_id] and len(picked) < disagreement:
                _, _, c, reasons = by_set[set_id].pop(0)
                picked.append((set_id, c, "disagreement", reasons))
    chosen = {(s, c["id"]) for s, c, _, _ in picked}
    for e, data in sets:
        rest = sorted(
            (c for c in data["cases"] if (e["id"], c["id"]) not in chosen),
            key=lambda c: _order(seed, e["id"], c["id"]),
        )
        picked += [(e["id"], c, "random", []) for c in rest[:per_set]]
    info = {e["id"]: (e, data) for e, data in sets}
    items = []
    for n, (set_id, c, stratum, reasons) in enumerate(picked, start=1):
        e, data = info[set_id]
        items.append(
            {
                "item": f"R{n:03d}",
                "dataset": set_id,
                "dataset_version": data["version"],
                "dataset_role": e.get("role"),
                "case": c["id"],
                "track": data["track"],
                "question_id": c["question_id"],
                "question_version": c["question_version"],
                "stratum": stratum,
                "why": reasons,
                "points": list(c["labels"]["points"]),
            }
        )
    sample_id = f"sample-{seed}"
    record = {
        "sample_id": sample_id,
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": _commit(),
        "rubric_version": RUBRIC_VERSION,
        "status": PENDING,
        "reviewers": [],
        "selection": {
            "seed": seed,
            "per_set_random": per_set,
            "disagreement_cases": disagreement,
            "rule": (
                "Development and exposed historical career-answer sets only (no sealed set). Stratum "
                "'disagreement': cases where the current rubric differs from a proposed label on a point, "
                "or the labeller marked a point unsure, taken round-robin across sets, most differences "
                "first, ties by sha256(seed:set:case). Stratum 'random': per set, the first cases by "
                "sha256(seed:set:case) not already chosen. The disagreement stratum is chosen on purpose "
                "and is not representative."
            ),
        },
        "datasets": {
            e["id"]: {"version": data["version"], "sha256": _sha(EVAL_DIR / e["file"]), "role": e.get("role")}
            for e, data in sets
        },
        "strata": {s: sum(i["stratum"] == s for i in items) for s in ("disagreement", "random")},
        "points_to_rate": sum(len(i["points"]) for i in items),
        "items": items,
    }
    samples_dir.mkdir(parents=True, exist_ok=True)
    (samples_dir / f"{sample_id}.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return record


def load_sample(sample_id: str, samples_dir: Path | None = None) -> dict:
    path = (samples_dir or SAMPLES) / f"{sample_id}.json"
    if not path.exists():
        raise SystemExit(f"no sample {sample_id} in {path.parent}")
    return json.loads(path.read_text(encoding="utf-8"))


def _cases(sample: dict) -> dict[tuple[str, str], dict]:
    """The sampled cases, after checking each set still has the version and hash it was drawn from."""
    entries = {e["id"]: e for e in _manifest()}
    out = {}
    for set_id, rec in sample["datasets"].items():
        e = entries[set_id]
        if _sha(EVAL_DIR / e["file"]) != rec["sha256"]:
            raise SystemExit(f"{set_id} changed since the sample was drawn: draw a new sample")
        for c in _open(e)["cases"]:
            out[(set_id, c["id"])] = c
    return out


def _protocol() -> dict:
    return json.loads((EVAL_DIR / "protocol.json").read_text(encoding="utf-8"))


def blind_packet(sample: dict, out_root: Path | None = None) -> Path:
    """First pass: question, rubric definitions and answer, with no proposed label or grader output."""
    out = (out_root or OUT) / sample["sample_id"]
    out.mkdir(parents=True, exist_ok=True)
    cases = _cases(sample)
    lab = _protocol()["labeling"]
    parts = [
        "<!doctype html><meta charset='utf-8'><title>Label review, first pass</title>",
        "<style>body{font:15px/1.5 system-ui;max-width:52rem;margin:2rem auto;padding:0 1rem}"
        "section{border-top:1px solid #999;padding:1rem 0;break-inside:avoid}blockquote{background:#f4f4f4;"
        "padding:.75rem;white-space:pre-wrap}td,th{border:1px solid #ccc;padding:.3rem .5rem;text-align:left;"
        "vertical-align:top}table{border-collapse:collapse;width:100%}</style>",
        f"<h1>Label review, first pass: {html.escape(sample['sample_id'])}</h1>",
        f"<p><b>Status:</b> {html.escape(sample['status'])}. Rubric {html.escape(sample['rubric_version'])}. "
        "This pass hides the proposed labels and the coach's decisions on purpose: label each point from the "
        "answer alone, in 1-form.csv.</p>",
        "<h2>How to label</h2><ul>",
        f"<li><b>A point is covered</b> when {html.escape(lab['points'].split(' when ', 1)[-1])}</li>",
        f"<li><b>Describes specific actions you took:</b> {html.escape(lab['action_criterion'])}</li>",
        f"<li><b>Contradiction:</b> {html.escape(lab['contradiction'].split(' (Protocol')[0])}</li>",
        "<li><b>your_label:</b> covered, missing or cant_tell. <b>uncertainty:</b> low, medium or high. "
        "<b>rationale:</b> a sentence, quoting the answer where you can.</li>",
        "<li><b>Structure, not practice.</b> Judge whether the answer does what the point describes. Whether the "
        "nursing or customer-service practice is right is a different judgement that needs the right expertise: "
        "if a point can't be judged without it, put <code>yes</code> in <code>needs_expertise</code> and say why. "
        "Points flagged <code>domain</code> are worded as if they judged correctness; the rubric only checks that "
        "the answer discusses the subject.</li></ul>",
    ]
    rows = []
    for it in sample["items"]:
        c = cases[(it["dataset"], it["case"])]
        q = get_question(it["track"], it["question_id"], it["question_version"])
        advice = {r.label: r.advice for r in q.rubric} if q else {}
        trs = "".join(
            f"<tr><td>{html.escape(p)}{' <small>[domain]</small>' if scope_note(p) else ''}<br>"
            f"<small>{html.escape(advice.get(p, ''))}</small></td><td></td></tr>"
            for p in it["points"]
        )
        parts.append(
            f"<section><h2>{html.escape(it['item'])}</h2><p><b>Question:</b> "
            f"{html.escape(q.prompt if q else it['question_id'])}</p><blockquote>{html.escape(c['answer'])}"
            f"</blockquote><table><tr><th>Rubric point</th><th>Your label</th></tr>{trs}</table></section>"
        )
        rows += [
            {
                "item": it["item"],  # not the case id: ids name the variant, a hint at the label
                "point": p,
                "domain_flag": "domain" if scope_note(p) else "",
                "your_label": "",
                "uncertainty": "",
                "needs_expertise": "",
                "rationale": "",
            }
            for p in it["points"]
        ]
    (out / "1-blind.html").write_text("\n".join(parts), encoding="utf-8")
    with (out / "1-form.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FORM)
        w.writeheader()
        w.writerows(rows)
    return out


def _ratings_path(sample_id: str, samples_dir: Path | None) -> Path:
    return (samples_dir or SAMPLES) / f"{sample_id}.ratings.json"


def import_ratings(
    sample_id: str, form: Path, reviewer: str, human: bool, samples_dir: Path | None = None
) -> dict:
    if not human:
        raise SystemExit("--human is required: only a person's labels are a review (another model's are not)")
    if not reviewer.strip():
        raise SystemExit("--reviewer is required: who reviewed, and in what capacity")
    if _MODEL_NAME.search(reviewer):
        raise SystemExit(
            f"{reviewer!r} reads as a model or tool: its labels aren't a review by a person and aren't imported"
        )
    sample = load_sample(sample_id, samples_dir)
    expected = {(it["item"], p) for it in sample["items"] for p in it["points"]}
    ratings = []
    seen: set[tuple[str, str]] = set()
    with form.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = {"item", "point", "your_label"} - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(
                f"the form is missing column(s) {sorted(missing)}: use the 1-form.csv the packet wrote"
            )
        for r in reader:
            key = (r["item"], r["point"])
            if key not in expected:
                raise SystemExit(f"unknown item/point in the form: {r['item']} / {r['point']}")
            if key in seen:
                raise SystemExit(f"{r['item']} / {r['point']} is rated twice in this form: keep one row")
            seen.add(key)
            label = r["your_label"].strip().lower()
            if not label:
                continue
            if label not in LABELS:
                raise SystemExit(f"{r['item']} / {r['point']}: your_label must be one of {sorted(LABELS)}")
            unc = r.get("uncertainty", "").strip().lower() or None
            if unc is not None and unc not in UNCERTAINTY:
                raise SystemExit(
                    f"{r['item']} / {r['point']}: uncertainty must be one of {sorted(UNCERTAINTY)}"
                )
            ratings.append(
                {
                    "item": r["item"],
                    "point": r["point"],
                    "label": label,
                    "uncertainty": unc,
                    "needs_expertise": r.get("needs_expertise", "").strip().lower() in {"yes", "y", "true"},
                    "rationale": r.get("rationale", "").strip() or None,
                }
            )
    path = _ratings_path(sample_id, samples_dir)
    store = (
        json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"passes": [], "adjudications": []}
    )
    record = {
        "reviewer": reviewer.strip(),
        "reviewer_kind": "human (declared at import)",
        "pass": "blind",
        "imported": datetime.now(UTC).isoformat(timespec="seconds"),
        "points_rated": len(ratings),
        "points_in_sample": len(expected),
        "ratings": ratings,
    }
    store["passes"].append(record)
    path.write_text(json.dumps(store, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return record


def _store(sample_id: str, samples_dir: Path | None) -> dict:
    path = _ratings_path(sample_id, samples_dir)
    return (
        json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"passes": [], "adjudications": []}
    )


def _latest_by_reviewer(store: dict) -> dict[str, dict[tuple[str, str], str]]:
    out: dict[str, dict[tuple[str, str], str]] = {}
    for p in store["passes"]:  # a reviewer's later pass replaces their earlier one
        out[p["reviewer"]] = {(r["item"], r["point"]): r["label"] for r in p["ratings"]}
    return out


def agreement(store: dict) -> dict:
    """Between people only, on points at least two of them labelled covered/missing."""
    people = _latest_by_reviewer(store)
    if len(people) < 2:
        return {"computed": False, "why": f"{len(people)} reviewer(s): agreement needs at least two people"}
    names = sorted(people)
    pairs = []
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            both = [
                k
                for k in people[a]
                if k in people[b] and people[a][k] != "cant_tell" and people[b][k] != "cant_tell"
            ]
            if not both:
                pairs.append({"reviewers": [a, b], "points": 0, "agreement": None, "kappa": None})
                continue
            agree = sum(people[a][k] == people[b][k] for k in both) / len(both)
            pa = sum(people[a][k] == "covered" for k in both) / len(both)
            pb = sum(people[b][k] == "covered" for k in both) / len(both)
            chance = pa * pb + (1 - pa) * (1 - pb)
            kappa = None if chance == 1 else (agree - chance) / (1 - chance)
            pairs.append(
                {
                    "reviewers": [a, b],
                    "points": len(both),
                    "agreement": round(agree, 3),
                    "kappa": None if kappa is None else round(kappa, 3),
                }
            )
    return {"computed": True, "pairs": pairs}


def reveal(sample_id: str, samples_dir: Path | None = None, out_root: Path | None = None) -> Path:
    """Second pass, after the blind ratings: proposed label, rubric decision and every reviewer's label."""
    sample = load_sample(sample_id, samples_dir)
    people = _latest_by_reviewer(_store(sample_id, samples_dir))
    if not people:
        raise SystemExit("no ratings imported yet: the reveal comes after the first, blind pass")
    cases = _cases(sample)
    out = (out_root or OUT) / sample_id
    out.mkdir(parents=True, exist_ok=True)
    rows, parts = (
        [],
        [
            "<!doctype html><meta charset='utf-8'><title>Label review, adjudication</title>",
            "<style>body{font:15px/1.5 system-ui;max-width:60rem;margin:2rem auto;padding:0 1rem}td,th{border:1px "
            "solid #ccc;padding:.3rem .5rem;text-align:left;vertical-align:top}table{border-collapse:collapse;"
            "width:100%}.diff{background:#fff3cd}</style>",
            f"<h1>Adjudication: {html.escape(sample_id)}</h1><p>Highlighted rows differ. Record an outcome for "
            "each in 2-adjudication.csv: keep (the proposed label stands), change (give the label; it takes a new "
            "dataset version) or unresolved.</p><table><tr><th>Item</th><th>Point</th><th>Proposed</th>"
            f"<th>Rubric {html.escape(sample['rubric_version'])}</th>"
            + "".join(f"<th>{html.escape(n)}</th>" for n in sorted(people))
            + "</tr>",
        ],
    )
    for it in sample["items"]:
        c = cases[(it["dataset"], it["case"])]
        q = get_question(it["track"], it["question_id"], it["question_version"])
        graded = {p.label: p.covered for p in grade(q, c["answer"]).points} if q else {}
        for p in it["points"]:
            proposed = "covered" if c["labels"]["points"][p] else "missing"
            if p in c["labels"].get("uncertain", []):
                proposed += " (labeller unsure)"
            rubric = "covered" if graded.get(p) else "missing"
            theirs = {n: people[n].get((it["item"], p), "") for n in sorted(people)}
            seen = {v for v in theirs.values() if v} | {proposed.split(" ")[0]}
            differs = len(seen) > 1 or "unsure" in proposed or "cant_tell" in seen
            parts.append(
                f"<tr class='{'diff' if differs else ''}'><td>{it['item']}</td><td>{html.escape(p)}</td>"
                f"<td>{proposed}</td><td>{rubric}</td>"
                + "".join(f"<td>{html.escape(v or '-')}</td>" for v in theirs.values())
                + "</tr>"
            )
            if differs:
                rows.append(
                    {
                        "item": it["item"],
                        "case": f"{it['dataset']}/{it['case']}",
                        "point": p,
                        "proposed": proposed,
                        "grader": rubric,
                        "reviewers": "; ".join(f"{n}: {v or '-'}" for n, v in theirs.items()),
                        "outcome": "",
                        "adjudicated_label": "",
                        "rationale": "",
                    }
                )
    parts.append("</table>")
    (out / "2-reveal.html").write_text("\n".join(parts), encoding="utf-8")
    with (out / "2-adjudication.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ADJ)
        w.writeheader()
        w.writerows(rows)
    return out


def adjudicate(
    sample_id: str, csv_path: Path, adjudicator: str, human: bool, samples_dir: Path | None = None
) -> dict:
    if not human:
        raise SystemExit("--human is required: adjudication is a person's decision")
    if not adjudicator.strip():
        raise SystemExit("--adjudicator is required: who decided, and in what capacity")
    sample = load_sample(sample_id, samples_dir)
    expected = {(it["item"], p) for it in sample["items"] for p in it["points"]}
    decisions = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (r["item"], r["point"]) not in expected:
                raise SystemExit(f"unknown item/point: {r['item']} / {r['point']}")
            outcome = r["outcome"].strip().lower()
            if not outcome:
                continue
            if outcome not in OUTCOMES:
                raise SystemExit(f"{r['item']} / {r['point']}: outcome must be one of {sorted(OUTCOMES)}")
            label = r.get("adjudicated_label", "").strip().lower() or None
            if outcome == "change" and label not in {"covered", "missing"}:
                raise SystemExit(
                    f"{r['item']} / {r['point']}: a change needs adjudicated_label covered or missing"
                )
            decisions.append(
                {
                    "item": r["item"],
                    "case": r["case"],
                    "point": r["point"],
                    "outcome": outcome,
                    "label": label,
                    "rationale": r.get("rationale", "").strip() or None,
                }
            )
    store = _store(sample_id, samples_dir)
    record = {
        "adjudicator": adjudicator.strip(),
        "adjudicator_kind": "human (declared at import)",
        "recorded": datetime.now(UTC).isoformat(timespec="seconds"),
        "decisions": decisions,
        "label_changes_pending": [d for d in decisions if d["outcome"] == "change"],
    }
    store["adjudications"].append(record)
    _ratings_path(sample_id, samples_dir).write_text(
        json.dumps(store, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return record


def status(sample_id: str, samples_dir: Path | None = None) -> dict:
    sample = load_sample(sample_id, samples_dir)
    store = _store(sample_id, samples_dir)
    people = _latest_by_reviewer(store)
    changes = [d for a in store["adjudications"] for d in a["label_changes_pending"]]
    decided = {(d["item"], d["point"]): d["outcome"] for a in store["adjudications"] for d in a["decisions"]}
    unresolved = sorted(f"{i} / {p}" for (i, p), o in decided.items() if o == "unresolved")
    differences = _differing(sample, people) if people else []
    undecided = sorted(f"{i} / {p}" for i, p in differences if (i, p) not in decided)
    if not people:
        state = PENDING
    elif not store["adjudications"]:
        state = f"first pass by {len(people)} person(s); adjudication pending"
    else:
        state = f"reviewed by {len(people)} person(s) and adjudicated; {len(changes)} label change(s) to make in new dataset versions"
    return {
        "sample_id": sample_id,
        "status": state,
        "items": len(sample["items"]),
        "points": sample["points_to_rate"],
        "strata": sample["strata"],
        "reviewers": sorted(people),
        "agreement": agreement(store),
        "label_changes": changes,
        "unresolved": unresolved,
        "not_adjudicated": undecided,
    }


def _differing(sample: dict, people: dict[str, dict[tuple[str, str], str]]) -> list[tuple[str, str]]:
    """Points where a reviewer's label differs from the proposed one, or someone couldn't tell."""
    cases = _cases(sample)
    out = []
    for it in sample["items"]:
        labels = cases[(it["dataset"], it["case"])]["labels"]["points"]
        for p in it["points"]:
            proposed = "covered" if labels[p] else "missing"
            theirs = {v[(it["item"], p)] for v in people.values() if (it["item"], p) in v}
            if theirs and (theirs - {proposed}):
                out.append((it["item"], p))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--seed", default="2026-11-05")
    b.add_argument("--per-set", type=int, default=2)
    b.add_argument("--disagreement", type=int, default=10)
    for name in ("packet", "reveal", "status"):
        sub.add_parser(name).add_argument("sample_id")
    for name, who in (("import", "--reviewer"), ("adjudicate", "--adjudicator")):
        s = sub.add_parser(name)
        s.add_argument("sample_id")
        s.add_argument("csv", type=Path)
        s.add_argument(who, default="")
        s.add_argument("--human", action="store_true", help="a person made these decisions")
    a = parser.parse_args()
    if a.cmd == "build":
        rec = build(a.seed, a.per_set, a.disagreement)
        print(
            f"{rec['sample_id']}: {len(rec['items'])} cases ({rec['strata']}), {rec['points_to_rate']} points; {rec['status']}"
        )
    elif a.cmd == "packet":
        out = blind_packet(load_sample(a.sample_id))
        print(f"wrote {out / '1-blind.html'} and {out / '1-form.csv'}")
    elif a.cmd == "import":
        rec = import_ratings(a.sample_id, a.csv, a.reviewer, a.human)
        print(f"recorded {rec['points_rated']} of {rec['points_in_sample']} points from {rec['reviewer']}")
    elif a.cmd == "reveal":
        out = reveal(a.sample_id)
        print(f"wrote {out / '2-reveal.html'} and {out / '2-adjudication.csv'}")
    elif a.cmd == "adjudicate":
        rec = adjudicate(a.sample_id, a.csv, a.adjudicator, a.human)
        print(
            f"recorded {len(rec['decisions'])} decisions, {len(rec['label_changes_pending'])} label changes pending"
        )
    else:
        print(json.dumps(status(a.sample_id), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
