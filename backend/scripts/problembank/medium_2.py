"""Medium problems, part 2: intervals, binary search on answers, greedy and dynamic programming."""

from functools import lru_cache
from itertools import combinations

from scripts.problembank import P, ints, word


def _intervals(r, n_hi=7, hi=20):
    out = []
    for _ in range(r.randint(1, n_hi)):
        a = r.randint(0, hi)
        out.append([a, a + r.randint(0, 6)])
    return out


def _merge(intervals):
    out = []
    for a, b in sorted(intervals):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


P(
    slug="merge-intervals",
    title="Merge Overlapping Intervals",
    difficulty="medium",
    topics=["intervals", "sorting"],
    summary="Combine every group of overlapping intervals.",
    statement="""
        Each interval is `[start, end]`. Merge all overlapping intervals (touching ones like `[1,4]` and
        `[4,5]` count as overlapping) and return the result sorted by start.
    """,
    constraints=["1 <= intervals.length <= 10^4", "0 <= start <= end <= 10^4"],
    sig="int[][] merge(int[][] intervals)",
    hints=[
        "Overlaps are easy to spot once the intervals are in order.",
        "Sort by start. Each interval either extends the last merged one or starts a new one.",
        "sort by start\nout = []\nfor a, b in intervals:\n    if out and a <= out[-1].end: out[-1].end = max(out[-1].end, b)\n    else: out.append([a, b])\nreturn out",
        "Sorting is O(n log n) and the sweep is O(n). Taking the max end handles an interval nested inside another.",
    ],
    time="O(n log n)",
    space="O(n)",
    model=_merge,
    java="""
        import java.util.*;

        class Solution {
            public int[][] merge(int[][] intervals) {
                Arrays.sort(intervals, (x, y) -> x[0] != y[0] ? Integer.compare(x[0], y[0]) : Integer.compare(x[1], y[1]));
                List<int[]> out = new ArrayList<>();
                for (int[] iv : intervals) {
                    if (!out.isEmpty() && iv[0] <= out.get(out.size() - 1)[1])
                        out.get(out.size() - 1)[1] = Math.max(out.get(out.size() - 1)[1], iv[1]);
                    else out.add(new int[] {iv[0], iv[1]});
                }
                return out.toArray(new int[0][]);
            }
        }
    """,
    tests=[
        {"intervals": [[1, 3], [2, 6], [8, 10], [15, 18]]},
        {"intervals": [[1, 4], [4, 5]]},
        {"intervals": [[1, 4], [2, 3]]},
        {"intervals": [[5, 6]]},
    ],
    gen=lambda r: {"intervals": _intervals(r)},
)

P(
    slug="insert-interval",
    title="Insert an Interval",
    difficulty="medium",
    topics=["intervals", "arrays"],
    summary="Add an interval to a sorted, non-overlapping list and merge.",
    statement="""
        `intervals` is sorted by start and has no overlaps. Insert `newInterval`, merging where needed, and
        return the resulting sorted, non-overlapping list. Touching intervals merge.
    """,
    constraints=["0 <= intervals.length <= 10^4", "intervals sorted and non-overlapping"],
    sig="int[][] insert(int[][] intervals, int[] newInterval)",
    hints=[
        "The list splits into three parts: entirely before, overlapping, entirely after.",
        "Copy intervals that end before the new start; merge every interval that overlaps; copy the rest.",
        "i = 0\nwhile i < n and intervals[i].end < new.start: out.append(intervals[i]); i += 1\n"
        "while i < n and intervals[i].start <= new.end: new = [min starts, max ends]; i += 1\nout.append(new)\nout += intervals[i:]\nreturn out",
        "One pass, O(n), because the input is already sorted.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda intervals, newInterval: _merge(intervals + [newInterval]),
    java="""
        import java.util.*;

        class Solution {
            public int[][] insert(int[][] intervals, int[] newInterval) {
                List<int[]> out = new ArrayList<>();
                int i = 0, n = intervals.length, a = newInterval[0], b = newInterval[1];
                while (i < n && intervals[i][1] < a) out.add(intervals[i++]);
                while (i < n && intervals[i][0] <= b) { a = Math.min(a, intervals[i][0]); b = Math.max(b, intervals[i][1]); i++; }
                out.add(new int[] {a, b});
                while (i < n) out.add(intervals[i++]);
                return out.toArray(new int[0][]);
            }
        }
    """,
    tests=[
        {"intervals": [[1, 3], [6, 9]], "newInterval": [2, 5]},
        {"intervals": [[1, 2], [3, 5], [6, 7], [8, 10], [12, 16]], "newInterval": [4, 8]},
        {"intervals": [], "newInterval": [5, 7]},
        {"intervals": [[1, 5]], "newInterval": [6, 8]},
    ],
    gen=lambda r: (lambda a: {"intervals": _merge(_intervals(r)), "newInterval": [a, a + r.randint(0, 5)]})(
        r.randint(0, 25)
    ),
)

P(
    slug="non-overlapping-intervals",
    title="Fewest Removals for No Overlap",
    difficulty="medium",
    topics=["intervals", "greedy", "sorting"],
    summary="Remove the fewest intervals so the rest don't overlap.",
    statement="""
        Return the minimum number of intervals to remove so the remaining ones don't overlap. Intervals that
        only touch (`[1,2]` and `[2,3]`) don't overlap.
    """,
    constraints=["1 <= intervals.length <= 10^5"],
    sig="int eraseOverlapIntervals(int[][] intervals)",
    hints=[
        "Flip it: keep as many non-overlapping intervals as possible.",
        "Sort by end time and greedily keep each interval that starts at or after the last kept end.",
        "sort by end\nkept, end = 0, -infinity\nfor a, b in intervals:\n    if a >= end: kept += 1; end = b\nreturn n - kept",
        "Choosing the interval that ends earliest leaves the most room for the rest (the classic activity-selection "
        "argument). O(n log n) for the sort.",
    ],
    time="O(n log n)",
    space="O(1)",
    model=lambda intervals: (
        len(intervals)
        - max(
            k
            for k in range(len(intervals) + 1)
            for c in combinations(sorted(intervals, key=lambda x: x[1]), k)
            if all(c[i][1] <= c[i + 1][0] for i in range(k - 1))
        )
    ),
    java="""
        import java.util.*;

        class Solution {
            public int eraseOverlapIntervals(int[][] intervals) {
                Arrays.sort(intervals, (x, y) -> Integer.compare(x[1], y[1]));
                int kept = 0;
                long end = Long.MIN_VALUE;
                for (int[] iv : intervals) if (iv[0] >= end) { kept++; end = iv[1]; }
                return intervals.length - kept;
            }
        }
    """,
    tests=[
        {"intervals": [[1, 2], [2, 3], [3, 4], [1, 3]]},
        {"intervals": [[1, 2], [1, 2], [1, 2]]},
        {"intervals": [[1, 2], [2, 3]]},
    ],
    gen=lambda r: {"intervals": _intervals(r, 7, 12)},
)

P(
    slug="meeting-rooms",
    title="Meeting Rooms Needed",
    difficulty="medium",
    topics=["intervals", "heaps", "sorting"],
    summary="Minimum rooms so no two overlapping meetings share one.",
    statement="""
        Each meeting is `[start, end)`: it frees its room at `end`, so a meeting ending at 10 and one starting
        at 10 can share a room. Return the minimum number of rooms needed for all meetings.
    """,
    constraints=["1 <= meetings.length <= 10^4", "0 <= start < end <= 10^6"],
    sig="int minMeetingRooms(int[][] meetings)",
    hints=[
        "The answer is the largest number of meetings happening at the same moment.",
        "Sort starts and ends separately. Sweep: a start needs a room unless an earlier meeting has already ended.",
        "starts, ends = sorted starts, sorted ends\nrooms = j = 0\nfor s in starts:\n    if s >= ends[j]: j += 1\n    else: rooms += 1\nreturn rooms",
        "Two sorted lists and one sweep: O(n log n). A min-heap of end times works the same way.",
    ],
    time="O(n log n)",
    space="O(n)",
    model=lambda meetings: max(sum(1 for a, b in meetings if a <= t < b) for t in {a for a, _ in meetings}),
    java="""
        import java.util.*;

        class Solution {
            public int minMeetingRooms(int[][] meetings) {
                int n = meetings.length;
                int[] starts = new int[n], ends = new int[n];
                for (int i = 0; i < n; i++) { starts[i] = meetings[i][0]; ends[i] = meetings[i][1]; }
                Arrays.sort(starts);
                Arrays.sort(ends);
                int rooms = 0, j = 0;
                for (int s : starts) { if (s >= ends[j]) j++; else rooms++; }
                return rooms;
            }
        }
    """,
    tests=[
        {"meetings": [[0, 30], [5, 10], [15, 20]]},
        {"meetings": [[7, 10], [2, 4]]},
        {"meetings": [[1, 5], [5, 10], [5, 6]]},
    ],
    gen=lambda r: {"meetings": [[a, a + r.randint(1, 6)] for a in ints(r, 1, 8, 0, 15)]},
)

P(
    slug="min-arrows-balloons",
    title="Fewest Arrows to Pop Balloons",
    difficulty="medium",
    topics=["intervals", "greedy", "sorting"],
    summary="Vertical arrows pop every balloon they pass through. How few are needed?",
    statement="""
        Balloon `i` spans `[x_start, x_end]` horizontally. A vertical arrow at `x` pops every balloon with
        `x_start <= x <= x_end`. Return the minimum number of arrows to pop all balloons.
    """,
    constraints=["1 <= points.length <= 10^5", "-2^31 <= x_start <= x_end <= 2^31 - 1"],
    sig="int findMinArrowShots(int[][] points)",
    hints=[
        "Where should the first arrow go to hit as many balloons as possible?",
        "Sort by end. Shoot at the first balloon's end; it pops everything that starts at or before that point.",
        "sort by end\narrows = 0\nlast = -infinity\nfor a, b in points:\n    if a > last: arrows += 1; last = b\nreturn arrows",
        "Greedy by end time, O(n log n). Compare with `Integer.compare` (not subtraction) because values span the full int range.",
    ],
    time="O(n log n)",
    space="O(1)",
    model=lambda points: __import__("functools").reduce(
        lambda acc, p: acc if p[0] <= acc[1] else (acc[0] + 1, p[1]),
        sorted(points, key=lambda p: p[1]),
        (0, float("-inf")),
    )[0],
    java="""
        import java.util.*;

        class Solution {
            public int findMinArrowShots(int[][] points) {
                Arrays.sort(points, (x, y) -> Integer.compare(x[1], y[1]));
                int arrows = 0;
                long last = Long.MIN_VALUE;
                for (int[] p : points) if (p[0] > last) { arrows++; last = p[1]; }
                return arrows;
            }
        }
    """,
    tests=[
        {"points": [[10, 16], [2, 8], [1, 6], [7, 12]]},
        {"points": [[1, 2], [3, 4], [5, 6], [7, 8]]},
        {"points": [[1, 2], [2, 3], [3, 4], [4, 5]]},
        {"points": [[-2147483648, 2147483647]]},
    ],
    gen=lambda r: {"points": _intervals(r, 8, 20)},
)

P(
    slug="koko-eating-speed",
    title="Slowest Eating Speed",
    difficulty="medium",
    topics=["binary-search"],
    summary="Find the minimum speed to finish all piles within h hours.",
    statement="""
        There are piles of bananas, `piles[i]` in pile `i`. Each hour you pick one pile and eat up to `k`
        bananas from it (if fewer remain, you finish the pile and wait out the hour). Return the minimum
        integer speed `k` that finishes everything within `h` hours.
    """,
    constraints=["1 <= piles.length <= 10^4", "piles.length <= h <= 10^9", "1 <= piles[i] <= 10^9"],
    sig="int minEatingSpeed(int[] piles, int h)",
    hints=[
        "If speed `k` works, does every faster speed work too?",
        "Yes, so binary search on `k` between 1 and the largest pile. Hours at speed `k` = sum of `ceil(p / k)`.",
        "lo, hi = 1, max(piles)\nwhile lo < hi:\n    mid = (lo + hi) // 2\n    if hours(mid) <= h: hi = mid\n    else: lo = mid + 1\nreturn lo",
        "Binary search on the answer: O(n log max(piles)). Sum hours in a long, and compute `ceil(p / k)` as `(p + k - 1) / k`.",
    ],
    time="O(n log m)",
    space="O(1)",
    model=lambda piles, h: next(k for k in range(1, max(piles) + 1) if sum(-(-p // k) for p in piles) <= h),
    java="""
        class Solution {
            public int minEatingSpeed(int[] piles, int h) {
                int lo = 1, hi = 0;
                for (int p : piles) hi = Math.max(hi, p);
                while (lo < hi) {
                    int mid = lo + (hi - lo) / 2;
                    long hours = 0;
                    for (int p : piles) hours += (p + (long) mid - 1) / mid;
                    if (hours <= h) hi = mid; else lo = mid + 1;
                }
                return lo;
            }
        }
    """,
    tests=[
        {"piles": [3, 6, 7, 11], "h": 8},
        {"piles": [30, 11, 23, 4, 20], "h": 5},
        {"piles": [30, 11, 23, 4, 20], "h": 6},
        {"piles": [1], "h": 1},
    ],
    gen=lambda r: (lambda piles: {"piles": piles, "h": r.randint(len(piles), 3 * len(piles) + 5)})(
        ints(r, 1, 6, 1, 60)
    ),
)

P(
    slug="ship-within-days",
    title="Smallest Ship Capacity",
    difficulty="medium",
    topics=["binary-search", "greedy"],
    summary="Lowest capacity that ships packages in order within D days.",
    statement="""
        Packages with weights `weights` must ship in the given order. Each day you load packages in order
        until the next one would exceed the ship's capacity. Return the smallest capacity that ships
        everything within `days` days.
    """,
    constraints=["1 <= days <= weights.length <= 5 * 10^4", "1 <= weights[i] <= 500"],
    sig="int shipWithinDays(int[] weights, int days)",
    hints=[
        "A bigger ship never needs more days. That monotonic property invites binary search.",
        "Search capacity between max(weights) and sum(weights). Check a capacity by greedily filling each day.",
        "lo, hi = max(weights), sum(weights)\nwhile lo < hi:\n    mid = (lo + hi) // 2\n    if daysNeeded(mid) <= days: hi = mid\n    else: lo = mid + 1\nreturn lo",
        "Each check is O(n), and there are O(log sum) checks. The lower bound is the heaviest package, since it must fit.",
    ],
    time="O(n log S)",
    space="O(1)",
    model=lambda weights, days: next(
        c
        for c in range(max(weights), sum(weights) + 1)
        if __import__("functools").reduce(
            lambda acc, w, c=c: (acc[0], acc[1] + w) if acc[1] + w <= c else (acc[0] + 1, w), weights, (1, 0)
        )[0]
        <= days
    ),
    java="""
        class Solution {
            private int daysNeeded(int[] weights, int cap) {
                int days = 1, load = 0;
                for (int w : weights) { if (load + w > cap) { days++; load = 0; } load += w; }
                return days;
            }
            public int shipWithinDays(int[] weights, int days) {
                int lo = 0, hi = 0;
                for (int w : weights) { lo = Math.max(lo, w); hi += w; }
                while (lo < hi) {
                    int mid = (lo + hi) >>> 1;
                    if (daysNeeded(weights, mid) <= days) hi = mid; else lo = mid + 1;
                }
                return lo;
            }
        }
    """,
    tests=[
        {"weights": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "days": 5},
        {"weights": [3, 2, 2, 4, 1, 4], "days": 3},
        {"weights": [1, 2, 3, 1, 1], "days": 4},
    ],
    gen=lambda r: (lambda w: {"weights": w, "days": r.randint(1, len(w))})(ints(r, 1, 10, 1, 15)),
)

P(
    slug="rotated-minimum",
    title="Minimum of a Rotated Sorted Array",
    difficulty="medium",
    topics=["arrays", "binary-search"],
    summary="Find the smallest value of a sorted array that was rotated.",
    statement="""
        A sorted array of distinct values was rotated at an unknown point (`[0,1,2,4,5,6,7]` might become
        `[4,5,6,7,0,1,2]`). Return its minimum in O(log n).
    """,
    constraints=["1 <= nums.length <= 5000", "distinct values"],
    sig="int findMin(int[] nums)",
    hints=[
        "Compare the middle value with the last value.",
        "If `nums[mid] > nums[hi]`, the drop (and the minimum) is to the right of `mid`; otherwise it's at `mid` or left.",
        "lo, hi = 0, n-1\nwhile lo < hi:\n    mid = (lo + hi) // 2\n    if nums[mid] > nums[hi]: lo = mid + 1\n    else: hi = mid\nreturn nums[lo]",
        "Each step keeps the half that contains the rotation point: O(log n).",
    ],
    time="O(log n)",
    space="O(1)",
    model=lambda nums: min(nums),
    java="""
        class Solution {
            public int findMin(int[] nums) {
                int lo = 0, hi = nums.length - 1;
                while (lo < hi) {
                    int mid = (lo + hi) >>> 1;
                    if (nums[mid] > nums[hi]) lo = mid + 1; else hi = mid;
                }
                return nums[lo];
            }
        }
    """,
    tests=[
        {"nums": [3, 4, 5, 1, 2]},
        {"nums": [4, 5, 6, 7, 0, 1, 2]},
        {"nums": [11, 13, 15, 17]},
        {"nums": [2, 1]},
    ],
    gen=lambda r: (lambda vals, k: {"nums": vals[k:] + vals[:k]})(
        *(lambda v: (v, r.randint(0, len(v) - 1)))(sorted(r.sample(range(-40, 40), r.randint(1, 12))))
    ),
)

P(
    slug="first-last-position",
    title="First and Last Position of a Value",
    difficulty="medium",
    topics=["arrays", "binary-search"],
    summary="Find where a value's block starts and ends in a sorted array.",
    statement="""
        `nums` is sorted ascending. Return `[first, last]`, the first and last index of `target`, or
        `[-1, -1]` if it's absent. Use O(log n).
    """,
    constraints=["0 <= nums.length <= 10^5", "sorted"],
    sig="int[] searchRange(int[] nums, int target)",
    hints=[
        "Find the left edge and the right edge with two separate binary searches.",
        "Search for the first index `>= target` and the first index `> target`; the block lies between.",
        "lo = lowerBound(target)\nif lo == n or nums[lo] != target: return [-1, -1]\nreturn [lo, lowerBound(target + 1) - 1]",
        "Two binary searches: O(log n) regardless of how many copies of the value there are.",
    ],
    time="O(log n)",
    space="O(1)",
    model=lambda nums, target: (
        [nums.index(target), len(nums) - 1 - nums[::-1].index(target)] if target in nums else [-1, -1]
    ),
    java="""
        class Solution {
            private int lowerBound(int[] a, long t) {
                int lo = 0, hi = a.length;
                while (lo < hi) { int mid = (lo + hi) >>> 1; if (a[mid] < t) lo = mid + 1; else hi = mid; }
                return lo;
            }
            public int[] searchRange(int[] nums, int target) {
                int lo = lowerBound(nums, target);
                if (lo == nums.length || nums[lo] != target) return new int[] {-1, -1};
                return new int[] {lo, lowerBound(nums, (long) target + 1) - 1};
            }
        }
    """,
    tests=[
        {"nums": [5, 7, 7, 8, 8, 10], "target": 8},
        {"nums": [5, 7, 7, 8, 8, 10], "target": 6},
        {"nums": [], "target": 0},
    ],
    gen=lambda r: {"nums": sorted(ints(r, 0, 15, 0, 6)), "target": r.randint(0, 6)},
)

P(
    slug="search-sorted-matrix",
    title="Search a Sorted Matrix",
    difficulty="medium",
    topics=["matrix", "binary-search"],
    summary="Find a value in a matrix sorted row by row.",
    statement="""
        Each row of `matrix` is sorted ascending, and each row's first value is greater than the previous
        row's last value. Return whether `target` is in the matrix, in O(log(rows × cols)).
    """,
    constraints=["1 <= rows, cols <= 100"],
    sig="boolean searchMatrix(int[][] matrix, int target)",
    hints=[
        "Read row by row, the matrix is one long sorted list.",
        "Binary search over positions `0 .. rows*cols - 1`, mapping position `p` to `matrix[p / cols][p % cols]`.",
        "lo, hi = 0, rows*cols - 1\nwhile lo <= hi:\n    mid = (lo + hi) // 2\n    v = matrix[mid // cols][mid % cols]\n"
        "    if v == target: return true\n    if v < target: lo = mid + 1\n    else: hi = mid - 1\nreturn false",
        "Treating the matrix as a flattened sorted array gives O(log(m n)).",
    ],
    time="O(log(m n))",
    space="O(1)",
    model=lambda matrix, target: any(target in row for row in matrix),
    java="""
        class Solution {
            public boolean searchMatrix(int[][] matrix, int target) {
                int rows = matrix.length, cols = matrix[0].length, lo = 0, hi = rows * cols - 1;
                while (lo <= hi) {
                    int mid = (lo + hi) >>> 1, v = matrix[mid / cols][mid % cols];
                    if (v == target) return true;
                    if (v < target) lo = mid + 1; else hi = mid - 1;
                }
                return false;
            }
        }
    """,
    tests=[
        {"matrix": [[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], "target": 3},
        {"matrix": [[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]], "target": 13},
        {"matrix": [[1]], "target": 1},
    ],
    gen=lambda r: (
        lambda m, n: (
            lambda vals: {"matrix": [vals[i * n : (i + 1) * n] for i in range(m)], "target": r.randint(0, 60)}
        )(sorted(r.sample(range(0, 60), m * n)))
    )(r.randint(1, 4), r.randint(1, 4)),
)

P(
    slug="task-scheduler",
    title="CPU Task Scheduler",
    difficulty="medium",
    topics=["greedy", "counting", "heaps"],
    summary="Fewest time units to run tasks with a cooldown between repeats.",
    statement="""
        Each letter in `tasks` is a task that takes one unit of time. Two runs of the same task must be at
        least `n` units apart; the CPU can idle. Return the minimum total time to run every task.
    """,
    constraints=["1 <= tasks.length <= 10^4", "0 <= n <= 100", "upper-case letters"],
    sig="int leastInterval(String tasks, int n)",
    hints=[
        "The most frequent task sets the skeleton of the schedule.",
        "With top count `m` shared by `k` tasks: `(m - 1) * (n + 1) + k` slots, but never fewer than the number of tasks.",
        "counts = count letters\nm = max(counts)\nk = number of letters with count m\nreturn max(len(tasks), (m - 1) * (n + 1) + k)",
        "Arrange the most frequent tasks into `m - 1` frames of length `n + 1` plus a final partial frame; other tasks fill "
        "the gaps. If they overflow the gaps, no idling is needed and the answer is just the task count. O(n).",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda tasks, n: (
        (
            lambda counts: (lambda f: f(f, dict(counts), {}, 0))(
                lambda f, left, ready, t: (
                    t
                    if not any(left.values())
                    else f(
                        f,
                        *(
                            lambda pick: (
                                ({**left, pick: left[pick] - 1} if pick else left),
                                ({**ready, pick: t + n + 1} if pick else ready),
                                t + 1,
                            )
                        )(
                            min(
                                (c for c in left if left[c] and ready.get(c, 0) <= t),
                                key=lambda c: (-left[c], c),
                                default=None,
                            )
                        ),
                    )
                )
            )
        )(__import__("collections").Counter(tasks))
        if len(tasks) <= 40
        else None
    ),
    java="""
        class Solution {
            public int leastInterval(String tasks, int n) {
                int[] counts = new int[26];
                int m = 0;
                for (char c : tasks.toCharArray()) m = Math.max(m, ++counts[c - 'A']);
                int k = 0;
                for (int c : counts) if (c == m) k++;
                return Math.max(tasks.length(), (m - 1) * (n + 1) + k);
            }
        }
    """,
    tests=[
        {"tasks": "AAABBB", "n": 2},
        {"tasks": "ACABDB", "n": 1},
        {"tasks": "AAABBB", "n": 3},
        {"tasks": "A", "n": 5},
        {"tasks": "AAAAAABCDEFG", "n": 2},
    ],
    gen=lambda r: {"tasks": word(r, 1, 14, "AABBCD"), "n": r.randint(0, 3)},
)

P(
    slug="gas-station-loop",
    title="Gas Station Loop",
    difficulty="medium",
    topics=["greedy", "arrays"],
    summary="Find the station where you can start and drive the full circle.",
    statement="""
        Stations sit on a circular road. At station `i` you get `gas[i]`; driving to station `i + 1` costs
        `cost[i]`. Starting with an empty tank, return the index of the station from which you can complete the
        loop, or `-1`. If an answer exists it is unique.
    """,
    constraints=["1 <= n <= 10^5", "0 <= gas[i], cost[i] <= 10^4"],
    sig="int canCompleteCircuit(int[] gas, int[] cost)",
    hints=[
        "If total gas is less than total cost, no start works.",
        "If you run dry between `start` and `i`, no station in that range can be the start. Restart at `i + 1`.",
        "total = tank = start = 0\nfor i in range(n):\n    diff = gas[i] - cost[i]\n    total += diff; tank += diff\n"
        "    if tank < 0: start = i + 1; tank = 0\nreturn start if total >= 0 else -1",
        "One pass, O(n). Skipping the failed stretch is safe: any start inside it reaches the failure point with even less gas.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda gas, cost: next(
        (
            s
            for s in range(len(gas))
            if all(
                sum(gas[(s + j) % len(gas)] - cost[(s + j) % len(gas)] for j in range(k + 1)) >= 0
                for k in range(len(gas))
            )
        ),
        -1,
    ),
    java="""
        class Solution {
            public int canCompleteCircuit(int[] gas, int[] cost) {
                int total = 0, tank = 0, start = 0;
                for (int i = 0; i < gas.length; i++) {
                    int diff = gas[i] - cost[i];
                    total += diff;
                    tank += diff;
                    if (tank < 0) { start = i + 1; tank = 0; }
                }
                return total >= 0 ? start : -1;
            }
        }
    """,
    tests=[
        {"gas": [1, 2, 3, 4, 5], "cost": [3, 4, 5, 1, 2]},
        {"gas": [2, 3, 4], "cost": [3, 4, 3]},
        {"gas": [5], "cost": [4]},
    ],
    gen=lambda r: (lambda n: {"gas": ints(r, n, n, 0, 6), "cost": ints(r, n, n, 0, 6)})(r.randint(1, 7)),
)

P(
    slug="jump-game-two",
    title="Fewest Jumps to the End",
    difficulty="medium",
    topics=["greedy", "arrays"],
    summary="Minimum jumps to reach the last index.",
    statement="""
        From index `i` you may jump forward up to `nums[i]` steps. Starting at index 0, return the minimum
        number of jumps to reach the last index. The last index is always reachable.
    """,
    constraints=["1 <= nums.length <= 10^4", "0 <= nums[i] <= 1000", "the end is reachable"],
    sig="int jump(int[] nums)",
    hints=[
        "Think in layers: all indices reachable with 1 jump, then with 2 jumps, and so on.",
        "Track the end of the current layer and the farthest index reachable from it.",
        "jumps = end = far = 0\nfor i in range(n - 1):\n    far = max(far, i + nums[i])\n    if i == end: jumps += 1; end = far\nreturn jumps",
        "This is BFS over index ranges done in one O(n) pass, with O(1) space.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda nums: (lambda f: f(f, 0))(
        lru_cache(None)(
            lambda f, i: (
                0
                if i >= len(nums) - 1
                else min((1 + f(f, j) for j in range(i + 1, min(len(nums), i + nums[i] + 1))), default=10**9)
            )
        )
    ),
    java="""
        class Solution {
            public int jump(int[] nums) {
                int jumps = 0, end = 0, far = 0;
                for (int i = 0; i < nums.length - 1; i++) {
                    far = Math.max(far, i + nums[i]);
                    if (i == end) { jumps++; end = far; }
                }
                return jumps;
            }
        }
    """,
    tests=[{"nums": [2, 3, 1, 1, 4]}, {"nums": [2, 3, 0, 1, 4]}, {"nums": [0]}, {"nums": [1, 1, 1, 1]}],
    gen=lambda r: {"nums": [r.randint(1, 4) for _ in range(r.randint(1, 12))]},
)

P(
    slug="partition-labels",
    title="Partition Labels",
    difficulty="medium",
    topics=["greedy", "strings", "two-pointers"],
    summary="Split a string so each letter appears in only one part.",
    statement="""
        Split `s` into as many parts as possible so that each letter appears in at most one part. Return the
        sizes of the parts, in order.
    """,
    constraints=["1 <= s.length <= 500", "lower-case letters"],
    sig="int[] partitionLabels(String s)",
    hints=[
        "A part can't end before the last occurrence of any letter inside it.",
        "Record each letter's last index. Extend the current part's end to cover each letter you see; cut when you reach it.",
        "last = {c: i for i, c in enumerate(s)}\nstart = end = 0\nfor i, c in enumerate(s):\n    end = max(end, last[c])\n"
        "    if i == end: sizes.append(end - start + 1); start = i + 1\nreturn sizes",
        "Cutting as early as allowed gives the most parts: O(n).",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda s: (
        lambda last: __import__("functools").reduce(
            lambda acc, ic: (
                (acc[0], max(acc[1], last[ic[1]]), acc[2])
                if ic[0] != max(acc[1], last[ic[1]])
                else (acc[0] + [ic[0] - acc[2] + 1], ic[0] + 1, ic[0] + 1)
            ),
            enumerate(s),
            ([], 0, 0),
        )[0]
    )({c: i for i, c in enumerate(s)}),
    java="""
        import java.util.*;

        class Solution {
            public int[] partitionLabels(String s) {
                int[] last = new int[26];
                for (int i = 0; i < s.length(); i++) last[s.charAt(i) - 'a'] = i;
                List<Integer> sizes = new ArrayList<>();
                int start = 0, end = 0;
                for (int i = 0; i < s.length(); i++) {
                    end = Math.max(end, last[s.charAt(i) - 'a']);
                    if (i == end) { sizes.add(end - start + 1); start = i + 1; }
                }
                return sizes.stream().mapToInt(Integer::intValue).toArray();
            }
        }
    """,
    tests=[{"s": "ababcbacadefegdehijhklij"}, {"s": "eccbbbbdec"}, {"s": "a"}, {"s": "abc"}],
    gen=lambda r: {"s": word(r, 1, 15, "abcdef")},
)

P(
    slug="wildcard-parentheses",
    title="Parentheses With Wildcards",
    difficulty="medium",
    topics=["strings", "greedy"],
    summary="Can '*' stand for '(', ')' or nothing to make the string valid?",
    statement="""
        `s` contains `(`, `)` and `*`. Each `*` can be `(`, `)` or an empty string. Return `true` if some
        choice makes `s` a valid parentheses string.
    """,
    constraints=["1 <= s.length <= 100"],
    sig="boolean checkValidString(String s)",
    hints=[
        "Track the range of possible open-bracket counts rather than one number.",
        "Keep `low` and `high`: `(` raises both, `)` lowers both, `*` lowers `low` and raises `high`. Clamp `low` at 0.",
        "low = high = 0\nfor c in s:\n    if c == '(': low += 1; high += 1\n    elif c == ')': low -= 1; high -= 1\n"
        "    else: low -= 1; high += 1\n    if high < 0: return false\n    low = max(low, 0)\nreturn low == 0",
        "`high < 0` means too many `)` even if every `*` is `(`. Ending with `low == 0` means some choice closes everything. O(n).",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda s: (lambda f: f(f, 0, 0))(
        lru_cache(None)(
            lambda f, i, open_: (
                open_ == 0
                if i == len(s)
                else open_ >= 0
                and (
                    f(f, i + 1, open_ + 1)
                    if s[i] == "("
                    else f(f, i + 1, open_ - 1)
                    if s[i] == ")"
                    else (f(f, i + 1, open_ + 1) or f(f, i + 1, open_ - 1) or f(f, i + 1, open_))
                )
            )
        )
    ),
    java="""
        class Solution {
            public boolean checkValidString(String s) {
                int low = 0, high = 0;
                for (char c : s.toCharArray()) {
                    if (c == '(') { low++; high++; }
                    else if (c == ')') { low--; high--; }
                    else { low--; high++; }
                    if (high < 0) return false;
                    low = Math.max(low, 0);
                }
                return low == 0;
            }
        }
    """,
    tests=[{"s": "()"}, {"s": "(*)"}, {"s": "(*))"}, {"s": ")("}, {"s": "((*"}, {"s": "*"}],
    gen=lambda r: {"s": word(r, 1, 10, "()*")},
)

P(
    slug="house-robber",
    title="House Robber",
    difficulty="medium",
    topics=["dynamic-programming"],
    summary="Maximize loot without robbing two neighboring houses.",
    statement="""
        `nums[i]` is the money in house `i` along a street. You can't rob two adjacent houses. Return the
        most money you can rob.
    """,
    constraints=["1 <= nums.length <= 100", "0 <= nums[i] <= 400"],
    sig="int rob(int[] nums)",
    hints=[
        "For each house, you either rob it or skip it.",
        "best(i) = max(best(i-1), best(i-2) + nums[i]). Only the last two values are needed.",
        "prev, cur = 0, 0\nfor x in nums:\n    prev, cur = cur, max(cur, prev + x)\nreturn cur",
        "Linear DP with two variables: O(n) time, O(1) space.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda nums: (
        max(
            sum(nums[i] for i in range(len(nums)) if mask >> i & 1)
            for mask in range(1 << len(nums))
            if not mask & (mask >> 1)
        )
        if len(nums) <= 16
        else None
    ),
    java="""
        class Solution {
            public int rob(int[] nums) {
                int prev = 0, cur = 0;
                for (int x : nums) { int next = Math.max(cur, prev + x); prev = cur; cur = next; }
                return cur;
            }
        }
    """,
    tests=[{"nums": [1, 2, 3, 1]}, {"nums": [2, 7, 9, 3, 1]}, {"nums": [5]}, {"nums": [2, 1, 1, 2]}],
    gen=lambda r: {"nums": ints(r, 1, 14, 0, 30)},
)

P(
    slug="house-robber-circle",
    title="House Robber on a Circle",
    difficulty="medium",
    topics=["dynamic-programming"],
    summary="Same as house robber, but the first and last houses are neighbors.",
    statement="""
        The houses form a circle, so the first and last are adjacent. You can't rob two adjacent houses.
        Return the most money you can rob.
    """,
    constraints=["1 <= nums.length <= 100", "0 <= nums[i] <= 1000"],
    sig="int robCircle(int[] nums)",
    hints=[
        "You can't take both the first and the last house.",
        "Solve the straight-line version twice: without the last house, and without the first. Take the better.",
        "if n == 1: return nums[0]\nreturn max(robLine(nums[0:n-1]), robLine(nums[1:n]))",
        "Two linear passes: O(n) time, O(1) space.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda nums: (
        nums[0]
        if len(nums) == 1
        else max(
            sum(nums[i] for i in range(len(nums)) if mask >> i & 1)
            for mask in range(1 << len(nums))
            if not mask & (mask >> 1) and not (mask & 1 and mask >> (len(nums) - 1) & 1)
        )
    ),
    java="""
        class Solution {
            private int line(int[] nums, int from, int to) {
                int prev = 0, cur = 0;
                for (int i = from; i <= to; i++) { int next = Math.max(cur, prev + nums[i]); prev = cur; cur = next; }
                return cur;
            }
            public int robCircle(int[] nums) {
                int n = nums.length;
                if (n == 1) return nums[0];
                return Math.max(line(nums, 0, n - 2), line(nums, 1, n - 1));
            }
        }
    """,
    tests=[{"nums": [2, 3, 2]}, {"nums": [1, 2, 3, 1]}, {"nums": [1, 2, 3]}, {"nums": [7]}],
    gen=lambda r: {"nums": ints(r, 1, 13, 0, 30)},
)

P(
    slug="word-break",
    title="Word Break",
    difficulty="medium",
    topics=["dynamic-programming", "strings", "hash-sets"],
    summary="Can a string be split into dictionary words?",
    statement="""
        Return `true` if `s` can be split into a sequence of one or more words from `dict` (words may be
        reused).
    """,
    constraints=["1 <= s.length <= 300", "1 <= dict.length <= 1000", "lower-case letters"],
    sig="boolean wordBreak(String s, String[] dict)",
    hints=[
        "If you know which prefixes can be split, can you extend that knowledge?",
        "ok[i] means `s[:i]` can be split. ok[i] is true if some `ok[j]` is true and `s[j:i]` is a word.",
        "ok = [true] + [false]*n\nfor i in 1..n:\n    for j in 0..i-1:\n        if ok[j] and s[j:i] in words: ok[i] = true; break\nreturn ok[n]",
        "O(n^2) substring checks with a hash set (O(n^3) counting substring building). Limiting `j` to the longest word length speeds it up.",
    ],
    time="O(n^2)",
    space="O(n)",
    model=lambda s, dict: (lambda f: f(f, 0))(
        lru_cache(None)(
            lambda f, i: i == len(s) or any(s.startswith(w, i) and f(f, i + len(w)) for w in dict)
        )
    ),
    java="""
        import java.util.*;

        class Solution {
            public boolean wordBreak(String s, String[] dict) {
                Set<String> words = new HashSet<>(Arrays.asList(dict));
                int n = s.length();
                boolean[] ok = new boolean[n + 1];
                ok[0] = true;
                for (int i = 1; i <= n; i++)
                    for (int j = 0; j < i && !ok[i]; j++)
                        if (ok[j] && words.contains(s.substring(j, i))) ok[i] = true;
                return ok[n];
            }
        }
    """,
    tests=[
        {"s": "leetcode", "dict": ["leet", "code"]},
        {"s": "applepenapple", "dict": ["apple", "pen"]},
        {"s": "catsandog", "dict": ["cats", "dog", "sand", "and", "cat"]},
        {"s": "aaaaaaa", "dict": ["aaaa", "aaa"]},
    ],
    gen=lambda r: {"s": word(r, 1, 12, "ab"), "dict": [word(r, 1, 3, "ab") for _ in range(r.randint(1, 4))]},
)

P(
    slug="partition-equal-subset",
    title="Split Into Two Equal Sums",
    difficulty="medium",
    topics=["dynamic-programming"],
    summary="Can an array be divided into two parts with equal sums?",
    statement="""
        Return `true` if `nums` can be split into two groups (every value in exactly one group) whose sums are equal.
    """,
    constraints=["1 <= nums.length <= 200", "1 <= nums[i] <= 100"],
    sig="boolean canPartition(int[] nums)",
    hints=[
        "Each group must sum to half the total. When is that impossible right away?",
        "If the total is odd, no. Otherwise it's subset sum: can some values add up to total / 2?",
        "if total % 2: return false\ntarget = total // 2\nreachable = {0}\nfor x in nums:\n    reachable |= {s + x for s in reachable if s + x <= target}\nreturn target in reachable",
        "A boolean DP over sums 0..target, updated from high to low for each value: O(n × target) time, O(target) space.",
    ],
    time="O(n * S)",
    space="O(S)",
    model=lambda nums: (
        sum(nums) % 2 == 0
        and sum(nums) // 2
        in __import__("functools").reduce(lambda acc, x: acc | {a + x for a in acc}, nums, {0})
    ),
    java="""
        class Solution {
            public boolean canPartition(int[] nums) {
                int total = 0;
                for (int x : nums) total += x;
                if (total % 2 != 0) return false;
                int target = total / 2;
                boolean[] ok = new boolean[target + 1];
                ok[0] = true;
                for (int x : nums) for (int s = target; s >= x; s--) if (ok[s - x]) ok[s] = true;
                return ok[target];
            }
        }
    """,
    tests=[{"nums": [1, 5, 11, 5]}, {"nums": [1, 2, 3, 5]}, {"nums": [2]}, {"nums": [1, 1]}],
    gen=lambda r: {"nums": ints(r, 1, 10, 1, 12)},
)

P(
    slug="target-sum-signs",
    title="Plus or Minus to Hit a Target",
    difficulty="medium",
    topics=["dynamic-programming", "backtracking"],
    summary="Count the ways to put + or - before each number to reach a target.",
    statement="""
        Put either `+` or `-` in front of every value in `nums`. Return how many sign choices make the expression
        equal `target`.
    """,
    constraints=["1 <= nums.length <= 20", "0 <= nums[i] <= 1000", "-1000 <= target <= 1000"],
    sig="int findTargetSumWays(int[] nums, int target)",
    hints=[
        "Trying all 2^n sign patterns works for small n. Can you count smarter?",
        "If P is the plus group, P - (total - P) = target, so P = (total + target) / 2. Count subsets with that sum.",
        "if (total + target) is odd or |target| > total: return 0\ngoal = (total + target) // 2\nways = [1] + [0]*goal\n"
        "for x in nums:\n    for s from goal down to x: ways[s] += ways[s - x]\nreturn ways[goal]",
        "The algebra turns it into counting subsets with a fixed sum: O(n × total). Zeros double the count, which this DP handles naturally.",
    ],
    time="O(n * S)",
    space="O(S)",
    model=lambda nums, target: sum(
        1
        for signs in __import__("itertools").product((1, -1), repeat=len(nums))
        if sum(a * b for a, b in zip(nums, signs, strict=True)) == target
    ),
    java="""
        class Solution {
            public int findTargetSumWays(int[] nums, int target) {
                int total = 0;
                for (int x : nums) total += x;
                if (Math.abs(target) > total || (total + target) % 2 != 0) return 0;
                int goal = (total + target) / 2;
                int[] ways = new int[goal + 1];
                ways[0] = 1;
                for (int x : nums) for (int s = goal; s >= x; s--) ways[s] += ways[s - x];
                return ways[goal];
            }
        }
    """,
    tests=[
        {"nums": [1, 1, 1, 1, 1], "target": 3},
        {"nums": [1], "target": 1},
        {"nums": [0, 0, 1], "target": 1},
        {"nums": [5], "target": -2},
    ],
    gen=lambda r: {"nums": ints(r, 1, 10, 0, 5), "target": r.randint(-6, 6)},
)

P(
    slug="longest-common-subsequence",
    title="Longest Common Subsequence",
    difficulty="medium",
    topics=["dynamic-programming", "strings"],
    summary="Length of the longest sequence both strings contain in order.",
    statement="""
        Return the length of the longest subsequence common to `a` and `b` (characters in the same order,
        not necessarily contiguous).
    """,
    constraints=["1 <= a.length, b.length <= 1000", "lower-case letters"],
    sig="int longestCommonSubsequence(String a, String b)",
    hints=[
        "Compare the last characters of the two prefixes.",
        "dp[i][j] = dp[i-1][j-1] + 1 if `a[i-1] == b[j-1]`, else max(dp[i-1][j], dp[i][j-1]).",
        "dp = (n+1) x (m+1) zeros\nfor i in 1..n:\n    for j in 1..m:\n        dp[i][j] = dp[i-1][j-1] + 1 if a[i-1] == b[j-1] else max(dp[i-1][j], dp[i][j-1])\nreturn dp[n][m]",
        "Classic 2-D DP: O(n m) time. Keeping only two rows makes it O(m) space.",
    ],
    time="O(n m)",
    space="O(n m)",
    model=lambda a, b: (lambda f: f(f, 0, 0))(
        lru_cache(None)(
            lambda f, i, j: (
                0
                if i == len(a) or j == len(b)
                else (1 + f(f, i + 1, j + 1) if a[i] == b[j] else max(f(f, i + 1, j), f(f, i, j + 1)))
            )
        )
    ),
    java="""
        class Solution {
            public int longestCommonSubsequence(String a, String b) {
                int n = a.length(), m = b.length();
                int[][] dp = new int[n + 1][m + 1];
                for (int i = 1; i <= n; i++)
                    for (int j = 1; j <= m; j++)
                        dp[i][j] = a.charAt(i - 1) == b.charAt(j - 1) ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1]);
                return dp[n][m];
            }
        }
    """,
    tests=[
        {"a": "abcde", "b": "ace"},
        {"a": "abc", "b": "abc"},
        {"a": "abc", "b": "def"},
        {"a": "bsbininm", "b": "jmjkbkjkv"},
    ],
    gen=lambda r: {"a": word(r, 1, 10, "abcd"), "b": word(r, 1, 10, "abcd")},
)

P(
    slug="coin-change-ways",
    title="Coin Change: Count the Ways",
    difficulty="medium",
    topics=["dynamic-programming"],
    summary="How many combinations of coins make an amount?",
    statement="""
        Return the number of combinations of `coins` (unlimited supply of each) that add up to `amount`.
        Order doesn't matter: 1+2 and 2+1 are the same combination. The answer fits in an int.
    """,
    constraints=["1 <= coins.length <= 300", "1 <= coins[i] <= 5000, distinct", "0 <= amount <= 5000"],
    sig="int change(int amount, int[] coins)",
    hints=[
        "Avoid counting the same combination in different orders.",
        "Loop over coins on the outside and amounts on the inside, so each combination is built in one coin order.",
        "ways = [1] + [0]*amount\nfor c in coins:\n    for a in c..amount:\n        ways[a] += ways[a - c]\nreturn ways[amount]",
        "O(coins × amount). Swapping the loop order would count permutations instead of combinations.",
    ],
    time="O(n * amount)",
    space="O(amount)",
    model=lambda amount, coins: (lambda f: f(f, 0, amount))(
        lru_cache(None)(
            lambda f, i, a: (
                1 if a == 0 else 0 if i == len(coins) or a < 0 else f(f, i, a - coins[i]) + f(f, i + 1, a)
            )
        )
    ),
    java="""
        class Solution {
            public int change(int amount, int[] coins) {
                int[] ways = new int[amount + 1];
                ways[0] = 1;
                for (int c : coins) for (int a = c; a <= amount; a++) ways[a] += ways[a - c];
                return ways[amount];
            }
        }
    """,
    tests=[
        {"amount": 5, "coins": [1, 2, 5]},
        {"amount": 3, "coins": [2]},
        {"amount": 10, "coins": [10]},
        {"amount": 0, "coins": [7]},
    ],
    gen=lambda r: {"amount": r.randint(0, 30), "coins": r.sample(range(1, 12), r.randint(1, 4))},
)

P(
    slug="max-product-subarray",
    title="Maximum Product Subarray",
    difficulty="medium",
    topics=["arrays", "dynamic-programming"],
    summary="Largest product of a contiguous subarray.",
    statement="""
        Return the largest product of any non-empty contiguous subarray of `nums`. The answer fits in an int.
    """,
    constraints=["1 <= nums.length <= 2 * 10^4", "-10 <= nums[i] <= 10"],
    sig="int maxProduct(int[] nums)",
    hints=[
        "A negative number can turn the smallest product into the largest.",
        "Track both the maximum and the minimum product of subarrays ending at each index.",
        "hi = lo = best = nums[0]\nfor x in nums[1:]:\n    hi, lo = max(x, hi*x, lo*x), min(x, hi*x, lo*x)\n    best = max(best, hi)\nreturn best",
        "Keeping the minimum lets a later negative flip it into a maximum: O(n) time, O(1) space.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda nums: max(
        __import__("math").prod(nums[i : j + 1]) for i in range(len(nums)) for j in range(i, len(nums))
    ),
    java="""
        class Solution {
            public int maxProduct(int[] nums) {
                int hi = nums[0], lo = nums[0], best = nums[0];
                for (int i = 1; i < nums.length; i++) {
                    int x = nums[i], a = hi * x, b = lo * x;
                    hi = Math.max(x, Math.max(a, b));
                    lo = Math.min(x, Math.min(a, b));
                    best = Math.max(best, hi);
                }
                return best;
            }
        }
    """,
    tests=[{"nums": [2, 3, -2, 4]}, {"nums": [-2, 0, -1]}, {"nums": [-2, 3, -4]}, {"nums": [-3]}],
    gen=lambda r: {"nums": ints(r, 1, 9, -4, 4)},
)

P(
    slug="unique-grid-paths",
    title="Paths Through a Grid",
    difficulty="medium",
    topics=["dynamic-programming", "math"],
    summary="Count right/down paths from one corner to the other.",
    statement="""
        A robot starts at the top-left of an `m × n` grid and can only move right or down. Return the number
        of distinct paths to the bottom-right corner. The answer fits in an int.
    """,
    constraints=["1 <= m, n <= 100", "answer <= 2 * 10^9"],
    sig="int uniquePaths(int m, int n)",
    hints=[
        "How many ways are there to reach a cell, given its top and left neighbors?",
        "paths(r, c) = paths(r-1, c) + paths(r, c-1), with 1 along the first row and column.",
        "row = [1]*n\nrepeat m-1 times:\n    for c in 1..n-1: row[c] += row[c-1]\nreturn row[n-1]",
        "One rolling row: O(m n) time, O(n) space. (It's also the binomial coefficient C(m+n-2, m-1).)",
    ],
    time="O(m n)",
    space="O(n)",
    model=lambda m, n: __import__("math").comb(m + n - 2, m - 1),
    java="""
        class Solution {
            public int uniquePaths(int m, int n) {
                int[] row = new int[n];
                java.util.Arrays.fill(row, 1);
                for (int r = 1; r < m; r++) for (int c = 1; c < n; c++) row[c] += row[c - 1];
                return row[n - 1];
            }
        }
    """,
    tests=[{"m": 3, "n": 7}, {"m": 3, "n": 2}, {"m": 1, "n": 1}, {"m": 10, "n": 10}, {"m": 17, "n": 17}],
    gen=lambda r: {"m": r.randint(1, 12), "n": r.randint(1, 12)},
)

P(
    slug="grid-paths-obstacles",
    title="Grid Paths Around Obstacles",
    difficulty="medium",
    topics=["dynamic-programming", "matrix"],
    summary="Count right/down paths that avoid blocked cells.",
    statement="""
        `grid[r][c]` is `1` for an obstacle and `0` for open. Moving only right or down from the top-left,
        return the number of paths to the bottom-right that avoid obstacles. The answer fits in an int.
    """,
    constraints=["1 <= m, n <= 100"],
    sig="int uniquePathsWithObstacles(int[][] grid)",
    hints=[
        "Same counting as without obstacles, except blocked cells contribute nothing.",
        "A blocked cell has 0 paths; otherwise paths = from above + from the left.",
        "row = [0]*n; row[0] = 1 if grid[0][0] == 0 else 0\nfor each row r:\n    for c in 0..n-1:\n"
        "        if grid[r][c]: row[c] = 0\n        elif c > 0: row[c] += row[c-1]\nreturn row[n-1]",
        "O(m n) time with a single rolling row. A blocked start or end gives 0.",
    ],
    time="O(m n)",
    space="O(n)",
    model=lambda grid: (lambda f: f(f, 0, 0))(
        lru_cache(None)(
            lambda f, r, c: (
                0
                if r >= len(grid) or c >= len(grid[0]) or grid[r][c]
                else 1
                if (r, c) == (len(grid) - 1, len(grid[0]) - 1)
                else f(f, r + 1, c) + f(f, r, c + 1)
            )
        )
    ),
    java="""
        class Solution {
            public int uniquePathsWithObstacles(int[][] grid) {
                int n = grid[0].length;
                int[] row = new int[n];
                row[0] = grid[0][0] == 0 ? 1 : 0;
                for (int[] cells : grid)
                    for (int c = 0; c < n; c++) {
                        if (cells[c] == 1) row[c] = 0;
                        else if (c > 0) row[c] += row[c - 1];
                    }
                return row[n - 1];
            }
        }
    """,
    tests=[
        {"grid": [[0, 0, 0], [0, 1, 0], [0, 0, 0]]},
        {"grid": [[0, 1], [0, 0]]},
        {"grid": [[1]]},
        {"grid": [[0]]},
    ],
    gen=lambda r: (
        lambda m, n: {"grid": [[1 if r.random() < 0.2 else 0 for _ in range(n)] for _ in range(m)]}
    )(r.randint(1, 5), r.randint(1, 5)),
)

P(
    slug="min-path-sum",
    title="Minimum Path Sum",
    difficulty="medium",
    topics=["dynamic-programming", "matrix"],
    summary="Cheapest right/down path through a grid of costs.",
    statement="""
        Each cell of `grid` holds a non-negative cost. Moving only right or down from the top-left to the
        bottom-right, return the smallest possible sum of the cells on the path.
    """,
    constraints=["1 <= m, n <= 200", "0 <= grid[i][j] <= 200"],
    sig="int minPathSum(int[][] grid)",
    hints=[
        "The cheapest way into a cell comes from its top or left neighbor.",
        "cost[r][c] = grid[r][c] + min(cost[r-1][c], cost[r][c-1]), treating outside cells as unreachable.",
        "row = [inf]*n; row[0] = 0\nfor each grid row:\n    row[0] += cells[0]\n    for c in 1..n-1: row[c] = cells[c] + min(row[c], row[c-1])\nreturn row[n-1]",
        "O(m n) time with one rolling row of size n.",
    ],
    time="O(m n)",
    space="O(n)",
    model=lambda grid: (lambda f: f(f, 0, 0))(
        lru_cache(None)(
            lambda f, r, c: (
                grid[r][c]
                + (
                    0
                    if (r, c) == (len(grid) - 1, len(grid[0]) - 1)
                    else min(
                        (f(f, r + 1, c) if r + 1 < len(grid) else 10**9),
                        (f(f, r, c + 1) if c + 1 < len(grid[0]) else 10**9),
                    )
                )
            )
        )
    ),
    java="""
        class Solution {
            public int minPathSum(int[][] grid) {
                int n = grid[0].length;
                int[] row = new int[n];
                java.util.Arrays.fill(row, Integer.MAX_VALUE);
                row[0] = 0;
                for (int[] cells : grid) {
                    row[0] += cells[0];
                    for (int c = 1; c < n; c++) row[c] = cells[c] + Math.min(row[c], row[c - 1]);
                }
                return row[n - 1];
            }
        }
    """,
    tests=[{"grid": [[1, 3, 1], [1, 5, 1], [4, 2, 1]]}, {"grid": [[1, 2, 3], [4, 5, 6]]}, {"grid": [[7]]}],
    gen=lambda r: (lambda m, n: {"grid": [[r.randint(0, 9) for _ in range(n)] for _ in range(m)]})(
        r.randint(1, 5), r.randint(1, 5)
    ),
)

P(
    slug="count-palindromic-substrings",
    title="Count Palindromic Substrings",
    difficulty="medium",
    topics=["strings", "dynamic-programming", "two-pointers"],
    summary="How many substrings read the same backwards?",
    statement="""
        Return how many substrings of `s` are palindromes. Substrings at different positions count separately,
        even if they're equal.
    """,
    constraints=["1 <= s.length <= 1000", "lower-case letters"],
    sig="int countSubstrings(String s)",
    hints=[
        "Every palindrome has a center.",
        "Expand around each of the `2n - 1` centers (single characters and gaps between them) while the ends match.",
        "count = 0\nfor center in 0..2n-2:\n    l, r = center // 2, center // 2 + center % 2\n    while l >= 0 and r < n and s[l] == s[r]:\n        count += 1; l -= 1; r += 1\nreturn count",
        "Each expansion step finds one new palindrome: O(n^2) time, O(1) space.",
    ],
    time="O(n^2)",
    space="O(1)",
    model=lambda s: sum(1 for i in range(len(s)) for j in range(i + 1, len(s) + 1) if s[i:j] == s[i:j][::-1]),
    java="""
        class Solution {
            public int countSubstrings(String s) {
                int n = s.length(), count = 0;
                for (int center = 0; center < 2 * n - 1; center++) {
                    int l = center / 2, r = l + center % 2;
                    while (l >= 0 && r < n && s.charAt(l) == s.charAt(r)) { count++; l--; r++; }
                }
                return count;
            }
        }
    """,
    tests=[{"s": "abc"}, {"s": "aaa"}, {"s": "a"}, {"s": "abba"}],
    gen=lambda r: {"s": word(r, 1, 14, "ab")},
)

P(
    slug="longest-palindromic-substring",
    title="Longest Palindromic Substring",
    difficulty="medium",
    topics=["strings", "two-pointers", "dynamic-programming"],
    summary="Find the longest substring that's a palindrome.",
    statement="""
        Return the longest palindromic substring of `s`. If several have the same maximum length, return the
        one that starts earliest.
    """,
    constraints=["1 <= s.length <= 1000", "letters and digits"],
    sig="String longestPalindrome(String s)",
    hints=[
        "Grow palindromes outward from their centers.",
        "Try every center (each character and each gap), expand while the ends match, and keep the longest.",
        "best = (0, 1)\nfor each center:\n    expand l, r while s[l] == s[r]\n    if longer than best (strictly): best = (l+1, r)\nreturn s[best]",
        "O(n^2) time, O(1) space. Only replacing on a strictly longer palindrome, scanning centers left to right, "
        "keeps the earliest one on ties.",
    ],
    time="O(n^2)",
    space="O(1)",
    model=lambda s: max(
        (s[i:j] for i in range(len(s)) for j in range(i + 1, len(s) + 1) if s[i:j] == s[i:j][::-1]),
        key=lambda t: (len(t), -s.find(t)),
    ),
    java="""
        class Solution {
            public String longestPalindrome(String s) {
                int n = s.length(), bestStart = 0, bestLen = 1;
                for (int center = 0; center < 2 * n - 1; center++) {
                    int l = center / 2, r = l + center % 2;
                    while (l >= 0 && r < n && s.charAt(l) == s.charAt(r)) { l--; r++; }
                    int len = r - l - 1, start = l + 1;
                    if (len > bestLen || (len == bestLen && start < bestStart)) { bestLen = len; bestStart = start; }
                }
                return s.substring(bestStart, bestStart + bestLen);
            }
        }
    """,
    tests=[{"s": "babad"}, {"s": "cbbd"}, {"s": "a"}, {"s": "forgeeksskeegfor"}, {"s": "abcd"}],
    gen=lambda r: {"s": word(r, 1, 14, "abc")},
)
