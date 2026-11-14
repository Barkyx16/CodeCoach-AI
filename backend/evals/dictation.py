"""Does the written-answer coach judge content, not delivery? Dictation-style transforms of written
answers, and how often each rubric decision survives them.

Speech-to-text output differs from typing in ways that carry no meaning: little or no
punctuation, lower case, dropped apostrophes, numbers written as words, and filler sounds. Each
transform below applies one of those to a written answer, mechanically and without changing a
word of content, so the coach should reach the same decision on every rubric point. Where it
doesn't, the difference is a delivery effect on a content judgement.

    python -m evals.dictation          # parity per transform over development answers and the corpus
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable
from pathlib import Path

from app.careers.grading import Feedback, grade
from app.careers.questions import Question, get_question, questions_for

EVAL_DIR = Path(__file__).resolve().parent
_UNITS = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
_TENS = ["_", "_", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def spoken(n: int) -> str:
    """0-9999 as words, the way speech-to-text often writes them."""
    if n < 20:
        return _UNITS[n]
    if n < 100:
        return _TENS[n // 10] + ("" if n % 10 == 0 else " " + _UNITS[n % 10])
    if n < 1000:
        rest = n % 100
        return _UNITS[n // 100] + " hundred" + ("" if rest == 0 else " " + spoken(rest))
    rest = n % 1000
    return spoken(n // 1000) + " thousand" + ("" if rest == 0 else " " + spoken(rest))


def no_punctuation(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[.,;:!?()\"“”‘’—–-]", " ", text)).strip().lower()


def no_apostrophes(text: str) -> str:
    return no_punctuation(text).replace("'", "")


def numbers_as_words(text: str) -> str:
    text = re.sub(r"(\d+)\s?%", lambda m: f"{m.group(1)} percent", text)
    return re.sub(r"\b\d{1,4}\b", lambda m: spoken(int(m.group(0))), text)


def with_fillers(text: str) -> str:
    words = text.split()
    return " ".join(w if i % 9 != 4 else f"um {w}" if i % 18 == 4 else f"uh {w}" for i, w in enumerate(words))


def full_dictation(text: str) -> str:
    return with_fillers(no_apostrophes(numbers_as_words(text)))


TRANSFORMS: dict[str, Callable[[str], str]] = {
    "no_punctuation": no_punctuation,
    "no_apostrophes": no_apostrophes,
    "numbers_as_words": numbers_as_words,
    "fillers": with_fillers,
    "all_of_these": full_dictation,
}


def decisions(fb: Feedback) -> tuple:
    return tuple(p.covered for p in fb.points)


def development_answers() -> list[tuple[Question, str, str]]:
    """Written (not dictated) answers from the development sets, with their questions."""
    out = []
    for name in ("career_dev.json", "career_families_dev.json"):
        data = json.loads((EVAL_DIR / name).read_text(encoding="utf-8"))
        for c in data["cases"]:
            if c.get("variant", "") in ("dictated", "keyword_list") or "dictated" in c.get("tags", []):
                continue
            q = get_question(data["track"], c["question_id"], c["question_version"])
            if q is not None:
                out.append((q, c["answer"], f"{data['id']}/{c['id']}"))
    return out


def corpus_answers(limit: int = 400) -> list[tuple[Question, str, str]]:
    """Answer-like text from the repository (test answers, question outlines read as answers),
    each paired with a question of a matching kind; deterministic."""
    import ast

    texts: list[str] = []
    for f in sorted((EVAL_DIR.parent / "tests").glob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        texts += [
            n.value
            for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and len(n.value.split()) >= 40
        ]
    qs = list(questions_for("registered-nurse"))
    texts += [" ".join(q.outline) for q in qs[::7]]
    texts = sorted(set(texts))[:limit]
    return [(qs[i % len(qs)], t, f"corpus/{i}") for i, t in enumerate(texts)]


def parity(
    items: list[tuple[Question, str, str]], grader: Callable[[Question, str], Feedback] = grade
) -> dict:
    out = {}
    for name, fn in TRANSFORMS.items():
        same = total = answers_changed = gained = lost = 0
        changed_ids: list[str] = []
        for q, text, uid in items:
            a, b = decisions(grader(q, text)), decisions(grader(q, fn(text)))
            diff = sum(x != y for x, y in zip(a, b, strict=True))
            same += len(a) - diff
            total += len(a)
            gained += sum(y and not x for x, y in zip(a, b, strict=True))
            lost += sum(x and not y for x, y in zip(a, b, strict=True))
            if diff:
                answers_changed += 1
                changed_ids.append(uid)
        out[name] = {
            "criteria_same": same,
            "criteria": total,
            "answers": len(items),
            "answers_changed": answers_changed,
            "points_gained": gained,
            "points_lost": lost,
            "changed": changed_ids[:12],
        }
    return out


def main() -> None:
    for label, items in (
        ("development (written answers)", development_answers()),
        ("corpus", corpus_answers()),
    ):
        print(f"== {label}: {len(items)} answers")
        for name, r in parity(items).items():
            print(
                f"  {name:18} same {r['criteria_same']}/{r['criteria']} criteria; {r['answers_changed']} answers changed "
                f"(+{r['points_gained']} / -{r['points_lost']} points)  e.g. {r['changed'][:4]}"
            )
    sys.exit(0)


if __name__ == "__main__":
    main()
