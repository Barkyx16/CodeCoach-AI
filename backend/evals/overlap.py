"""Duplicate and near-duplicate answers across evaluation splits (docs/EVAL_PROTOCOL.md).

Three checks, on every pair of answers from different splits:
  exact       identical text
  normalized  identical after lower-casing, dropping punctuation and collapsing whitespace
  near        word 3-gram Jaccard similarity >= NEAR_JACCARD, or containment (the share of the
              shorter answer's 3-grams found in the longer one) >= NEAR_CONTAINMENT

Only pairs from different splits are flagged: within one split, close variants are often the point
(a typed answer and its dictated version; a correct solution and the same code with one bug). Code
is compared with whitespace collapsed only, since punctuation (`<` vs `<=`) is meaningful there.

A flagged pair must be reviewed: evals/overlap_review.json records each decision (distinct
despite the similarity, or a real duplicate to remove) with who reviewed it and why. Output names
case ids and similarity only, never answer text, so the tool can run over a sealed set without
showing it. `--show ID ID` prints two answers for a reviewer who is allowed to read both.

    python -m evals.overlap            # every split; exit 1 if a flagged pair has no review
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
REVIEW_FILE = EVAL_DIR / "overlap_review.json"
NEAR_JACCARD = 0.5
NEAR_CONTAINMENT = 0.8
_WORD = re.compile(r"[a-z0-9']+")


@dataclass(frozen=True)
class Item:
    uid: str  # "<dataset id>/<case id>"
    split: str
    family: str
    text: str
    code: bool = False


def normalize(text: str, code: bool = False) -> str:
    if code:
        return " ".join(text.split())
    return " ".join(_WORD.findall(text.lower()))


def shingles(text: str, n: int = 3, code: bool = False) -> set[tuple[str, ...]]:
    words = normalize(text, code).split()
    return {tuple(words[i : i + n]) for i in range(max(0, len(words) - n + 1))} or {tuple(words)}


def compare(a: Item, b: Item) -> dict | None:
    code = a.code or b.code
    if a.text == b.text:
        return {"kind": "exact", "jaccard": 1.0, "containment": 1.0}
    if normalize(a.text, code) == normalize(b.text, code):
        return {"kind": "normalized", "jaccard": 1.0, "containment": 1.0}
    sa, sb = shingles(a.text, code=code), shingles(b.text, code=code)
    inter = len(sa & sb)
    jaccard = inter / len(sa | sb) if sa | sb else 0.0
    containment = inter / min(len(sa), len(sb)) if sa and sb else 0.0
    if jaccard >= NEAR_JACCARD or containment >= NEAR_CONTAINMENT:
        return {"kind": "near", "jaccard": round(jaccard, 3), "containment": round(containment, 3)}
    return None


def career_items(path: Path, split: str | None = None) -> list[Item]:
    data = json.loads(path.read_text(encoding="utf-8"))
    sp = split or data.get("split", "dev")
    return [
        Item(f"{data['id']}/{c['id']}", sp, f"{data['id']}/{c.get('family', c['id'])}", c["answer"])
        for c in data["cases"]
    ]


def coding_items(path: Path, dataset_id: str, split: str) -> list[Item]:
    data = json.loads(path.read_text(encoding="utf-8"))
    # A coding case is the code *for a problem*: the same code for two problems is two cases.
    return [
        Item(
            f"{dataset_id}/{s['id']}",
            split,
            f"{dataset_id}/{s['id']}",
            f"{s['problem']}\n{s['code']}",
            code=True,
        )
        for s in data["samples"]
    ]


def all_items(include_sealed: bool = True) -> list[Item]:
    manifest = json.loads((EVAL_DIR / "datasets.json").read_text(encoding="utf-8"))
    items: list[Item] = []
    for d in manifest["datasets"]:
        if d.get("sealed") and not include_sealed:
            continue
        path = EVAL_DIR / d["file"]
        if d["domain"] == "career-answer":
            items += career_items(path, d["split"])
        elif d["domain"] == "coding-review":
            items += coding_items(path, d["id"], d["split"])
    return items


def flagged_pairs(items: list[Item]) -> list[dict]:
    out = []
    for a, b in combinations(items, 2):
        if a.split == b.split or a.family == b.family:
            continue  # within a split, close variants are often the point
        hit = compare(a, b)
        if hit:
            out.append({"a": a.uid, "b": b.uid, "splits": sorted({a.split, b.split}), **hit})
    return out


def reviews() -> dict[frozenset, dict]:
    if not REVIEW_FILE.exists():
        return {}
    data = json.loads(REVIEW_FILE.read_text(encoding="utf-8"))
    return {frozenset((r["a"], r["b"])): r for r in data["pairs"]}


def unreviewed(pairs: list[dict]) -> list[dict]:
    known = reviews()
    return [p for p in pairs if frozenset((p["a"], p["b"])) not in known]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--show", nargs=2, metavar=("UID", "UID"), help="print two answers (only if you may read both)"
    )
    parser.add_argument("--extra", nargs="*", default=[], help="career case files not yet in datasets.json")
    args = parser.parse_args()
    items = all_items()
    registered = {i.uid.split("/")[0] for i in items}
    for path in args.extra:
        extra = career_items(Path(path))
        if extra and extra[0].uid.split("/")[0] not in registered:
            items += extra
    if args.show:
        by = {i.uid: i for i in items}
        for uid in args.show:
            print(f"--- {uid} ({by[uid].split})\n{by[uid].text}\n")
        return
    pairs = flagged_pairs(items)
    missing = unreviewed(pairs)
    print(f"{len(items)} answers checked; {len(pairs)} flagged pairs; {len(missing)} without a review")
    for p in pairs:
        mark = "UNREVIEWED" if p in missing else "reviewed"
        print(f"  {mark:10} {p['kind']:10} j={p['jaccard']} c={p['containment']}  {p['a']}  ~  {p['b']}")
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
