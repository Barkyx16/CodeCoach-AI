"""Generate a Java test driver for a problem and compare its output with expected results.

This module is pure: it builds source text and parses text. It never compiles or runs
anything. Running untrusted code is the job of an isolated runner (see
docs/security/threat-model.md); the same driver will be used inside that boundary.

Driver protocol: for every test case the driver prints exactly one line

    @@CC_RESULT@@ {"index": 0, "ok": true, "output": <json>}
    @@CC_RESULT@@ {"index": 1, "ok": false, "exception": "IllegalArgumentException"}

The random-looking prefix lets the parser ignore anything the user's code prints itself.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

RESULT_PREFIX = "@@CC_RESULT@@ "

SUPPORTED_TYPES = {"int", "long", "boolean", "char", "String", "int[]", "String[]"}


class UnsupportedTypeError(ValueError):
    pass


def java_literal(value: Any, java_type: str) -> str:
    """Render a JSON value as a Java expression of the given type."""
    match java_type:
        case "int":
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"expected int, got {value!r}")
            return str(value)
        case "long":
            return f"{int(value)}L"
        case "boolean":
            return "true" if value else "false"
        case "char":
            if not isinstance(value, str) or len(value) != 1:
                raise TypeError(f"expected single character, got {value!r}")
            return f"(char) {ord(value)}"
        case "String":
            if value is None:
                return "null"
            # json.dumps produces a valid Java string literal for these inputs: it escapes
            # quotes, backslashes and control characters, and emits \\uXXXX for non-ASCII.
            return json.dumps(str(value), ensure_ascii=True)
        case "int[]":
            return "new int[] {" + ", ".join(java_literal(v, "int") for v in value) + "}"
        case "String[]":
            return "new String[] {" + ", ".join(java_literal(v, "String") for v in value) + "}"
    raise UnsupportedTypeError(f"unsupported Java type: {java_type}")


_DRIVER_TEMPLATE = """\
import java.util.function.Supplier;

public class Main {
    private static final String PREFIX = "@@CC_RESULT@@ ";

    public static void main(String[] args) {
%(calls)s
    }

    private static void run(int index, Supplier<Object> call) {
        StringBuilder sb = new StringBuilder(PREFIX).append("{\\"index\\": ").append(index);
        try {
            Object out = call.get();
            sb.append(", \\"ok\\": true, \\"output\\": ").append(toJson(out));
        } catch (Throwable t) {
            sb.append(", \\"ok\\": false, \\"exception\\": ").append(toJson(t.getClass().getSimpleName()));
        }
        System.out.println(sb.append("}"));
        System.out.flush();
    }

    private static String toJson(Object o) {
        if (o == null) return "null";
        if (o instanceof String s) return quote(s);
        if (o instanceof Character c) return quote(String.valueOf(c));
        if (o instanceof Number || o instanceof Boolean) return String.valueOf(o);
        if (o instanceof int[] arr) {
            StringBuilder sb = new StringBuilder("[");
            for (int i = 0; i < arr.length; i++) sb.append(i == 0 ? "" : ", ").append(arr[i]);
            return sb.append("]").toString();
        }
        if (o instanceof String[] arr) {
            StringBuilder sb = new StringBuilder("[");
            for (int i = 0; i < arr.length; i++) sb.append(i == 0 ? "" : ", ").append(toJson(arr[i]));
            return sb.append("]").toString();
        }
        return quote(String.valueOf(o));
    }

    private static String quote(String s) {
        StringBuilder sb = new StringBuilder("\\"");
        for (char c : s.toCharArray()) {
            switch (c) {
                case '"' -> sb.append("\\\\\\"");
                case '\\\\' -> sb.append("\\\\\\\\");
                case '\\n' -> sb.append("\\\\n");
                case '\\r' -> sb.append("\\\\r");
                case '\\t' -> sb.append("\\\\t");
                default -> {
                    if (c < 0x20 || c > 0x7e) sb.append(String.format("\\\\u%%04x", (int) c));
                    else sb.append(c);
                }
            }
        }
        return sb.append("\\"").toString();
    }
}
"""


def build_driver(signature: dict, test_inputs: list[dict]) -> str:
    """Return Main.java source that calls Solution.<method> once per test input."""
    method = signature["method"]
    params = signature["params"]
    for t in [p["type"] for p in params] + [signature["returns"]]:
        if t not in SUPPORTED_TYPES:
            raise UnsupportedTypeError(f"unsupported Java type: {t}")
    calls = []
    for index, case_input in enumerate(test_inputs):
        args = ", ".join(java_literal(case_input[p["name"]], p["type"]) for p in params)
        calls.append(f"        run({index}, () -> new Solution().{method}({args}));")
    return _DRIVER_TEMPLATE % {"calls": "\n".join(calls)}


@dataclass(frozen=True)
class CaseOutcome:
    index: int
    passed: bool
    actual: Any = None
    exception: str | None = None
    missing: bool = False


def parse_driver_output(stdout: str) -> dict[int, dict]:
    results: dict[int, dict] = {}
    for line in stdout.splitlines():
        if not line.startswith(RESULT_PREFIX):
            continue
        try:
            payload = json.loads(line[len(RESULT_PREFIX) :])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("index"), int):
            results.setdefault(payload["index"], payload)  # first report wins
    return results


def outputs_match(expected: Any, actual: Any) -> bool:
    # bool is a subclass of int in Python; keep true != 1.
    if isinstance(expected, bool) or isinstance(actual, bool):
        return type(expected) is type(actual) and expected == actual
    return expected == actual


def judge_cases(expected_outputs: list[Any], stdout: str) -> list[CaseOutcome]:
    """Compare driver output with expected outputs. Missing lines count as failures."""
    reported = parse_driver_output(stdout)
    outcomes = []
    for index, expected in enumerate(expected_outputs):
        row = reported.get(index)
        if row is None:
            outcomes.append(CaseOutcome(index=index, passed=False, missing=True))
            continue
        expects_throw = isinstance(expected, dict) and "throws" in expected
        if row.get("ok"):
            passed = not expects_throw and outputs_match(expected, row.get("output"))
            outcomes.append(CaseOutcome(index=index, passed=passed, actual=row.get("output")))
        else:
            exc = row.get("exception")
            passed = expects_throw and exc == expected["throws"]
            outcomes.append(CaseOutcome(index=index, passed=passed, exception=exc))
    return outcomes
