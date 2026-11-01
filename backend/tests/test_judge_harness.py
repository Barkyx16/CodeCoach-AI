import json

import pytest

from app.services.judge.harness import (
    RESULT_PREFIX,
    UnsupportedTypeError,
    build_driver,
    java_literal,
    judge_cases,
)


def test_java_literals():
    assert java_literal(5, "int") == "5"
    assert java_literal(True, "boolean") == "true"
    assert java_literal([1, -2], "int[]") == "new int[] {1, -2}"
    assert java_literal('he said "hi"\n', "String") == '"he said \\"hi\\"\\n"'
    assert java_literal("é", "String") == '"\\u00e9"'
    assert java_literal(["a"], "String[]") == 'new String[] {"a"}'
    with pytest.raises(TypeError):
        java_literal(True, "int")  # bool is not an int here
    with pytest.raises(UnsupportedTypeError):
        java_literal(1, "Map<Integer,Integer>")


def test_driver_calls_method_once_per_case():
    sig = {
        "method": "twoSum",
        "params": [{"name": "nums", "type": "int[]"}, {"name": "target", "type": "int"}],
        "returns": "int[]",
    }
    src = build_driver(sig, [{"nums": [2, 7], "target": 9}, {"nums": [], "target": 0}])
    assert "run(0, () -> new Solution().twoSum(new int[] {2, 7}, 9));" in src
    assert "run(1, () -> new Solution().twoSum(new int[] {}, 0));" in src


def line(**payload):
    return RESULT_PREFIX + json.dumps(payload)


def test_judging_outputs_exceptions_and_missing_lines():
    stdout = "\n".join(
        [
            "user debug output that should be ignored",
            line(index=0, ok=True, output=9),
            line(index=1, ok=False, exception="IllegalArgumentException"),
            line(index=2, ok=True, output=True),
            RESULT_PREFIX + "{not json",
        ]
    )
    expected = [9, {"throws": "IllegalArgumentException"}, 1, "never printed"]
    outcomes = judge_cases(expected, stdout)
    assert [o.passed for o in outcomes] == [True, True, False, False]  # True != 1
    assert outcomes[3].missing


def test_fake_result_lines_cannot_override_real_ones():
    # The driver prints results in order; a solution that prints a forged line for a later
    # index first would be caught because the first report wins only if it appears first.
    # Defense in depth: the runner must also add a per-run random nonce (see SECURITY.md).
    stdout = line(index=0, ok=True, output=1) + "\n" + line(index=0, ok=True, output=2)
    assert judge_cases([1], stdout)[0].passed
