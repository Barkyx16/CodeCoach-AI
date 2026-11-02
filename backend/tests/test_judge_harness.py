import json
import shutil
import subprocess

import pytest

from app.services.judge.harness import (
    UnsupportedTypeError,
    build_driver,
    java_literal,
    judge_cases,
    result_prefix,
)

NONCE = "a1b2c3d4"


def test_java_literals():
    assert java_literal(5, "int") == "5"
    assert java_literal(True, "boolean") == "true"
    assert java_literal([1, -2], "int[]") == "new int[] {1, -2}"
    assert java_literal('he said "hi"\n', "String") == '"he said \\"hi\\"\\n"'
    assert java_literal("é", "String") == '"\\u00e9"'
    assert java_literal(["a"], "String[]") == 'new String[] {"a"}'
    assert (
        java_literal([[1, 2], [], [3]], "int[][]")
        == "new int[][] {new int[] {1, 2}, new int[] {}, new int[] {3}}"
    )
    with pytest.raises(TypeError):
        java_literal(True, "int")  # bool is not an int here
    with pytest.raises(UnsupportedTypeError):
        java_literal(1, "Map<Integer,Integer>")


def test_driver_reads_nonce_before_calling_learner_code():
    sig = {
        "method": "twoSum",
        "params": [{"name": "nums", "type": "int[]"}, {"name": "target", "type": "int"}],
        "returns": "int[]",
    }
    src = build_driver(sig, [{"nums": [2, 7], "target": 9}, {"nums": [], "target": 0}])
    assert "run(out, prefix, 0, () -> new Solution().twoSum(new int[] {2, 7}, 9));" in src
    assert "run(out, prefix, 1, () -> new Solution().twoSum(new int[] {}, 0));" in src
    # Nonce + captured stream are set up before the first call into Solution.
    assert (
        src.index("readLine()")
        < src.index("final PrintStream out = System.out")
        < src.index("new Solution()")
    )


def line(nonce=NONCE, **payload):
    return result_prefix(nonce) + json.dumps(payload)


def test_judging_outputs_exceptions_and_missing_lines():
    stdout = "\n".join(
        [
            "user debug output that should be ignored",
            line(index=0, ok=True, output=9, ms=0.5),
            line(index=1, ok=False, exception="IllegalArgumentException", message="empty", ms=0.1),
            line(index=2, ok=True, output=True),
            result_prefix(NONCE) + "{not json",
        ]
    )
    expected = [9, {"throws": "IllegalArgumentException"}, 1, "never printed"]
    outcomes = judge_cases(expected, stdout, NONCE)
    assert [o.passed for o in outcomes] == [True, True, False, False]  # True != 1
    assert outcomes[0].ms == 0.5 and outcomes[1].message == "empty"
    assert outcomes[3].missing


def test_lines_with_the_wrong_nonce_are_ignored():
    forged = line(nonce="guess", index=0, ok=True, output=9)
    assert judge_cases([9], forged, NONCE)[0].missing
    real_after_forged = forged + "\n" + line(index=0, ok=True, output=1)
    assert not judge_cases([9], real_after_forged, NONCE)[0].passed


def test_first_report_per_index_wins():
    stdout = line(index=0, ok=True, output=1) + "\n" + line(index=0, ok=True, output=2)
    assert judge_cases([1], stdout, NONCE)[0].passed


FORGER = r"""
import java.io.*;
class Solution {
    static {
        // 1) Print lines that look like results, guessing the format without the nonce.
        System.out.println("@@CC:@@ {\"index\": 0, \"ok\": true, \"output\": 42}");
        System.out.println("@@CC:guess@@ {\"index\": 0, \"ok\": true, \"output\": 42}");
        // 2) Replace System.out so later driver output is swallowed or rewritten.
        System.setOut(new PrintStream(new ByteArrayOutputStream()));
    }
    public int max(int[] nums) { return -1; }
}
"""


@pytest.mark.skipif(shutil.which("javac") is None, reason="JDK not installed")
def test_forged_results_and_stream_swaps_do_not_fool_the_judge(tmp_path):
    """Compiles a hostile Solution with the real driver and runs it in a real JVM (trusted
    test code on the developer's machine; untrusted code only ever runs in the sandbox)."""
    sig = {"method": "max", "params": [{"name": "nums", "type": "int[]"}], "returns": "int"}
    (tmp_path / "Solution.java").write_text(FORGER)
    (tmp_path / "Main.java").write_text(build_driver(sig, [{"nums": [42]}]))
    subprocess.run(
        ["javac", "-d", str(tmp_path), *map(str, tmp_path.glob("*.java"))], check=True, capture_output=True
    )
    nonce = "f3e2d1c0b9a8"
    ran = subprocess.run(
        ["java", "-cp", str(tmp_path), "Main"],
        input=nonce + "\n",
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    outcome = judge_cases([42], ran.stdout, nonce)[0]
    assert not outcome.passed  # the forged "42" lines were ignored
    assert outcome.actual == -1  # the real result still got out via the captured stream


@pytest.mark.skipif(shutil.which("javac") is None, reason="JDK not installed")
def test_grids_go_in_and_come_out_as_nested_arrays(tmp_path):
    sig = {"method": "transpose", "params": [{"name": "grid", "type": "int[][]"}], "returns": "int[][]"}
    (tmp_path / "Solution.java").write_text(
        "class Solution { public int[][] transpose(int[][] g) {"
        " if (g.length == 0) return new int[0][];"
        " int[][] t = new int[g[0].length][g.length];"
        " for (int i = 0; i < g.length; i++) for (int j = 0; j < g[0].length; j++) t[j][i] = g[i][j];"
        " return t; } }"
    )
    (tmp_path / "Main.java").write_text(build_driver(sig, [{"grid": [[1, 2, 3], [4, 5, 6]]}, {"grid": []}]))
    subprocess.run(
        ["javac", "-d", str(tmp_path), *map(str, tmp_path.glob("*.java"))], check=True, capture_output=True
    )
    ran = subprocess.run(
        ["java", "-cp", str(tmp_path), "Main"], input=NONCE + "\n", capture_output=True, text=True, timeout=30
    )
    outcomes = judge_cases([[[1, 4], [2, 5], [3, 6]], []], ran.stdout, NONCE)
    assert [o.passed for o in outcomes] == [True, True], outcomes
