"""Hard problems, part 1: arrays, strings and dynamic programming."""

from collections import Counter
from functools import lru_cache
from itertools import combinations

from scripts.problembank import P, ints, word


def _interleave_case(r):
    a, b = word(r, 0, 5, "ab"), word(r, 0, 5, "ab")
    if r.random() < 0.4:
        return {"s1": a, "s2": b, "s3": "".join(r.sample(a + b, len(a + b)))}
    out, i, j = [], 0, 0
    while i < len(a) or j < len(b):
        if j == len(b) or (i < len(a) and r.random() < 0.5):
            out.append(a[i])
            i += 1
        else:
            out.append(b[j])
            j += 1
    return {"s1": a, "s2": b, "s3": "".join(out)}


def _min_window(s, t):
    need = Counter(t)
    best = ""
    for i in range(len(s)):
        for j in range(i + 1, len(s) + 1):
            if not need - Counter(s[i:j]):
                if not best or j - i < len(best):
                    best = s[i:j]
                break
    return best


P(
    slug="trapping-rain-water",
    title="Trapping Rain Water",
    difficulty="hard",
    topics=["arrays", "two-pointers", "stacks"],
    summary="How much rain water collects between bars of an elevation map?",
    statement="""
        `height[i]` is the height of a bar of width 1. After it rains, water collects in the dips. Return the
        total units of trapped water.
    """,
    constraints=["0 <= height.length <= 2 * 10^4", "0 <= height[i] <= 10^5"],
    sig="int trap(int[] height)",
    hints=[
        "How much water sits above a single bar?",
        "Water above bar `i` = min(tallest bar to its left, tallest to its right) - height[i]. Two pointers can track both maxima in one pass.",
        "l, r = 0, n-1\nleftMax = rightMax = water = 0\nwhile l < r:\n    if height[l] < height[r]:\n        leftMax = max(leftMax, height[l]); water += leftMax - height[l]; l += 1\n"
        "    else:\n        rightMax = max(rightMax, height[r]); water += rightMax - height[r]; r -= 1\nreturn water",
        "Always move the side with the lower bar: its water level is fixed by its own max, because the other side is already at least that tall. O(n) time, O(1) space.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda height: sum(
        max(0, min(max(height[: i + 1]), max(height[i:])) - height[i]) for i in range(len(height))
    ),
    java="""
        class Solution {
            public int trap(int[] height) {
                int l = 0, r = height.length - 1, leftMax = 0, rightMax = 0, water = 0;
                while (l < r) {
                    if (height[l] < height[r]) { leftMax = Math.max(leftMax, height[l]); water += leftMax - height[l++]; }
                    else { rightMax = Math.max(rightMax, height[r]); water += rightMax - height[r--]; }
                }
                return water;
            }
        }
    """,
    tests=[
        {"height": [0, 1, 0, 2, 1, 0, 1, 3, 2, 1, 2, 1]},
        {"height": [4, 2, 0, 3, 2, 5]},
        {"height": []},
        {"height": [3, 0, 0, 3]},
    ],
    gen=lambda r: {"height": ints(r, 0, 20, 0, 8)},
)

P(
    slug="largest-rectangle-histogram",
    title="Largest Rectangle in a Histogram",
    difficulty="hard",
    topics=["stacks", "arrays"],
    summary="Biggest rectangle that fits under a bar chart.",
    statement="""
        `heights[i]` is the height of a bar of width 1. Return the area of the largest rectangle that fits
        entirely under the bars.
    """,
    constraints=["1 <= heights.length <= 10^5", "0 <= heights[i] <= 10^4"],
    sig="int largestRectangleArea(int[] heights)",
    hints=[
        "For each bar, imagine the widest rectangle that uses that bar's height.",
        "It extends left and right until a shorter bar. A stack of increasing heights finds both boundaries.",
        "stack = []\nbest = 0\nfor i in 0..n (treat heights[n] as 0):\n    while stack and heights[stack[-1]] > h:\n"
        "        top = stack.pop()\n        left = stack[-1] + 1 if stack else 0\n        best = max(best, heights[top] * (i - left))\n    stack.append(i)\nreturn best",
        "When a bar is popped, the current index is its right boundary and the new stack top is its left boundary. Each bar is pushed and popped once: O(n).",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda heights: max(
        min(heights[i : j + 1]) * (j - i + 1) for i in range(len(heights)) for j in range(i, len(heights))
    ),
    java="""
        import java.util.*;

        class Solution {
            public int largestRectangleArea(int[] heights) {
                Deque<Integer> stack = new ArrayDeque<>();
                int best = 0, n = heights.length;
                for (int i = 0; i <= n; i++) {
                    int h = i == n ? 0 : heights[i];
                    while (!stack.isEmpty() && heights[stack.peek()] > h) {
                        int top = stack.pop();
                        int left = stack.isEmpty() ? 0 : stack.peek() + 1;
                        best = Math.max(best, heights[top] * (i - left));
                    }
                    stack.push(i);
                }
                return best;
            }
        }
    """,
    tests=[{"heights": [2, 1, 5, 6, 2, 3]}, {"heights": [2, 4]}, {"heights": [0]}, {"heights": [3, 3, 3]}],
    gen=lambda r: {"heights": ints(r, 1, 15, 0, 9)},
)

P(
    slug="sliding-window-maximum",
    title="Sliding Window Maximum",
    difficulty="hard",
    topics=["sliding-window", "queues", "arrays"],
    summary="The maximum of every window of size k.",
    statement="""
        Return the maximum of each contiguous window of size `k` as it slides from the left of `nums` to the right.
    """,
    constraints=["1 <= k <= nums.length <= 10^5"],
    sig="int[] maxSlidingWindow(int[] nums, int k)",
    hints=[
        "Recomputing each window's max is O(n k). Which values can never be a future maximum?",
        "A value is useless once a larger value arrives after it. Keep a deque of indices with decreasing values.",
        "dq = deque()\nfor i, x in enumerate(nums):\n    if dq and dq[0] <= i - k: dq.popleft()\n    while dq and nums[dq[-1]] <= x: dq.pop()\n"
        "    dq.append(i)\n    if i >= k - 1: out.append(nums[dq[0]])\nreturn out",
        "The deque front is always the window's maximum, and each index enters and leaves once: O(n).",
    ],
    time="O(n)",
    space="O(k)",
    model=lambda nums, k: [max(nums[i : i + k]) for i in range(len(nums) - k + 1)],
    java="""
        import java.util.*;

        class Solution {
            public int[] maxSlidingWindow(int[] nums, int k) {
                int[] out = new int[nums.length - k + 1];
                Deque<Integer> dq = new ArrayDeque<>();
                for (int i = 0; i < nums.length; i++) {
                    if (!dq.isEmpty() && dq.peekFirst() <= i - k) dq.pollFirst();
                    while (!dq.isEmpty() && nums[dq.peekLast()] <= nums[i]) dq.pollLast();
                    dq.addLast(i);
                    if (i >= k - 1) out[i - k + 1] = nums[dq.peekFirst()];
                }
                return out;
            }
        }
    """,
    tests=[{"nums": [1, 3, -1, -3, 5, 3, 6, 7], "k": 3}, {"nums": [1], "k": 1}, {"nums": [9, 8, 7], "k": 2}],
    gen=lambda r: (lambda nums: {"nums": nums, "k": r.randint(1, len(nums))})(ints(r, 1, 15, -9, 9)),
)

P(
    slug="minimum-window-substring",
    title="Minimum Window Substring",
    difficulty="hard",
    topics=["strings", "sliding-window", "hash-maps"],
    summary="Shortest substring of s containing every character of t.",
    statement="""
        Return the shortest substring of `s` that contains every character of `t` (with multiplicity: if `t`
        has two `a`s, the window needs two). If several are equally short, return the leftmost. If none exists,
        return `""`.
    """,
    constraints=["1 <= s.length, t.length <= 10^5", "English letters"],
    sig="String minWindow(String s, String t)",
    hints=[
        "Grow a window until it covers t, then shrink it as much as possible.",
        "Track how many required characters are still missing. Shrink from the left while the window stays valid.",
        "need = counts(t); missing = len(t)\nleft = 0\nfor right, c in enumerate(s):\n    if need[c] > 0: missing -= 1\n    need[c] -= 1\n"
        "    while missing == 0:\n        record window if shorter\n        need[s[left]] += 1\n        if need[s[left]] > 0: missing += 1\n        left += 1\nreturn best",
        "Each index enters and leaves the window once: O(|s| + |t|). Only replacing on a strictly shorter window keeps the leftmost one.",
    ],
    time="O(n + m)",
    space="O(1)",
    model=_min_window,
    java="""
        class Solution {
            public String minWindow(String s, String t) {
                int[] need = new int[128];
                for (char c : t.toCharArray()) need[c]++;
                int missing = t.length(), left = 0, bestStart = 0, bestLen = Integer.MAX_VALUE;
                for (int right = 0; right < s.length(); right++) {
                    if (need[s.charAt(right)]-- > 0) missing--;
                    while (missing == 0) {
                        if (right - left + 1 < bestLen) { bestLen = right - left + 1; bestStart = left; }
                        if (++need[s.charAt(left++)] > 0) missing++;
                    }
                }
                return bestLen == Integer.MAX_VALUE ? "" : s.substring(bestStart, bestStart + bestLen);
            }
        }
    """,
    tests=[
        {"s": "ADOBECODEBANC", "t": "ABC"},
        {"s": "a", "t": "a"},
        {"s": "a", "t": "aa"},
        {"s": "abab", "t": "ab"},
    ],
    gen=lambda r: {"s": word(r, 1, 14, "abc"), "t": word(r, 1, 3, "abc")},
)

P(
    slug="edit-distance",
    title="Edit Distance",
    difficulty="hard",
    topics=["dynamic-programming", "strings"],
    summary="Fewest inserts, deletes and replacements to turn one word into another.",
    statement="""
        Return the minimum number of single-character insertions, deletions and replacements needed to turn
        `a` into `b`.
    """,
    constraints=["0 <= a.length, b.length <= 500", "lower-case letters"],
    sig="int minDistance(String a, String b)",
    hints=[
        "Compare the last characters of the two prefixes.",
        "If they match, no cost; otherwise take 1 + the best of insert, delete or replace.",
        "dp[i][0] = i; dp[0][j] = j\nfor i, j:\n    if a[i-1] == b[j-1]: dp[i][j] = dp[i-1][j-1]\n"
        "    else: dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])\nreturn dp[n][m]",
        "O(n m) time; keeping two rows makes it O(m) space. Delete = up, insert = left, replace = diagonal.",
    ],
    time="O(n m)",
    space="O(n m)",
    model=lambda a, b: (lambda f: f(f, 0, 0))(
        lru_cache(None)(
            lambda f, i, j: (
                len(b) - j
                if i == len(a)
                else len(a) - i
                if j == len(b)
                else (
                    f(f, i + 1, j + 1)
                    if a[i] == b[j]
                    else 1 + min(f(f, i + 1, j), f(f, i, j + 1), f(f, i + 1, j + 1))
                )
            )
        )
    ),
    java="""
        class Solution {
            public int minDistance(String a, String b) {
                int n = a.length(), m = b.length();
                int[][] dp = new int[n + 1][m + 1];
                for (int i = 0; i <= n; i++) dp[i][0] = i;
                for (int j = 0; j <= m; j++) dp[0][j] = j;
                for (int i = 1; i <= n; i++)
                    for (int j = 1; j <= m; j++)
                        dp[i][j] = a.charAt(i - 1) == b.charAt(j - 1) ? dp[i - 1][j - 1]
                            : 1 + Math.min(dp[i - 1][j - 1], Math.min(dp[i - 1][j], dp[i][j - 1]));
                return dp[n][m];
            }
        }
    """,
    tests=[
        {"a": "horse", "b": "ros"},
        {"a": "intention", "b": "execution"},
        {"a": "", "b": "abc"},
        {"a": "same", "b": "same"},
    ],
    gen=lambda r: {"a": word(r, 0, 8, "abc"), "b": word(r, 0, 8, "abc")},
)

P(
    slug="regex-matching",
    title="Regular Expression Matching",
    difficulty="hard",
    topics=["dynamic-programming", "strings", "recursion"],
    summary="Match a string against a pattern with . and *.",
    statement="""
        Return `true` if pattern `p` matches all of `s`. In `p`, `.` matches any single character and `*` means
        zero or more of the element right before it. Every `*` follows a letter or `.`.
    """,
    constraints=["1 <= s.length <= 20", "1 <= p.length <= 20", "s: lower-case letters; p: letters, '.', '*'"],
    sig="boolean isMatch(String s, String p)",
    hints=[
        "Look at the first character match, and whether the next pattern character is a `*`.",
        "With a star, either skip `x*` entirely, or (if the first character matches) consume one character of `s` and keep the star.",
        "def match(i, j):\n    if j == len(p): return i == len(s)\n    first = i < len(s) and p[j] in (s[i], '.')\n"
        "    if j + 1 < len(p) and p[j+1] == '*':\n        return match(i, j + 2) or (first and match(i + 1, j))\n    return first and match(i + 1, j + 1)",
        "Memoizing on (i, j) makes it O(n m). Without memoization the recursion is exponential.",
    ],
    time="O(n m)",
    space="O(n m)",
    model=lambda s, p: __import__("re").fullmatch(p, s) is not None,
    java="""
        class Solution {
            public boolean isMatch(String s, String p) {
                int n = s.length(), m = p.length();
                boolean[][] dp = new boolean[n + 1][m + 1];
                dp[n][m] = true;
                for (int i = n; i >= 0; i--)
                    for (int j = m - 1; j >= 0; j--) {
                        boolean first = i < n && (p.charAt(j) == s.charAt(i) || p.charAt(j) == '.');
                        if (j + 1 < m && p.charAt(j + 1) == '*') dp[i][j] = dp[i][j + 2] || (first && dp[i + 1][j]);
                        else dp[i][j] = first && dp[i + 1][j + 1];
                    }
                return dp[0][0];
            }
        }
    """,
    tests=[
        {"s": "aa", "p": "a"},
        {"s": "aa", "p": "a*"},
        {"s": "ab", "p": ".*"},
        {"s": "aab", "p": "c*a*b"},
        {"s": "mississippi", "p": "mis*is*p*."},
        {"s": "ab", "p": ".*c"},
    ],
    gen=lambda r: {
        "s": word(r, 1, 6, "ab"),
        "p": "".join(r.choice(["a", "b", ".", "a*", "b*", ".*"]) for _ in range(r.randint(1, 4))),
    },
)

P(
    slug="wildcard-matching",
    title="Wildcard Matching",
    difficulty="hard",
    topics=["dynamic-programming", "greedy", "strings"],
    summary="Match a string against a pattern with ? and *.",
    statement="""
        Return `true` if pattern `p` matches all of `s`. `?` matches any single character and `*` matches any
        sequence of characters (including none).
    """,
    constraints=["0 <= s.length, p.length <= 2000", "s: lower-case letters; p: letters, '?', '*'"],
    sig="boolean isMatchWildcard(String s, String p)",
    hints=[
        "A `*` can absorb nothing or one more character.",
        "dp[i][j] = s[:i] matches p[:j]. For `*`: dp[i][j-1] (empty) or dp[i-1][j] (absorb one more).",
        "dp[0][0] = true; dp[0][j] = dp[0][j-1] when p[j-1] == '*'\nfor i, j:\n    if p[j-1] == '*': dp[i][j] = dp[i][j-1] or dp[i-1][j]\n"
        "    elif p[j-1] in (s[i-1], '?'): dp[i][j] = dp[i-1][j-1]\nreturn dp[n][m]",
        "O(n m) DP. A greedy two-pointer method that remembers the last `*` also runs in O(n m) worst case with O(1) space.",
    ],
    time="O(n m)",
    space="O(n m)",
    model=lambda s, p: __import__("fnmatch").fnmatchcase(s, p.replace("[", "[[]")),
    java="""
        class Solution {
            public boolean isMatchWildcard(String s, String p) {
                int n = s.length(), m = p.length();
                boolean[][] dp = new boolean[n + 1][m + 1];
                dp[0][0] = true;
                for (int j = 1; j <= m; j++) dp[0][j] = dp[0][j - 1] && p.charAt(j - 1) == '*';
                for (int i = 1; i <= n; i++)
                    for (int j = 1; j <= m; j++) {
                        char c = p.charAt(j - 1);
                        if (c == '*') dp[i][j] = dp[i][j - 1] || dp[i - 1][j];
                        else if (c == '?' || c == s.charAt(i - 1)) dp[i][j] = dp[i - 1][j - 1];
                    }
                return dp[n][m];
            }
        }
    """,
    tests=[
        {"s": "aa", "p": "a"},
        {"s": "aa", "p": "*"},
        {"s": "cb", "p": "?a"},
        {"s": "adceb", "p": "*a*b"},
        {"s": "acdcb", "p": "a*c?b"},
        {"s": "", "p": "***"},
    ],
    gen=lambda r: {"s": word(r, 0, 7, "ab"), "p": word(r, 0, 5, "ab?*")},
)

P(
    slug="longest-valid-parentheses",
    title="Longest Valid Parentheses",
    difficulty="hard",
    topics=["stacks", "dynamic-programming", "strings"],
    summary="Length of the longest well-formed parentheses substring.",
    statement="""
        `s` contains only `(` and `)`. Return the length of the longest contiguous substring that is a
        well-formed (balanced) parentheses string.
    """,
    constraints=["0 <= s.length <= 3 * 10^4"],
    sig="int longestValidParentheses(String s)",
    hints=[
        "An unmatched `)` splits the string into independent parts.",
        "Keep a stack of indices, starting with -1 as a base. On `)`, pop; if the stack is empty, push this index as the new base; otherwise the valid run is `i - top`.",
        "stack = [-1]\nbest = 0\nfor i, c in enumerate(s):\n    if c == '(': stack.append(i)\n    else:\n        stack.pop()\n"
        "        if not stack: stack.append(i)\n        else: best = max(best, i - stack[-1])\nreturn best",
        "The stack bottom always marks the last position a valid run can't cross. O(n) time and space.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda s: max(
        [0]
        + [
            j - i
            for i in range(len(s))
            for j in range(i + 2, len(s) + 1, 2)
            if all(s[i:k].count("(") >= s[i:k].count(")") for k in range(i, j + 1))
            and s[i:j].count("(") * 2 == j - i
        ]
    ),
    java="""
        import java.util.*;

        class Solution {
            public int longestValidParentheses(String s) {
                Deque<Integer> stack = new ArrayDeque<>();
                stack.push(-1);
                int best = 0;
                for (int i = 0; i < s.length(); i++) {
                    if (s.charAt(i) == '(') stack.push(i);
                    else {
                        stack.pop();
                        if (stack.isEmpty()) stack.push(i);
                        else best = Math.max(best, i - stack.peek());
                    }
                }
                return best;
            }
        }
    """,
    tests=[{"s": "(()"}, {"s": ")()())"}, {"s": ""}, {"s": "()(())"}, {"s": "(()(((()"}],
    gen=lambda r: {"s": word(r, 0, 14, "()")},
)

P(
    slug="burst-balloons",
    title="Burst Balloons",
    difficulty="hard",
    topics=["dynamic-programming"],
    summary="Order balloon bursts to collect the most coins.",
    statement="""
        Bursting balloon `i` earns `nums[left] * nums[i] * nums[right]`, where `left` and `right` are its current
        neighbors (treat missing neighbors as 1). The balloon then disappears. Return the most coins you can collect
        by bursting them all.
    """,
    constraints=["1 <= nums.length <= 300", "0 <= nums[i] <= 100"],
    sig="int maxCoins(int[] nums)",
    hints=[
        "Choosing the first balloon to burst changes everyone's neighbors. What if you choose the last one instead?",
        "If balloon `k` is the last in the open interval (i, j), its neighbors are exactly `i` and `j`. Split into two independent intervals.",
        "pad nums with 1 at both ends\nfor length from 2 upward:\n    for i, j = i + length:\n        dp[i][j] = max over k in (i, j) of dp[i][k] + v[i]*v[k]*v[j] + dp[k][j]\nreturn dp[0][n+1]",
        "Interval DP over O(n^2) intervals with O(n) choices each: O(n^3).",
    ],
    time="O(n^3)",
    space="O(n^2)",
    model=lambda nums: (lambda f: f(f, tuple(nums)))(
        lru_cache(None)(
            lambda f, t: (
                0
                if not t
                else max(
                    (t[i - 1] if i > 0 else 1) * t[i] * (t[i + 1] if i + 1 < len(t) else 1)
                    + f(f, t[:i] + t[i + 1 :])
                    for i in range(len(t))
                )
            )
        )
    ),
    java="""
        class Solution {
            public int maxCoins(int[] nums) {
                int n = nums.length;
                int[] v = new int[n + 2];
                v[0] = v[n + 1] = 1;
                for (int i = 0; i < n; i++) v[i + 1] = nums[i];
                int[][] dp = new int[n + 2][n + 2];
                for (int len = 2; len <= n + 1; len++)
                    for (int i = 0; i + len <= n + 1; i++) {
                        int j = i + len;
                        for (int k = i + 1; k < j; k++) dp[i][j] = Math.max(dp[i][j], dp[i][k] + v[i] * v[k] * v[j] + dp[k][j]);
                    }
                return dp[0][n + 1];
            }
        }
    """,
    tests=[{"nums": [3, 1, 5, 8]}, {"nums": [1, 5]}, {"nums": [7]}, {"nums": [0, 2, 0]}],
    gen=lambda r: {"nums": ints(r, 1, 7, 0, 9)},
    explain={0: "Burst 1, 5, 3, 8: 3*1*5 + 3*5*8 + 1*3*8 + 1*8*1 = 167."},
)

P(
    slug="distinct-subsequences",
    title="Distinct Subsequences",
    difficulty="hard",
    topics=["dynamic-programming", "strings"],
    summary="Count the ways a string appears as a subsequence of another.",
    statement="""
        Return how many distinct subsequences of `s` equal `t` (different sets of positions count separately).
        The answer fits in an int.
    """,
    constraints=["1 <= s.length, t.length <= 1000", "English letters"],
    sig="int numDistinct(String s, String t)",
    hints=[
        "Each character of `s` can either be used to match the next character of `t` or skipped.",
        "ways[j] = number of ways to form `t[:j]` so far. Process `s` left to right and update `j` from right to left.",
        "ways = [1] + [0]*m\nfor c in s:\n    for j from m down to 1:\n        if t[j-1] == c: ways[j] += ways[j-1]\nreturn ways[m]",
        "O(n m) time with one array; iterating `j` backwards stops one character of `s` from being used twice.",
    ],
    time="O(n m)",
    space="O(m)",
    model=lambda s, t: sum(
        1 for idx in combinations(range(len(s)), len(t)) if "".join(s[i] for i in idx) == t
    ),
    java="""
        class Solution {
            public int numDistinct(String s, String t) {
                int m = t.length();
                long[] ways = new long[m + 1];
                ways[0] = 1;
                for (char c : s.toCharArray())
                    for (int j = m; j >= 1; j--) if (t.charAt(j - 1) == c) ways[j] += ways[j - 1];
                return (int) ways[m];
            }
        }
    """,
    tests=[
        {"s": "rabbbit", "t": "rabbit"},
        {"s": "babgbag", "t": "bag"},
        {"s": "abc", "t": "abcd"},
        {"s": "aaaa", "t": "aa"},
    ],
    gen=lambda r: {"s": word(r, 1, 12, "ab"), "t": word(r, 1, 3, "ab")},
)

P(
    slug="interleaving-string",
    title="Interleaving Strings",
    difficulty="hard",
    topics=["dynamic-programming", "strings"],
    summary="Is s3 a merge of s1 and s2 that keeps each one's order?",
    statement="""
        Return `true` if `s3` can be formed by interleaving `s1` and `s2`: every character of both is used once,
        and each string's characters keep their relative order.
    """,
    constraints=["0 <= s1.length, s2.length <= 100", "lower-case letters"],
    sig="boolean isInterleave(String s1, String s2, String s3)",
    hints=[
        "After using `i` characters of s1 and `j` of s2, the next character of s3 is `s3[i + j]`.",
        "ok[i][j] = (ok[i-1][j] and s1[i-1] == s3[i+j-1]) or (ok[i][j-1] and s2[j-1] == s3[i+j-1]).",
        "if len(s1) + len(s2) != len(s3): return false\nok[0][0] = true\nfor i, j: ok[i][j] = (from above and s1 char matches) or (from left and s2 char matches)\nreturn ok[n][m]",
        "O(n m) time, O(m) with one row. Checking lengths first avoids index errors and quick wrong answers.",
    ],
    time="O(n m)",
    space="O(m)",
    model=lambda s1, s2, s3: (
        len(s1) + len(s2) == len(s3)
        and (lambda f: f(f, 0, 0))(
            lru_cache(None)(
                lambda f, i, j: (
                    i + j == len(s3)
                    or (
                        (i < len(s1) and s1[i] == s3[i + j] and f(f, i + 1, j))
                        or (j < len(s2) and s2[j] == s3[i + j] and f(f, i, j + 1))
                    )
                )
            )
        )
    ),
    java="""
        class Solution {
            public boolean isInterleave(String s1, String s2, String s3) {
                int n = s1.length(), m = s2.length();
                if (n + m != s3.length()) return false;
                boolean[] ok = new boolean[m + 1];
                for (int i = 0; i <= n; i++)
                    for (int j = 0; j <= m; j++) {
                        if (i == 0 && j == 0) { ok[0] = true; continue; }
                        boolean fromTop = i > 0 && ok[j] && s1.charAt(i - 1) == s3.charAt(i + j - 1);
                        boolean fromLeft = j > 0 && ok[j - 1] && s2.charAt(j - 1) == s3.charAt(i + j - 1);
                        ok[j] = fromTop || fromLeft;
                    }
                return ok[m];
            }
        }
    """,
    tests=[
        {"s1": "aabcc", "s2": "dbbca", "s3": "aadbbcbcac"},
        {"s1": "aabcc", "s2": "dbbca", "s3": "aadbbbaccc"},
        {"s1": "", "s2": "", "s3": ""},
        {"s1": "a", "s2": "", "s3": "c"},
    ],
    gen=lambda r: _interleave_case(r),
)

P(
    slug="palindrome-min-cuts",
    title="Fewest Cuts for Palindrome Pieces",
    difficulty="hard",
    topics=["dynamic-programming", "strings"],
    summary="Cut a string into palindromes using as few cuts as possible.",
    statement="""
        Return the minimum number of cuts needed to split `s` so that every piece is a palindrome.
    """,
    constraints=["1 <= s.length <= 2000", "lower-case letters"],
    sig="int minCut(String s)",
    hints=[
        "If you know the fewest cuts for every prefix, can you extend to a longer prefix?",
        "cuts[i] = min over palindromic `s[j..i]` of cuts[j-1] + 1 (or 0 if j == 0). Precompute which substrings are palindromes.",
        "pal[j][i] = s[j] == s[i] and (i - j < 2 or pal[j+1][i-1])\nfor i in range(n):\n    cuts[i] = min(0 if j == 0 else cuts[j-1] + 1 for j with pal[j][i])\nreturn cuts[n-1]",
        "O(n^2) time and space. Expanding around centers can fill the cuts array without the n×n table.",
    ],
    time="O(n^2)",
    space="O(n^2)",
    model=lambda s: (lambda f: f(f, 0))(
        lru_cache(None)(
            lambda f, i: (
                -1
                if i == len(s)
                else min(1 + f(f, j) for j in range(i + 1, len(s) + 1) if s[i:j] == s[i:j][::-1])
            )
        )
    ),
    java="""
        class Solution {
            public int minCut(String s) {
                int n = s.length();
                boolean[][] pal = new boolean[n][n];
                int[] cuts = new int[n];
                for (int i = 0; i < n; i++) {
                    cuts[i] = i;
                    for (int j = 0; j <= i; j++)
                        if (s.charAt(j) == s.charAt(i) && (i - j < 2 || pal[j + 1][i - 1])) {
                            pal[j][i] = true;
                            cuts[i] = Math.min(cuts[i], j == 0 ? 0 : cuts[j - 1] + 1);
                        }
                }
                return cuts[n - 1];
            }
        }
    """,
    tests=[{"s": "aab"}, {"s": "a"}, {"s": "ab"}, {"s": "racecarxyz"}],
    gen=lambda r: {"s": word(r, 1, 12, "ab")},
)

P(
    slug="shortest-palindrome",
    title="Shortest Palindrome by Adding to the Front",
    difficulty="hard",
    topics=["strings"],
    summary="Add the fewest characters in front to make a palindrome.",
    statement="""
        Return the shortest palindrome you can make by adding characters only to the front of `s`.
    """,
    constraints=["0 <= s.length <= 5 * 10^4", "lower-case letters"],
    sig="String shortestPalindrome(String s)",
    hints=[
        "What part of `s` can you keep as the middle of the palindrome?",
        "Find the longest prefix of `s` that is a palindrome; reverse the rest and put it in front.",
        "longest palindromic prefix length L = KMP failure value of (s + '#' + reverse(s)) at the end\nreturn reverse(s[L:]) + s",
        "Checking each prefix naively is O(n^2). The KMP prefix function on `s + '#' + reversed(s)` finds the longest palindromic prefix in O(n).",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda s: next(s[k:][::-1] + s for k in range(len(s), -1, -1) if s[:k] == s[:k][::-1]),
    java="""
        class Solution {
            public String shortestPalindrome(String s) {
                String rev = new StringBuilder(s).reverse().toString();
                String t = s + "#" + rev;
                int[] fail = new int[t.length()];
                for (int i = 1; i < t.length(); i++) {
                    int k = fail[i - 1];
                    while (k > 0 && t.charAt(i) != t.charAt(k)) k = fail[k - 1];
                    if (t.charAt(i) == t.charAt(k)) k++;
                    fail[i] = k;
                }
                int keep = fail[t.length() - 1];
                return rev.substring(0, s.length() - keep) + s;
            }
        }
    """,
    tests=[{"s": "aacecaaa"}, {"s": "abcd"}, {"s": ""}, {"s": "aba"}],
    gen=lambda r: {"s": word(r, 0, 10, "ab")},
)

P(
    slug="count-smaller-after-self",
    title="Count Smaller Numbers to the Right",
    difficulty="hard",
    topics=["arrays", "sorting", "binary-search"],
    summary="For each value, how many later values are smaller?",
    statement="""
        Return an array `counts` where `counts[i]` is how many values to the right of `nums[i]` are strictly smaller than it.
    """,
    constraints=["1 <= nums.length <= 10^5", "-10^4 <= nums[i] <= 10^4"],
    sig="int[] countSmaller(int[] nums)",
    hints=[
        'Checking every pair is O(n^2). Which data structure answers "how many seen values are smaller than x?" quickly?',
        "Scan from the right, inserting values into a Fenwick tree (binary indexed tree) over the value range and querying the prefix count before inserting.",
        "for i from n-1 down to 0:\n    counts[i] = bit.prefixSum(index(nums[i]) - 1)\n    bit.add(index(nums[i]), 1)\nreturn counts",
        "Each query and update is O(log V): O(n log V) total. Merge sort that counts moves during merging also gives O(n log n).",
    ],
    time="O(n log n)",
    space="O(n)",
    model=lambda nums: [sum(1 for y in nums[i + 1 :] if y < x) for i, x in enumerate(nums)],
    java="""
        class Solution {
            public int[] countSmaller(int[] nums) {
                int offset = 10001, size = 20003;
                int[] tree = new int[size + 1], counts = new int[nums.length];
                for (int i = nums.length - 1; i >= 0; i--) {
                    int idx = nums[i] + offset;
                    int c = 0;
                    for (int k = idx - 1; k > 0; k -= k & -k) c += tree[k];
                    counts[i] = c;
                    for (int k = idx; k <= size; k += k & -k) tree[k]++;
                }
                return counts;
            }
        }
    """,
    tests=[{"nums": [5, 2, 6, 1]}, {"nums": [-1]}, {"nums": [-1, -1]}, {"nums": [10000, -10000, 0]}],
    gen=lambda r: {"nums": ints(r, 1, 15, -10, 10)},
)

P(
    slug="reverse-pairs",
    title="Count Reverse Pairs",
    difficulty="hard",
    topics=["arrays", "sorting"],
    summary="Count pairs where an earlier value is more than double a later one.",
    statement="""
        Return the number of pairs `(i, j)` with `i < j` and `nums[i] > 2 * nums[j]`.
    """,
    constraints=["1 <= nums.length <= 5 * 10^4", "-2^31 <= nums[i] <= 2^31 - 1"],
    sig="int reversePairs(int[] nums)",
    hints=[
        "This is like counting inversions with a twist.",
        "Merge sort: before merging two sorted halves, count pairs between them with two pointers, then merge as usual.",
        "def sort(lo, hi):\n    if hi - lo <= 1: return 0\n    mid = (lo + hi) // 2\n    count = sort(lo, mid) + sort(mid, hi)\n"
        "    j = mid\n    for i in lo..mid-1:\n        while j < hi and nums[i] > 2 * nums[j]: j += 1\n        count += j - mid\n    merge halves\n    return count",
        "Both halves are sorted when counting, so the pointer `j` only moves forward: O(n log n). Compute `2 * nums[j]` as a long to avoid overflow.",
    ],
    time="O(n log n)",
    space="O(n)",
    model=lambda nums: sum(
        1 for i in range(len(nums)) for j in range(i + 1, len(nums)) if nums[i] > 2 * nums[j]
    ),
    java="""
        class Solution {
            private int sort(int[] a, int[] tmp, int lo, int hi) {
                if (hi - lo <= 1) return 0;
                int mid = (lo + hi) >>> 1;
                int count = sort(a, tmp, lo, mid) + sort(a, tmp, mid, hi);
                for (int i = lo, j = mid; i < mid; i++) {
                    while (j < hi && (long) a[i] > 2L * a[j]) j++;
                    count += j - mid;
                }
                int i = lo, j = mid, k = lo;
                while (i < mid || j < hi) tmp[k++] = (j == hi || (i < mid && a[i] <= a[j])) ? a[i++] : a[j++];
                System.arraycopy(tmp, lo, a, lo, hi - lo);
                return count;
            }
            public int reversePairs(int[] nums) {
                return sort(nums, new int[nums.length], 0, nums.length);
            }
        }
    """,
    tests=[
        {"nums": [1, 3, 2, 3, 1]},
        {"nums": [2, 4, 3, 5, 1]},
        {"nums": [2147483647, 2147483647, 2147483647]},
        {"nums": [-5, -5]},
    ],
    gen=lambda r: {"nums": ints(r, 1, 15, -10, 10)},
)

P(
    slug="first-missing-positive",
    title="First Missing Positive",
    difficulty="hard",
    topics=["arrays", "hash-sets"],
    summary="Smallest positive integer not in the array, in O(n) time and O(1) space.",
    statement="""
        Return the smallest positive integer that does not appear in `nums`. Use O(n) time and O(1) extra space
        (you may rearrange `nums`).
    """,
    constraints=["1 <= nums.length <= 10^5", "-2^31 <= nums[i] <= 2^31 - 1"],
    sig="int firstMissingPositive(int[] nums)",
    hints=[
        "The answer is between 1 and n + 1. Only values in that range matter.",
        "Use the array itself as a hash table: swap each value `v` in `[1, n]` into slot `v - 1`.",
        "for i in range(n):\n    while 1 <= nums[i] <= n and nums[nums[i] - 1] != nums[i]:\n        swap nums[i] with nums[nums[i] - 1]\n"
        "for i in range(n):\n    if nums[i] != i + 1: return i + 1\nreturn n + 1",
        "Each swap puts one value in its final slot, so there are at most n swaps: O(n) time, O(1) space.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda nums: next(k for k in range(1, len(nums) + 2) if k not in set(nums)),
    java="""
        class Solution {
            public int firstMissingPositive(int[] nums) {
                int n = nums.length;
                for (int i = 0; i < n; i++)
                    while (nums[i] >= 1 && nums[i] <= n && nums[nums[i] - 1] != nums[i]) {
                        int v = nums[i];
                        nums[i] = nums[v - 1];
                        nums[v - 1] = v;
                    }
                for (int i = 0; i < n; i++) if (nums[i] != i + 1) return i + 1;
                return n + 1;
            }
        }
    """,
    tests=[
        {"nums": [1, 2, 0]},
        {"nums": [3, 4, -1, 1]},
        {"nums": [7, 8, 9, 11, 12]},
        {"nums": [1]},
        {"nums": [1, 1]},
    ],
    gen=lambda r: {"nums": ints(r, 1, 12, -3, 10)},
)

P(
    slug="candy-distribution",
    title="Hand Out Candy by Rating",
    difficulty="hard",
    topics=["greedy", "arrays"],
    summary="Fewest candies so higher-rated kids get more than their neighbors.",
    statement="""
        Children stand in a line with ratings `ratings`. Each child gets at least one candy, and a child with a
        higher rating than a neighbor must get more candies than that neighbor. Return the minimum total.
    """,
    constraints=["1 <= n <= 2 * 10^4", "0 <= ratings[i] <= 2 * 10^4"],
    sig="int candy(int[] ratings)",
    hints=[
        "Handle the left-neighbor rule and the right-neighbor rule separately.",
        "Left to right: if rating rises, give one more than the left neighbor. Right to left: if rating rises toward the left, take the max with one more than the right neighbor.",
        "c = [1]*n\nfor i in 1..n-1: if r[i] > r[i-1]: c[i] = c[i-1] + 1\nfor i from n-2 down to 0: if r[i] > r[i+1]: c[i] = max(c[i], c[i+1] + 1)\nreturn sum(c)",
        "Two passes satisfy both rules with the minimum candies: O(n).",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda ratings: (lambda f: sum(f(f, [1] * len(ratings))))(
        lambda f, c: (
            c
            if all(
                not (i > 0 and ratings[i] > ratings[i - 1] and c[i] <= c[i - 1])
                and not (i + 1 < len(c) and ratings[i] > ratings[i + 1] and c[i] <= c[i + 1])
                for i in range(len(c))
            )
            else f(
                f,
                [
                    max(
                        c[i],
                        (c[i - 1] + 1 if i > 0 and ratings[i] > ratings[i - 1] else 1),
                        (c[i + 1] + 1 if i + 1 < len(c) and ratings[i] > ratings[i + 1] else 1),
                    )
                    for i in range(len(c))
                ],
            )
        )
    ),
    java="""
        class Solution {
            public int candy(int[] ratings) {
                int n = ratings.length;
                int[] c = new int[n];
                java.util.Arrays.fill(c, 1);
                for (int i = 1; i < n; i++) if (ratings[i] > ratings[i - 1]) c[i] = c[i - 1] + 1;
                for (int i = n - 2; i >= 0; i--) if (ratings[i] > ratings[i + 1]) c[i] = Math.max(c[i], c[i + 1] + 1);
                int total = 0;
                for (int x : c) total += x;
                return total;
            }
        }
    """,
    tests=[{"ratings": [1, 0, 2]}, {"ratings": [1, 2, 2]}, {"ratings": [5]}, {"ratings": [1, 3, 4, 5, 2]}],
    gen=lambda r: {"ratings": ints(r, 1, 12, 0, 6)},
)

P(
    slug="stock-profit-k-trades",
    title="Best Profit With at Most K Trades",
    difficulty="hard",
    topics=["dynamic-programming", "arrays"],
    summary="Maximize profit with at most k buy-sell transactions.",
    statement="""
        `prices[i]` is the price on day `i`. You may complete at most `k` transactions (buy then sell), holding at
        most one share at a time. Return the maximum profit.
    """,
    constraints=["1 <= k <= 100", "1 <= prices.length <= 1000"],
    sig="int maxProfitK(int k, int[] prices)",
    hints=[
        "Track your best balance after each number of buys and sells.",
        "buy[j] = best balance holding a share in transaction j; sell[j] = best balance after completing j transactions.",
        "buy = [-inf]*(k+1); sell = [0]*(k+1)\nfor p in prices:\n    for j in 1..k:\n        buy[j] = max(buy[j], sell[j-1] - p)\n        sell[j] = max(sell[j], buy[j] + p)\nreturn sell[k]",
        "O(n k) time and O(k) space. If k ≥ n/2, it's the unlimited case: just sum every rise.",
    ],
    time="O(n k)",
    space="O(k)",
    model=lambda k, prices: (lambda f: f(f, 0, k, False))(
        lru_cache(None)(
            lambda f, i, left, holding: (
                0
                if i == len(prices) or (left == 0 and not holding)
                else max(
                    f(f, i + 1, left, holding),
                    (prices[i] + f(f, i + 1, left - 1, False))
                    if holding
                    else (-prices[i] + f(f, i + 1, left, True)),
                )
            )
        )
    ),
    java="""
        import java.util.*;

        class Solution {
            public int maxProfitK(int k, int[] prices) {
                int[] buy = new int[k + 1], sell = new int[k + 1];
                Arrays.fill(buy, Integer.MIN_VALUE / 2);
                for (int p : prices)
                    for (int j = 1; j <= k; j++) {
                        buy[j] = Math.max(buy[j], sell[j - 1] - p);
                        sell[j] = Math.max(sell[j], buy[j] + p);
                    }
                return sell[k];
            }
        }
    """,
    tests=[
        {"k": 2, "prices": [2, 4, 1]},
        {"k": 2, "prices": [3, 2, 6, 5, 0, 3]},
        {"k": 1, "prices": [7, 6, 4, 3, 1]},
        {"k": 3, "prices": [1, 5, 2, 8, 3, 9]},
    ],
    gen=lambda r: {"k": r.randint(1, 3), "prices": ints(r, 1, 12, 0, 15)},
)

P(
    slug="dungeon-game",
    title="Dungeon Game",
    difficulty="hard",
    topics=["dynamic-programming", "matrix"],
    summary="Minimum starting health to cross a dungeon alive.",
    statement="""
        A knight starts at the top-left of `dungeon` and must reach the bottom-right, moving only right or down.
        Each cell adds its value to his health (negative values hurt). His health must stay at least 1 at every
        moment. Return the minimum starting health.
    """,
    constraints=["1 <= rows, cols <= 200", "-1000 <= dungeon[i][j] <= 1000"],
    sig="int calculateMinimumHP(int[][] dungeon)",
    hints=[
        "Planning forward is hard because you don't know future damage. Plan backwards from the princess.",
        "need[r][c] = max(1, min(need[r+1][c], need[r][c+1]) - dungeon[r][c]).",
        "need = grid of inf with need[m][n-1] = need[m-1][n] = 1\nfor r from m-1 down to 0:\n    for c from n-1 down to 0:\n"
        "        need[r][c] = max(1, min(need[r+1][c], need[r][c+1]) - dungeon[r][c])\nreturn need[0][0]",
        "Working backwards turns it into a clean DP: O(m n) time. A forward DP fails because the best path so far may not be the safest later.",
    ],
    time="O(m n)",
    space="O(m n)",
    model=lambda dungeon: (
        lambda paths: min(max(1, 1 - min(__import__("itertools").accumulate(p))) for p in paths)
    )(
        [
            [dungeon[r][c] for r, c in path]
            for path in (
                lambda m, n: [
                    (
                        lambda moves: [
                            (sum(1 for x in moves[:i] if x), sum(1 for x in moves[:i] if not x))
                            for i in range(m + n - 1)
                        ]
                    )(mv)
                    for mv in set(__import__("itertools").permutations([1] * (m - 1) + [0] * (n - 1)))
                ]
            )(len(dungeon), len(dungeon[0]))
        ]
    ),
    java="""
        import java.util.*;

        class Solution {
            public int calculateMinimumHP(int[][] dungeon) {
                int m = dungeon.length, n = dungeon[0].length;
                int[][] need = new int[m + 1][n + 1];
                for (int[] row : need) Arrays.fill(row, Integer.MAX_VALUE);
                need[m][n - 1] = need[m - 1][n] = 1;
                for (int r = m - 1; r >= 0; r--)
                    for (int c = n - 1; c >= 0; c--)
                        need[r][c] = Math.max(1, Math.min(need[r + 1][c], need[r][c + 1]) - dungeon[r][c]);
                return need[0][0];
            }
        }
    """,
    tests=[
        {"dungeon": [[-2, -3, 3], [-5, -10, 1], [10, 30, -5]]},
        {"dungeon": [[0]]},
        {"dungeon": [[100]]},
        {"dungeon": [[-3, 5]]},
    ],
    gen=lambda r: {
        "dungeon": [
            [r.randint(-9, 6) for _ in range(c)] for c in [r.randint(1, 4)] for _ in range(r.randint(1, 4))
        ]
    },
)

P(
    slug="split-array-largest-sum",
    title="Split Array to Minimize the Largest Sum",
    difficulty="hard",
    topics=["binary-search", "dynamic-programming", "greedy"],
    summary="Split into k pieces so the biggest piece sum is as small as possible.",
    statement="""
        Split `nums` into `k` non-empty contiguous pieces. Return the smallest possible value of the largest piece sum.
    """,
    constraints=["1 <= nums.length <= 1000", "0 <= nums[i] <= 10^6", "1 <= k <= min(50, n)"],
    sig="int splitArray(int[] nums, int k)",
    hints=[
        "Guess a limit for the largest sum. Can you check a guess quickly?",
        "Greedily fill pieces up to the limit and count them; fewer than or equal to k pieces means the limit works. Binary search the limit.",
        "lo, hi = max(nums), sum(nums)\nwhile lo < hi:\n    mid = (lo + hi) // 2\n    if piecesNeeded(mid) <= k: hi = mid\n    else: lo = mid + 1\nreturn lo",
        "Binary search on the answer with a greedy O(n) check: O(n log(sum)). (A DP over split points is O(n^2 k).)",
    ],
    time="O(n log S)",
    space="O(1)",
    model=lambda nums, k: min(
        max(sum(nums[a:b]) for a, b in zip((0, *cuts), (*cuts, len(nums)), strict=True))
        for cuts in combinations(range(1, len(nums)), k - 1)
    ),
    java="""
        class Solution {
            public int splitArray(int[] nums, int k) {
                long lo = 0, hi = 0;
                for (int x : nums) { lo = Math.max(lo, x); hi += x; }
                while (lo < hi) {
                    long mid = (lo + hi) / 2, load = 0;
                    int pieces = 1;
                    for (int x : nums) { if (load + x > mid) { pieces++; load = 0; } load += x; }
                    if (pieces <= k) hi = mid; else lo = mid + 1;
                }
                return (int) lo;
            }
        }
    """,
    tests=[
        {"nums": [7, 2, 5, 10, 8], "k": 2},
        {"nums": [1, 2, 3, 4, 5], "k": 2},
        {"nums": [1, 4, 4], "k": 3},
        {"nums": [5], "k": 1},
    ],
    gen=lambda r: (lambda nums: {"nums": nums, "k": r.randint(1, len(nums))})(ints(r, 1, 9, 0, 12)),
)

P(
    slug="russian-doll-envelopes",
    title="Russian Doll Envelopes",
    difficulty="hard",
    topics=["dynamic-programming", "binary-search", "sorting"],
    summary="Most envelopes you can nest inside each other.",
    statement="""
        `envelopes[i] = [w, h]`. One envelope fits in another only if both its width and height are strictly
        smaller. Return the maximum number of envelopes you can nest (no rotating).
    """,
    constraints=["1 <= envelopes.length <= 10^5"],
    sig="int maxEnvelopes(int[][] envelopes)",
    hints=[
        "Sort by width so you only have to think about heights.",
        "Sort width ascending and, for equal widths, height descending. Then find the longest strictly increasing subsequence of heights.",
        "sort by (w, -h)\ntails = []\nfor _, h in envelopes:\n    i = lower_bound(tails, h)\n    if i == len(tails): tails.append(h) else: tails[i] = h\nreturn len(tails)",
        "The descending tie-break stops two equal-width envelopes from both appearing in the chain. LIS with binary search: O(n log n).",
    ],
    time="O(n log n)",
    space="O(n)",
    model=lambda envelopes: (
        lambda es: (lambda f: max(f(f, i) for i in range(len(es))))(
            lru_cache(None)(
                lambda f, i: (
                    1
                    + max(
                        [f(f, j) for j in range(len(es)) if es[j][0] < es[i][0] and es[j][1] < es[i][1]]
                        or [0]
                    )
                )
            )
        )
    )(sorted(map(tuple, envelopes))),
    java="""
        import java.util.*;

        class Solution {
            public int maxEnvelopes(int[][] envelopes) {
                Arrays.sort(envelopes, (a, b) -> a[0] != b[0] ? Integer.compare(a[0], b[0]) : Integer.compare(b[1], a[1]));
                int[] tails = new int[envelopes.length];
                int size = 0;
                for (int[] e : envelopes) {
                    int lo = 0, hi = size;
                    while (lo < hi) { int mid = (lo + hi) >>> 1; if (tails[mid] < e[1]) lo = mid + 1; else hi = mid; }
                    tails[lo] = e[1];
                    if (lo == size) size++;
                }
                return size;
            }
        }
    """,
    tests=[
        {"envelopes": [[5, 4], [6, 4], [6, 7], [2, 3]]},
        {"envelopes": [[1, 1], [1, 1], [1, 1]]},
        {"envelopes": [[4, 5], [4, 6], [6, 7], [2, 3], [1, 1]]},
    ],
    gen=lambda r: {"envelopes": [[r.randint(1, 8), r.randint(1, 8)] for _ in range(r.randint(1, 9))]},
)

P(
    slug="jump-game-equal-values",
    title="Jump Game With Teleports",
    difficulty="hard",
    topics=["graphs", "arrays", "hash-maps"],
    summary="Fewest moves to the end, where equal values let you teleport.",
    statement="""
        From index `i` you can move to `i + 1`, `i - 1`, or any index `j` with `nums[j] == nums[i]`. Return the
        minimum number of moves from index 0 to the last index.
    """,
    constraints=["1 <= nums.length <= 5 * 10^4"],
    sig="int minJumps(int[] nums)",
    hints=[
        "Every move costs the same: think shortest path in a graph.",
        "BFS over indices. Group indices by value; after using a value's teleports once, clear that group so it isn't scanned again.",
        "groups = value -> list of indices\nqueue = [0]; dist[0] = 0\nwhile queue:\n    i = pop front\n    for j in [i-1, i+1] + groups[nums[i]]:\n"
        "        if unvisited: dist[j] = dist[i] + 1; push j\n    groups[nums[i]] = []\nreturn dist[n-1]",
        "Clearing each value group after first use keeps BFS at O(n); without it, many equal values make it O(n^2).",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda nums: (
        lambda n: (lambda f: f(f, {0}, {0}, 0))(
            lambda f, frontier, seen, d: (
                d
                if n - 1 in frontier
                else (lambda nxt: f(f, nxt, seen | nxt, d + 1))(
                    {
                        j
                        for i in frontier
                        for j in [i - 1, i + 1] + [k for k in range(n) if nums[k] == nums[i]]
                        if 0 <= j < n and j not in seen
                    }
                )
            )
        )
    )(len(nums)),
    java="""
        import java.util.*;

        class Solution {
            public int minJumps(int[] nums) {
                int n = nums.length;
                Map<Integer, List<Integer>> groups = new HashMap<>();
                for (int i = 0; i < n; i++) groups.computeIfAbsent(nums[i], k -> new ArrayList<>()).add(i);
                int[] dist = new int[n];
                Arrays.fill(dist, -1);
                dist[0] = 0;
                Deque<Integer> queue = new ArrayDeque<>(List.of(0));
                while (!queue.isEmpty()) {
                    int i = queue.poll();
                    if (i == n - 1) return dist[i];
                    List<Integer> next = new ArrayList<>(groups.getOrDefault(nums[i], List.of()));
                    next.add(i - 1);
                    next.add(i + 1);
                    groups.remove(nums[i]);
                    for (int j : next)
                        if (j >= 0 && j < n && dist[j] == -1) { dist[j] = dist[i] + 1; queue.add(j); }
                }
                return -1;
            }
        }
    """,
    tests=[
        {"nums": [100, -23, -23, 404, 100, 23, 23, 23, 3, 404]},
        {"nums": [7]},
        {"nums": [7, 6, 9, 6, 9, 6, 9, 7]},
        {"nums": [1, 2, 3, 4]},
    ],
    gen=lambda r: {"nums": ints(r, 1, 14, 0, 5)},
)

P(
    slug="shortest-subarray-sum-k",
    title="Shortest Subarray With Sum at Least K (With Negatives)",
    difficulty="hard",
    topics=["queues", "prefix-sums", "sliding-window"],
    summary="Shortest window whose sum reaches k when values can be negative.",
    statement="""
        Return the length of the shortest non-empty contiguous subarray of `nums` with sum at least `k`, or `-1` if
        there isn't one. Values may be negative.
    """,
    constraints=["1 <= nums.length <= 10^5", "-10^5 <= nums[i] <= 10^5", "1 <= k <= 10^9"],
    sig="int shortestSubarray(int[] nums, int k)",
    hints=[
        "Negative values break the usual two-pointer window. Work with prefix sums instead.",
        "Keep a deque of indices with increasing prefix sums. Pop from the front while the current prefix minus the front prefix reaches k.",
        "P = prefix sums (P[0] = 0)\ndq = deque()\nfor j in 0..n:\n    while dq and P[j] - P[dq[0]] >= k: best = min(best, j - dq.popleft())\n"
        "    while dq and P[dq[-1]] >= P[j]: dq.pop()\n    dq.append(j)\nreturn best or -1",
        "A larger, later prefix can never be a better start than a smaller one, so the deque stays increasing. Each index enters and leaves once: O(n). Use long prefix sums.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda nums, k: min(
        [j - i for i in range(len(nums)) for j in range(i + 1, len(nums) + 1) if sum(nums[i:j]) >= k] or [-1]
    ),
    java="""
        import java.util.*;

        class Solution {
            public int shortestSubarray(int[] nums, int k) {
                int n = nums.length, best = Integer.MAX_VALUE;
                long[] P = new long[n + 1];
                for (int i = 0; i < n; i++) P[i + 1] = P[i] + nums[i];
                Deque<Integer> dq = new ArrayDeque<>();
                for (int j = 0; j <= n; j++) {
                    while (!dq.isEmpty() && P[j] - P[dq.peekFirst()] >= k) best = Math.min(best, j - dq.pollFirst());
                    while (!dq.isEmpty() && P[dq.peekLast()] >= P[j]) dq.pollLast();
                    dq.addLast(j);
                }
                return best == Integer.MAX_VALUE ? -1 : best;
            }
        }
    """,
    tests=[
        {"nums": [1], "k": 1},
        {"nums": [1, 2], "k": 4},
        {"nums": [2, -1, 2], "k": 3},
        {"nums": [84, -37, 32, 40, 95], "k": 167},
    ],
    gen=lambda r: {"nums": ints(r, 1, 12, -6, 9), "k": r.randint(1, 15)},
)

P(
    slug="subarrays-k-distinct",
    title="Subarrays With Exactly K Distinct Values",
    difficulty="hard",
    topics=["sliding-window", "hash-maps"],
    summary="Count subarrays containing exactly k different values.",
    statement="""
        Return the number of contiguous subarrays of `nums` that contain exactly `k` distinct values.
    """,
    constraints=["1 <= nums.length <= 2 * 10^4", "1 <= nums[i], k <= nums.length"],
    sig="int subarraysWithKDistinct(int[] nums, int k)",
    hints=[
        '"At most k" is easy with a sliding window. How do you get "exactly k" from it?',
        "exactly(k) = atMost(k) - atMost(k - 1).",
        "def atMost(k):\n    count = left = 0\n    for right, x in enumerate(nums):\n        add x; while distinct > k: remove nums[left]; left += 1\n"
        "        count += right - left + 1\n    return count\nreturn atMost(k) - atMost(k - 1)",
        'Each window pass is O(n), and every subarray ending at `right` inside the window counts toward "at most". Two passes: O(n).',
    ],
    time="O(n)",
    space="O(n)",
    model=lambda nums, k: sum(
        1 for i in range(len(nums)) for j in range(i + 1, len(nums) + 1) if len(set(nums[i:j])) == k
    ),
    java="""
        class Solution {
            private int atMost(int[] nums, int k) {
                int[] counts = new int[nums.length + 2];
                int left = 0, distinct = 0, total = 0;
                for (int right = 0; right < nums.length; right++) {
                    if (counts[nums[right]]++ == 0) distinct++;
                    while (distinct > k) if (--counts[nums[left++]] == 0) distinct--;
                    total += right - left + 1;
                }
                return total;
            }
            public int subarraysWithKDistinct(int[] nums, int k) {
                return atMost(nums, k) - atMost(nums, k - 1);
            }
        }
    """,
    tests=[{"nums": [1, 2, 1, 2, 3], "k": 2}, {"nums": [1, 2, 1, 3, 4], "k": 3}, {"nums": [1], "k": 1}],
    gen=lambda r: (
        lambda n: {"nums": [r.randint(1, min(n, 4)) for _ in range(n)], "k": r.randint(1, min(n, 4))}
    )(r.randint(1, 12)),
)

P(
    slug="min-k-bit-flips",
    title="Fewest K-Length Flips to All Ones",
    difficulty="hard",
    topics=["greedy", "sliding-window", "bit-manipulation"],
    summary="Flip windows of length k to make a binary array all ones.",
    statement="""
        One operation flips every bit in a contiguous window of length `k` of the binary array `nums`. Return the
        minimum number of operations to make every bit `1`, or `-1` if it's impossible.
    """,
    constraints=["1 <= k <= nums.length <= 10^5"],
    sig="int minKBitFlips(int[] nums, int k)",
    hints=[
        "The leftmost 0 can only be fixed by a flip starting exactly there.",
        "Go left to right; flip whenever the current bit (after earlier flips) is 0. Track active flips with a difference array instead of flipping k bits each time.",
        "flips = active = 0\nended = [0]*(n+1)\nfor i in range(n):\n    active -= ended[i]\n    if (nums[i] + active) % 2 == 0:\n"
        "        if i + k > n: return -1\n        flips += 1; active += 1; ended[i + k] += 1\nreturn flips",
        "The greedy choice is forced at each step, so it's optimal. The difference array makes it O(n) instead of O(n k).",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda nums, k: min(
        [
            bin(mask).count("1")
            for mask in range(1 << (len(nums) - k + 1))
            if all(
                (
                    nums[i]
                    + sum(1 for s in range(max(0, i - k + 1), min(i, len(nums) - k) + 1) if mask >> s & 1)
                )
                % 2
                for i in range(len(nums))
            )
        ]
        or [-1]
    ),
    java="""
        class Solution {
            public int minKBitFlips(int[] nums, int k) {
                int n = nums.length, flips = 0, active = 0;
                int[] ended = new int[n + 1];
                for (int i = 0; i < n; i++) {
                    active -= ended[i];
                    if ((nums[i] + active) % 2 == 0) {
                        if (i + k > n) return -1;
                        flips++;
                        active++;
                        ended[i + k]++;
                    }
                }
                return flips;
            }
        }
    """,
    tests=[
        {"nums": [0, 1, 0], "k": 1},
        {"nums": [1, 1, 0], "k": 2},
        {"nums": [0, 0, 0, 1, 0, 1, 1, 0], "k": 3},
    ],
    gen=lambda r: (lambda nums: {"nums": nums, "k": r.randint(1, len(nums))})(ints(r, 1, 10, 0, 1)),
)
