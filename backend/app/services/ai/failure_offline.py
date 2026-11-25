"""Offline "explain my failure": deterministic, rule-based explanations of judge verdicts.

Inputs are only what the learner can already see: the verdict, the (redacted) compiler output,
the first failing PUBLIC test, and pass counts. Hidden tests are never described beyond counts.

Each rule turns a concrete piece of evidence (a javac message, an exception class, an
expected-vs-actual pair) into a cause category, a plain-English explanation and next steps.
Nothing here guesses about code it can't see, and confidence is set by how direct the evidence
is: a compiler message is "high", a pattern in a wrong answer is "medium", a hidden-test
failure is "low".
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass

from app.schemas.ai import FailureExplanation
from app.services.ai.base import FailingCase, FailureContext
from app.services.ai.static_analysis import strip_comments_and_literals

_DIAG = re.compile(r"^(?P<file>[\w$]+\.java)(?::(?P<line>\d+))?(?: \(judge driver\))?: error: (?P<msg>.*)$")
_DETAIL = re.compile(r"^\s+(?P<key>symbol|location|required|found|reason):\s+(?P<value>.*)$")
_JAVA_UTIL = {
    "ArrayList", "List", "HashMap", "Map", "HashSet", "Set", "Arrays", "Collections", "Deque",
    "ArrayDeque", "Stack", "Queue", "LinkedList", "PriorityQueue", "TreeMap", "TreeSet",
    "Iterator", "LinkedHashMap", "LinkedHashSet", "Objects",
}  # fmt: skip


@dataclass(frozen=True)
class Diagnostic:
    file: str
    line: int | None
    message: str
    details: dict[str, str]


def parse_javac(output: str) -> list[Diagnostic]:
    diags: list[Diagnostic] = []
    current: dict | None = None
    for raw in output.splitlines():
        m = _DIAG.match(raw)
        if m:
            if current:
                diags.append(Diagnostic(**current))
            current = {
                "file": m["file"],
                "line": int(m["line"]) if m["line"] else None,
                "message": m["msg"].strip(),
                "details": {},
            }
            continue
        d = _DETAIL.match(raw)
        if d and current is not None:
            current["details"].setdefault(d["key"], d["value"].strip())
    if current:
        diags.append(Diagnostic(**current))
    return diags


def _signature_text(ctx: FailureContext) -> str:
    sig = ctx.problem.signature
    params = ", ".join(f"{p['type']} {p['name']}" for p in sig.get("params", []))
    return f"public {sig.get('returns')} {sig.get('method')}({params})"


def _explain(
    cause: str,
    headline: str,
    explanation: str,
    evidence: str,
    steps: list[str],
    *,
    line: int | None = None,
    concept: str | None = None,
    confidence: str = "medium",
) -> FailureExplanation:
    return FailureExplanation.model_validate(
        {
            "cause": cause,
            "headline": headline,
            "explanation": explanation,
            "evidence": evidence,
            "line_hint": line,
            "next_steps": steps[:3],
            "concept": concept,
            "confidence": confidence,
        }
    )


# --- compile errors -------------------------------------------------------------------------


def _compile(ctx: FailureContext) -> FailureExplanation:
    diags = parse_javac(ctx.compile_output or "")
    learner = [d for d in diags if d.file == "Solution.java"]
    driver = [d for d in diags if d.file != "Solution.java"]
    if not learner and driver:
        return _driver_mismatch(ctx, driver[0])
    if not diags:
        return _explain(
            "compile-error",
            "Your code didn't compile.",
            "The compiler rejected the code, but its output couldn't be matched to a known "
            "message. Read the compiler output from the top: the first error is usually the "
            "real one, and later errors are often knock-on effects.",
            (ctx.compile_output or "(no compiler output)").splitlines()[0][:200]
            if ctx.compile_output
            else "(no compiler output)",
            ["Fix the first compiler error only, then submit again."],
            confidence="low",
        )
    d = learner[0]
    more = len(learner) - 1
    exp = _compile_rule(ctx, d)
    if more:
        exp = exp.model_copy(
            update={
                "next_steps": [
                    *exp.next_steps[:2],
                    f"There {'is' if more == 1 else 'are'} {more} more compiler "
                    f"error{'s' if more != 1 else ''} after this one. Fix this first: later errors "
                    "are often caused by the first.",
                ]
            }
        )
    return exp


def _compile_rule(ctx: FailureContext, d: Diagnostic) -> FailureExplanation:  # noqa: PLR0911, PLR0912
    msg, line = d.message, d.line
    evidence = f"Compiler, line {line}: {msg}" if line else f"Compiler: {msg}"
    symbol = d.details.get("symbol", "")
    location = d.details.get("location", "")

    def ce(headline: str, why: str, steps: list[str], concept: str | None = None) -> FailureExplanation:
        return _explain(
            "compile-error", headline, why, evidence, steps, line=line, concept=concept, confidence="high"
        )

    if msg == "cannot find symbol":
        kind, _, name = symbol.partition(" ")
        bare = name.split("(")[0]
        if kind == "class" and bare in _JAVA_UTIL:
            return ce(
                f"`{bare}` needs an import.",
                f"`{bare}` lives in the `java.util` package, and Java only knows about classes you "
                "import (apart from `java.lang`).",
                ["Add `import java.util.*;` at the very top of the file, above `class Solution`."],
                concept="Java imports and packages",
            )
        if kind == "method" and bare == "length" and "[]" in location:
            return ce(
                "Arrays use `.length`, not `.length()`.",
                "On an array, `length` is a field, so it has no parentheses. `length()` is a method "
                "on `String`.",
                [f"On line {line}, change `.length()` to `.length` for the array."],
                concept="Arrays vs. Strings in Java",
            )
        if kind == "variable" and bare == "length" and "String" in location:
            return ce(
                "Strings use `.length()`, not `.length`.",
                "On a `String`, `length()` is a method and needs parentheses. The bare `.length` "
                "field only exists on arrays.",
                [f"On line {line}, change `.length` to `.length()`."],
                concept="Arrays vs. Strings in Java",
            )
        if kind == "method" and bare == "size" and "[]" in location:
            return ce(
                "Arrays don't have `.size()`.",
                "`size()` is for collections like `List` and `Map`. Arrays have a `length` field.",
                [f"On line {line}, use `.length` instead of `.size()`."],
                concept="Arrays vs. collections",
            )
        if kind == "variable":
            return ce(
                f"Java can't find a variable named `{bare}`.",
                f"`{bare}` is used on line {line}, but no variable with that name is visible there. "
                "Usually it's a typo, or the variable was declared inside a block (a loop or an "
                "`if`) and is used after that block has ended. Variables only exist inside the "
                "braces where they're declared.",
                [
                    f"Check the spelling of `{bare}` (Java is case-sensitive).",
                    "If it's declared inside a loop or `if`, move the declaration above that block.",
                ],
                concept="Variable scope",
            )
        if kind == "method":
            return ce(
                f"Java can't find the method `{bare}` you called.",
                f"Line {line} calls `{name}`, but there's no method with that name and those "
                "parameter types. It may be misspelled, called on the wrong type, or called with "
                "the wrong argument types.",
                [
                    f"Check the spelling and the argument types of `{bare}`.",
                    "Check that you're calling it on the right kind of object.",
                ],
            )
        return ce(
            "Java can't find a name you used.",
            f"Something on line {line} refers to {symbol or 'a name'} that doesn't exist where it's used.",
            ["Check the spelling, and whether it needs an import such as `import java.util.*;`."],
        )

    m = re.match(r"incompatible types: possible lossy conversion from (\w+) to (\w+)", msg)
    if m:
        return ce(
            f"Converting `{m[1]}` to `{m[2]}` could lose information.",
            f"Java won't silently narrow a `{m[1]}` into a `{m[2]}`, because values could be cut off.",
            [
                f"If the value always fits, cast it explicitly: `({m[2]}) value`.",
                f"Otherwise keep the variable as `{m[1]}`.",
            ],
            concept="Primitive type conversions",
        )
    m = re.match(r"incompatible types: (.+) cannot be converted to (.+)", msg)
    if m:
        return ce(
            f"A `{m[1]}` is used where a `{m[2]}` is expected.",
            f"On line {line}, the value has type `{m[1]}` but the code needs a `{m[2]}`. Check the "
            "return statement and assignment on that line against the declared types.",
            [f"Compare line {line} with the method signature: `{_signature_text(ctx)}`."],
            concept="Static typing",
        )
    if msg == "missing return statement":
        return ce(
            "Not every path through the method returns a value.",
            "Java requires a `return` on every path. A common case: returning inside a loop or "
            "an `if`, with nothing after it for when the loop ends or the condition is false.",
            ["Add a `return` at the end of the method for the case where nothing was found."],
            concept="Definite return",
        )
    m = re.match(r"variable (\w+) might not have been initialized", msg)
    if m:
        return ce(
            f"`{m[1]}` might be used before it has a value.",
            "Local variables have no default value in Java. If some path skips the assignment, "
            "the compiler rejects any later read.",
            [f"Give `{m[1]}` a starting value where you declare it."],
            concept="Definite assignment",
        )
    m = re.match(r"variable (\w+) is already defined", msg)
    if m:
        return ce(
            f"`{m[1]}` is declared twice.",
            f"Line {line} declares `{m[1]}` again in a scope where it already exists.",
            [
                f"Drop the type in front of `{m[1]}` on line {line} to reuse the existing variable, or rename it."
            ],
            concept="Variable scope",
        )
    if msg == "unreachable statement":
        return ce(
            "Some code can never run.",
            "The statement follows a `return`, `break`, `continue` or `throw` in the same block, so "
            "it can never execute.",
            [f"Look at what comes right before line {line}, then delete or move the dead code."],
        )
    m = re.match(r"(\w+) cannot be dereferenced", msg)
    if m:
        return ce(
            f"`{m[1]}` is a primitive, so it has no methods.",
            f"Primitives like `{m[1]}` aren't objects, so you can't call methods on them with `.`. "
            "Compare them with `==`, and use helpers like `Integer.toString(x)` or "
            "`Character.isDigit(c)`.",
            [f"Rewrite the call on line {line} without `.` on the primitive."],
            concept="Primitives vs. objects",
        )
    m = re.match(r"bad operand types? for (?:binary|unary) operator '(.+)'", msg)
    if m:
        return ce(
            f"The `{m[1]}` operator can't be used with these types.",
            f"Line {line} applies `{m[1]}` to types it doesn't support, for example `&&` on "
            "integers or `-` on Strings.",
            ["Check the types on both sides of the operator."],
            concept="Operators and types",
        )
    if re.match(r"non-static (method|variable) .+ cannot be referenced from a static context", msg):
        return ce(
            "Something non-static is used from a static method.",
            "A `static` method belongs to the class, not to an object, so it can't use instance "
            "fields or methods directly.",
            ["Make the helper `static` too, or keep everything as instance (non-static) methods."],
            concept="static vs. instance members",
        )
    if msg in ("reached end of file while parsing",) or msg.startswith(
        "class, interface, enum, or record expected"
    ):
        return ce(
            "The braces `{ }` don't match up.",
            "Java reached the end of the file (or found code outside the class) because an opening "
            "or closing brace is missing or extra.",
            ["Count the braces: every method and the class need a matching `}`."],
        )
    m = re.match(r"'(.+)' expected", msg)
    if m or msg == "illegal start of expression" or msg.startswith("not a statement"):
        expected = f"`{m[1]}`" if m else "valid Java"
        return ce(
            f"Syntax error near line {line}.",
            f"The compiler expected {expected} there. Usually it's a missing `;`, an unclosed "
            "parenthesis or brace, or a method written inside another method.",
            [f"Look at line {line} and the line just above it."],
        )
    if msg.startswith("unclosed string literal") or msg.startswith("unclosed character literal"):
        return ce(
            "A quote isn't closed.",
            "Strings use double quotes (\"abc\"), chars use single quotes ('a'), and both must close "
            "on the same line.",
            [f"Check the quotes on line {line}."],
        )
    m = re.match(r"method (\w+) in class (\w+) cannot be applied to given types", msg)
    if m:
        req, found = d.details.get("required", "?"), d.details.get("found", "?")
        return ce(
            f"`{m[1]}` is called with the wrong arguments.",
            f"`{m[1]}` expects ({req}) but was given ({found}).",
            [f"Match the call on line {line} to the method's parameters."],
        )
    m = re.match(r"unreported exception (\S+); must be caught", msg)
    if m:
        return ce(
            f"`{m[1]}` must be handled.",
            f"`{m[1]}` is a checked exception, so Java requires a `try/catch` around the call, or a "
            "`throws` clause.",
            ["These problems don't need checked exceptions; prefer an approach without them."],
            concept="Checked exceptions",
        )
    if "is public, should be declared in a file named" in msg:
        return ce(
            "Keep the class name `Solution`.",
            "Your code is saved as Solution.java, and a public class has to match its file name.",
            ["Rename the class back to `Solution`."],
        )
    return ce(
        "Your code didn't compile.",
        f"The compiler reported: {msg}.",
        [f"Look at line {line} and the line just above it." if line else "Read the first compiler error."],
    )


def _driver_mismatch(ctx: FailureContext, d: Diagnostic) -> FailureExplanation:
    sig = _signature_text(ctx)
    return _explain(
        "compile-error",
        "The judge couldn't call your method: its signature changed.",
        "Your code compiles on its own, but the judge calls the method exactly as it appears in "
        f"the starter code: `{sig}`. If the class is renamed, or the method's name, parameter "
        "types or return type change, the judge's call no longer matches.",
        f"Judge driver: {d.message}" + (f" ({d.details['symbol']})" if d.details.get("symbol") else ""),
        [
            f"Keep `class Solution` and the method as `{sig}`.",
            "Put any extra logic in helper methods instead of changing this signature.",
        ],
        concept="Method signatures",
        confidence="high",
    )


# --- runtime errors -------------------------------------------------------------------------


def _case_evidence(case: FailingCase) -> str:
    args = ", ".join(f"{k} = {json.dumps(v)}" for k, v in (case.input or {}).items())
    where = f" at line {case.line}" if case.line else ""
    if case.exception:
        msg = f": {case.message}" if case.message else ""
        return f"Public test {case.index + 1} ({args}) threw {case.exception}{msg}{where}"
    return (
        f"Public test {case.index + 1} ({args}): expected {json.dumps(case.expected)}, "
        f"got {json.dumps(case.actual)}"
    )


def _line_of_pattern(code: str, pattern: str) -> int | None:
    stripped = strip_comments_and_literals(code)
    for i, line in enumerate(stripped.splitlines(), start=1):
        if re.search(pattern, line):
            return i
    return None


def _exception(ctx: FailureContext, case: FailingCase) -> FailureExplanation:  # noqa: PLR0911
    exc, msg = case.exception or "", case.message or ""
    line = case.line
    evidence = _case_evidence(case)
    at = f"line {line}" if line else "your code"

    if exc in (
        "ArrayIndexOutOfBoundsException",
        "StringIndexOutOfBoundsException",
        "IndexOutOfBoundsException",
    ):
        idx = re.search(r"-?\d+", msg)
        bad = int(idx[0]) if idx else None
        if bad is not None and bad < 0:
            why = (
                f"The code read index {bad}. Negative indexes never exist in Java; something "
                "decremented past 0, or a `- 1` ran on an empty range."
            )
        else:
            why = (
                f"The code read {'index ' + str(bad) if bad is not None else 'an index'} past the end. "
                "Valid indexes are 0 to length - 1, so the usual culprits are a loop condition "
                "with `<=` instead of `<`, or reading `i + 1` on the last element."
            )
        suspect = _line_of_pattern(ctx.code, r"<=\s*\w+\.(length|size\(\))")
        steps = [
            f"Trace {at} with the input from public test {case.index + 1}.",
            "Check each loop bound and every `i + 1` / `i - 1` access.",
            "Make sure empty and single-element inputs are handled first.",
        ]
        if suspect and suspect != line:
            # The throw site and the bug are often different lines: the bound lives in the loop header.
            steps[1] = (
                f"Line {suspect} loops while the index is `<=` the length: that last step is one too far."
            )
        line = line or suspect or _line_of_pattern(ctx.code, r"\[\s*\w+\s*\+\s*1\s*\]")
        return _explain(
            "index-out-of-bounds",
            f"An index went out of range at {at}.",
            why,
            evidence,
            steps,
            line=line,
            concept="Array bounds and off-by-one errors",
            confidence="high",
        )
    if exc == "NullPointerException":
        return _explain(
            "null-reference",
            f"Something was `null` when it was used at {at}.",
            "A method was called (or a field read) on a `null` reference. Common causes: a "
            "`Map.get` for a missing key unboxed into an `int`, an object field never initialised, "
            "or returning `null` and using the result.",
            evidence,
            [
                "Use `getOrDefault` or `containsKey` before reading from a Map.",
                f"Check which variable on {at} could be null for this input.",
            ],
            line=line,
            concept="null and autoboxing",
            confidence="high",
        )
    if exc == "ArithmeticException":
        return _explain(
            "arithmetic",
            f"Division (or `%`) by zero at {at}.",
            "Integer division or modulo by zero throws in Java. The divisor became 0 for this input.",
            evidence,
            ["Find which divisor can be 0, and handle that case before dividing."],
            line=line or _line_of_pattern(ctx.code, r"[/%]\s*\w"),
            concept="Integer arithmetic",
            confidence="high",
        )
    if exc == "NumberFormatException":
        return _explain(
            "number-format",
            "A String couldn't be parsed as a number.",
            "`Integer.parseInt` (or similar) was given text that isn't a valid number, such as an "
            "empty string, a sign on its own, or a value too large for an `int`.",
            evidence,
            ["Check what's passed to the parse call, or parse digit by digit."],
            line=line,
            concept="Parsing input",
            confidence="high",
        )
    if exc == "StackOverflowError":
        return _explain(
            "recursion-depth",
            "The recursion never stopped (stack overflow).",
            "Each recursive call uses stack space. Either the base case is never reached for this "
            "input, or each call doesn't make the problem smaller.",
            evidence,
            [
                "Check that the base case covers the smallest inputs (empty, 0, 1).",
                "Check that every recursive call works on a strictly smaller input.",
                "If recursion depth grows with n, consider an iterative loop instead.",
            ],
            line=line,
            concept="Recursion and base cases",
            confidence="high",
        )
    if exc in ("NegativeArraySizeException",):
        return _explain(
            "arithmetic",
            "An array was created with a negative size.",
            "The size expression came out negative for this input.",
            evidence,
            ["Check the size expression in `new ...[size]` for empty inputs."],
            line=line,
            confidence="high",
        )
    if exc in ("ConcurrentModificationException",):
        return _explain(
            "other",
            "A collection was modified while being looped over.",
            "Adding to or removing from a List/Map inside a for-each over it is not allowed.",
            evidence,
            ["Collect changes in a separate list, or use an explicit Iterator's remove()."],
            line=line,
            concept="Iterators",
            confidence="high",
        )
    if exc in ("UnsupportedOperationException",):
        return _explain(
            "other",
            "The code tried to change an immutable collection.",
            "Collections from `List.of`, `Map.of` or `Arrays.asList` can't be resized.",
            evidence,
            ["Copy into a `new ArrayList<>(...)` before modifying it."],
            line=line,
            concept="Immutable collections",
            confidence="high",
        )
    if exc in ("EmptyStackException", "NoSuchElementException"):
        return _explain(
            "other",
            "The code read from an empty stack, queue or iterator.",
            "`pop`, `peek`, `remove` or `next` was called when there was nothing left.",
            evidence,
            ["Check `isEmpty()` before popping or polling."],
            line=line,
            concept="Stacks and queues",
            confidence="high",
        )
    return _explain(
        "crash",
        f"Your code threw {exc} at {at}.",
        f"{exc} was thrown{': ' + msg if msg else ''} while running public test {case.index + 1}.",
        evidence,
        [f"Trace {at} with that test's input."],
        line=line,
        confidence="medium",
    )


# --- wrong answers --------------------------------------------------------------------------


def _wrong_answer(ctx: FailureContext, case: FailingCase) -> FailureExplanation:  # noqa: PLR0911
    exp, act = case.expected, case.actual
    evidence = _case_evidence(case)
    trace = f"Trace your code by hand with public test {case.index + 1}'s input."

    def wa(
        headline: str, why: str, steps: list[str], cause: str = "wrong-answer", **kw
    ) -> FailureExplanation:
        return _explain(cause, headline, why, evidence, [*steps, trace], **kw)

    if act is None and exp is not None:
        return wa(
            "The method returned `null`.",
            "A `null` result usually means the starter code's placeholder return is still being "
            "reached, or a path through the method doesn't build the answer.",
            ["Check which `return` statement runs for this input."],
            confidence="medium",
        )
    if isinstance(exp, bool) and isinstance(act, bool):
        return wa(
            f"Returned {str(act).lower()} where {str(exp).lower()} was expected.",
            "For yes/no problems, a flipped answer usually means one condition is inverted, or the "
            "method returns early before checking everything.",
            ["Check every early `return true/false` and the final return."],
        )
    if isinstance(exp, int) and isinstance(act, int):
        if act < 0 <= exp and exp > 2**31 // 2:
            return wa(
                "The number overflowed.",
                f"The expected value ({exp}) is large and yours ({act}) is negative: an `int` "
                "wrapped around past 2,147,483,647.",
                [
                    "Use `long` for the running total, or rearrange the arithmetic (e.g. `lo + (hi - lo) / 2`)."
                ],
                cause="overflow",
                concept="Integer overflow",
                confidence="high",
            )
        if abs(exp - act) == 1:
            return wa(
                f"Off by one: got {act}, expected {exp}.",
                "Being exactly one away usually means a loop bound (`<` vs `<=`), a starting value, "
                "or a `+ 1` / `- 1` adjustment is slightly off.",
                ["Check loop bounds and initial values.", "Check the last iteration and the empty case."],
                concept="Off-by-one errors",
                confidence="medium",
            )
        if act == 0 and exp != 0:
            return wa(
                "Returned 0: the result was never updated.",
                "A result of 0 often means the variable holding the answer kept its initial value, for "
                "example because the loop never ran or the update condition was never true.",
                ["Check that the loop runs, and that the answer variable is assigned inside it."],
                confidence="medium",
            )
    if isinstance(exp, list) and isinstance(act, list):
        if act == list(reversed(exp)) and exp != act:
            return wa(
                "Right values, reversed order.",
                "Your result has the expected elements in the opposite order.",
                ["Check the direction you build the result, or which index comes first."],
                concept="Output order",
                confidence="medium",
            )
        if Counter(map(json.dumps, act)) == Counter(map(json.dumps, exp)):
            return wa(
                "Right values, wrong order.",
                "Your result contains the expected elements, but the problem requires a specific order.",
                ["Re-read the statement for the required order."],
                concept="Output order",
                confidence="medium",
            )
        if len(act) != len(exp):
            return wa(
                f"Wrong number of elements: got {len(act)}, expected {len(exp)}.",
                "The result has too many or too few elements. Check when elements are added, and "
                "whether the final element is handled after the loop ends.",
                ["Check what happens on the last iteration and after the loop."],
                confidence="medium",
            )
    if isinstance(exp, str) and isinstance(act, str):
        if act.strip() == exp.strip() and act != exp:
            return wa(
                "Extra or missing spaces.",
                "The text matches except for leading or trailing whitespace.",
                ["Check where spaces are added, especially the first and last word."],
                concept="String building",
                confidence="high",
            )
        if act.lower() == exp.lower():
            return wa(
                "Upper/lower case differs.",
                "The letters are right but the case is different.",
                ["Check any toUpperCase/toLowerCase calls."],
                confidence="high",
            )
        if act == exp[::-1]:
            return wa(
                "The string is reversed.",
                "Your result is the expected string backwards.",
                ["Check the direction you build the string."],
                confidence="medium",
            )
    return wa(
        "Wrong answer on a public test.",
        f"For this input your code returned {json.dumps(act)} instead of {json.dumps(exp)}.",
        ["Re-read the problem statement for any rule the code doesn't handle."],
        confidence="low",
    )


def _hidden_only(ctx: FailureContext) -> FailureExplanation:
    constraints = "; ".join(ctx.problem.constraints[:3]) or "the stated constraints"
    failed = ctx.hidden_total - ctx.hidden_passed
    return _explain(
        "hidden-edge-case",
        "All public tests pass, but a hidden edge case fails.",
        f"{failed} of {ctx.hidden_total} hidden tests failed. Hidden tests usually cover the edges "
        f"of the input range ({constraints}). Their inputs stay hidden so you practise finding edge "
        "cases yourself, the way you would in an interview.",
        f"Public tests: {ctx.public_passed}/{ctx.public_total} passed. Hidden tests: "
        f"{ctx.hidden_passed}/{ctx.hidden_total} passed.",
        [
            "Try the smallest inputs: empty, a single element, two equal elements.",
            "Try extremes: negative numbers, the largest values (overflow?), all elements equal.",
            "Write those inputs down and trace your code on each one.",
        ],
        concept="Edge-case testing",
        confidence="low",
    )


# --- limits ---------------------------------------------------------------------------------


def _time_limit(ctx: FailureContext) -> FailureExplanation:
    a, expected = ctx.analysis, ctx.problem.expected_time
    reached = ctx.public_passed
    evidence = f"Time limit exceeded after {reached} of {ctx.public_total} public tests had finished."
    if a.exponential_recursion:
        return _explain(
            "time-limit",
            "Exponential recursion is too slow.",
            "Each call makes two or more recursive calls without remembering results, so the same "
            "subproblems are solved again and again: O(2^n).",
            evidence,
            ["Cache results in a map or array (memoisation), or build the answer bottom-up."],
            concept="Memoisation / dynamic programming",
            confidence="medium",
        )
    if expected and a.estimated_time not in (expected, "O(1)") and a.max_loop_depth >= 2:
        return _explain(
            "time-limit",
            f"Your approach looks like {a.estimated_time}; this problem needs {expected}.",
            f"Nested loops make roughly n² steps. With the input sizes in the constraints that is "
            f"too slow. The target is {expected}.",
            evidence,
            [
                "Ask what the inner loop is searching for, and whether a HashMap/HashSet could find it in O(1).",
                "Ask for a hint if you're unsure which data structure fits.",
            ],
            concept="Time complexity",
            confidence="medium",
        )
    loop_line = _line_of_pattern(ctx.code, r"\bwhile\s*\(")
    return _explain(
        "time-limit",
        "The code ran out of time, possibly in an infinite loop.",
        "No obvious nested loops were found, so the most common cause is a loop whose variables "
        "never move toward the exit condition, for example a `while` that never updates its "
        "pointer in one branch.",
        evidence,
        [
            "In every loop, check that each branch moves an index or pointer.",
            "Check `while` conditions for cases that can never become false.",
        ],
        line=loop_line,
        concept="Loop termination",
        confidence="low",
    )


def _memory_limit(ctx: FailureContext) -> FailureExplanation:
    return _explain(
        "memory-limit",
        "The code used too much memory.",
        "Memory ran out. Typical causes: adding to a collection inside a loop that never ends, "
        "allocating an array sized by a value instead of by the input length, or storing every "
        "intermediate result.",
        f"Memory limit exceeded after {ctx.public_passed} of {ctx.public_total} public tests finished.",
        [
            "Check loops that add to a list, map or StringBuilder: do they always end?",
            "Check the size of every `new` array.",
        ],
        concept="Space complexity",
        confidence="low",
    )


# --- entry point ----------------------------------------------------------------------------


def explain_offline(ctx: FailureContext) -> FailureExplanation:
    status = ctx.status
    case = ctx.failing_case
    if status == "COMPILE_ERROR":
        return _compile(ctx)
    if status == "TIME_LIMIT":
        return _time_limit(ctx)
    if status == "MEMORY_LIMIT":
        return _memory_limit(ctx)
    if case is not None and case.exception:
        return _exception(ctx, case)
    if status == "RUNTIME_ERROR":
        return _explain(
            "crash",
            "Your program stopped before finishing all tests.",
            "The run ended early without reporting an exception, for example because of "
            "`System.exit`, or because it printed more output than allowed.",
            f"{ctx.public_passed} of {ctx.public_total} public tests finished.",
            ["Remove any `System.exit` calls and large debug printing."],
            confidence="low",
        )
    if case is not None and not case.missing:
        return _wrong_answer(ctx, case)
    return _hidden_only(ctx)
