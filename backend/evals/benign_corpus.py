"""The broad benign corpus: ordinary text from the repository that the grader-instruction filter
must leave alone (rubric v2 onwards; made repeatable for rubric v6, Volume 4 brief 05).

    python -m evals.benign_corpus

Sentences come from every career's question prompts, outlines, tips and rubric advice, and from
the app's seeded content (lessons, scenarios, drills, problems). Test files are left out: some of
their strings are attacks on purpose. Prints the corpus size, a hash of its sentences (its
version: it changes when the content does) and every sentence the filter would leave out, which
should be none. A clean result here shows only that this text isn't caught; it says nothing about
answers nobody has written yet.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path

from app.careers import CATALOG
from app.careers.grading import _SENTENCE, _markup, _normalize, _to_grader
from app.careers.questions import questions_for

APP = Path(__file__).resolve().parent.parent / "app"


def _strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def texts(every: int = 1) -> list[tuple[str, str]]:
    """The corpus; `every` > 1 keeps every n-th question of each career (a deterministic sample)."""
    out: list[tuple[str, str]] = []
    for track in sorted(CATALOG):
        for q in list(questions_for(track))[::every]:
            out.append((f"question/{track}/{q.id}", q.prompt))
            out += [(f"outline/{track}/{q.id}", t) for t in q.outline]
            out += [(f"tip/{track}/{q.id}", t) for t in q.tips]
            out += [(f"advice/{track}/{q.id}", r.advice) for r in q.rubric]
    for f in sorted((APP / "seed").rglob("*")):
        if f.suffix == ".json":
            data = json.loads(f.read_text("utf-8"))
            # prose only: serialized test data ('["1", "2", "Fizz"]') isn't answer-like text
            out += [
                (f"seed/{f.relative_to(APP / 'seed')}", s)
                for s in _strings(data)
                if not s.lstrip().startswith(("[", "{"))
            ]
        elif f.suffix in (".md", ".txt"):
            out.append((f"seed/{f.relative_to(APP / 'seed')}", f.read_text("utf-8")))
    return out


def scan(every: int = 1) -> dict:
    sentences = 0
    digest = hashlib.sha256()
    flagged: list[dict] = []
    for where, text in texts(every):
        for a, b in _markup(text)[0]:  # delimited blocks addressed to a machine
            flagged.append({"where": where, "text": text[a:b][:120], "kind": "markup"})
        for m in _SENTENCE.finditer(text):
            s = _normalize(m.group(0)).text
            if len(s.split()) < 3:
                continue
            sentences += 1
            digest.update(s.encode())
            if _to_grader(s):
                flagged.append({"where": where, "text": s[:120], "kind": "sentence"})
    return {"sentences": sentences, "sha256": digest.hexdigest(), "flagged": flagged}


def main() -> None:
    r = scan()
    print(f"{r['sentences']} sentences, corpus sha256 {r['sha256'][:16]}, {len(r['flagged'])} flagged")
    for f in r["flagged"][:50]:
        print(f"  {f['kind']:8} {f['where']}: {f['text']}")


if __name__ == "__main__":
    main()
