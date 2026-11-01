"""Deterministic, explainable checks on Java source.

These power the offline reviewer (no API key needed) and are also passed to the LLM as
grounding facts, so the model's review is anchored to things we can actually detect.

This is heuristic text analysis, not a Java parser: every finding is phrased as something
to check, and offline reviews always report confidence "low" or "medium".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_LINE_COMMENT = re.compile(r"//[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_STRING = re.compile(r'"(?:\\.|[^"\\])*"')
_CHAR = re.compile(r"'(?:\\.|[^'\\])'")
_LOOP = re.compile(r"\b(for|while)\s*\(")
_DO = re.compile(r"\bdo\s*\{")


@dataclass
class Finding:
    severity: str  # low | medium | high
    category: str  # correctness | edge-case | complexity | readability | style
    detail: str
    suggestion: str
    line: int | None = None


@dataclass
class Analysis:
    findings: list[Finding] = field(default_factory=list)
    max_loop_depth: int = 0
    uses_collections: bool = False
    allocates_arrays: bool = False
    uses_sort: bool = False
    has_recursion: bool = False
    is_unchanged_starter: bool = False
    line_count: int = 0

    @property
    def estimated_time(self) -> str:
        if self.has_recursion and self.max_loop_depth == 0:
            return "depends on recursion (check for repeated subproblems)"
        base = {0: "O(1)", 1: "O(n)", 2: "O(n^2)"}.get(self.max_loop_depth, f"O(n^{self.max_loop_depth})")
        if self.uses_sort and self.max_loop_depth <= 1:
            return "O(n log n)"
        return base

    @property
    def estimated_space(self) -> str:
        return "O(n)" if (self.uses_collections or self.allocates_arrays) else "O(1)"


def strip_comments_and_literals(source: str) -> str:
    """Blank out comments and literals but keep line structure so line numbers stay right."""

    def blank(m: re.Match) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))

    out = _BLOCK_COMMENT.sub(blank, source)
    out = _LINE_COMMENT.sub(blank, out)
    out = _STRING.sub(lambda m: '"' + " " * (len(m.group(0)) - 2) + '"', out)
    return _CHAR.sub(lambda m: "'" + " " * (len(m.group(0)) - 2) + "'", out)


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _max_loop_depth(code: str) -> int:
    """Track loop nesting with a brace stack. Handles brace-less single-statement loop bodies
    approximately: a loop header immediately followed by another loop counts as nested."""
    depth_stack: list[bool] = []  # True when the brace opened a loop body
    pending_loop = False
    current = best = 0
    i = 0
    while i < len(code):
        m = _LOOP.match(code, i) or _DO.match(code, i)
        if m and (i == 0 or not (code[i - 1].isalnum() or code[i - 1] == "_")):
            if m.re is _DO:
                pending_loop = True
                i = m.end() - 1  # let the '{' be processed below
                continue
            # skip the balanced loop header (...)
            j, parens = m.end(), 1
            while j < len(code) and parens:
                parens += {"(": 1, ")": -1}.get(code[j], 0)
                j += 1
            rest = code[j:].lstrip()
            if rest.startswith("{"):
                pending_loop = True
            else:
                # brace-less body: counts as one level for the next statement only
                best = max(best, current + 1)
                nxt = _LOOP.match(rest)
                if nxt:
                    best = max(best, current + 2)
            i = j
            continue
        ch = code[i]
        if ch == "{":
            depth_stack.append(pending_loop)
            if pending_loop:
                current += 1
                best = max(best, current)
            pending_loop = False
        elif ch == "}" and depth_stack and depth_stack.pop():
            current -= 1
        i += 1
    return best


def analyze(
    source: str,
    *,
    signature: dict | None = None,
    starter_code: str | None = None,
    expected_time: str | None = None,
) -> Analysis:
    analysis = Analysis(line_count=source.count("\n") + 1)
    code = strip_comments_and_literals(source)

    if starter_code is not None and _normalize(source) == _normalize(starter_code):
        analysis.is_unchanged_starter = True
        analysis.findings.append(
            Finding(
                "high",
                "correctness",
                "This is still the starter code, so it returns a placeholder value.",
                "Replace the TODO with your own logic. Ask for a level-1 hint if you're not sure where to start.",
            )
        )
        return analysis

    if re.search(r"\bTODO\b", source):
        analysis.findings.append(
            Finding(
                "medium",
                "correctness",
                "A TODO comment is still in the code.",
                "Finish or remove the TODO before submitting.",
                _line_of(source, source.index("TODO")),
            )
        )

    analysis.max_loop_depth = _max_loop_depth(code)
    analysis.uses_collections = bool(
        re.search(
            r"\bnew\s+(HashMap|HashSet|TreeMap|TreeSet|ArrayList|LinkedList|ArrayDeque|Stack|PriorityQueue|StringBuilder)\b",
            code,
        )
    )
    analysis.allocates_arrays = (
        bool(re.search(r"\bnew\s+\w+\s*\[\s*(?!\d+\s*\])[^\]\s]", code)) or ".toCharArray()" in code
    )
    analysis.uses_sort = bool(re.search(r"\b(Arrays|Collections)\.sort\s*\(|\.sort\s*\(", code))

    method = (signature or {}).get("method")
    if method:
        calls = len(re.findall(rf"\b{re.escape(method)}\s*\(", code))
        analysis.has_recursion = calls > 1  # declaration + at least one call

    if analysis.max_loop_depth >= 2 and expected_time and "^2" not in expected_time:
        m = _LOOP.search(code)
        analysis.findings.append(
            Finding(
                "medium",
                "complexity",
                f"Nested loops make this roughly O(n^{analysis.max_loop_depth}), but an {expected_time} approach exists.",
                "Ask what the inner loop is searching for, and whether a HashMap/HashSet or two pointers "
                "could answer that question without rescanning.",
                _line_of(code, m.start()) if m else None,
            )
        )

    if analysis.uses_sort and expected_time in {"O(n)", "O(log n)"}:
        m = re.search(r"\.sort\s*\(", code)
        analysis.findings.append(
            Finding(
                "low",
                "complexity",
                f"Sorting costs O(n log n); the target complexity is {expected_time}.",
                "Sorting is a valid first solution. Mention the trade-off, then look for a linear pass.",
                _line_of(code, m.start()) if m else None,
            )
        )

    for m in re.finditer(r"\b(\w+)\s*\+=\s*[^;]*;", code):
        var = m.group(1)
        if re.search(rf"\bString\s+{re.escape(var)}\b", code) and analysis.max_loop_depth >= 1:
            analysis.findings.append(
                Finding(
                    "medium",
                    "complexity",
                    f"`{var} += ...` inside a loop copies the whole string every time (O(n^2) overall).",
                    "Build the result with a StringBuilder or a char[] instead.",
                    _line_of(code, m.start()),
                )
            )
            break

    params = (signature or {}).get("params", [])
    array_params = [p["name"] for p in params if p["type"].endswith("[]")]
    string_params = [p["name"] for p in params if p["type"] == "String"]
    for name in array_params:
        idx = re.search(rf"\b{re.escape(name)}\s*\[\s*0\s*\]", code)
        guarded = re.search(
            rf"\b{re.escape(name)}\s*\.\s*length\s*(==|<=|<|>|!=)\s*[01]\b", code
        ) or re.search(rf"\b{re.escape(name)}\s*==\s*null", code)
        if idx and not guarded:
            analysis.findings.append(
                Finding(
                    "medium",
                    "edge-case",
                    f"`{name}[0]` is read without checking whether `{name}` is empty.",
                    f"Decide what should happen when `{name}.length == 0` and handle it first.",
                    _line_of(code, idx.start()),
                )
            )
    for name in string_params:
        idx = re.search(rf"\b{re.escape(name)}\s*\.\s*charAt\s*\(\s*0\s*\)", code)
        guarded = re.search(rf"\b{re.escape(name)}\s*\.\s*(isEmpty|length)\s*\(", code)
        if idx and not guarded:
            analysis.findings.append(
                Finding(
                    "medium",
                    "edge-case",
                    f"`{name}.charAt(0)` will throw on an empty string.",
                    "Check for the empty string before reading the first character.",
                    _line_of(code, idx.start()),
                )
            )

    m = re.search(r"\(\s*(\w+)\s*\+\s*(\w+)\s*\)\s*/\s*2", code)
    if m:
        analysis.findings.append(
            Finding(
                "low",
                "correctness",
                f"`({m.group(1)} + {m.group(2)}) / 2` can overflow for very large indexes.",
                f"Write `{m.group(1)} + ({m.group(2)} - {m.group(1)}) / 2` instead. Interviewers notice this.",
                _line_of(code, m.start()),
            )
        )

    m = re.search(r"\bnew\s+Stack\s*<", code)
    if m:
        analysis.findings.append(
            Finding(
                "low",
                "style",
                "`java.util.Stack` is a legacy synchronized class.",
                "Prefer `Deque<T> stack = new ArrayDeque<>()` with push/pop.",
                _line_of(code, m.start()),
            )
        )

    m = re.search(r"System\s*\.\s*(out|err)\s*\.\s*print", code)
    if m:
        analysis.findings.append(
            Finding(
                "low",
                "style",
                "Debug printing is left in the solution.",
                "Remove print statements before submitting; they slow the judge and clutter output.",
                _line_of(code, m.start()),
            )
        )

    m = re.search(r"catch\s*\(\s*(Exception|Throwable)\s+\w+\s*\)\s*\{\s*\}", code)
    if m:
        analysis.findings.append(
            Finding(
                "medium",
                "correctness",
                "An empty catch block silently swallows every exception.",
                "Catch only the exception you expect, or let it propagate.",
                _line_of(code, m.start()),
            )
        )

    for m in re.finditer(r"\b(?:int|long|String|boolean|char|double)\s+([a-z])\s*[=;]", code):
        if m.group(1) not in {"i", "j", "k", "n", "m", "c"}:
            analysis.findings.append(
                Finding(
                    "low",
                    "readability",
                    f"The single-letter variable `{m.group(1)}` hides its purpose.",
                    "Use a descriptive name such as `largest`, `count` or `left`.",
                    _line_of(code, m.start()),
                )
            )
            break

    return analysis


def _normalize(code: str) -> str:
    return re.sub(r"\s+", "", code)
