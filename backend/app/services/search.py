"""Keyword search over the problem library.

People search the way they talk: "reverse words", "longest substring without repeats",
"dp on grids", "hashmap". So instead of one substring match on the title, a query is split into
words, filler words are dropped, common abbreviations are expanded, and each problem is scored
by where the words appear (title > topics > summary > full statement).

A problem matches when it contains every meaningful word. If nothing contains them all, the
search falls back to problems that contain most of them, ranked by score, so a slightly
over-specified query still finds something useful.

Matching runs in Python over the small text of each problem, which keeps it identical on SQLite
and PostgreSQL. At tens of thousands of problems this would move to Postgres full-text search.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

# Words that carry no meaning in a search like "i want to find a problem about strings".
STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "about",
        "any",
        "as",
        "at",
        "be",
        "by",
        "can",
        "do",
        "does",
        "for",
        "from",
        "give",
        "get",
        "have",
        "how",
        "i",
        "im",
        "i'm",
        "in",
        "into",
        "is",
        "it",
        "its",
        "me",
        "my",
        "need",
        "of",
        "on",
        "or",
        "problem",
        "problems",
        "question",
        "questions",
        "show",
        "some",
        "something",
        "that",
        "the",
        "them",
        "then",
        "there",
        "these",
        "this",
        "to",
        "use",
        "using",
        "want",
        "way",
        "what",
        "when",
        "where",
        "which",
        "with",
        "you",
        "your",
    ]
)

# Abbreviation or alternate spelling -> words it should also match. Each entry is checked as a
# whole word, so "dp" matches "dynamic programming" but not "dpi".
SYNONYMS: dict[str, tuple[str, ...]] = {
    "dp": ("dynamic programming", "memo"),
    "memoization": ("dynamic programming", "memo"),
    "hashmap": ("hash map", "hashmap", "map"),
    "hashtable": ("hash map", "hash table"),
    "dict": ("hash map", "map"),
    "dictionary": ("hash map", "map"),
    "hashset": ("hash set", "set"),
    "set": ("hash set", "set"),
    "bfs": ("breadth-first", "breadth first", "queue", "level"),
    "dfs": ("depth-first", "depth first", "recursion", "backtracking"),
    "2": ("two",),
    "max": ("maximum", "largest", "max"),
    "maximum": ("max", "largest", "biggest"),
    "largest": ("maximum", "max", "biggest"),
    "biggest": ("largest", "maximum", "max"),
    "min": ("minimum", "smallest", "min"),
    "minimum": ("min", "smallest", "fewest"),
    "smallest": ("minimum", "min"),
    "str": ("string",),
    "arr": ("array",),
    "list": ("array", "list"),
    "matrix": ("grid", "matrix", "2d"),
    "grid": ("matrix", "grid", "2d"),
    "2d": ("grid", "matrix"),
    "sort": ("sorted", "sorting", "order"),
    "sorting": ("sort", "sorted"),
    "search": ("binary search", "find", "search"),
    "count": ("counting", "number of", "how many"),
    "duplicates": ("duplicate", "repeated", "repeat"),
    "duplicate": ("duplicates", "repeated", "repeat"),
    "unique": ("distinct", "no repeat", "without repeat"),
    "distinct": ("unique",),
    "reverse": ("reversed", "backwards", "reverse"),
    "palindrome": ("palindromic", "reads the same"),
    "sum": ("add up", "total", "sum"),
    "subarray": ("contiguous", "window", "subarray"),
    "substring": ("contiguous", "window", "substring"),
    "window": ("sliding window", "window"),
    "pointers": ("two pointers", "pointer"),
    "stack": ("stacks", "stack"),
    "queue": ("queues", "queue"),
    "heap": ("heaps", "priority queue"),
    "pq": ("priority queue", "heap"),
    "graph": ("graphs", "edges", "nodes"),
    "tree": ("trees", "binary tree"),
    "interval": ("intervals", "ranges", "meetings"),
    "intervals": ("interval", "ranges"),
    "greedy": ("greedy",),
    "recursion": ("recursive", "recursion"),
    "recursive": ("recursion",),
}

WEIGHTS = (("title", 6), ("topics", 4), ("summary", 3), ("statement", 1))


@dataclass(frozen=True)
class Searchable:
    """The text fields of one item, already lower-cased."""

    title: str
    topics: str
    summary: str
    statement: str


def tokenize(query: str) -> list[str]:
    words = re.findall(r"[a-z0-9']+", query.lower())
    return [w for w in words if w not in STOPWORDS]


def _stem(word: str) -> str:
    """Tiny plural folding: 'strings' -> 'string', 'matches' -> 'match'. Enough for search."""
    if len(word) > 4 and word.endswith("es") and word[-3] in "sxz":
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def alternatives(word: str) -> tuple[str, ...]:
    stem = _stem(word)
    return tuple(dict.fromkeys((word, stem, *SYNONYMS.get(word, ()), *SYNONYMS.get(stem, ()))))


def _contains(text: str, phrase: str) -> bool:
    # Word-start match: "sort" finds "sorted" and "sorting" but "set" doesn't find "reset".
    return re.search(r"(?<![a-z0-9])" + re.escape(phrase), text) is not None


def score_term(item: Searchable, term: str) -> int:
    best = 0
    for phrase in alternatives(term):
        for field, weight in WEIGHTS:
            if weight > best and _contains(getattr(item, field), phrase):
                best = weight
    return best


def rank[T](items: Iterable[tuple[T, Searchable]], query: str) -> list[T]:
    """Items matching the query, best first. Ties keep their original (library) order."""
    terms = tokenize(query)
    if not terms:
        return [obj for obj, _ in items]
    scored: list[tuple[int, int, int, T]] = []
    for position, (obj, text) in enumerate(items):
        scores = [score_term(text, t) for t in terms]
        hits = sum(1 for s in scores if s)
        if hits:
            scored.append((hits, sum(scores), position, obj))
    if not scored:
        return []
    full = [row for row in scored if row[0] == len(terms)]
    if full:
        chosen = full
    else:
        # Nothing has every word: keep items that have most of them (at least half, rounded up).
        need = max(1, (len(terms) + 1) // 2)
        chosen = [row for row in scored if row[0] >= need]
    chosen.sort(key=lambda row: (-row[0], -row[1], row[2]))
    return [row[3] for row in chosen]
