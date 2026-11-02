"""Hard problems, part 4: dynamic programming, combinatorics and bitmasks."""

from functools import lru_cache
from itertools import combinations, permutations, product

from scripts.problembank import P, ints, word

MOD = 1_000_000_007


def _min_removals(s):
    for k in range(len(s) + 1):
        for drop in combinations(range(len(s)), k):
            t = "".join(c for i, c in enumerate(s) if i not in drop)
            bal = 0
            ok = True
            for c in t:
                bal += 1 if c == "(" else -1 if c == ")" else 0
                if bal < 0:
                    ok = False
                    break
            if ok and bal == 0:
                return k
    return len(s)


P(
    slug="distinct-palindromic-subsequences",
    title="Count Distinct Palindromic Subsequences",
    difficulty="hard",
    topics=["dynamic-programming", "strings"],
    summary="How many different non-empty palindromic subsequences does a string have?",
    statement="""
        Return the number of **different** non-empty palindromic subsequences of `s` (as strings, so equal sequences
        from different positions count once), modulo `10^9 + 7`. `s` contains only `a`, `b`, `c` and `d`.
    """,
    constraints=["1 <= s.length <= 1000", "s[i] in {a, b, c, d}"],
    sig="int countPalindromicSubsequences(String s)",
    hints=[
        "Count palindromes by their outer letter: for each letter, look inside the first and last occurrence in a range.",
        "dp[i][j] for each letter x: palindromes in s[i..j] that start and end with x. Use the first/last x in the range and recurse inside.",
        "def count(i, j):\n    total = 0\n    for x in 'abcd':\n        lo, hi = first and last index of x in [i, j]\n        if none: continue\n"
        "        total += 1 if lo == hi else 2 + count(lo + 1, hi - 1)\n    return total % MOD",
        "Memoize on (i, j): O(4 n^2) states, each O(1) with precomputed next/previous occurrence tables.",
    ],
    time="O(n^2)",
    space="O(n^2)",
    model=lambda s: (
        len({t for k in range(1, len(s) + 1) for c in combinations(s, k) if (t := "".join(c)) == t[::-1]})
        % MOD
    ),
    java="""
        class Solution {
            private Integer[][] memo;
            private String s;
            private int count(int i, int j) {
                if (i > j) return 0;
                if (memo[i][j] != null) return memo[i][j];
                long total = 0;
                for (char x = 'a'; x <= 'd'; x++) {
                    int lo = s.indexOf(x, i), hi = s.lastIndexOf(x, j);
                    if (lo == -1 || lo > j) continue;
                    total += lo == hi ? 1 : 2 + count(lo + 1, hi - 1);
                }
                return memo[i][j] = (int) (total % 1_000_000_007);
            }
            public int countPalindromicSubsequences(String s) {
                this.s = s;
                memo = new Integer[s.length()][s.length()];
                return count(0, s.length() - 1);
            }
        }
    """,
    tests=[{"s": "bccb"}, {"s": "abcd"}, {"s": "aaa"}, {"s": "abcba"}],
    gen=lambda r: {"s": word(r, 1, 10, "abcd")},
    explain={0: "b, c, bb, cc, bcb, bccb."},
)

P(
    slug="strange-printer",
    title="Strange Printer",
    difficulty="hard",
    topics=["dynamic-programming", "strings"],
    summary="Fewest printing passes when each pass prints one repeated letter.",
    statement="""
        A printer prints a run of one repeated character per turn, covering any contiguous range and overwriting what
        was there. Return the minimum number of turns to print `s`.
    """,
    constraints=["1 <= s.length <= 100", "lower-case letters"],
    sig="int strangePrinter(String s)",
    hints=[
        "The first character of a range is printed in some turn; that turn can also cover later copies of the same character.",
        "turns(i, j) = turns(i+1, j) + 1, or, for each k in (i, j] with s[k] == s[i], turns(i+1, k-1) + turns(k, j) (print s[i] together with s[k]).",
        "def turns(i, j):\n    if i > j: return 0\n    best = 1 + turns(i + 1, j)\n    for k in i+1..j:\n        if s[k] == s[i]: best = min(best, turns(i + 1, k - 1) + turns(k, j))\n    return best",
        "Interval DP with memoization: O(n^3). Collapsing runs of equal letters first shrinks n.",
    ],
    time="O(n^3)",
    space="O(n^2)",
    model=lambda s: (lambda f: f(f, s))(
        lru_cache(None)(
            lambda f, t: (
                0
                if not t
                else min(
                    [1 + f(f, t[1:])] + [f(f, t[1:k]) + f(f, t[k:]) for k in range(1, len(t)) if t[k] == t[0]]
                )
            )
        )
    ),
    java="""
        class Solution {
            public int strangePrinter(String s) {
                int n = s.length();
                int[][] dp = new int[n + 1][n + 1];
                for (int i = n - 1; i >= 0; i--)
                    for (int j = i; j < n; j++) {
                        dp[i][j] = 1 + dp[i + 1][j];
                        for (int k = i + 1; k <= j; k++)
                            if (s.charAt(k) == s.charAt(i)) dp[i][j] = Math.min(dp[i][j], (k - 1 >= i + 1 ? dp[i + 1][k - 1] : 0) + dp[k][j]);
                    }
                return dp[0][n - 1];
            }
        }
    """,
    tests=[{"s": "aaabbb"}, {"s": "aba"}, {"s": "a"}, {"s": "abcabc"}],
    gen=lambda r: {"s": word(r, 1, 9, "abc")},
)

P(
    slug="min-cost-cut-stick",
    title="Cheapest Order to Cut a Stick",
    difficulty="hard",
    topics=["dynamic-programming", "sorting"],
    summary="Order the cuts so the total cost (length of piece being cut) is lowest.",
    statement="""
        A stick runs from `0` to `n`. You must make cuts at every position in `cuts`, in any order. Each cut costs the
        length of the piece being cut. Return the minimum total cost.
    """,
    constraints=["2 <= n <= 10^6", "1 <= cuts.length <= 100", "cuts are distinct, strictly between 0 and n"],
    sig="int minCost(int n, int[] cuts)",
    hints=[
        "Think about the last cut instead of the first.",
        "Sort cuts and add the ends 0 and n. cost(i, j) for the piece between points i and j = (p[j] - p[i]) + min over k of cost(i, k) + cost(k, j).",
        "p = [0] + sorted(cuts) + [n]\nfor length 2 upward:\n    for i, j = i + length:\n        dp[i][j] = p[j] - p[i] + min(dp[i][k] + dp[k][j] for k in (i, j))\nreturn dp[0][m+1]",
        "Interval DP over the cut points: O(m^3) for m cuts, independent of n.",
    ],
    time="O(m^3)",
    space="O(m^2)",
    model=lambda n, cuts: min(
        sum(
            (lambda done: min([c for c in [n] + done if c > x]) - max([c for c in [0] + done if c < x]))(
                list(order[:i])
            )
            for i, x in enumerate(order)
        )
        for order in permutations(cuts)
    ),
    java="""
        import java.util.*;

        class Solution {
            public int minCost(int n, int[] cuts) {
                int m = cuts.length;
                int[] p = new int[m + 2];
                Arrays.sort(cuts);
                for (int i = 0; i < m; i++) p[i + 1] = cuts[i];
                p[m + 1] = n;
                int[][] dp = new int[m + 2][m + 2];
                for (int len = 2; len <= m + 1; len++)
                    for (int i = 0; i + len <= m + 1; i++) {
                        int j = i + len;
                        dp[i][j] = Integer.MAX_VALUE;
                        for (int k = i + 1; k < j; k++) dp[i][j] = Math.min(dp[i][j], dp[i][k] + dp[k][j]);
                        dp[i][j] += p[j] - p[i];
                    }
                return dp[0][m + 1];
            }
        }
    """,
    tests=[{"n": 7, "cuts": [1, 3, 4, 5]}, {"n": 9, "cuts": [5, 6, 1, 4, 2]}, {"n": 2, "cuts": [1]}],
    gen=lambda r: (lambda n: {"n": n, "cuts": r.sample(range(1, n), r.randint(1, min(6, n - 1)))})(
        r.randint(2, 20)
    ),
)

P(
    slug="tallest-billboard",
    title="Tallest Billboard",
    difficulty="hard",
    topics=["dynamic-programming"],
    summary="Build two equal-height supports from rods; maximize the height.",
    statement="""
        You have rods of lengths `rods`. Weld some of them into two supports of equal height (each rod used at most
        once, some may go unused). Return the largest possible height, or `0` if no positive height is possible.
    """,
    constraints=["1 <= rods.length <= 20", "1 <= rods[i] <= 1000", "sum(rods) <= 5000"],
    sig="int tallestBillboard(int[] rods)",
    hints=[
        "Each rod goes on the left, on the right, or nowhere. 3^20 is too many choices.",
        "Track only the difference between the two sides: best[diff] = the tallest shorter side achieving that difference.",
        "best = {0: 0}\nfor r in rods:\n    for diff, short in snapshot of best:\n        put r on the taller side: best[diff + r] = max(.., short)\n"
        "        put r on the shorter side: new diff |diff - r|, shorter side short + min(r, diff)\nreturn best[0]",
        "There are at most sum(rods) differences: O(n × sum) time and O(sum) space.",
    ],
    time="O(n · S)",
    space="O(S)",
    model=lambda rods: max(
        left
        for choice in product((0, 1, 2), repeat=len(rods))
        for left, rr in [
            (
                sum(x for x, c in zip(rods, choice, strict=True) if c == 1),
                sum(x for x, c in zip(rods, choice, strict=True) if c == 2),
            )
        ]
        if left == rr
    ),
    java="""
        import java.util.*;

        class Solution {
            public int tallestBillboard(int[] rods) {
                Map<Integer, Integer> best = new HashMap<>();
                best.put(0, 0);
                for (int r : rods) {
                    Map<Integer, Integer> next = new HashMap<>(best);
                    for (Map.Entry<Integer, Integer> e : best.entrySet()) {
                        int diff = e.getKey(), shortSide = e.getValue();
                        next.merge(diff + r, shortSide, Math::max);
                        int newDiff = Math.abs(diff - r), newShort = shortSide + Math.min(r, diff);
                        next.merge(newDiff, newShort, Math::max);
                    }
                    best = next;
                }
                return best.get(0);
            }
        }
    """,
    tests=[{"rods": [1, 2, 3, 6]}, {"rods": [1, 2, 3, 4, 5, 6]}, {"rods": [1, 2]}, {"rods": [5, 5]}],
    gen=lambda r: {"rods": ints(r, 1, 8, 1, 9)},
)

P(
    slug="profitable-schemes",
    title="Profitable Schemes",
    difficulty="hard",
    topics=["dynamic-programming"],
    summary="Count crime plans that need at most n people and make at least minProfit.",
    statement="""
        Crime `i` needs `group[i]` members and makes `profit[i]`. A member can take part in only one crime. Count the
        subsets of crimes that use at most `n` members in total and make at least `minProfit`, modulo `10^9 + 7`.
    """,
    constraints=["1 <= n <= 100", "0 <= minProfit <= 100", "1 <= group.length <= 100"],
    sig="int profitableSchemes(int n, int minProfit, int[] group, int[] profit)",
    hints=[
        "It's a knapsack with two dimensions: people used and profit made.",
        "Cap profit at `minProfit` (more profit doesn't change anything): dp[people][profit] counts subsets.",
        "dp[0][0] = 1\nfor each crime (g, p):\n    for people from n down to g:\n        for pr from minProfit down to 0:\n            dp[people][min(minProfit, pr + p)] += dp[people - g][pr]\nreturn sum(dp[people][minProfit] for all people)",
        "O(crimes × n × minProfit). Capping profit keeps the table small.",
    ],
    time="O(k n P)",
    space="O(n P)",
    model=lambda n, minProfit, group, profit: (
        sum(
            1
            for mask in range(1 << len(group))
            if sum(group[i] for i in range(len(group)) if mask >> i & 1) <= n
            and sum(profit[i] for i in range(len(group)) if mask >> i & 1) >= minProfit
        )
        % MOD
    ),
    java="""
        class Solution {
            public int profitableSchemes(int n, int minProfit, int[] group, int[] profit) {
                long[][] dp = new long[n + 1][minProfit + 1];
                dp[0][0] = 1;
                for (int c = 0; c < group.length; c++) {
                    int g = group[c], p = profit[c];
                    for (int people = n; people >= g; people--)
                        for (int pr = minProfit; pr >= 0; pr--) {
                            int to = Math.min(minProfit, pr + p);
                            dp[people][to] = (dp[people][to] + dp[people - g][pr]) % 1_000_000_007;
                        }
                }
                long total = 0;
                for (int people = 0; people <= n; people++) total = (total + dp[people][minProfit]) % 1_000_000_007;
                return (int) total;
            }
        }
    """,
    tests=[
        {"n": 5, "minProfit": 3, "group": [2, 2], "profit": [2, 3]},
        {"n": 10, "minProfit": 5, "group": [2, 3, 5], "profit": [6, 7, 8]},
        {"n": 1, "minProfit": 1, "group": [2], "profit": [5]},
    ],
    gen=lambda r: (
        lambda k: {
            "n": r.randint(1, 10),
            "minProfit": r.randint(0, 8),
            "group": ints(r, k, k, 1, 5),
            "profit": ints(r, k, k, 0, 5),
        }
    )(r.randint(1, 8)),
)

P(
    slug="music-playlists",
    title="Number of Music Playlists",
    difficulty="hard",
    topics=["dynamic-programming", "math"],
    summary="Count playlists that use every song, with a replay gap.",
    statement="""
        You have `n` different songs and want a playlist of `goal` songs (goal ≥ n) where every song plays at least once
        and a song can only replay after `k` other songs have played since its last play. Return the number of
        playlists modulo `10^9 + 7`.
    """,
    constraints=["0 <= k < n <= goal <= 100"],
    sig="int numMusicPlaylists(int n, int goal, int k)",
    hints=[
        "Build the playlist one slot at a time, tracking how many distinct songs you've used.",
        "dp[i][j] = playlists of length i using j distinct songs. Next song is new (n - j choices) or a replay (j - k choices if j > k).",
        "dp[0][0] = 1\nfor i in 1..goal:\n    for j in 1..n:\n        dp[i][j] = dp[i-1][j-1] * (n - j + 1) + dp[i-1][j] * max(j - k, 0)\nreturn dp[goal][n]",
        "O(goal × n). A replay can only use songs outside the last k played, which is why the count is `j - k`.",
    ],
    time="O(goal · n)",
    space="O(goal · n)",
    model=lambda n, goal, k: (
        sum(
            1
            for p in product(range(n), repeat=goal)
            if len(set(p)) == n and all(p[i] not in p[max(0, i - k) : i] for i in range(goal))
        )
        % MOD
    ),
    java="""
        class Solution {
            public int numMusicPlaylists(int n, int goal, int k) {
                long[][] dp = new long[goal + 1][n + 1];
                dp[0][0] = 1;
                for (int i = 1; i <= goal; i++)
                    for (int j = 1; j <= n; j++) {
                        dp[i][j] = dp[i - 1][j - 1] * (n - j + 1) % 1_000_000_007;
                        if (j > k) dp[i][j] = (dp[i][j] + dp[i - 1][j] * (j - k)) % 1_000_000_007;
                    }
                return (int) dp[goal][n];
            }
        }
    """,
    tests=[
        {"n": 3, "goal": 3, "k": 1},
        {"n": 2, "goal": 3, "k": 0},
        {"n": 2, "goal": 3, "k": 1},
        {"n": 3, "goal": 5, "k": 1},
    ],
    gen=lambda r: (lambda n: {"n": n, "goal": r.randint(n, min(n + 3, 6)), "k": r.randint(0, n - 1)})(
        r.randint(1, 4)
    ),
)

P(
    slug="min-taps-garden",
    title="Fewest Taps to Water a Garden",
    difficulty="hard",
    topics=["greedy", "dynamic-programming"],
    summary="Open the fewest taps so the whole garden is watered.",
    statement="""
        A garden spans `[0, n]` and has a tap at each integer point `i` (0..n) that waters `[i - ranges[i], i + ranges[i]]`.
        Return the fewest taps to water the entire garden, or `-1` if impossible.
    """,
    constraints=["1 <= n <= 10^4", "ranges.length == n + 1", "0 <= ranges[i] <= 100"],
    sig="int minTaps(int n, int[] ranges)",
    hints=[
        "Turn each tap into an interval, and the problem into covering [0, n] with as few intervals as possible.",
        'For each left point, record the farthest right point reachable. Then jump greedily like "jump game II".',
        "reach[l] = max right end of a tap starting at or before l (clamped to [0, n])\ntaps = 0; end = far = 0\nfor i in 0..n-1:\n    far = max(far, reach[i])\n"
        "    if i == end:\n        if far <= i: return -1\n        taps += 1; end = far\nreturn taps",
        "Greedy interval covering in O(n + max range).",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda n, ranges: min(
        [
            k
            for k in range(1, n + 2)
            for c in combinations(range(n + 1), k)
            if all(any(i - ranges[i] <= x and x + 1 <= i + ranges[i] for i in c) for x in range(n))
        ][:1]
        or [-1]
    ),
    java="""
        class Solution {
            public int minTaps(int n, int[] ranges) {
                int[] reach = new int[n + 1];
                for (int i = 0; i <= n; i++) {
                    int l = Math.max(0, i - ranges[i]), r = Math.min(n, i + ranges[i]);
                    reach[l] = Math.max(reach[l], r);
                }
                int taps = 0, end = 0, far = 0;
                for (int i = 0; i < n; i++) {
                    far = Math.max(far, reach[i]);
                    if (i == end) {
                        if (far <= i) return -1;
                        taps++;
                        end = far;
                    }
                }
                return taps;
            }
        }
    """,
    tests=[
        {"n": 5, "ranges": [3, 4, 1, 1, 0, 0]},
        {"n": 3, "ranges": [0, 0, 0, 0]},
        {"n": 7, "ranges": [1, 2, 1, 0, 2, 1, 0, 1]},
    ],
    gen=lambda r: (lambda n: {"n": n, "ranges": ints(r, n + 1, n + 1, 0, 3)})(r.randint(1, 7)),
)

P(
    slug="max-students-exam",
    title="Most Students Without Cheating",
    difficulty="hard",
    topics=["dynamic-programming", "bit-manipulation"],
    summary="Seat the most students so nobody can see a neighbor's paper.",
    statement="""
        `seats` rows contain `'.'` (usable) and `'#'` (broken). A student can see the papers of students to the left,
        right, upper-left and upper-right. Seat as many students as possible on usable seats so nobody can see
        anyone else's paper. Return that number.
    """,
    constraints=["1 <= rows, cols <= 8"],
    sig="int maxStudents(String[] seats)",
    hints=[
        "Rows only interact with the row directly above. Represent a row's seating as a bitmask.",
        "A mask is valid if it uses only good seats and has no two adjacent bits. Two consecutive rows conflict if a student is diagonally adjacent.",
        "dp[mask] = best total ending with this mask on the current row\nfor each row:\n    for each valid mask m:\n        for each previous mask pm:\n"
        "            if not (m & (pm << 1)) and not (m & (pm >> 1)): new[m] = max(new[m], dp[pm] + popcount(m))\nreturn max(dp)",
        "O(rows × 4^cols) = fine for 8 columns, and a classic bitmask DP.",
    ],
    time="O(m · 4^n)",
    space="O(2^n)",
    model=lambda seats: (
        lambda cells: max(
            len(c)
            for k in range(len(cells) + 1)
            for c in combinations(cells, k)
            if not any(
                (a[0] == b[0] and abs(a[1] - b[1]) == 1) or (abs(a[0] - b[0]) == 1 and abs(a[1] - b[1]) == 1)
                for a, b in combinations(c, 2)
            )
        )
    )([(i, j) for i, row in enumerate(seats) for j, ch in enumerate(row) if ch == "."]),
    java="""
        import java.util.*;

        class Solution {
            public int maxStudents(String[] seats) {
                int m = seats.length, n = seats[0].length();
                int[] dp = new int[1 << n];
                Arrays.fill(dp, -1);
                dp[0] = 0;
                for (int r = 0; r < m; r++) {
                    int good = 0;
                    for (int c = 0; c < n; c++) if (seats[r].charAt(c) == '.') good |= 1 << c;
                    int[] next = new int[1 << n];
                    Arrays.fill(next, -1);
                    for (int mask = 0; mask < (1 << n); mask++) {
                        if ((mask & ~good) != 0 || (mask & (mask << 1)) != 0) continue;
                        for (int prev = 0; prev < (1 << n); prev++) {
                            if (dp[prev] < 0 || (mask & (prev << 1)) != 0 || (mask & (prev >> 1)) != 0) continue;
                            next[mask] = Math.max(next[mask], dp[prev] + Integer.bitCount(mask));
                        }
                    }
                    dp = next;
                }
                int best = 0;
                for (int v : dp) best = Math.max(best, v);
                return best;
            }
        }
    """,
    tests=[
        {"seats": ["#.##.#", ".####.", "#.##.#"]},
        {"seats": [".#", "##", "#.", "##", ".#"]},
        {"seats": ["#...#", ".#.#.", "..#..", ".#.#.", "#...#"]},
    ],
    gen=lambda r: {
        "seats": [
            "".join(r.choice("..#") for _ in range(cols))
            for cols in [r.randint(1, 4)]
            for _ in range(r.randint(1, 3))
        ]
    },
)

P(
    slug="count-pickup-delivery",
    title="Count Valid Pickup/Delivery Orders",
    difficulty="hard",
    topics=["math", "dynamic-programming"],
    summary="Orderings of n pickups and deliveries where each delivery follows its pickup.",
    statement="""
        There are `n` orders, each with a pickup and a delivery. Count the sequences of all `2n` events where every
        delivery comes after its own pickup, modulo `10^9 + 7`.
    """,
    constraints=["1 <= n <= 500"],
    sig="int countOrders(int n)",
    hints=[
        "Insert order number n into a valid sequence of the first n - 1 orders.",
        "There are `2n - 1` slots for the pickup... count the ways to place both: `(2n - 1)(2n) / 2 = n(2n - 1)`.",
        "ways = 1\nfor i in 2..n:\n    ways = ways * i * (2*i - 1) % MOD\nreturn ways",
        "O(n). Equivalently (2n)! / 2^n, since each order's two events must be in one of their two possible orders.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda n: (__import__("math").factorial(2 * n) // 2**n) % MOD,
    java="""
        class Solution {
            public int countOrders(int n) {
                long ways = 1;
                for (int i = 2; i <= n; i++) ways = ways * i % 1_000_000_007 * (2L * i - 1) % 1_000_000_007;
                return (int) ways;
            }
        }
    """,
    tests=[{"n": 1}, {"n": 2}, {"n": 3}, {"n": 500}],
    gen=lambda r: {"n": r.randint(4, 200)},
)

P(
    slug="freedom-trail",
    title="Spell a Word on a Rotating Dial",
    difficulty="hard",
    topics=["dynamic-programming", "strings"],
    summary="Fewest rotations and presses to spell a key on a ring of letters.",
    statement="""
        `ring` is written around a dial; the letter at index 0 starts at the 12 o'clock position. To spell `key`, for each
        character rotate the ring one step at a time (either direction) until that character is at 12 o'clock, then
        press the button (one step). Return the minimum total steps. Every character of `key` is in `ring`.
    """,
    constraints=["1 <= ring.length, key.length <= 100", "lower-case letters"],
    sig="int findRotateSteps(String ring, String key)",
    hints=[
        "After spelling a character, where you are on the ring matters for the next one.",
        "dp over (position in key, current ring index): try every ring index holding the next character, paying the circular distance.",
        "dp = {0: 0}   # ring index -> cost\nfor c in key:\n    new = {}\n    for j where ring[j] == c:\n        new[j] = min(cost + circular distance(i, j) for i, cost in dp) + 1\n    dp = new\nreturn min(dp.values())",
        "O(len(key) × len(ring)^2) in the worst case. Circular distance is `min(|i - j|, n - |i - j|)`.",
    ],
    time="O(k · r^2)",
    space="O(r)",
    model=lambda ring, key: (
        lambda n: (lambda f: f(f, 0, 0))(
            lru_cache(None)(
                lambda f, i, pos: (
                    0
                    if i == len(key)
                    else min(
                        min(abs(pos - j), n - abs(pos - j)) + 1 + f(f, i + 1, j)
                        for j in range(n)
                        if ring[j] == key[i]
                    )
                )
            )
        )
    )(len(ring)),
    java="""
        import java.util.*;

        class Solution {
            public int findRotateSteps(String ring, String key) {
                int n = ring.length();
                int[] dp = new int[n];
                Arrays.fill(dp, Integer.MAX_VALUE);
                dp[0] = 0;
                for (char c : key.toCharArray()) {
                    int[] next = new int[n];
                    Arrays.fill(next, Integer.MAX_VALUE);
                    for (int j = 0; j < n; j++) {
                        if (ring.charAt(j) != c) continue;
                        for (int i = 0; i < n; i++) {
                            if (dp[i] == Integer.MAX_VALUE) continue;
                            int d = Math.abs(i - j);
                            next[j] = Math.min(next[j], dp[i] + Math.min(d, n - d) + 1);
                        }
                    }
                    dp = next;
                }
                int best = Integer.MAX_VALUE;
                for (int v : dp) best = Math.min(best, v);
                return best;
            }
        }
    """,
    tests=[
        {"ring": "godding", "key": "gd"},
        {"ring": "godding", "key": "godding"},
        {"ring": "a", "key": "aaa"},
    ],
    gen=lambda r: (
        lambda ring: {"ring": ring, "key": "".join(r.choice(ring) for _ in range(r.randint(1, 5)))}
    )(word(r, 1, 8, "abcd")),
)

P(
    slug="race-car",
    title="Race Car",
    difficulty="hard",
    topics=["dynamic-programming", "graphs"],
    summary="Shortest instruction sequence of A (accelerate) and R (reverse) to reach a target.",
    statement="""
        A car starts at position 0 with speed +1. Instruction `A`: position += speed, speed *= 2. Instruction `R`: speed
        becomes -1 if it was positive, otherwise +1 (position unchanged). Return the length of the shortest instruction
        sequence that ends with the car at position `target`.
    """,
    constraints=["1 <= target <= 10^4"],
    sig="int racecar(int target)",
    hints=[
        "The state is (position, speed), and each instruction is one step: think BFS.",
        "BFS over (position, speed), pruning positions far beyond the target (e.g. beyond 2 × target) and below a small negative bound.",
        "queue = [(0, 1)]; seen = {(0, 1)}; steps = 0\nwhile queue:\n    for each state in this level:\n        if pos == target: return steps\n"
        "        A: (pos + speed, speed * 2); R: (pos, -1 if speed > 0 else 1)\n        enqueue unseen states within bounds\n    steps += 1",
        "BFS finds the shortest sequence. A DP over targets (overshoot then reverse, or stop short and reverse twice) runs in O(T log T).",
    ],
    time="O(T log T)",
    space="O(T log T)",
    model=lambda target: (lambda f: f(f, [(0, 1)], {(0, 1)}, 0))(
        lambda f, frontier, seen, d: (
            d
            if any(p == target for p, _ in frontier)
            else (lambda nxt: f(f, nxt, seen | set(nxt), d + 1))(
                list(
                    {
                        s
                        for p, v in frontier
                        for s in ((p + v, v * 2), (p, -1 if v > 0 else 1))
                        if s not in seen and -2 * target - 2 <= s[0] <= 2 * target + 2
                    }
                )
            )
        )
    ),
    java="""
        import java.util.*;

        class Solution {
            public int racecar(int target) {
                Deque<int[]> queue = new ArrayDeque<>();
                Set<Long> seen = new HashSet<>();
                queue.add(new int[] {0, 1});
                seen.add(1L);
                for (int steps = 0; ; steps++) {
                    for (int k = queue.size(); k > 0; k--) {
                        int[] s = queue.poll();
                        if (s[0] == target) return steps;
                        int[][] nexts = {{s[0] + s[1], s[1] * 2}, {s[0], s[1] > 0 ? -1 : 1}};
                        for (int[] t : nexts) {
                            if (Math.abs(t[0]) > 2 * target + 2) continue;
                            long key = ((long) t[0] << 32) ^ (t[1] & 0xffffffffL);
                            if (seen.add(key)) queue.add(t);
                        }
                    }
                }
            }
        }
    """,
    tests=[{"target": 3}, {"target": 6}, {"target": 1}, {"target": 5}, {"target": 100}],
    gen=lambda r: {"target": r.randint(2, 60)},
)

P(
    slug="min-difficulty-job-schedule",
    title="Minimum Difficulty Job Schedule",
    difficulty="hard",
    topics=["dynamic-programming"],
    summary="Split ordered jobs across d days to minimize the sum of daily maximums.",
    statement="""
        Jobs must be done in order, at least one per day, over exactly `d` days. A day's difficulty is the hardest job
        done that day. Return the minimum total difficulty, or `-1` if there are fewer jobs than days.
    """,
    constraints=["1 <= jobs.length <= 300", "0 <= jobs[i] <= 1000", "1 <= d <= 10"],
    sig="int minDifficulty(int[] jobs, int d)",
    hints=[
        "Decide where each day ends.",
        "dp[k][i] = best total to finish the first i jobs in k days. The last day covers jobs j..i-1, costing their max.",
        "dp[0][0] = 0\nfor k in 1..d:\n    for i in k..n:\n        hardest = 0\n        for j from i-1 down to k-1:\n            hardest = max(hardest, jobs[j])\n            dp[k][i] = min(dp[k][i], dp[k-1][j] + hardest)\nreturn dp[d][n]",
        "O(d × n^2). Walking `j` backward lets you maintain the day's maximum incrementally.",
    ],
    time="O(d · n^2)",
    space="O(d · n)",
    model=lambda jobs, d: (
        -1
        if len(jobs) < d
        else min(
            sum(max(jobs[a:b]) for a, b in zip((0, *c), (*c, len(jobs)), strict=True))
            for c in combinations(range(1, len(jobs)), d - 1)
        )
    ),
    java="""
        import java.util.*;

        class Solution {
            public int minDifficulty(int[] jobs, int d) {
                int n = jobs.length;
                if (n < d) return -1;
                int[][] dp = new int[d + 1][n + 1];
                for (int[] row : dp) Arrays.fill(row, Integer.MAX_VALUE / 2);
                dp[0][0] = 0;
                for (int k = 1; k <= d; k++)
                    for (int i = k; i <= n; i++) {
                        int hardest = 0;
                        for (int j = i - 1; j >= k - 1; j--) {
                            hardest = Math.max(hardest, jobs[j]);
                            dp[k][i] = Math.min(dp[k][i], dp[k - 1][j] + hardest);
                        }
                    }
                return dp[d][n];
            }
        }
    """,
    tests=[
        {"jobs": [6, 5, 4, 3, 2, 1], "d": 2},
        {"jobs": [9, 9, 9], "d": 4},
        {"jobs": [1, 1, 1], "d": 3},
        {"jobs": [7, 1, 7, 1, 7, 1], "d": 3},
    ],
    gen=lambda r: {"jobs": ints(r, 1, 9, 0, 9), "d": r.randint(1, 4)},
)

P(
    slug="max-performance-team",
    title="Maximum Performance of a Team",
    difficulty="hard",
    topics=["heaps", "greedy", "sorting"],
    summary="Choose up to k engineers maximizing (sum of speeds) × (minimum efficiency).",
    statement="""
        Engineer `i` has `speed[i]` and `efficiency[i]`. A team's performance is the sum of its speeds times the
        minimum efficiency in the team. Choose at most `k` engineers (at least one) to maximize performance. Return it.
    """,
    constraints=["1 <= k <= n <= 10^5", "1 <= speed[i] <= 10^5", "1 <= efficiency[i] <= 10^8"],
    sig="long maxPerformance(int n, int[] speed, int[] efficiency, int k)",
    hints=[
        "Fix the engineer with the lowest efficiency in the team. Who else should join?",
        "Process engineers by decreasing efficiency. The current one sets the minimum; add the fastest k - 1 seen so far (a min-heap of speeds).",
        "sort by efficiency descending\nheap = []; total = best = 0\nfor speed, eff in engineers:\n    push speed; total += speed\n    if len(heap) > k: total -= pop min\n    best = max(best, total * eff)\nreturn best",
        "O(n log n). The product exceeds an int, so return a long.",
    ],
    time="O(n log n)",
    space="O(k)",
    model=lambda n, speed, efficiency, k: max(
        sum(speed[i] for i in c) * min(efficiency[i] for i in c)
        for size in range(1, k + 1)
        for c in combinations(range(n), size)
    ),
    java="""
        import java.util.*;

        class Solution {
            public long maxPerformance(int n, int[] speed, int[] efficiency, int k) {
                Integer[] order = new Integer[n];
                for (int i = 0; i < n; i++) order[i] = i;
                Arrays.sort(order, (a, b) -> Integer.compare(efficiency[b], efficiency[a]));
                PriorityQueue<Integer> heap = new PriorityQueue<>();
                long total = 0, best = 0;
                for (int i : order) {
                    heap.add(speed[i]);
                    total += speed[i];
                    if (heap.size() > k) total -= heap.poll();
                    best = Math.max(best, total * efficiency[i]);
                }
                return best;
            }
        }
    """,
    tests=[
        {"n": 6, "speed": [2, 10, 3, 1, 5, 8], "efficiency": [5, 4, 3, 9, 7, 2], "k": 2},
        {"n": 6, "speed": [2, 10, 3, 1, 5, 8], "efficiency": [5, 4, 3, 9, 7, 2], "k": 3},
        {"n": 1, "speed": [100000], "efficiency": [100000000], "k": 1},
    ],
    gen=lambda r: (
        lambda n: {
            "n": n,
            "speed": ints(r, n, n, 1, 20),
            "efficiency": ints(r, n, n, 1, 20),
            "k": r.randint(1, n),
        }
    )(r.randint(1, 7)),
)

P(
    slug="three-non-overlapping-subarrays",
    title="Three Non-Overlapping Subarrays With Max Sum",
    difficulty="hard",
    topics=["dynamic-programming", "prefix-sums", "sliding-window"],
    summary="Pick three disjoint windows of length k with the largest total.",
    statement="""
        Choose three non-overlapping subarrays of length `k` from `nums` with the largest total sum. Return their start
        indices in ascending order. If several choices tie, return the lexicographically smallest.
    """,
    constraints=["1 <= nums.length <= 2 * 10^4", "1 <= k <= nums.length / 3", "1 <= nums[i] < 2^16"],
    sig="int[] maxSumOfThreeSubarrays(int[] nums, int k)",
    hints=[
        "Fix the middle window; then you want the best window entirely to its left and the best entirely to its right.",
        "Precompute window sums, then `left[i]` = start of the best window ending by i, `right[i]` = best window starting at or after i (preferring smaller indices on ties).",
        "w = window sums\nleft[i] = argmax of w[0..i] (first best)\nright[i] = argmax of w[i..] (first best, scanning from the right with >=)\n"
        "for mid in k..len(w)-k-1:\n    a, c = left[mid - k], right[mid + k]\n    keep the best w[a] + w[mid] + w[c]\nreturn [a, mid, c]",
        "O(n) with prefix sums. The tie-breaking direction in `left` (strict >) and `right` (>=) is what yields the lexicographically smallest answer.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda nums, k: (
        lambda w: list(
            max(
                (
                    (a, b, c)
                    for a in range(len(w))
                    for b in range(a + k, len(w))
                    for c in range(b + k, len(w))
                ),
                key=lambda t: (w[t[0]] + w[t[1]] + w[t[2]], -t[0], -t[1], -t[2]),
            )
        )
    )([sum(nums[i : i + k]) for i in range(len(nums) - k + 1)]),
    java="""
        class Solution {
            public int[] maxSumOfThreeSubarrays(int[] nums, int k) {
                int m = nums.length - k + 1;
                int[] w = new int[m];
                int sum = 0;
                for (int i = 0; i < nums.length; i++) {
                    sum += nums[i];
                    if (i >= k) sum -= nums[i - k];
                    if (i >= k - 1) w[i - k + 1] = sum;
                }
                int[] left = new int[m], right = new int[m];
                for (int i = 0, best = 0; i < m; i++) { if (w[i] > w[best]) best = i; left[i] = best; }
                for (int i = m - 1, best = m - 1; i >= 0; i--) { if (w[i] >= w[best]) best = i; right[i] = best; }
                int[] ans = null;
                for (int mid = k; mid + k < m; mid++) {
                    int a = left[mid - k], c = right[mid + k];
                    if (ans == null || w[a] + w[mid] + w[c] > w[ans[0]] + w[ans[1]] + w[ans[2]]) ans = new int[] {a, mid, c};
                }
                return ans;
            }
        }
    """,
    tests=[
        {"nums": [1, 2, 1, 2, 6, 7, 5, 1], "k": 2},
        {"nums": [1, 2, 1, 2, 1, 2, 1, 2, 1], "k": 2},
        {"nums": [4, 5, 6], "k": 1},
    ],
    gen=lambda r: (lambda k: {"nums": ints(r, 3 * k, 3 * k + 6, 1, 6), "k": k})(r.randint(1, 3)),
)

P(
    slug="longest-duplicate-substring",
    title="Longest Repeated Substring",
    difficulty="hard",
    topics=["strings", "binary-search", "hash-maps"],
    summary="Length of the longest substring that appears at least twice.",
    statement="""
        Return the length of the longest substring that occurs at least twice in `s` (occurrences may overlap).
        Return `0` if no character repeats.
    """,
    constraints=["2 <= s.length <= 3 * 10^4", "lower-case letters"],
    sig="int longestDupSubstring(String s)",
    hints=[
        "If a repeated substring of length L exists, one of length L - 1 does too. That's binary-searchable.",
        "Binary search on L. For each L, check for a repeat with a rolling hash (Rabin-Karp) and a hash set (verify matches to rule out collisions).",
        "lo, hi = 0, n - 1\nwhile lo < hi:\n    mid = (lo + hi + 1) // 2\n    if hasRepeat(mid): lo = mid\n    else: hi = mid - 1\nreturn lo",
        "O(n log n) expected with rolling hashes. A suffix array gives the same answer deterministically.",
    ],
    time="O(n log n)",
    space="O(n)",
    model=lambda s: max(
        [0] + [j - i for i in range(len(s)) for j in range(i + 1, len(s) + 1) if s.find(s[i:j], i + 1) != -1]
    ),
    java="""
        import java.util.*;

        class Solution {
            private boolean hasRepeat(String s, int len) {
                if (len == 0) return true;
                long mod = 1_000_000_007L, base = 131, power = 1, h = 0;
                for (int i = 0; i < len; i++) power = power * base % mod;
                Map<Long, List<Integer>> seen = new HashMap<>();
                for (int i = 0; i < s.length(); i++) {
                    h = (h * base + s.charAt(i)) % mod;
                    if (i >= len) h = ((h - s.charAt(i - len) * power) % mod + mod) % mod;
                    if (i >= len - 1) {
                        int start = i - len + 1;
                        List<Integer> starts = seen.computeIfAbsent(h, k -> new ArrayList<>());
                        for (int other : starts) if (s.regionMatches(other, s, start, len)) return true;
                        starts.add(start);
                    }
                }
                return false;
            }
            public int longestDupSubstring(String s) {
                int lo = 0, hi = s.length() - 1;
                while (lo < hi) {
                    int mid = (lo + hi + 1) / 2;
                    if (hasRepeat(s, mid)) lo = mid; else hi = mid - 1;
                }
                return lo;
            }
        }
    """,
    tests=[{"s": "banana"}, {"s": "abcd"}, {"s": "aaaaa"}, {"s": "abcabcab"}],
    gen=lambda r: {"s": word(r, 2, 14, "ab")},
)

P(
    slug="scramble-string",
    title="Scramble String",
    difficulty="hard",
    topics=["dynamic-programming", "recursion", "strings"],
    summary="Can one string be scrambled into another by recursive split-and-swap?",
    statement="""
        To scramble a string of length > 1, split it into two non-empty parts at any point, optionally swap the two
        parts, and scramble each part recursively. Return `true` if `s2` is a scrambled form of `s1`.
    """,
    constraints=["1 <= s1.length == s2.length <= 30", "lower-case letters"],
    sig="boolean isScramble(String s1, String s2)",
    hints=[
        "Try every split point, with and without the swap.",
        "s1 = a + b matches s2 if (a ~ s2's same-length prefix and b ~ the rest) or (a ~ s2's same-length suffix and b ~ the rest).",
        "def scr(x, y):\n    if x == y: return true\n    if sorted(x) != sorted(y): return false\n    for i in 1..len-1:\n"
        "        if scr(x[:i], y[:i]) and scr(x[i:], y[i:]): return true\n        if scr(x[:i], y[-i:]) and scr(x[i:], y[:-i]): return true\n    return false",
        "Memoizing on (x, y) (or on index triples) gives O(n^4). The sorted-letters check prunes most branches early.",
    ],
    time="O(n^4)",
    space="O(n^3)",
    model=lambda s1, s2: (lambda f: f(f, s1, s2))(
        lru_cache(None)(
            lambda f, x, y: (
                x == y
                or (
                    sorted(x) == sorted(y)
                    and any(
                        (f(f, x[:i], y[:i]) and f(f, x[i:], y[i:]))
                        or (f(f, x[:i], y[-i:]) and f(f, x[i:], y[:-i]))
                        for i in range(1, len(x))
                    )
                )
            )
        )
    ),
    java="""
        import java.util.*;

        class Solution {
            private Map<String, Boolean> memo = new HashMap<>();
            public boolean isScramble(String x, String y) {
                if (x.equals(y)) return true;
                String key = x + "#" + y;
                Boolean cached = memo.get(key);
                if (cached != null) return cached;
                char[] a = x.toCharArray(), b = y.toCharArray();
                Arrays.sort(a);
                Arrays.sort(b);
                boolean result = false;
                if (Arrays.equals(a, b)) {
                    int n = x.length();
                    for (int i = 1; i < n && !result; i++)
                        result = (isScramble(x.substring(0, i), y.substring(0, i)) && isScramble(x.substring(i), y.substring(i)))
                            || (isScramble(x.substring(0, i), y.substring(n - i)) && isScramble(x.substring(i), y.substring(0, n - i)));
                }
                memo.put(key, result);
                return result;
            }
        }
    """,
    tests=[
        {"s1": "great", "s2": "rgeat"},
        {"s1": "abcde", "s2": "caebd"},
        {"s1": "a", "s2": "a"},
        {"s1": "abc", "s2": "bca"},
    ],
    gen=lambda r: (lambda s: {"s1": s, "s2": "".join(r.sample(s, len(s)))})(word(r, 1, 7, "abc")),
)

P(
    slug="min-removals-valid-parentheses",
    title="Fewest Removals for Valid Parentheses",
    difficulty="hard",
    topics=["strings", "stacks", "greedy"],
    summary="Remove the fewest brackets so the string is balanced.",
    statement="""
        `s` contains `(`, `)` and lower-case letters. Return the minimum number of brackets to remove so the result is
        a valid parentheses string (letters are always fine).
    """,
    constraints=["1 <= s.length <= 10^5"],
    sig="int minRemovals(String s)",
    hints=[
        "Scan left to right, tracking unmatched open brackets.",
        "A `)` with no open bracket to match must be removed. Any `(` still open at the end must be removed too.",
        "open = removals = 0\nfor c in s:\n    if c == '(': open += 1\n    elif c == ')':\n        if open: open -= 1\n        else: removals += 1\nreturn removals + open",
        "One pass, O(n), O(1) space. (Listing every way to remove them is the harder variant that needs BFS or backtracking.)",
    ],
    time="O(n)",
    space="O(1)",
    model=_min_removals,
    java="""
        class Solution {
            public int minRemovals(String s) {
                int open = 0, removals = 0;
                for (char c : s.toCharArray()) {
                    if (c == '(') open++;
                    else if (c == ')') { if (open > 0) open--; else removals++; }
                }
                return removals + open;
            }
        }
    """,
    tests=[{"s": "()())()"}, {"s": "(a)())()"}, {"s": ")("}, {"s": "abc"}],
    gen=lambda r: {"s": word(r, 1, 10, "()a")},
)

P(
    slug="count-vowel-strings",
    title="Count Vowel Chains",
    difficulty="hard",
    topics=["dynamic-programming", "math"],
    summary="Count length-n strings of vowels obeying follow-up rules.",
    statement="""
        Count strings of length `n` made of `a, e, i, o, u` where: `a` may only be followed by `e`; `e` by `a` or `i`;
        `i` by anything except `i`; `o` by `i` or `u`; `u` by `a`. Return the count modulo `10^9 + 7`.
    """,
    constraints=["1 <= n <= 2 * 10^4"],
    sig="int countVowelPermutation(int n)",
    hints=[
        "Track how many valid strings end with each vowel.",
        "Turn the rules around: a new string ending in `a` comes from strings ending in `e`, `i` or `u`, and so on.",
        "a = e = i = o = u = 1\nrepeat n - 1 times:\n    a, e, i, o, u = e + i + u, a + i, e + o, i, i + o\nreturn (a + e + i + o + u) % MOD",
        "Five counters updated n times: O(n) time, O(1) space.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda n: (
        sum(
            1
            for t in product("aeiou", repeat=n)
            if all(
                b in {"a": "e", "e": "ai", "i": "aeou", "o": "iu", "u": "a"}[a]
                for a, b in zip(t, t[1:], strict=False)
            )
        )
        % MOD
        if n <= 7
        else None
    ),
    java="""
        class Solution {
            public int countVowelPermutation(int n) {
                long M = 1_000_000_007, a = 1, e = 1, i = 1, o = 1, u = 1;
                for (int k = 1; k < n; k++) {
                    long na = (e + i + u) % M, ne = (a + i) % M, ni = (e + o) % M, no = i, nu = (i + o) % M;
                    a = na; e = ne; i = ni; o = no; u = nu;
                }
                return (int) ((a + e + i + o + u) % M);
            }
        }
    """,
    tests=[{"n": 1}, {"n": 2}, {"n": 5}, {"n": 7}],
    gen=lambda r: {"n": r.randint(3, 6)},
    gen_count=2,
)

P(
    slug="min-insertions-palindrome",
    title="Fewest Insertions to Make a Palindrome",
    difficulty="hard",
    topics=["dynamic-programming", "strings"],
    summary="Insert the fewest characters anywhere to make a palindrome.",
    statement="""
        In one step you can insert any character anywhere in `s`. Return the minimum number of steps to make `s` a palindrome.
    """,
    constraints=["1 <= s.length <= 500", "lower-case letters"],
    sig="int minInsertions(String s)",
    hints=[
        "Characters that already pair up don't need help. Which ones do?",
        "The answer is `n - LPS`, where LPS is the longest palindromic subsequence (= LCS of `s` and its reverse).",
        "dp[i][j] = min insertions for s[i..j]\nif s[i] == s[j]: dp[i][j] = dp[i+1][j-1]\nelse: dp[i][j] = 1 + min(dp[i+1][j], dp[i][j-1])\nreturn dp[0][n-1]",
        "Interval DP, O(n^2) time and O(n^2) (or O(n)) space.",
    ],
    time="O(n^2)",
    space="O(n^2)",
    model=lambda s: (lambda f: f(f, s))(
        lru_cache(None)(
            lambda f, t: (
                0 if len(t) <= 1 else f(f, t[1:-1]) if t[0] == t[-1] else 1 + min(f(f, t[1:]), f(f, t[:-1]))
            )
        )
    ),
    java="""
        class Solution {
            public int minInsertions(String s) {
                int n = s.length();
                int[][] dp = new int[n][n];
                for (int i = n - 2; i >= 0; i--)
                    for (int j = i + 1; j < n; j++)
                        dp[i][j] = s.charAt(i) == s.charAt(j) ? dp[i + 1][j - 1] : 1 + Math.min(dp[i + 1][j], dp[i][j - 1]);
                return dp[0][n - 1];
            }
        }
    """,
    tests=[{"s": "zzazz"}, {"s": "mbadm"}, {"s": "leetcode"}, {"s": "a"}],
    gen=lambda r: {"s": word(r, 1, 10, "abc")},
)

P(
    slug="arithmetic-subsequences",
    title="Count Arithmetic Subsequences",
    difficulty="hard",
    topics=["dynamic-programming", "hash-maps"],
    summary="Count subsequences of length 3+ with a constant difference.",
    statement="""
        Return the number of subsequences of `nums` (by index positions) with at least three elements where every pair of
        consecutive elements has the same difference. The answer fits in an int.
    """,
    constraints=["1 <= nums.length <= 1000", "-2^31 <= nums[i] <= 2^31 - 1"],
    sig="int numberOfArithmeticSlices(int[] nums)",
    hints=[
        'Count "weak" arithmetic subsequences of length 2+ ending at each index, grouped by difference.',
        "dp[i][d] = number of subsequences of length ≥ 2 ending at i with difference d. Extending one that ends at j adds dp[j][d] to the answer (those become length ≥ 3).",
        "for i in range(n):\n    for j in range(i):\n        d = nums[i] - nums[j]\n        count = dp[j].get(d, 0)\n        answer += count\n        dp[i][d] += count + 1\nreturn answer",
        "O(n^2) time with hash maps per index. Use long for the difference: it can overflow an int.",
    ],
    time="O(n^2)",
    space="O(n^2)",
    model=lambda nums: sum(
        1
        for k in range(3, len(nums) + 1)
        for c in combinations(nums, k)
        if len({c[i + 1] - c[i] for i in range(k - 1)}) == 1
    ),
    java="""
        import java.util.*;

        class Solution {
            public int numberOfArithmeticSlices(int[] nums) {
                int n = nums.length;
                List<Map<Long, Integer>> dp = new ArrayList<>();
                long answer = 0;
                for (int i = 0; i < n; i++) {
                    dp.add(new HashMap<>());
                    for (int j = 0; j < i; j++) {
                        long d = (long) nums[i] - nums[j];
                        int count = dp.get(j).getOrDefault(d, 0);
                        answer += count;
                        dp.get(i).merge(d, count + 1, Integer::sum);
                    }
                }
                return (int) answer;
            }
        }
    """,
    tests=[
        {"nums": [2, 4, 6, 8, 10]},
        {"nums": [7, 7, 7, 7, 7]},
        {"nums": [1, 2]},
        {"nums": [1, 3, 5, 2, 4, 6]},
    ],
    gen=lambda r: {"nums": ints(r, 1, 10, 0, 6)},
)

P(
    slug="frog-jump",
    title="Frog Crossing the River",
    difficulty="hard",
    topics=["dynamic-programming", "hash-maps"],
    summary="Can a frog cross on stones if each jump is k-1, k or k+1 units?",
    statement="""
        `stones` gives sorted stone positions, starting with `0`. The frog starts on the first stone and its first jump
        must be 1 unit. If its last jump was `k` units, the next must be `k - 1`, `k` or `k + 1` (and forward). Return
        `true` if it can reach the last stone.
    """,
    constraints=["2 <= stones.length <= 2000", "stones[0] == 0, strictly increasing"],
    sig="boolean canCross(int[] stones)",
    hints=[
        "The state is (stone, last jump length).",
        "For each stone keep the set of jump lengths that can land on it, and push each forward with k-1, k, k+1.",
        "jumps = {stone: set() for stone in stones}; jumps[0] = {0}\nfor s in stones:\n    for k in jumps[s]:\n        for step in (k - 1, k, k + 1):\n"
        "            if step > 0 and s + step in jumps: jumps[s + step].add(step)\nreturn len(jumps[last]) > 0",
        "At most n jump sizes per stone: O(n^2) time and space. Starting with jump size 0 makes the first jump 1.",
    ],
    time="O(n^2)",
    space="O(n^2)",
    model=lambda stones: (
        lambda pos: (lambda f: f(f, 0, 0))(
            lru_cache(None)(
                lambda f, s, k: (
                    s == stones[-1]
                    or any(
                        step > 0 and s + step in pos and f(f, s + step, step) for step in (k - 1, k, k + 1)
                    )
                )
            )
        )
    )(set(stones)),
    java="""
        import java.util.*;

        class Solution {
            public boolean canCross(int[] stones) {
                Map<Integer, Set<Integer>> jumps = new HashMap<>();
                for (int s : stones) jumps.put(s, new HashSet<>());
                jumps.get(0).add(0);
                for (int s : stones)
                    for (int k : jumps.get(s))
                        for (int step = k - 1; step <= k + 1; step++)
                            if (step > 0 && jumps.containsKey(s + step)) jumps.get(s + step).add(step);
                return !jumps.get(stones[stones.length - 1]).isEmpty();
            }
        }
    """,
    tests=[
        {"stones": [0, 1, 3, 5, 6, 8, 12, 17]},
        {"stones": [0, 1, 2, 3, 4, 8, 9, 11]},
        {"stones": [0, 2]},
        {"stones": [0, 1]},
    ],
    gen=lambda r: {"stones": [0] + sorted(r.sample(range(1, 20), r.randint(1, 8)))},
)

P(
    slug="min-swaps-increasing",
    title="Swaps to Make Two Sequences Increasing",
    difficulty="hard",
    topics=["dynamic-programming"],
    summary="Swap a[i] and b[i] at some positions so both arrays strictly increase.",
    statement="""
        `a` and `b` have the same length. You may swap `a[i]` with `b[i]` at any positions. Return the minimum number of
        swaps so that both arrays are strictly increasing. The input guarantees it's possible.
    """,
    constraints=["2 <= n <= 10^5", "it is always possible"],
    sig="int minSwap(int[] a, int[] b)",
    hints=[
        "At each index you either swap or don't, and only the previous index's choice matters.",
        "Keep `keep` = min swaps if index i is not swapped, `swap` = if it is. Update from the previous pair based on which orderings are valid.",
        "keep, swap = 0, 1\nfor i in 1..n-1:\n    nk = ns = inf\n    if a[i-1] < a[i] and b[i-1] < b[i]: nk = keep; ns = swap + 1\n"
        "    if a[i-1] < b[i] and b[i-1] < a[i]: nk = min(nk, swap); ns = min(ns, keep + 1)\n    keep, swap = nk, ns\nreturn min(keep, swap)",
        "Two-state DP: O(n) time, O(1) space.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda a, b: min(
        bin(mask).count("1")
        for mask in range(1 << len(a))
        if (
            lambda x, y: (
                all(x[i] < x[i + 1] for i in range(len(x) - 1))
                and all(y[i] < y[i + 1] for i in range(len(y) - 1))
            )
        )(
            [b[i] if mask >> i & 1 else a[i] for i in range(len(a))],
            [a[i] if mask >> i & 1 else b[i] for i in range(len(a))],
        )
    ),
    java="""
        class Solution {
            public int minSwap(int[] a, int[] b) {
                int keep = 0, swap = 1;
                for (int i = 1; i < a.length; i++) {
                    int nk = Integer.MAX_VALUE, ns = Integer.MAX_VALUE;
                    if (a[i - 1] < a[i] && b[i - 1] < b[i]) { nk = keep; ns = swap + 1; }
                    if (a[i - 1] < b[i] && b[i - 1] < a[i]) { nk = Math.min(nk, swap); ns = Math.min(ns, keep + 1); }
                    keep = nk;
                    swap = ns;
                }
                return Math.min(keep, swap);
            }
        }
    """,
    tests=[
        {"a": [1, 3, 5, 4], "b": [1, 2, 3, 7]},
        {"a": [0, 3, 5, 8, 9], "b": [2, 1, 4, 6, 9]},
        {"a": [1, 2], "b": [3, 4]},
    ],
    gen=lambda r: (
        lambda pairs: (
            lambda swaps: {
                "a": [q if s else p for (p, q), s in zip(pairs, swaps, strict=True)],
                "b": [p if s else q for (p, q), s in zip(pairs, swaps, strict=True)],
            }
        )([r.random() < 0.5 for _ in pairs])
    )([(2 * i + r.randint(0, 1), 2 * i + r.randint(0, 1) + 10 * 0) for i in range(r.randint(2, 8))]),
)

P(
    slug="best-team-no-conflicts",
    title="Best Team With No Conflicts",
    difficulty="hard",
    topics=["dynamic-programming", "sorting"],
    summary="Highest total score with no younger player outscoring an older one.",
    statement="""
        Player `i` has `scores[i]` and `ages[i]`. A team has a conflict if a younger player has a strictly higher score
        than an older player (players of the same age never conflict). Return the highest total score of a team with
        no conflicts.
    """,
    constraints=["1 <= n <= 1000", "1 <= scores[i] <= 10^6", "1 <= ages[i] <= 1000"],
    sig="int bestTeamScore(int[] scores, int[] ages)",
    hints=[
        "Sort players so that a valid team appears as a non-decreasing sequence.",
        "Sort by (age, score). Then a team is valid exactly when its scores are non-decreasing: a max-sum non-decreasing subsequence.",
        "sort players by (age, score)\nfor i in range(n):\n    best[i] = score[i] + max(best[j] for j < i if score[j] <= score[i], default 0)\nreturn max(best)",
        "O(n^2) DP after sorting (O(n log n) with a Fenwick tree over scores).",
    ],
    time="O(n^2)",
    space="O(n)",
    model=lambda scores, ages: max(
        sum(scores[i] for i in c)
        for k in range(1, len(scores) + 1)
        for c in combinations(range(len(scores)), k)
        if not any(ages[i] < ages[j] and scores[i] > scores[j] for i in c for j in c)
    ),
    java="""
        import java.util.*;

        class Solution {
            public int bestTeamScore(int[] scores, int[] ages) {
                int n = scores.length;
                Integer[] order = new Integer[n];
                for (int i = 0; i < n; i++) order[i] = i;
                Arrays.sort(order, (x, y) -> ages[x] != ages[y] ? Integer.compare(ages[x], ages[y]) : Integer.compare(scores[x], scores[y]));
                int[] best = new int[n];
                int answer = 0;
                for (int i = 0; i < n; i++) {
                    int si = scores[order[i]];
                    best[i] = si;
                    for (int j = 0; j < i; j++) if (scores[order[j]] <= si) best[i] = Math.max(best[i], best[j] + si);
                    answer = Math.max(answer, best[i]);
                }
                return answer;
            }
        }
    """,
    tests=[
        {"scores": [1, 3, 5, 10, 15], "ages": [1, 2, 3, 4, 5]},
        {"scores": [4, 5, 6, 5], "ages": [2, 1, 2, 1]},
        {"scores": [1, 2, 3, 5], "ages": [8, 9, 10, 1]},
    ],
    gen=lambda r: (lambda n: {"scores": ints(r, n, n, 1, 9), "ages": ints(r, n, n, 1, 5)})(r.randint(1, 8)),
)

P(
    slug="parallel-courses-two",
    title="Fewest Semesters With a Course Limit",
    difficulty="hard",
    topics=["dynamic-programming", "bit-manipulation", "graphs"],
    summary="Schedule courses with prerequisites, at most k per semester, in the fewest semesters.",
    statement="""
        Courses are `1..n`. `relations[i] = [a, b]` means course `a` must be finished in an earlier semester than course
        `b`. You can take at most `k` courses per semester. Return the minimum number of semesters to finish all courses.
        The prerequisites contain no cycles.
    """,
    constraints=["1 <= n <= 12", "1 <= k <= n"],
    sig="int minNumberOfSemesters(int n, int[][] relations, int k)",
    hints=[
        "Greedy choices (like taking the courses with the most dependents) can fail. With n ≤ 12, search over sets of finished courses.",
        "BFS over bitmasks of finished courses. From a mask, the available courses are those whose prerequisites are all in it; take any subset of size ≤ k (or all of them if fewer).",
        "pre[c] = mask of prerequisites\ndist[0] = 0; BFS over masks:\n    avail = courses not in mask whose pre ⊆ mask\n    for each subset s of avail with popcount ≤ k (or s = avail if it fits):\n        visit mask | s",
        "Up to 2^n states with subset enumeration: about O(3^n), fine for n = 12.",
    ],
    time="O(3^n)",
    space="O(2^n)",
    model=lambda n, relations, k: (
        lambda pre: (lambda f: f(f, {0}, 0))(
            lambda f, frontier, d: (
                d
                if (1 << n) - 1 in frontier
                else f(
                    f,
                    {
                        mask | sum(1 << c for c in pick)
                        for mask in frontier
                        for avail in [[c for c in range(n) if not mask >> c & 1 and pre[c] & mask == pre[c]]]
                        for size in range(1, min(k, len(avail)) + 1)
                        for pick in combinations(avail, size)
                    },
                    d + 1,
                )
            )
        )
    )([sum(1 << (a - 1) for a, b in relations if b - 1 == c) for c in range(n)]),
    java="""
        import java.util.*;

        class Solution {
            public int minNumberOfSemesters(int n, int[][] relations, int k) {
                int[] pre = new int[n];
                for (int[] r : relations) pre[r[1] - 1] |= 1 << (r[0] - 1);
                int full = (1 << n) - 1;
                int[] dist = new int[1 << n];
                Arrays.fill(dist, -1);
                dist[0] = 0;
                Deque<Integer> queue = new ArrayDeque<>(List.of(0));
                while (!queue.isEmpty()) {
                    int mask = queue.poll();
                    if (mask == full) return dist[mask];
                    int avail = 0;
                    for (int c = 0; c < n; c++) if ((mask >> c & 1) == 0 && (pre[c] & mask) == pre[c]) avail |= 1 << c;
                    for (int s = avail; s > 0; s = (s - 1) & avail) {
                        if (Integer.bitCount(s) > k) continue;
                        int next = mask | s;
                        if (dist[next] == -1) { dist[next] = dist[mask] + 1; queue.add(next); }
                    }
                }
                return -1;
            }
        }
    """,
    tests=[
        {"n": 4, "relations": [[2, 1], [3, 1], [1, 4]], "k": 2},
        {"n": 5, "relations": [[2, 1], [3, 1], [4, 1], [1, 5]], "k": 2},
        {"n": 3, "relations": [], "k": 1},
        {"n": 6, "relations": [[1, 4], [2, 4], [3, 5], [4, 6]], "k": 2},
    ],
    gen=lambda r: (
        lambda n: {
            "n": n,
            "relations": [
                [a, b]
                for a, b in r.sample(
                    [(a, b) for a in range(1, n + 1) for b in range(a + 1, n + 1)],
                    min(n * (n - 1) // 2, r.randint(0, n)),
                )
            ],
            "k": r.randint(1, n),
        }
    )(r.randint(1, 6)),
)

P(
    slug="minimum-xor-sum",
    title="Minimum XOR Sum of Two Arrays",
    difficulty="hard",
    topics=["dynamic-programming", "bit-manipulation"],
    summary="Rearrange one array to minimize the sum of pairwise XORs.",
    statement="""
        Rearrange `b` (any permutation) to minimize `(a[0] XOR b[0]) + (a[1] XOR b[1]) + ...`. Return the minimum sum.
    """,
    constraints=["1 <= n <= 14", "0 <= values <= 10^7"],
    sig="int minimumXORSum(int[] a, int[] b)",
    hints=[
        "Trying all n! permutations is too slow for n = 14. What do you need to remember after assigning the first i elements of a?",
        "Only which elements of b are used: a bitmask. The number of set bits tells you which index of a comes next.",
        "dp = [inf] * 2^n; dp[0] = 0\nfor mask in range(2^n):\n    i = popcount(mask)\n    for j not in mask:\n        dp[mask | 1<<j] = min(.., dp[mask] + (a[i] ^ b[j]))\nreturn dp[full]",
        "O(n × 2^n) — the standard bitmask DP for assignment problems.",
    ],
    time="O(n · 2^n)",
    space="O(2^n)",
    model=lambda a, b: min(sum(x ^ y for x, y in zip(a, p, strict=True)) for p in permutations(b)),
    java="""
        import java.util.*;

        class Solution {
            public int minimumXORSum(int[] a, int[] b) {
                int n = a.length;
                int[] dp = new int[1 << n];
                Arrays.fill(dp, Integer.MAX_VALUE);
                dp[0] = 0;
                for (int mask = 0; mask < (1 << n); mask++) {
                    if (dp[mask] == Integer.MAX_VALUE) continue;
                    int i = Integer.bitCount(mask);
                    if (i == n) continue;
                    for (int j = 0; j < n; j++)
                        if ((mask >> j & 1) == 0) dp[mask | 1 << j] = Math.min(dp[mask | 1 << j], dp[mask] + (a[i] ^ b[j]));
                }
                return dp[(1 << n) - 1];
            }
        }
    """,
    tests=[{"a": [1, 2], "b": [2, 3]}, {"a": [1, 0, 3], "b": [5, 3, 4]}, {"a": [7], "b": [7]}],
    gen=lambda r: (lambda n: {"a": ints(r, n, n, 0, 15), "b": ints(r, n, n, 0, 15)})(r.randint(1, 6)),
)

P(
    slug="ways-to-stay-in-place",
    title="Ways to Return to the Start",
    difficulty="hard",
    topics=["dynamic-programming"],
    summary="Count step sequences that end back at index 0.",
    statement="""
        A pointer starts at index 0 of an array of length `arrLen`. Each step it moves left, moves right, or stays,
        never leaving the array. Return the number of ways to be back at index 0 after exactly `steps` steps, modulo
        `10^9 + 7`.
    """,
    constraints=["1 <= steps <= 500", "1 <= arrLen <= 10^6"],
    sig="int numWays(int steps, int arrLen)",
    hints=[
        "You can never get further than steps / 2 from the start and still come back.",
        "dp[pos] = ways to be at `pos` after the current number of steps; each step adds from pos - 1, pos and pos + 1.",
        "limit = min(arrLen, steps // 2 + 1)\ndp = [1] + [0]*(limit - 1)\nrepeat steps times:\n    new[p] = dp[p] + dp[p-1] + dp[p+1] (within bounds)\n    dp = new\nreturn dp[0]",
        "O(steps × min(arrLen, steps)) time. Capping the positions is what makes huge `arrLen` values fine.",
    ],
    time="O(s · min(s, L))",
    space="O(min(s, L))",
    model=lambda steps, arrLen: (
        (lambda f: f(f, 0, steps))(
            lru_cache(None)(
                lambda f, pos, left: (
                    (1 if pos == 0 else 0)
                    if left == 0
                    else sum(
                        f(f, q, left - 1) for q in (pos - 1, pos, pos + 1) if 0 <= q < arrLen and q <= left
                    )
                )
            )
        )
        % MOD
    ),
    java="""
        class Solution {
            public int numWays(int steps, int arrLen) {
                int limit = Math.min(arrLen, steps / 2 + 1);
                long[] dp = new long[limit];
                dp[0] = 1;
                for (int s = 0; s < steps; s++) {
                    long[] next = new long[limit];
                    for (int p = 0; p < limit; p++) {
                        long v = dp[p];
                        if (p > 0) v += dp[p - 1];
                        if (p + 1 < limit) v += dp[p + 1];
                        next[p] = v % 1_000_000_007;
                    }
                    dp = next;
                }
                return (int) dp[0];
            }
        }
    """,
    tests=[
        {"steps": 3, "arrLen": 2},
        {"steps": 2, "arrLen": 4},
        {"steps": 4, "arrLen": 2},
        {"steps": 27, "arrLen": 7},
    ],
    gen=lambda r: {"steps": r.randint(1, 30), "arrLen": r.randint(1, 1000000)},
)
