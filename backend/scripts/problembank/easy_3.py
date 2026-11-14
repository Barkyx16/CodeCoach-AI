"""Easy problems, part 3: two pointers, searching, matrices and simulation."""

import bisect

from scripts.problembank import P, grid, ints

P(
    slug="stock-profit-once",
    title="Best Time to Buy and Sell Once",
    difficulty="easy",
    topics=["arrays", "greedy"],
    summary="Buy one day, sell a later day, maximize the profit.",
    statement="""
        `prices[i]` is a stock's price on day `i`. Choose one day to buy and a later day to sell.
        Return the largest possible profit, or `0` if no profit is possible.
    """,
    constraints=["1 <= prices.length <= 10^5", "0 <= prices[i] <= 10^4"],
    sig="int maxProfit(int[] prices)",
    hints=[
        "For each selling day, the best buy is the cheapest price seen before it.",
        "Track the minimum price so far and the best profit so far in one pass.",
        "low = infinity\nbest = 0\nfor p in prices:\n    low = min(low, p)\n    best = max(best, p - low)\nreturn best",
        "One pass, O(n) time and O(1) space, versus O(n^2) for trying every pair of days.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda prices: max(
        [0] + [prices[j] - prices[i] for i in range(len(prices)) for j in range(i + 1, len(prices))]
    ),
    java="""
        class Solution {
            public int maxProfit(int[] prices) {
                int low = Integer.MAX_VALUE, best = 0;
                for (int p : prices) { low = Math.min(low, p); best = Math.max(best, p - low); }
                return best;
            }
        }
    """,
    tests=[
        {"prices": [7, 1, 5, 3, 6, 4]},
        {"prices": [7, 6, 4, 3, 1]},
        {"prices": [5]},
        {"prices": [2, 4, 1, 7]},
    ],
    gen=lambda r: {"prices": ints(r, 1, 30, 0, 50)},
    explain={0: "Buy at 1, sell at 6."},
)

P(
    slug="stock-profit-many",
    title="Buy and Sell Many Times",
    difficulty="easy",
    topics=["arrays", "greedy"],
    summary="Trade as often as you like; maximize total profit.",
    statement="""
        `prices[i]` is the price on day `i`. You may buy and sell many times, but hold at most one share
        at a time. Return the maximum total profit.
    """,
    constraints=["1 <= prices.length <= 3 * 10^4", "0 <= prices[i] <= 10^4"],
    sig="int maxProfitMany(int[] prices)",
    hints=[
        "Think about every day-to-day price rise.",
        "Collecting every positive difference `prices[i] - prices[i-1]` equals the best trading plan.",
        "profit = 0\nfor i in 1..n-1:\n    if prices[i] > prices[i-1]: profit += prices[i] - prices[i-1]\nreturn profit",
        "Any rising stretch's profit is the sum of its daily rises, so summing all rises is optimal. O(n).",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda prices: sum(max(0, b - a) for a, b in zip(prices, prices[1:], strict=False)),
    java="""
        class Solution {
            public int maxProfitMany(int[] prices) {
                int profit = 0;
                for (int i = 1; i < prices.length; i++) if (prices[i] > prices[i - 1]) profit += prices[i] - prices[i - 1];
                return profit;
            }
        }
    """,
    tests=[{"prices": [7, 1, 5, 3, 6, 4]}, {"prices": [1, 2, 3, 4, 5]}, {"prices": [7, 6, 4, 3, 1]}],
    gen=lambda r: {"prices": ints(r, 1, 30, 0, 50)},
)

P(
    slug="nearby-duplicate",
    title="Duplicate Within k",
    difficulty="easy",
    topics=["arrays", "hash-maps", "sliding-window"],
    summary="Are two equal values at most k positions apart?",
    statement="""
        Return `true` if there are two different indices `i` and `j` with `nums[i] == nums[j]` and
        `|i - j| <= k`.
    """,
    constraints=["1 <= nums.length <= 10^5", "0 <= k <= 10^5"],
    sig="boolean containsNearbyDuplicate(int[] nums, int k)",
    hints=[
        "For each value, which earlier occurrence matters most?",
        "Remember the last index where each value appeared.",
        "last = {}\nfor i, x in enumerate(nums):\n    if x in last and i - last[x] <= k: return true\n    last[x] = i\nreturn false",
        "Only the most recent occurrence can be closest, so a map of last indices gives O(n) time.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda nums, k: any(
        nums[i] == nums[j] for i in range(len(nums)) for j in range(i + 1, min(len(nums), i + k + 1))
    ),
    java="""
        import java.util.*;

        class Solution {
            public boolean containsNearbyDuplicate(int[] nums, int k) {
                Map<Integer, Integer> last = new HashMap<>();
                for (int i = 0; i < nums.length; i++) {
                    Integer prev = last.put(nums[i], i);
                    if (prev != null && i - prev <= k) return true;
                }
                return false;
            }
        }
    """,
    tests=[
        {"nums": [1, 2, 3, 1], "k": 3},
        {"nums": [1, 0, 1, 1], "k": 1},
        {"nums": [1, 2, 3, 1, 2, 3], "k": 2},
        {"nums": [5], "k": 0},
    ],
    gen=lambda r: {"nums": ints(r, 1, 20, 0, 8), "k": r.randint(0, 5)},
)

P(
    slug="two-sum-sorted",
    title="Two Sum in a Sorted Array",
    difficulty="easy",
    topics=["arrays", "two-pointers"],
    summary="Find two values that add up to a target in a sorted array.",
    statement="""
        `nums` is sorted in non-decreasing order. Return the 1-based indices `[i, j]` (`i < j`) of the
        two values that add up to `target`. Exactly one answer exists. Use O(1) extra space.
    """,
    constraints=["2 <= nums.length <= 3 * 10^4", "exactly one solution"],
    sig="int[] twoSumSorted(int[] nums, int target)",
    hints=[
        "Sorting gives you information about which way to move.",
        "Start one pointer at each end. If the sum is too small, move the left pointer right; too big, move the right one left.",
        "i, j = 0, n-1\nwhile True:\n    s = nums[i] + nums[j]\n    if s == target: return [i+1, j+1]\n    if s < target: i += 1\n    else: j -= 1",
        "Each step rules out one value for good, so it's O(n) time with O(1) space.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda nums, target: next(
        [i + 1, j + 1]
        for i in range(len(nums))
        for j in range(i + 1, len(nums))
        if nums[i] + nums[j] == target
    ),
    java="""
        class Solution {
            public int[] twoSumSorted(int[] nums, int target) {
                int i = 0, j = nums.length - 1;
                while (true) {
                    int s = nums[i] + nums[j];
                    if (s == target) return new int[] {i + 1, j + 1};
                    if (s < target) i++; else j--;
                }
            }
        }
    """,
    tests=[
        {"nums": [2, 7, 11, 15], "target": 9},
        {"nums": [2, 3, 4], "target": 6},
        {"nums": [-1, 0], "target": -1},
    ],
    gen=lambda r: (
        lambda vals: (lambda i, j: {"nums": vals, "target": vals[i] + vals[j]})(
            *sorted(r.sample(range(len(vals)), 2))
        )
    )(sorted(r.sample(range(-40, 40), r.randint(2, 12)))),
)

P(
    slug="sorted-squares",
    title="Squares of a Sorted Array",
    difficulty="easy",
    topics=["arrays", "two-pointers"],
    summary="Square every value and keep the result sorted.",
    statement="""
        `nums` is sorted in non-decreasing order and may contain negatives. Return the squares of its
        values, also sorted in non-decreasing order.
    """,
    constraints=["1 <= nums.length <= 10^4", "-10^4 <= nums[i] <= 10^4", "sorted"],
    sig="int[] sortedSquares(int[] nums)",
    hints=[
        "Where are the largest squares in a sorted array with negatives?",
        "At the two ends. Fill the result from the back, taking the bigger square from either end.",
        "i, j = 0, n-1\nfor pos from n-1 down to 0:\n    if abs(nums[i]) > abs(nums[j]): out[pos] = nums[i]**2; i += 1\n"
        "    else: out[pos] = nums[j]**2; j -= 1\nreturn out",
        "Two pointers give O(n) instead of the O(n log n) of squaring and sorting.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda nums: sorted(x * x for x in nums),
    java="""
        class Solution {
            public int[] sortedSquares(int[] nums) {
                int n = nums.length, i = 0, j = n - 1;
                int[] out = new int[n];
                for (int pos = n - 1; pos >= 0; pos--) {
                    if (Math.abs(nums[i]) > Math.abs(nums[j])) { out[pos] = nums[i] * nums[i]; i++; }
                    else { out[pos] = nums[j] * nums[j]; j--; }
                }
                return out;
            }
        }
    """,
    tests=[{"nums": [-4, -1, 0, 3, 10]}, {"nums": [-7, -3, 2, 3, 11]}, {"nums": [1]}, {"nums": [-5, -3]}],
    gen=lambda r: {"nums": sorted(ints(r, 1, 15, -30, 30))},
)

P(
    slug="search-insert-position",
    title="Search Insert Position",
    difficulty="easy",
    topics=["arrays", "binary-search"],
    summary="Find where a value is, or where it would go, in a sorted array.",
    statement="""
        `nums` is sorted with distinct values. Return the index of `target` if present, otherwise the
        index where it would be inserted to keep the array sorted. Aim for O(log n).
    """,
    constraints=["1 <= nums.length <= 10^4", "distinct, sorted ascending"],
    sig="int searchInsert(int[] nums, int target)",
    hints=[
        "This is the first index whose value is at least `target`.",
        "Binary search for that boundary: `lo = 0, hi = n` (n is a valid answer).",
        "lo, hi = 0, n\nwhile lo < hi:\n    mid = (lo + hi) // 2\n    if nums[mid] < target: lo = mid + 1\n    else: hi = mid\nreturn lo",
        "The search keeps the invariant answer ∈ [lo, hi], halving each step: O(log n). Starting `hi` at `n` "
        "handles targets larger than everything.",
    ],
    time="O(log n)",
    space="O(1)",
    model=lambda nums, target: bisect.bisect_left(nums, target),
    java="""
        class Solution {
            public int searchInsert(int[] nums, int target) {
                int lo = 0, hi = nums.length;
                while (lo < hi) {
                    int mid = (lo + hi) >>> 1;
                    if (nums[mid] < target) lo = mid + 1; else hi = mid;
                }
                return lo;
            }
        }
    """,
    tests=[
        {"nums": [1, 3, 5, 6], "target": 5},
        {"nums": [1, 3, 5, 6], "target": 2},
        {"nums": [1, 3, 5, 6], "target": 7},
        {"nums": [1, 3, 5, 6], "target": 0},
    ],
    gen=lambda r: {"nums": sorted(r.sample(range(-30, 30), r.randint(1, 12))), "target": r.randint(-35, 35)},
)

P(
    slug="count-in-sorted",
    title="Count a Value in a Sorted Array",
    difficulty="easy",
    topics=["arrays", "binary-search"],
    summary="How many times does a value appear in a sorted array?",
    statement="""
        `nums` is sorted in non-decreasing order. Return how many times `target` appears, in O(log n).
    """,
    constraints=["0 <= nums.length <= 10^5", "sorted"],
    sig="int countOccurrences(int[] nums, int target)",
    hints=[
        "The copies of `target` form one block. Find its edges.",
        "Binary search for the first index `>= target` and the first index `> target`; subtract.",
        "left = first index with nums[i] >= target\nright = first index with nums[i] > target\nreturn right - left",
        "Two binary searches: O(log n) even if the value appears thousands of times.",
    ],
    time="O(log n)",
    space="O(1)",
    model=lambda nums, target: nums.count(target),
    java="""
        class Solution {
            private int firstAtLeast(int[] a, long t) {
                int lo = 0, hi = a.length;
                while (lo < hi) { int mid = (lo + hi) >>> 1; if (a[mid] < t) lo = mid + 1; else hi = mid; }
                return lo;
            }
            public int countOccurrences(int[] nums, int target) {
                return firstAtLeast(nums, (long) target + 1) - firstAtLeast(nums, target);
            }
        }
    """,
    tests=[
        {"nums": [1, 2, 2, 2, 3], "target": 2},
        {"nums": [1, 1, 1], "target": 1},
        {"nums": [1, 3], "target": 2},
        {"nums": [], "target": 0},
    ],
    gen=lambda r: {"nums": sorted(ints(r, 0, 25, 0, 6)), "target": r.randint(0, 6)},
)

P(
    slug="mountain-peak-index",
    title="Peak of a Mountain Array",
    difficulty="easy",
    topics=["arrays", "binary-search"],
    summary="Find the top of an array that rises then falls.",
    statement="""
        `nums` strictly increases to a single peak and then strictly decreases. Return the index of the
        peak, in O(log n).
    """,
    constraints=["3 <= nums.length <= 10^5", "nums is a mountain array"],
    sig="int peakIndex(int[] nums)",
    hints=[
        "Compare a middle value with its right neighbor. What does that tell you?",
        "If `nums[mid] < nums[mid + 1]` you're still climbing, so the peak is to the right; otherwise it's at `mid` or left.",
        "lo, hi = 0, n-1\nwhile lo < hi:\n    mid = (lo + hi) // 2\n    if nums[mid] < nums[mid+1]: lo = mid + 1\n    else: hi = mid\nreturn lo",
        "Each comparison discards half the array: O(log n).",
    ],
    time="O(log n)",
    space="O(1)",
    model=lambda nums: nums.index(max(nums)),
    java="""
        class Solution {
            public int peakIndex(int[] nums) {
                int lo = 0, hi = nums.length - 1;
                while (lo < hi) {
                    int mid = (lo + hi) >>> 1;
                    if (nums[mid] < nums[mid + 1]) lo = mid + 1; else hi = mid;
                }
                return lo;
            }
        }
    """,
    tests=[
        {"nums": [0, 1, 0]},
        {"nums": [0, 2, 1, 0]},
        {"nums": [0, 10, 5, 2]},
        {"nums": [1, 2, 3, 4, 5, 3]},
    ],
    gen=lambda r: (lambda up, down: {"nums": up + down})(
        sorted(r.sample(range(0, 50), r.randint(1, 8))),
        sorted(r.sample(range(-50, 0), r.randint(1, 8)), reverse=True),
    ),
)

P(
    slug="valid-mountain",
    title="Valid Mountain Array",
    difficulty="easy",
    topics=["arrays", "two-pointers"],
    summary="Does an array strictly rise and then strictly fall?",
    statement="""
        Return `true` if `nums` has length at least 3 and strictly increases up to some peak (not the
        first or last element) and then strictly decreases.
    """,
    constraints=["1 <= nums.length <= 10^4"],
    sig="boolean validMountainArray(int[] nums)",
    hints=[
        "Walk up as far as you can, then walk down as far as you can.",
        "It's a mountain if the peak isn't at either end and the walk down reaches the last index.",
        "i = 0\nwhile i+1 < n and nums[i] < nums[i+1]: i += 1\nif i == 0 or i == n-1: return false\n"
        "while i+1 < n and nums[i] > nums[i+1]: i += 1\nreturn i == n-1",
        "One climb and one descent: O(n). Flat steps stop both walks, which correctly rejects plateaus.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda nums: (
        len(nums) >= 3
        and any(
            all(nums[k] < nums[k + 1] for k in range(p))
            and all(nums[k] > nums[k + 1] for k in range(p, len(nums) - 1))
            for p in range(1, len(nums) - 1)
        )
    ),
    java="""
        class Solution {
            public boolean validMountainArray(int[] nums) {
                int n = nums.length, i = 0;
                while (i + 1 < n && nums[i] < nums[i + 1]) i++;
                if (i == 0 || i == n - 1) return false;
                while (i + 1 < n && nums[i] > nums[i + 1]) i++;
                return i == n - 1;
            }
        }
    """,
    tests=[
        {"nums": [2, 1]},
        {"nums": [3, 5, 5]},
        {"nums": [0, 3, 2, 1]},
        {"nums": [1, 2, 3]},
        {"nums": [3, 2, 1]},
    ],
    gen=lambda r: {"nums": ints(r, 1, 7, 0, 5)},
)

P(
    slug="height-checker",
    title="Height Checker",
    difficulty="easy",
    topics=["arrays", "sorting"],
    summary="How many students stand in the wrong place?",
    statement="""
        Students should line up in non-decreasing order of height. Given the current order `heights`,
        return how many positions hold a different height than they would in the sorted line.
    """,
    constraints=["1 <= heights.length <= 100", "1 <= heights[i] <= 100"],
    sig="int heightChecker(int[] heights)",
    hints=[
        "Compare the line with its sorted version.",
        "Heights are small (1-100), so counting sort builds the sorted version in O(n).",
        "expected = sorted(heights)\nreturn count of i where heights[i] != expected[i]",
        "Sorting is O(n log n); counting sort with 101 buckets makes it O(n + 100).",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda heights: sum(a != b for a, b in zip(heights, sorted(heights), strict=False)),
    java="""
        class Solution {
            public int heightChecker(int[] heights) {
                int[] counts = new int[101];
                for (int h : heights) counts[h]++;
                int wrong = 0, h = 0;
                for (int x : heights) {
                    while (counts[h] == 0) h++;
                    if (x != h) wrong++;
                    counts[h]--;
                }
                return wrong;
            }
        }
    """,
    tests=[{"heights": [1, 1, 4, 2, 1, 3]}, {"heights": [5, 1, 2, 3, 4]}, {"heights": [1, 2, 3]}],
    gen=lambda r: {"heights": [r.randint(1, 8) for _ in range(r.randint(1, 15))]},
)

P(
    slug="evens-before-odds",
    title="Evens Before Odds",
    difficulty="easy",
    topics=["arrays", "two-pointers"],
    summary="Put all even values first, keeping order within each group.",
    statement="""
        Return an array with all the even values of `nums` first, then all the odd values. Keep the
        original relative order inside each group.
    """,
    constraints=["0 <= nums.length <= 5000", "0 <= nums[i] <= 5000"],
    sig="int[] sortByParity(int[] nums)",
    hints=[
        "Two passes keep the order simple.",
        "First copy the evens in order, then the odds in order.",
        "out = [x for x in nums if x % 2 == 0] + [x for x in nums if x % 2 == 1]\nreturn out",
        "Two linear passes: O(n) time and O(n) space. Keeping relative order is why an in-place swap trick isn't used here.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda nums: [x for x in nums if x % 2 == 0] + [x for x in nums if x % 2],
    java="""
        class Solution {
            public int[] sortByParity(int[] nums) {
                int[] out = new int[nums.length];
                int w = 0;
                for (int x : nums) if (x % 2 == 0) out[w++] = x;
                for (int x : nums) if (x % 2 != 0) out[w++] = x;
                return out;
            }
        }
    """,
    tests=[{"nums": [3, 1, 2, 4]}, {"nums": [0]}, {"nums": [1, 3, 5]}, {"nums": []}],
    gen=lambda r: {"nums": ints(r, 0, 15, 0, 20)},
)

P(
    slug="transpose-matrix",
    title="Transpose a Matrix",
    difficulty="easy",
    topics=["matrix", "arrays"],
    summary="Flip a matrix over its diagonal.",
    statement="""
        Return the transpose of `matrix`: row `i`, column `j` of the result is row `j`, column `i` of the input.
        The matrix is not necessarily square.
    """,
    constraints=["1 <= rows, cols <= 1000", "rows * cols <= 10^5"],
    sig="int[][] transpose(int[][] matrix)",
    hints=[
        "What are the dimensions of the result?",
        "A rows×cols matrix becomes cols×rows. Copy `matrix[i][j]` to `out[j][i]`.",
        "out = new matrix of size cols x rows\nfor i in rows:\n    for j in cols:\n        out[j][i] = matrix[i][j]\nreturn out",
        "Visiting every cell once is O(rows × cols). For non-square input you must allocate a new array.",
    ],
    time="O(m * n)",
    space="O(m * n)",
    model=lambda matrix: [list(col) for col in zip(*matrix, strict=False)],
    java="""
        class Solution {
            public int[][] transpose(int[][] matrix) {
                int rows = matrix.length, cols = matrix[0].length;
                int[][] out = new int[cols][rows];
                for (int i = 0; i < rows; i++) for (int j = 0; j < cols; j++) out[j][i] = matrix[i][j];
                return out;
            }
        }
    """,
    tests=[
        {"matrix": [[1, 2, 3], [4, 5, 6], [7, 8, 9]]},
        {"matrix": [[1, 2, 3], [4, 5, 6]]},
        {"matrix": [[5]]},
    ],
    gen=lambda r: {"matrix": grid(r, r.randint(1, 4), r.randint(1, 4), -9, 9)},
)

P(
    slug="diagonal-sum",
    title="Matrix Diagonal Sum",
    difficulty="easy",
    topics=["matrix"],
    summary="Add up both diagonals of a square matrix.",
    statement="""
        Return the sum of the primary diagonal and the secondary diagonal of the square matrix `mat`.
        If the size is odd, count the center cell only once.
    """,
    constraints=["1 <= n <= 100", "1 <= mat[i][j] <= 100"],
    sig="int diagonalSum(int[][] mat)",
    hints=[
        "Row `i` touches the primary diagonal at column `i` and the secondary at column `n-1-i`.",
        "Add both for each row, but when they're the same cell (odd n, middle row) add it once.",
        "total = 0\nfor i in range(n):\n    total += mat[i][i]\n    if i != n-1-i: total += mat[i][n-1-i]\nreturn total",
        "One pass over rows: O(n), not O(n^2).",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda mat: sum(
        mat[i][j] for i in range(len(mat)) for j in range(len(mat)) if i == j or i + j == len(mat) - 1
    ),
    java="""
        class Solution {
            public int diagonalSum(int[][] mat) {
                int n = mat.length, total = 0;
                for (int i = 0; i < n; i++) {
                    total += mat[i][i];
                    if (i != n - 1 - i) total += mat[i][n - 1 - i];
                }
                return total;
            }
        }
    """,
    tests=[
        {"mat": [[1, 2, 3], [4, 5, 6], [7, 8, 9]]},
        {"mat": [[1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1]]},
        {"mat": [[5]]},
    ],
    gen=lambda r: (lambda n: {"mat": grid(r, n, n, 1, 9)})(r.randint(1, 6)),
)

P(
    slug="flip-and-invert-image",
    title="Flip and Invert an Image",
    difficulty="easy",
    topics=["matrix", "two-pointers"],
    summary="Mirror each row of a binary image, then invert it.",
    statement="""
        `image` is a binary matrix. Reverse each row, then replace every `0` with `1` and every `1` with `0`.
        Return the resulting image.
    """,
    constraints=["1 <= n <= 20", "image[i][j] is 0 or 1"],
    sig="int[][] flipAndInvertImage(int[][] image)",
    hints=[
        "You can do both steps in one sweep per row.",
        "Swap from both ends toward the middle, inverting each value as you place it.",
        "for row in image:\n    i, j = 0, len(row)-1\n    while i <= j:\n        row[i], row[j] = 1 - row[j], 1 - row[i]\n        i += 1; j -= 1\nreturn image",
        "Each cell is touched once: O(n^2) total for an n×n image, in place. When `i == j` the middle cell is just inverted.",
    ],
    time="O(n^2)",
    space="O(1)",
    model=lambda image: [[1 - v for v in reversed(row)] for row in image],
    java="""
        class Solution {
            public int[][] flipAndInvertImage(int[][] image) {
                for (int[] row : image) {
                    int i = 0, j = row.length - 1;
                    while (i <= j) {
                        int a = row[i], b = row[j];
                        row[i] = 1 - b; row[j] = 1 - a;
                        i++; j--;
                    }
                }
                return image;
            }
        }
    """,
    tests=[{"image": [[1, 1, 0], [1, 0, 1], [0, 0, 0]]}, {"image": [[1]]}, {"image": [[1, 0], [0, 1]]}],
    gen=lambda r: (lambda n: {"image": grid(r, n, n, 0, 1)})(r.randint(1, 5)),
)

P(
    slug="toeplitz-matrix",
    title="Toeplitz Matrix",
    difficulty="easy",
    topics=["matrix"],
    summary="Is every top-left to bottom-right diagonal constant?",
    statement="""
        A matrix is Toeplitz if every diagonal from top-left to bottom-right holds a single value.
        Return whether `matrix` is Toeplitz.
    """,
    constraints=["1 <= rows, cols <= 20"],
    sig="boolean isToeplitzMatrix(int[][] matrix)",
    hints=[
        "Each cell shares a diagonal with the cell up and to the left of it.",
        "Check `matrix[i][j] == matrix[i-1][j-1]` for every cell not in the first row or column.",
        "for i in 1..rows-1:\n    for j in 1..cols-1:\n        if matrix[i][j] != matrix[i-1][j-1]: return false\nreturn true",
        "Comparing each cell with one neighbor covers all diagonals: O(rows × cols), O(1) space.",
    ],
    time="O(m * n)",
    space="O(1)",
    model=lambda matrix: all(
        len({matrix[i][j] for i in range(len(matrix)) for j in range(len(matrix[0])) if j - i == d}) <= 1
        for d in range(-len(matrix), len(matrix[0]))
    ),
    java="""
        class Solution {
            public boolean isToeplitzMatrix(int[][] matrix) {
                for (int i = 1; i < matrix.length; i++)
                    for (int j = 1; j < matrix[0].length; j++)
                        if (matrix[i][j] != matrix[i - 1][j - 1]) return false;
                return true;
            }
        }
    """,
    tests=[
        {"matrix": [[1, 2, 3, 4], [5, 1, 2, 3], [9, 5, 1, 2]]},
        {"matrix": [[1, 2], [2, 2]]},
        {"matrix": [[7]]},
    ],
    gen=lambda r: (
        lambda base, rows, cols: {
            "matrix": [
                [base[j - i + rows] if r.random() < 0.85 else r.randint(0, 3) for j in range(cols)]
                for i in range(rows)
            ]
        }
    )([r.randint(0, 3) for _ in range(20)], r.randint(1, 4), r.randint(1, 4)),
)

P(
    slug="reshape-matrix",
    title="Reshape a Matrix",
    difficulty="easy",
    topics=["matrix"],
    summary="Refill a matrix's values into a new shape.",
    statement="""
        Reshape `mat` into `r` rows and `c` columns, filling row by row in the original reading order.
        If `r * c` doesn't equal the number of cells, return the original matrix unchanged.
    """,
    constraints=["1 <= rows, cols <= 100", "1 <= r, c <= 300"],
    sig="int[][] matrixReshape(int[][] mat, int r, int c)",
    hints=[
        "Think of both matrices as one long list of values.",
        "Cell number `k` lives at `(k / cols, k % cols)` in the old shape and `(k / c, k % c)` in the new one.",
        "if rows*cols != r*c: return mat\nout = r x c matrix\nfor k in range(r*c):\n    out[k // c][k % c] = mat[k // cols][k % cols]\nreturn out",
        "Mapping a single index to both shapes copies every value once: O(rows × cols).",
    ],
    time="O(m * n)",
    space="O(m * n)",
    model=lambda mat, r, c: (
        mat
        if len(mat) * len(mat[0]) != r * c
        else (lambda flat: [flat[i * c : (i + 1) * c] for i in range(r)])([v for row in mat for v in row])
    ),
    java="""
        class Solution {
            public int[][] matrixReshape(int[][] mat, int r, int c) {
                int rows = mat.length, cols = mat[0].length;
                if (rows * cols != r * c) return mat;
                int[][] out = new int[r][c];
                for (int k = 0; k < r * c; k++) out[k / c][k % c] = mat[k / cols][k % cols];
                return out;
            }
        }
    """,
    tests=[
        {"mat": [[1, 2], [3, 4]], "r": 1, "c": 4},
        {"mat": [[1, 2], [3, 4]], "r": 2, "c": 4},
        {"mat": [[1, 2, 3, 4]], "r": 2, "c": 2},
    ],
    gen=lambda r_: (
        lambda m, n: {
            "mat": grid(r_, m, n, 0, 9),
            "r": r_.choice([1, m * n, n, 2]),
            "c": r_.choice([m, 1, m * n, 3]),
        }
    )(r_.randint(1, 3), r_.randint(1, 3)),
)

P(
    slug="richest-customer",
    title="Richest Customer Wealth",
    difficulty="easy",
    topics=["matrix", "arrays"],
    summary="Find the largest row sum.",
    statement="""
        `accounts[i][j]` is how much customer `i` has in bank `j`. A customer's wealth is the sum of
        their row. Return the largest wealth.
    """,
    constraints=["1 <= customers, banks <= 50", "1 <= accounts[i][j] <= 100"],
    sig="int maximumWealth(int[][] accounts)",
    hints=[
        "Each customer's wealth is independent of the others.",
        "Sum each row and keep the maximum.",
        "best = 0\nfor row in accounts:\n    best = max(best, sum(row))\nreturn best",
        "Every cell is added once: O(customers × banks).",
    ],
    time="O(m * n)",
    space="O(1)",
    model=lambda accounts: max(sum(row) for row in accounts),
    java="""
        class Solution {
            public int maximumWealth(int[][] accounts) {
                int best = 0;
                for (int[] row : accounts) {
                    int s = 0;
                    for (int v : row) s += v;
                    best = Math.max(best, s);
                }
                return best;
            }
        }
    """,
    tests=[{"accounts": [[1, 2, 3], [3, 2, 1]]}, {"accounts": [[1, 5], [7, 3], [3, 5]]}, {"accounts": [[9]]}],
    gen=lambda r: {"accounts": grid(r, r.randint(1, 5), r.randint(1, 5), 1, 30)},
)

P(
    slug="lucky-numbers-matrix",
    title="Lucky Numbers in a Matrix",
    difficulty="easy",
    topics=["matrix"],
    summary="Find values that are the smallest in their row and largest in their column.",
    statement="""
        `matrix` has distinct values. A lucky number is the minimum of its row and the maximum of its
        column. Return all lucky numbers in ascending order.
    """,
    constraints=["1 <= rows, cols <= 50", "all values distinct"],
    sig="int[] luckyNumbers(int[][] matrix)",
    hints=[
        "Compute each row's minimum and each column's maximum first.",
        "A value is lucky when it equals both its row minimum and its column maximum.",
        "rowMin = [min(row) for row]\ncolMax = [max(col) for col]\nreturn sorted(v for each cell (i,j) with v == rowMin[i] == colMax[j])",
        "Two passes to build the min/max tables, one to check: O(rows × cols). (With distinct values there's at most one lucky number.)",
    ],
    time="O(m * n)",
    space="O(m + n)",
    model=lambda matrix: sorted(
        v
        for i, row in enumerate(matrix)
        for j, v in enumerate(row)
        if v == min(row) and v == max(r[j] for r in matrix)
    ),
    java="""
        import java.util.*;

        class Solution {
            public int[] luckyNumbers(int[][] matrix) {
                int m = matrix.length, n = matrix[0].length;
                int[] rowMin = new int[m], colMax = new int[n];
                Arrays.fill(rowMin, Integer.MAX_VALUE);
                Arrays.fill(colMax, Integer.MIN_VALUE);
                for (int i = 0; i < m; i++)
                    for (int j = 0; j < n; j++) {
                        rowMin[i] = Math.min(rowMin[i], matrix[i][j]);
                        colMax[j] = Math.max(colMax[j], matrix[i][j]);
                    }
                List<Integer> lucky = new ArrayList<>();
                for (int i = 0; i < m; i++)
                    for (int j = 0; j < n; j++)
                        if (matrix[i][j] == rowMin[i] && matrix[i][j] == colMax[j]) lucky.add(matrix[i][j]);
                Collections.sort(lucky);
                return lucky.stream().mapToInt(Integer::intValue).toArray();
            }
        }
    """,
    tests=[
        {"matrix": [[3, 7, 8], [9, 11, 13], [15, 16, 17]]},
        {"matrix": [[1, 10, 4, 2], [9, 3, 8, 7], [15, 16, 17, 12]]},
        {"matrix": [[7, 8], [1, 2]]},
        {"matrix": [[3, 1], [2, 4]]},
    ],
    gen=lambda r: (
        lambda m, n: (lambda vals: {"matrix": [vals[i * n : (i + 1) * n] for i in range(m)]})(
            r.sample(range(1, 100), m * n)
        )
    )(r.randint(1, 4), r.randint(1, 4)),
)

P(
    slug="pivot-index",
    title="Find the Pivot Index",
    difficulty="easy",
    topics=["arrays", "prefix-sums"],
    summary="Find where the left and right sums balance.",
    statement="""
        Return the leftmost index `i` where the sum of values strictly to its left equals the sum of
        values strictly to its right. Return `-1` if there is none.
    """,
    constraints=["1 <= nums.length <= 10^4", "-1000 <= nums[i] <= 1000"],
    sig="int pivotIndex(int[] nums)",
    hints=[
        "If you know the total, the right sum follows from the left sum.",
        "right = total - left - nums[i]. Walk left to right keeping `left`.",
        "total = sum(nums)\nleft = 0\nfor i, x in enumerate(nums):\n    if left == total - left - x: return i\n    left += x\nreturn -1",
        "One pass after computing the total: O(n) time, O(1) space.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda nums: next((i for i in range(len(nums)) if sum(nums[:i]) == sum(nums[i + 1 :])), -1),
    java="""
        class Solution {
            public int pivotIndex(int[] nums) {
                int total = 0, left = 0;
                for (int x : nums) total += x;
                for (int i = 0; i < nums.length; i++) {
                    if (left == total - left - nums[i]) return i;
                    left += nums[i];
                }
                return -1;
            }
        }
    """,
    tests=[{"nums": [1, 7, 3, 6, 5, 6]}, {"nums": [1, 2, 3]}, {"nums": [2, 1, -1]}, {"nums": [0]}],
    gen=lambda r: {"nums": ints(r, 1, 10, -3, 3)},
)

P(
    slug="third-maximum",
    title="Third Distinct Maximum",
    difficulty="easy",
    topics=["arrays"],
    summary="Return the third-largest distinct value, or the maximum if there isn't one.",
    statement="""
        Return the third-largest **distinct** value in `nums`. If there are fewer than three distinct
        values, return the largest value.
    """,
    constraints=["1 <= nums.length <= 10^4", "-2^31 <= nums[i] <= 2^31 - 1"],
    sig="int thirdMax(int[] nums)",
    hints=[
        "Keep the top three distinct values as you scan.",
        'Use `long` (or nullable values) so a real `Integer.MIN_VALUE` isn\'t confused with "empty".',
        "a = b = c = None\nfor x in nums:\n    if x in (a, b, c): continue\n    shift x into the right place among a > b > c\nreturn c if c is not None else a",
        "Tracking three values is O(n) time and O(1) space. Skipping duplicates is what makes them distinct.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda nums: sorted(set(nums))[-3] if len(set(nums)) >= 3 else max(nums),
    java="""
        class Solution {
            public int thirdMax(int[] nums) {
                long a = Long.MIN_VALUE, b = Long.MIN_VALUE, c = Long.MIN_VALUE;
                for (int x : nums) {
                    if (x == a || x == b || x == c) continue;
                    if (x > a) { c = b; b = a; a = x; }
                    else if (x > b) { c = b; b = x; }
                    else if (x > c) c = x;
                }
                return (int) (c == Long.MIN_VALUE ? a : c);
            }
        }
    """,
    tests=[{"nums": [3, 2, 1]}, {"nums": [1, 2]}, {"nums": [2, 2, 3, 1]}, {"nums": [1, 2, -2147483648]}],
    gen=lambda r: {"nums": ints(r, 1, 12, -5, 5)},
)

P(
    slug="candy-types",
    title="Most Candy Types You Can Keep",
    difficulty="easy",
    topics=["hash-sets", "greedy"],
    summary="Keep half the candies; maximize how many kinds you get.",
    statement="""
        `candyType[i]` is the type of candy `i`. You may keep exactly half of the candies (`n` is even).
        Return the maximum number of different types you can keep.
    """,
    constraints=["2 <= n <= 10^4", "n is even"],
    sig="int distributeCandies(int[] candyType)",
    hints=[
        "Two limits apply: the number of types that exist, and how many candies you can keep.",
        "The answer is `min(number of distinct types, n / 2)`.",
        "return min(len(set(candyType)), len(candyType) // 2)",
        "Counting distinct types with a set is O(n).",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda candyType: min(len(set(candyType)), len(candyType) // 2),
    java="""
        import java.util.*;

        class Solution {
            public int distributeCandies(int[] candyType) {
                Set<Integer> types = new HashSet<>();
                for (int t : candyType) types.add(t);
                return Math.min(types.size(), candyType.length / 2);
            }
        }
    """,
    tests=[{"candyType": [1, 1, 2, 2, 3, 3]}, {"candyType": [1, 1, 2, 3]}, {"candyType": [6, 6, 6, 6]}],
    gen=lambda r: {"candyType": [r.randint(1, 6) for _ in range(2 * r.randint(1, 8))]},
)

P(
    slug="assign-cookies",
    title="Assign Cookies",
    difficulty="easy",
    topics=["greedy", "sorting", "two-pointers"],
    summary="Give cookies to as many satisfied children as possible.",
    statement="""
        Child `i` is content with a cookie of size at least `greed[i]`. Each child gets at most one cookie,
        and `sizes[j]` are the cookie sizes. Return the maximum number of content children.
    """,
    constraints=["0 <= greed.length, sizes.length <= 3 * 10^4"],
    sig="int findContentChildren(int[] greed, int[] sizes)",
    hints=[
        "Should the smallest cookie go to the least greedy child?",
        "Sort both arrays. Walk the cookies; if the current cookie satisfies the current child, move to the next child.",
        "sort greed, sizes\ni = 0\nfor s in sizes:\n    if i < len(greed) and s >= greed[i]: i += 1\nreturn i",
        "Giving each child the smallest cookie that works never wastes a bigger cookie: O(n log n + m log m) for sorting.",
    ],
    time="O(n log n + m log m)",
    space="O(1)",
    model=lambda greed, sizes: (
        lambda g, s: __import__("functools").reduce(
            lambda i, c: i + 1 if i < len(g) and c >= g[i] else i, s, 0
        )
    )(sorted(greed), sorted(sizes)),
    java="""
        import java.util.*;

        class Solution {
            public int findContentChildren(int[] greed, int[] sizes) {
                Arrays.sort(greed);
                Arrays.sort(sizes);
                int i = 0;
                for (int s : sizes) if (i < greed.length && s >= greed[i]) i++;
                return i;
            }
        }
    """,
    tests=[
        {"greed": [1, 2, 3], "sizes": [1, 1]},
        {"greed": [1, 2], "sizes": [1, 2, 3]},
        {"greed": [], "sizes": [5]},
        {"greed": [10, 9, 8, 7], "sizes": [5, 6, 7, 8]},
    ],
    gen=lambda r: {"greed": ints(r, 0, 8, 1, 10), "sizes": ints(r, 0, 8, 1, 10)},
)

P(
    slug="lemonade-change",
    title="Lemonade Change",
    difficulty="easy",
    topics=["greedy", "simulation"],
    summary="Can you give correct change to every customer?",
    statement="""
        Lemonade costs 5. Customers pay with bills of 5, 10 or 20, in the order given by `bills`.
        You start with no money. Return `true` if you can give every customer correct change.
    """,
    constraints=["1 <= bills.length <= 10^5", "bills[i] is 5, 10 or 20"],
    sig="boolean lemonadeChange(int[] bills)",
    hints=[
        "Only fives and tens are ever useful as change.",
        "For a 20, prefer giving a 10 and a 5 over three 5s: fives are more flexible.",
        "five = ten = 0\nfor b in bills:\n    if b == 5: five += 1\n    elif b == 10: ten += 1; five -= 1\n"
        "    elif ten > 0: ten -= 1; five -= 1\n    else: five -= 3\n    if five < 0: return false\nreturn true",
        "The greedy choice keeps the most fives for later: O(n) time, O(1) space.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda bills: (lambda f: f(f, 0, 0, 0))(
        lambda f, i, five, ten: (
            True
            if i == len(bills)
            else (
                f(f, i + 1, five + 1, ten)
                if bills[i] == 5
                else (five >= 1 and f(f, i + 1, five - 1, ten + 1))
                if bills[i] == 10
                else (
                    (ten >= 1 and five >= 1 and f(f, i + 1, five - 1, ten - 1))
                    or (five >= 3 and f(f, i + 1, five - 3, ten))
                )
            )
        )
    ),
    java="""
        class Solution {
            public boolean lemonadeChange(int[] bills) {
                int five = 0, ten = 0;
                for (int b : bills) {
                    if (b == 5) five++;
                    else if (b == 10) { ten++; five--; }
                    else if (ten > 0) { ten--; five--; }
                    else five -= 3;
                    if (five < 0) return false;
                }
                return true;
            }
        }
    """,
    tests=[
        {"bills": [5, 5, 5, 10, 20]},
        {"bills": [5, 5, 10, 10, 20]},
        {"bills": [10]},
        {"bills": [5, 5, 5, 5, 20, 20]},
    ],
    gen=lambda r: {"bills": [5] + [r.choice([5, 5, 10, 20]) for _ in range(r.randint(0, 10))]},
)

P(
    slug="perfect-square",
    title="Valid Perfect Square",
    difficulty="easy",
    topics=["binary-search", "math"],
    summary="Is a number a perfect square? No square-root functions.",
    statement="""
        Return `true` if `num` is a perfect square (the square of an integer). Don't use built-in
        square-root functions.
    """,
    constraints=["1 <= num <= 2^31 - 1"],
    sig="boolean isPerfectSquare(int num)",
    hints=[
        "Search for an integer whose square is exactly `num`.",
        "Binary search on `r` in `[1, num]`, comparing `r * r` (as a long) with `num`.",
        "lo, hi = 1, num\nwhile lo <= hi:\n    mid = (lo + hi) // 2\n    if mid*mid == num: return true\n    if mid*mid < num: lo = mid + 1\n    else: hi = mid - 1\nreturn false",
        "O(log num) with long arithmetic to avoid overflow.",
    ],
    time="O(log n)",
    space="O(1)",
    model=lambda num: __import__("math").isqrt(num) ** 2 == num,
    java="""
        class Solution {
            public boolean isPerfectSquare(int num) {
                long lo = 1, hi = num;
                while (lo <= hi) {
                    long mid = (lo + hi) / 2, sq = mid * mid;
                    if (sq == num) return true;
                    if (sq < num) lo = mid + 1; else hi = mid - 1;
                }
                return false;
            }
        }
    """,
    tests=[{"num": 16}, {"num": 14}, {"num": 1}, {"num": 2147395600}, {"num": 2147483647}],
    gen=lambda r: {"num": r.choice([r.randint(1, 3000) ** 2, r.randint(1, 10**7)])},
)

P(
    slug="baseball-scores",
    title="Baseball Score Keeper",
    difficulty="easy",
    topics=["stacks", "simulation"],
    summary="Apply scoring operations and total the record.",
    statement="""
        Each operation in `ops` is one of: an integer (record that score), `"+"` (record the sum of the
        previous two scores), `"D"` (record double the previous score), or `"C"` (remove the previous
        score). All operations are valid. Return the sum of the remaining scores.
    """,
    constraints=["1 <= ops.length <= 1000"],
    sig="int calPoints(String[] ops)",
    hints=[
        "Every operation looks at or changes the most recent scores.",
        "A stack fits: push numbers, pop for C, peek for D and +.",
        "stack = []\nfor op in ops:\n    if op == 'C': stack.pop()\n    elif op == 'D': stack.append(2 * stack[-1])\n"
        "    elif op == '+': stack.append(stack[-1] + stack[-2])\n    else: stack.append(int(op))\nreturn sum(stack)",
        "Each operation is O(1) on the stack, so O(n) overall.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda ops: sum(
        __import__("functools").reduce(
            lambda st, op: (
                st[:-1]
                if op == "C"
                else st + [2 * st[-1]]
                if op == "D"
                else st + [st[-1] + st[-2]]
                if op == "+"
                else st + [int(op)]
            ),
            ops,
            [],
        )
    ),
    java="""
        import java.util.*;

        class Solution {
            public int calPoints(String[] ops) {
                Deque<Integer> stack = new ArrayDeque<>();
                for (String op : ops) {
                    if (op.equals("C")) stack.pop();
                    else if (op.equals("D")) stack.push(2 * stack.peek());
                    else if (op.equals("+")) { int a = stack.pop(), b = stack.peek(); stack.push(a); stack.push(a + b); }
                    else stack.push(Integer.parseInt(op));
                }
                int total = 0;
                for (int s : stack) total += s;
                return total;
            }
        }
    """,
    tests=[
        {"ops": ["5", "2", "C", "D", "+"]},
        {"ops": ["5", "-2", "4", "C", "D", "9", "+", "+"]},
        {"ops": ["1", "C"]},
    ],
    gen=lambda r: {
        "ops": [str(r.randint(-9, 9)), str(r.randint(-9, 9))]
        + [r.choice(["D", "+", str(r.randint(-9, 9))]) for _ in range(r.randint(0, 6))]
    },
    explain={0: "Record 5, 2; cancel 2; double 5 → 10; 5+10 → 15. Total 30."},
)

P(
    slug="next-greater-in-other",
    title="Next Greater Element in Another Array",
    difficulty="easy",
    topics=["stacks", "hash-maps"],
    summary="For each value of a subset, find the next bigger value to its right in the full array.",
    statement="""
        `nums1` is a subset of `nums2`, and all values are distinct. For each `x` in `nums1`, find `x` in
        `nums2` and return the first value to its right that is greater than `x`, or `-1` if none.
    """,
    constraints=["1 <= nums1.length <= nums2.length <= 1000", "distinct values"],
    sig="int[] nextGreaterElement(int[] nums1, int[] nums2)",
    hints=[
        "Compute the next greater value for every element of `nums2` once.",
        "A decreasing stack: when a bigger value arrives, it's the answer for everything smaller on the stack.",
        "next = {}\nstack = []\nfor x in nums2:\n    while stack and stack[-1] < x: next[stack.pop()] = x\n    stack.append(x)\n"
        "return [next.get(x, -1) for x in nums1]",
        "Every value is pushed and popped once: O(n + m), versus O(n * m) for scanning right each time.",
    ],
    time="O(n + m)",
    space="O(n)",
    model=lambda nums1, nums2: [next((y for y in nums2[nums2.index(x) + 1 :] if y > x), -1) for x in nums1],
    java="""
        import java.util.*;

        class Solution {
            public int[] nextGreaterElement(int[] nums1, int[] nums2) {
                Map<Integer, Integer> next = new HashMap<>();
                Deque<Integer> stack = new ArrayDeque<>();
                for (int x : nums2) {
                    while (!stack.isEmpty() && stack.peek() < x) next.put(stack.pop(), x);
                    stack.push(x);
                }
                int[] out = new int[nums1.length];
                for (int i = 0; i < nums1.length; i++) out[i] = next.getOrDefault(nums1[i], -1);
                return out;
            }
        }
    """,
    tests=[
        {"nums1": [4, 1, 2], "nums2": [1, 3, 4, 2]},
        {"nums1": [2, 4], "nums2": [1, 2, 3, 4]},
        {"nums1": [5], "nums2": [5]},
    ],
    gen=lambda r: (lambda b: {"nums1": r.sample(b, r.randint(1, len(b))), "nums2": b})(
        r.sample(range(0, 40), r.randint(1, 12))
    ),
)

P(
    slug="min-cost-stairs",
    title="Cheapest Way Up the Stairs",
    difficulty="easy",
    topics=["dynamic-programming"],
    summary="Climb stairs paying a cost per step; minimize the total.",
    statement="""
        `cost[i]` is the cost of stepping on stair `i`. From a stair you may climb one or two stairs.
        You may start on stair 0 or 1. Return the minimum cost to reach the top (just past the last stair).
    """,
    constraints=["2 <= cost.length <= 1000", "0 <= cost[i] <= 999"],
    sig="int minCostClimbingStairs(int[] cost)",
    hints=[
        "The cheapest way to reach a stair depends only on the two stairs below it.",
        "best[i] = cost[i] + min(best[i-1], best[i-2]); the answer is min of the last two.",
        "a, b = cost[0], cost[1]\nfor i in 2..n-1:\n    a, b = b, cost[i] + min(a, b)\nreturn min(a, b)",
        "Bottom-up DP with two variables: O(n) time, O(1) space.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda cost: (lambda f: min(f(f, len(cost) - 1), f(f, len(cost) - 2)))(
        __import__("functools").lru_cache(None)(
            lambda f, i: cost[i] if i < 2 else cost[i] + min(f(f, i - 1), f(f, i - 2))
        )
    ),
    java="""
        class Solution {
            public int minCostClimbingStairs(int[] cost) {
                int a = cost[0], b = cost[1];
                for (int i = 2; i < cost.length; i++) { int c = cost[i] + Math.min(a, b); a = b; b = c; }
                return Math.min(a, b);
            }
        }
    """,
    tests=[{"cost": [10, 15, 20]}, {"cost": [1, 100, 1, 1, 1, 100, 1, 1, 100, 1]}, {"cost": [0, 0]}],
    gen=lambda r: {"cost": ints(r, 2, 15, 0, 30)},
)

P(
    slug="tribonacci",
    title="Tribonacci Number",
    difficulty="easy",
    topics=["dynamic-programming", "math"],
    summary="Each term is the sum of the three before it.",
    statement="""
        T(0) = 0, T(1) = 1, T(2) = 1, and T(n) = T(n-1) + T(n-2) + T(n-3). Return T(n).
    """,
    constraints=["0 <= n <= 37"],
    sig="int tribonacci(int n)",
    hints=[
        "You only need the last three values.",
        "Slide a window of three values forward n times.",
        "a, b, c = 0, 1, 1\nrepeat n times: a, b, c = b, c, a + b + c\nreturn a",
        "O(n) time and O(1) space. T(37) = 2082876103 still fits in an int.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda n: __import__("functools").reduce(
        lambda t, _: (t[1], t[2], t[0] + t[1] + t[2]), range(n), (0, 1, 1)
    )[0],
    java="""
        class Solution {
            public int tribonacci(int n) {
                int a = 0, b = 1, c = 1;
                for (int i = 0; i < n; i++) { int d = a + b + c; a = b; b = c; c = d; }
                return a;
            }
        }
    """,
    tests=[{"n": 4}, {"n": 25}, {"n": 0}, {"n": 37}],
    gen=lambda r: {"n": r.randint(1, 30)},
)

P(
    slug="day-of-year",
    title="Day of the Year",
    difficulty="easy",
    topics=["strings", "math"],
    summary="Turn a date into its day number within the year.",
    statement="""
        `date` is a valid date `"YYYY-MM-DD"` in the Gregorian calendar. Return its day number in the
        year (January 1 is day 1). Remember leap years: divisible by 4, except centuries not divisible by 400.
    """,
    constraints=["date is between 1900-01-01 and 2100-12-31"],
    sig="int dayOfYear(String date)",
    hints=[
        "Add up the lengths of the months before this one, then add the day.",
        "February has 29 days in leap years: `(y % 4 == 0 && y % 100 != 0) || y % 400 == 0`.",
        "days = [31,28,31,30,31,30,31,31,30,31,30,31]\nif leap(year): days[1] = 29\nreturn sum(days[:month-1]) + day",
        "Constant work: at most 11 additions. The leap-year rule is the part people get wrong (1900 is not a leap year; 2000 is).",
    ],
    time="O(1)",
    space="O(1)",
    model=lambda date: __import__("datetime").date.fromisoformat(date).timetuple().tm_yday,
    java="""
        class Solution {
            public int dayOfYear(String date) {
                int y = Integer.parseInt(date.substring(0, 4));
                int m = Integer.parseInt(date.substring(5, 7));
                int d = Integer.parseInt(date.substring(8, 10));
                int[] days = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
                if ((y % 4 == 0 && y % 100 != 0) || y % 400 == 0) days[1] = 29;
                int total = d;
                for (int i = 0; i < m - 1; i++) total += days[i];
                return total;
            }
        }
    """,
    tests=[
        {"date": "2019-01-09"},
        {"date": "2019-02-10"},
        {"date": "2020-12-31"},
        {"date": "1900-03-01"},
        {"date": "2000-03-01"},
    ],
    gen=lambda r: {
        "date": (
            __import__("datetime").date(1900, 1, 1)
            + __import__("datetime").timedelta(days=r.randint(0, 73000))
        ).isoformat()
    },
)

P(
    slug="count-odds-in-range",
    title="Count Odd Numbers in a Range",
    difficulty="easy",
    topics=["math"],
    summary="How many odd numbers lie between low and high?",
    statement="""
        Return how many odd numbers are in the inclusive range `[low, high]`.
    """,
    constraints=["0 <= low <= high <= 10^9"],
    sig="int countOdds(int low, int high)",
    hints=[
        "Looping over a range of a billion numbers is too slow. Count with arithmetic.",
        "The number of odd values in `[0, x]` is `(x + 1) / 2`.",
        "return (high + 1) // 2 - low // 2",
        "Odds up to `high` minus odds below `low`: O(1).",
    ],
    time="O(1)",
    space="O(1)",
    model=lambda low, high: (
        sum(1 for x in range(low, high + 1) if x % 2) if high - low < 10**5 else (high + 1) // 2 - low // 2
    ),
    java="""
        class Solution {
            public int countOdds(int low, int high) {
                return (high + 1) / 2 - low / 2;
            }
        }
    """,
    tests=[
        {"low": 3, "high": 7},
        {"low": 8, "high": 10},
        {"low": 0, "high": 0},
        {"low": 0, "high": 1000000000},
    ],
    gen=lambda r: (lambda a: {"low": a, "high": a + r.randint(0, 500)})(r.randint(0, 10**6)),
)

P(
    slug="sum-of-unique",
    title="Sum of Unique Values",
    difficulty="easy",
    topics=["arrays", "hash-maps"],
    summary="Add up the values that appear exactly once.",
    statement="""
        Return the sum of all values in `nums` that appear exactly once.
    """,
    constraints=["1 <= nums.length <= 100", "1 <= nums[i] <= 100"],
    sig="int sumOfUnique(int[] nums)",
    hints=[
        "You need to know how often each value appears.",
        "Count first, then add the values whose count is 1.",
        "counts = count each value\nreturn sum(v for v, c in counts if c == 1)",
        "Counting with an array of 101 slots makes it O(n).",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda nums: sum(x for x in nums if nums.count(x) == 1),
    java="""
        class Solution {
            public int sumOfUnique(int[] nums) {
                int[] counts = new int[101];
                for (int x : nums) counts[x]++;
                int total = 0;
                for (int v = 1; v <= 100; v++) if (counts[v] == 1) total += v;
                return total;
            }
        }
    """,
    tests=[{"nums": [1, 2, 3, 2]}, {"nums": [1, 1, 1, 1, 1]}, {"nums": [1, 2, 3, 4, 5]}],
    gen=lambda r: {"nums": [r.randint(1, 10) for _ in range(r.randint(1, 15))]},
)
