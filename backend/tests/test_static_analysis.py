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
    assert a.has_recursion and a.exponential_recursion and a.estimated_time == "O(2^n)"


def test_constant_size_allocations_are_not_linear_space():
    assert analyze("int[] f() { return new int[0]; }").estimated_space == "O(1)"
    assert analyze("int[] f() { return new int[] {1, 2}; }").estimated_space == "O(1)"
    assert analyze("int[] f(int n) { return new int[n]; }").estimated_space == "O(n)"
    assert analyze("int[] f(int[] a) { return new int[a.length + 1]; }").estimated_space == "O(n)"


# --- rules added after the first evaluation run (evals/results/offline-baseline.md) ----------


def test_two_pointer_inner_whiles_are_one_pass():
    code = """boolean f(String s) { int left = 0, right = s.length() - 1;
        while (left < right) {
            while (left < right && s.charAt(left) == ' ') left++;
            while (left < right && s.charAt(right) == ' ') right--;
            left++; right--;
        } return true; }"""
    assert analyze(code).max_loop_depth == 1
    # A genuinely nested loop with a different condition still counts.
    nested = "for (int i = 0; i < n; i++) { while (j < i) { j++; } }"
    assert analyze(nested).max_loop_depth == 2


def test_constraints_that_guarantee_non_empty_input_suppress_the_guard_warning():
    code = "int f(int[] nums) { int best = nums[0]; return best; }"
    assert "edge-case" in cats(analyze(code, signature=SIG))
    assert "edge-case" not in cats(analyze(code, signature=SIG, constraints=["1 <= nums.length <= 10^5"]))


def test_halving_loop_is_logarithmic_and_linear_scan_is_flagged_when_log_n_is_required():
    bsearch = "int f(int[] a, int t) { int lo = 0, hi = a.length - 1; while (lo <= hi) { int mid = lo + (hi - lo) / 2; lo = mid + 1; } return -1; }"
    assert analyze(bsearch, expected_time="O(log n)").estimated_time == "O(log n)"
    assert "complexity" not in cats(analyze(bsearch, expected_time="O(log n)"))
    scan = "int f(int[] a, int t) { for (int i = 0; i < a.length; i++) if (a[i] == t) return i; return -1; }"
    assert "complexity" in cats(analyze(scan, expected_time="O(log n)"))


def test_sorting_is_flagged_against_linear_targets_like_n_plus_m():
    code = "int[] f(int[] a, int[] b) { int[] r = new int[a.length + b.length]; Arrays.sort(r); return r; }"
    assert "complexity" in cats(analyze(code, expected_time="O(n + m)"))
    assert "complexity" not in cats(analyze(code, expected_time="O(n log n)"))


def test_memoised_or_single_branch_recursion_is_not_exponential():
    sig = {"method": "climbStairs", "params": [{"name": "n", "type": "int"}], "returns": "int"}
    memo = "int climbStairs(int n) { if (memo[n] != 0) return memo[n]; return memo[n] = climbStairs(n-1) + climbStairs(n-2); }"
    assert not analyze(memo, signature=sig).exponential_recursion
    single = "int climbStairs(int n) { if (n <= 2) return n; return 1 + climbStairs(n - 1); }"
    assert not analyze(single, signature=sig).exponential_recursion


def test_a_method_call_with_the_same_name_is_not_recursion():
    """Regression found by the eval: `sb.reverse()` inside a method named reverse."""
    sig = {"method": "reverse", "params": [{"name": "s", "type": "String"}], "returns": "String"}
    a = analyze(
        "String reverse(String s) { return new StringBuilder(s).reverse().toString(); }", signature=sig
    )
    assert not a.has_recursion and a.estimated_time == "O(1)"
