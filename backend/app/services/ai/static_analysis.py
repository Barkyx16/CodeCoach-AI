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
    halving_loop: bool = False  # a loop that halves its range each step (binary search)
    exponential_recursion: bool = False  # two+ self-calls per invocation, no memoisation
    line_count: int = 0

    @property
    def estimated_time(self) -> str:
        if self.exponential_recursion:
            return "O(2^n)"
        if self.has_recursion and self.max_loop_depth == 0:
            return "depends on recursion (check for repeated subproblems)"
        if self.halving_loop and self.max_loop_depth == 1 and not self.uses_sort:
            return "O(log n)"
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


def _condition_terms(header: str) -> set[str]:
    """Comparisons in a loop header, normalised: 'left < right && x' -> {'left<right'}."""
    return {re.sub(r"\s+", "", c) for c in re.findall(r"\w+\s*(?:<=|>=|<|>|!=)\s*\w+", header)}


def _max_loop_depth(code: str) -> int:
    """Loop nesting depth, tracked with a brace stack.

    Two-pointer rule: an inner `while` whose condition repeats a comparison from an enclosing
    loop (e.g. `while (left < right && …) left++;` inside `while (left < right)`) advances the
    SAME pointers as the outer loop, so together they're still one linear pass. It doesn't add
    a nesting level.

    Brace-less loop bodies are handled approximately: a loop header immediately followed by
    another loop counts as nested.
    """
    stack: list[tuple[bool, set[str]]] = []  # (counts as a nesting level, condition terms)
    pending: tuple[bool, set[str]] | None = None
    current = best = 0
    i = 0
    while i < len(code):
        m = _LOOP.match(code, i) or _DO.match(code, i)
        if m and (i == 0 or not (code[i - 1].isalnum() or code[i - 1] == "_")):
            if m.re is _DO:
                pending = (True, set())
                i = m.end() - 1  # let the '{' be processed below
                continue
            j, parens = m.end(), 1
            while j < len(code) and parens:
                parens += {"(": 1, ")": -1}.get(code[j], 0)
                j += 1
            header = code[m.end() : j - 1]
            terms = _condition_terms(header)
            enclosing = set().union(*(t for _, t in stack)) if stack else set()
            same_pass = m.group(1) == "while" and bool(terms & enclosing)
            counts = not same_pass
            rest = code[j:].lstrip()
            if rest.startswith("{"):
                pending = (counts, terms)
            elif counts:
                # brace-less body: counts as one level for the next statement only
                best = max(best, current + 1)
                if _LOOP.match(rest):
                    best = max(best, current + 2)
            i = j
            continue
        ch = code[i]
        if ch == "{":
            if pending is not None:
                counts, terms = pending
                stack.append((counts, terms))
                if counts:
                    current += 1
                    best = max(best, current)
            else:
                stack.append((False, set()))
            pending = None
        elif ch == "}" and stack:
            counts, _ = stack.pop()
            if counts:
                current -= 1
        i += 1
    return best


def analyze(
    source: str,
    *,
    signature: dict | None = None,
    starter_code: str | None = None,
    expected_time: str | None = None,
    constraints: list[str] | None = None,
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
        # A self-call is unqualified or `this.`-qualified; `sb.reverse(` is a different method.
        call = re.compile(rf"(?:(?<![\w.])|(?<=\bthis\.)){re.escape(method)}\s*\(")
        calls = len(call.findall(code))
        analysis.has_recursion = calls > 1  # declaration + at least one call
        memoised = bool(re.search(r"\b(memo|cache|dp)\w*\b|\bnew\s+(HashMap|int\s*\[|long\s*\[)", code))
        branching = any(len(call.findall(stmt)) >= 2 for stmt in code.split(";"))
        analysis.exponential_recursion = analysis.has_recursion and branching and not memoised
    analysis.halving_loop = (
        bool(re.search(r"=\s*[^;=]*(/\s*2\b|>>>?\s*1\b)", code)) and analysis.max_loop_depth >= 1
    )
    linear_target = _is_linear(expected_time)

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

    if analysis.exponential_recursion and expected_time and "2^" not in expected_time:
        m = re.search(rf"\b{re.escape(method or '')}\s*\(", code[code.find("{") + 1 :]) if method else None
        analysis.findings.append(
            Finding(
                "high",
                "complexity",
                f"Each call makes two or more recursive calls without memoisation: about O(2^n) time, "
                f"but an {expected_time} approach exists.",
                "Cache results you've already computed (memoisation), or build the answer bottom-up.",
                None if m is None else _line_of(code, m.start() + code.find("{") + 1),
            )
        )

    if (
        expected_time
        and _normalize_big_o(expected_time) == "logn"
        and analysis.max_loop_depth == 1
        and not analysis.halving_loop
    ):
        m = _LOOP.search(code)
        analysis.findings.append(
            Finding(
                "medium",
                "complexity",
                "A single pass over the input is O(n), but this problem asks for O(log n).",
                "The input is sorted: compare with the middle element and discard half of the range each step.",
                _line_of(code, m.start()) if m else None,
            )
        )

    if analysis.uses_sort and linear_target:
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
        if _guaranteed_non_empty(name, constraints):
            continue  # the problem promises at least one element, so nums[0] is safe
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


def _normalize_big_o(expr: str) -> str:
    return re.sub(r"\s+", "", expr.lower()).removeprefix("o(").removesuffix(")")


def _is_linear(expected_time: str | None) -> bool:
    """O(n), O(n + m), O(log n): anything a sort (O(n log n)) would be worse than."""
    return expected_time is not None and _normalize_big_o(expected_time) in {"n", "n+m", "logn", "1"}


def _guaranteed_non_empty(name: str, constraints: list[str] | None) -> bool:
    pattern = re.compile(rf"\b1\s*<=\s*{re.escape(name)}\.length")
    return any(pattern.search(c) for c in constraints or [])
