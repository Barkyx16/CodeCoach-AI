from app.services.ai.static_analysis import analyze, strip_comments_and_literals

SIG = {"method": "max", "params": [{"name": "nums", "type": "int[]"}], "returns": "int"}


def cats(a):
    return {f.category for f in a.findings}


def test_single_loop_is_linear_constant_space():
    a = analyze(
        "class S { int max(int[] nums) { int b = nums.length == 0 ? 0 : nums[0];"
        " for (int n : nums) { if (n > b) b = n; } return b; } }",
        signature=SIG,
        expected_time="O(n)",
    )
    assert a.max_loop_depth == 1 and a.estimated_time == "O(n)" and a.estimated_space == "O(1)"
    assert "edge-case" not in cats(a)


def test_nested_loops_with_braces_and_without():
    braces = "for (int i=0;i<n;i++) { for (int j=0;j<n;j++) { x++; } }"
    braceless = "for (int i=0;i<n;i++)\n    for (int j=0;j<n;j++)\n        x++;"
    sequential = "for (int i=0;i<n;i++) { x++; }\nfor (int j=0;j<n;j++) { y++; }"
    assert analyze(braces).max_loop_depth == 2
    assert analyze(braceless).max_loop_depth == 2
    assert analyze(sequential).max_loop_depth == 1


def test_loops_inside_comments_and_strings_are_ignored():
    code = '// for (int i...) { for (...) { } }\nString s = "while (true) { for (;;) {} }";\nint x = 1;'
    assert analyze(code).max_loop_depth == 0
    stripped = strip_comments_and_literals(code)
    assert stripped.count("\n") == code.count("\n")  # line numbers preserved


def test_unguarded_first_element():
    a = analyze("int max(int[] nums) { int best = nums[0]; return best; }", signature=SIG)
    finding = next(f for f in a.findings if f.category == "edge-case")
    assert "nums" in finding.detail and finding.line == 1


def test_guarded_first_element_is_fine():
    a = analyze("int max(int[] nums) { if (nums.length == 0) throw new X(); return nums[0]; }", signature=SIG)
    assert "edge-case" not in cats(a)


def test_string_concat_in_loop_and_overflow_and_legacy_stack():
    code = """String reverse(String s) {
    String out = "";
    for (int i = s.length() - 1; i >= 0; i--) { out += s.charAt(i); }
    int mid = (low + high) / 2;
    Stack<Integer> st = new Stack<>();
    return out;
}"""
    a = analyze(code)
    details = " ".join(f.detail for f in a.findings)
    assert "copies the whole string" in details
    assert "overflow" in details
    assert "legacy" in details


def test_sort_estimates_n_log_n():
    a = analyze(
        "boolean f(int[] nums) { Arrays.sort(nums); for (int i=1;i<nums.length;i++) {} return false; }",
        expected_time="O(n)",
    )
    assert a.estimated_time == "O(n log n)" and "complexity" in cats(a)


def test_unchanged_starter_short_circuits():
    starter = "class Solution {\n  public int max(int[] nums) {\n    return 0;\n  }\n}\n"
    a = analyze("class Solution { public int max(int[] nums) { return 0; } }", starter_code=starter)
    assert a.is_unchanged_starter and a.findings[0].severity == "high"


def test_empty_catch_and_single_letter_names():
    a = analyze("void f() { try { g(); } catch (Exception e) { } int q = 3; }")
    assert "correctness" in cats(a) and "readability" in cats(a)


def test_recursion_detected():
    sig = {"method": "climbStairs", "params": [{"name": "n", "type": "int"}], "returns": "int"}
    a = analyze(
        "int climbStairs(int n) { if (n <= 2) return n; return climbStairs(n-1) + climbStairs(n-2); }",
        signature=sig,
    )
    assert a.has_recursion and "recursion" in a.estimated_time


def test_constant_size_allocations_are_not_linear_space():
    assert analyze("int[] f() { return new int[0]; }").estimated_space == "O(1)"
    assert analyze("int[] f() { return new int[] {1, 2}; }").estimated_space == "O(1)"
    assert analyze("int[] f(int n) { return new int[n]; }").estimated_space == "O(n)"
    assert analyze("int[] f(int[] a) { return new int[a.length + 1]; }").estimated_space == "O(n)"
