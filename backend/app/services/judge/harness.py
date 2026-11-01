"""Generate the Java test driver for a problem, and judge its output.

This module is pure: it builds source text and parses text. It never compiles or runs
anything. Untrusted code runs only inside the isolated runner (docs/SECURITY.md §4).

Driver protocol
---------------
The driver (Main.java) runs inside the sandbox next to the learner's Solution.java:

1. Before ANY learner code runs, it reads a per-run random nonce from the first line of stdin
   and keeps it in a local variable (locals are not reachable through reflection), and it
   captures the original System.out stream. Learner code that later calls System.setOut, or
   prints lines that look like results, can't produce lines with the right nonce.
2. For every test case it prints exactly one line through the captured stream:

       @@CC:<nonce>@@ {"index": 0, "ok": true, "output": <json>, "ms": 1.25}
       @@CC:<nonce>@@ {"index": 1, "ok": false, "exception": "ArithmeticException", "message": "/ by zero", "ms": 0.4}

3. Hidden expected outputs never enter the sandbox: the driver only prints what the learner's
   code returned, and comparison happens here, outside the sandbox.

Residual risk (documented in SECURITY.md): learner code shares the JVM with the driver, so a
determined user could still tamper with their *own* verdict through deep reflection. That
can only affect their own account, never the host or other users.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

SUPPORTED_TYPES = {"int", "long", "boolean", "char", "String", "int[]", "String[]"}
MAX_MESSAGE_CHARS = 300


class UnsupportedTypeError(ValueError):
    pass


def result_prefix(nonce: str) -> str:
    return f"@@CC:{nonce}@@ "


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


# Placeholders: __CALLS__ (one line per test case) and __MAX_MESSAGE__.
_DRIVER_TEMPLATE = r"""
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.PrintStream;
import java.util.function.Supplier;

public final class Main {
    private Main() {}

    public static void main(String[] args) throws Exception {
        // Read the nonce and capture stdout BEFORE any learner code (including Solution's
        // static initialisers) can run.
        final String nonce;
        try (BufferedReader in = new BufferedReader(new InputStreamReader(System.in))) {
            String line = in.readLine();
            nonce = line == null ? "" : line.trim();
        }
        final PrintStream out = System.out;
        final String prefix = "@@CC:" + nonce + "@@ ";
__CALLS__
        out.flush();
    }

    private static void run(PrintStream out, String prefix, int index, Supplier<Object> call) {
        StringBuilder sb = new StringBuilder(prefix).append("{\"index\": ").append(index);
        long start = System.nanoTime();
        try {
            Object result = call.get();
            double ms = (System.nanoTime() - start) / 1_000_000.0;
            sb.append(", \"ok\": true, \"output\": ").append(toJson(result)).append(", \"ms\": ").append(ms);
        } catch (Throwable t) {
            double ms = (System.nanoTime() - start) / 1_000_000.0;
            String message = t.getMessage() == null ? "" : t.getMessage();
            if (message.length() > __MAX_MESSAGE__) message = message.substring(0, __MAX_MESSAGE__);
            sb.append(", \"ok\": false, \"exception\": ").append(toJson(t.getClass().getSimpleName()))
              .append(", \"message\": ").append(toJson(message))
              .append(", \"line\": ").append(learnerLine(t)).append(", \"ms\": ").append(ms);
        }
        out.println(sb.append("}"));
        out.flush();
    }

    // Line of the innermost frame in the learner's file, so feedback can point at it.
    private static String learnerLine(Throwable t) {
        for (StackTraceElement e : t.getStackTrace()) {
            if ("Solution.java".equals(e.getFileName()) && e.getLineNumber() > 0) {
                return String.valueOf(e.getLineNumber());
            }
        }
        return "null";
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
        StringBuilder sb = new StringBuilder("\"");
        for (char c : s.toCharArray()) {
            switch (c) {
                case '"' -> sb.append("\\\"");
                case '\\' -> sb.append("\\\\");
                case '\n' -> sb.append("\\n");
                case '\r' -> sb.append("\\r");
                case '\t' -> sb.append("\\t");
                default -> {
                    if (c < 0x20 || c > 0x7e) sb.append(String.format("\\u%04x", (int) c));
                    else sb.append(c);
                }
            }
        }
        return sb.append("\"").toString();
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
        calls.append(f"        run(out, prefix, {index}, () -> new Solution().{method}({args}));")
    return (
        _DRIVER_TEMPLATE.replace("__CALLS__", "\n".join(calls))
        .replace("__MAX_MESSAGE__", str(MAX_MESSAGE_CHARS))
        .lstrip()
    )


@dataclass(frozen=True)
class CaseOutcome:
    index: int
    passed: bool
    actual: Any = None
    exception: str | None = None
    message: str | None = None
    missing: bool = False
    ms: float | None = None
    line: int | None = None  # learner's source line where an exception was thrown


def parse_driver_output(stdout: str, nonce: str = "") -> dict[int, dict]:
    prefix = result_prefix(nonce)
    results: dict[int, dict] = {}
    for line in stdout.splitlines():
        if not line.startswith(prefix):
            continue
        try:
            payload = json.loads(line[len(prefix) :])
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


def judge_cases(expected_outputs: list[Any], stdout: str, nonce: str = "") -> list[CaseOutcome]:
    """Compare driver output with expected outputs. Missing lines count as failures."""
    reported = parse_driver_output(stdout, nonce)
    outcomes = []
    for index, expected in enumerate(expected_outputs):
        row = reported.get(index)
        if row is None:
            outcomes.append(CaseOutcome(index=index, passed=False, missing=True))
            continue
        ms = row.get("ms") if isinstance(row.get("ms"), int | float) else None
        expects_throw = isinstance(expected, dict) and "throws" in expected
        if row.get("ok"):
            passed = not expects_throw and outputs_match(expected, row.get("output"))
            outcomes.append(CaseOutcome(index=index, passed=passed, actual=row.get("output"), ms=ms))
        else:
            exc = row.get("exception")
            passed = expects_throw and exc == expected["throws"]
            line = row.get("line")
            outcomes.append(
                CaseOutcome(
                    index=index,
                    passed=passed,
                    exception=exc,
                    message=row.get("message"),
                    ms=ms,
                    line=line if isinstance(line, int) and not isinstance(line, bool) and line > 0 else None,
                )
            )
    return outcomes
