"""Easy problems, part 1: arrays and iteration."""

from collections import Counter

from scripts.problembank import P, ints

P(
    slug="sum-of-evens",
    title="Sum of Even Numbers",
    difficulty="easy",
    topics=["arrays", "iteration"],
    summary="Add up only the even values in an array.",
    statement="""
        Given an integer array `nums`, return the sum of the values that are even.
        Negative numbers can be even too (`-4` is even). An empty array sums to `0`.
    """,
    constraints=["0 <= nums.length <= 10^4", "-10^4 <= nums[i] <= 10^4"],
    sig="int sumEvens(int[] nums)",
    hints=[
        "Visit every number once and decide whether it belongs in the total.",
        "A number is even when `n % 2 == 0`. In Java that also works for negatives.",
        "total = 0\nfor n in nums:\n    if n % 2 == 0: total += n\nreturn total",
        "One pass with a running total: O(n) time, O(1) space. Using `% 2 == 0` rather than "
        "`% 2 == 1` for the check matters, because in Java `-3 % 2` is `-1`, not `1`.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda nums: sum(x for x in nums if x % 2 == 0),
    java="""
        class Solution {
            public int sumEvens(int[] nums) {
                int total = 0;
                for (int n : nums) if (n % 2 == 0) total += n;
                return total;
            }
        }
    """,
    tests=[
        {"nums": [1, 2, 3, 4]},
        {"nums": [-4, -3, 7]},
        {"nums": []},
        {"nums": [1, 3, 5]},
        {"nums": [0, 0, 10]},
    ],
    gen=lambda r: {"nums": ints(r, 0, 30, -100, 100)},
    explain={0: "2 + 4 = 6."},
)

P(
    slug="count-negatives",
    title="Count Negative Numbers",
    difficulty="easy",
    topics=["arrays", "counting"],
    summary="Count how many values in an array are below zero.",
    statement="""
        Given an integer array `nums`, return how many of its values are strictly less than zero.
        Zero is not negative.
    """,
    constraints=["0 <= nums.length <= 10^4", "-10^5 <= nums[i] <= 10^5"],
    sig="int countNegatives(int[] nums)",
    hints=[
        "You only need a counter and one look at each value.",
        "Increase the counter whenever a value is `< 0` (not `<= 0`).",
        "count = 0\nfor n in nums:\n    if n < 0: count += 1\nreturn count",
        "A single scan is O(n) time and O(1) space. The only trap is zero: the problem says strictly "
        "less than zero, so `0` must not be counted.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda nums: sum(1 for x in nums if x < 0),
    java="""
        class Solution {
            public int countNegatives(int[] nums) {
                int count = 0;
                for (int n : nums) if (n < 0) count++;
                return count;
            }
        }
    """,
    tests=[{"nums": [-1, 2, -3, 0]}, {"nums": [5, 6]}, {"nums": [0, 0]}, {"nums": [-7]}, {"nums": []}],
    gen=lambda r: {"nums": ints(r, 0, 25, -20, 20)},
)

P(
    slug="second-largest",
    title="Second Largest Value",
    difficulty="easy",
    topics=["arrays", "iteration"],
    summary="Find the second-largest distinct value, or -1 if there isn't one.",
    statement="""
        Given an array of non-negative integers `nums`, return the second-largest **distinct** value.
        If every value is the same, or the array has fewer than two values, return `-1`.

        For `[5, 5, 3]` the largest is `5` and the second-largest distinct value is `3`.
    """,
    constraints=["0 <= nums.length <= 10^4", "0 <= nums[i] <= 10^9"],
    sig="int secondLargest(int[] nums)",
    hints=[
        "Can you find the answer in a single pass if you remember two numbers as you go?",
        "Track `first` (largest so far) and `second` (largest value strictly smaller than `first`).",
        "first = second = -1\nfor n in nums:\n    if n > first: second = first; first = n\n"
        "    elif first > n > second: second = n\nreturn second",
        "Keeping the top two values makes this O(n) time and O(1) space; sorting would be O(n log n). "
        "The `first > n` check is what skips duplicates of the maximum, so `[5, 5, 3]` gives `3`.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda nums: sorted(set(nums))[-2] if len(set(nums)) >= 2 else -1,
    java="""
        class Solution {
            public int secondLargest(int[] nums) {
                int first = -1, second = -1;
                for (int n : nums) {
                    if (n > first) { second = first; first = n; }
                    else if (n < first && n > second) second = n;
                }
                return second;
            }
        }
    """,
    tests=[
        {"nums": [3, 9, 4, 7]},
        {"nums": [5, 5, 3]},
        {"nums": [8, 8]},
        {"nums": [1]},
        {"nums": []},
        {"nums": [0, 2, 2, 1]},
    ],
    gen=lambda r: {"nums": ints(r, 0, 20, 0, 15)},
    explain={1: "5 appears twice; the next distinct value is 3.", 2: "Only one distinct value."},
)

P(
    slug="is-sorted",
    title="Is the Array Sorted?",
    difficulty="easy",
    topics=["arrays", "iteration"],
    summary="Check whether an array is in non-decreasing order.",
    statement="""
        Return `true` if `nums` is sorted in non-decreasing order (each value is greater than or
        equal to the one before it), otherwise `false`. Empty and one-element arrays are sorted.
    """,
    constraints=["0 <= nums.length <= 10^4", "-10^9 <= nums[i] <= 10^9"],
    sig="boolean isSorted(int[] nums)",
    hints=[
        "You only ever need to compare neighbors.",
        "If any value is smaller than the one before it, the array isn't sorted.",
        "for i from 1 to n-1:\n    if nums[i] < nums[i-1]: return false\nreturn true",
        "Comparing each adjacent pair once is O(n) time and O(1) space. Equal neighbors are allowed "
        "(non-decreasing), so the check is `<`, not `<=`.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda nums: all(nums[i] >= nums[i - 1] for i in range(1, len(nums))),
    java="""
        class Solution {
            public boolean isSorted(int[] nums) {
                for (int i = 1; i < nums.length; i++) if (nums[i] < nums[i - 1]) return false;
                return true;
            }
        }
    """,
    tests=[
        {"nums": [1, 2, 2, 5]},
        {"nums": [3, 1]},
        {"nums": []},
        {"nums": [7]},
        {"nums": [1, 2, 3, 2]},
        {"nums": [-5, -5, 0]},
    ],
    gen=lambda r: {"nums": sorted(ints(r, 0, 15, -9, 9)) if r.random() < 0.5 else ints(r, 2, 15, -9, 9)},
)

P(
    slug="reverse-array",
    title="Reverse an Array",
    difficulty="easy",
    topics=["arrays", "two-pointers"],
    summary="Return the values of an array in reverse order.",
    statement="""
        Given an integer array `nums`, return a new array with the same values in reverse order.
    """,
    constraints=["0 <= nums.length <= 10^4"],
    sig="int[] reverseArray(int[] nums)",
    hints=[
        "The first value of the answer is the last value of the input.",
        "Either fill a new array from the back, or swap pairs from both ends moving inward.",
        "out = new array of size n\nfor i from 0 to n-1:\n    out[i] = nums[n-1-i]\nreturn out",
        "Copying with index `n-1-i` is O(n) time and O(n) space for the result. Swapping in place with "
        "two pointers (`i` from the left, `j` from the right, until they meet) needs no extra array.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda nums: nums[::-1],
    java="""
        class Solution {
            public int[] reverseArray(int[] nums) {
                int n = nums.length;
                int[] out = new int[n];
                for (int i = 0; i < n; i++) out[i] = nums[n - 1 - i];
                return out;
            }
        }
    """,
    tests=[{"nums": [1, 2, 3]}, {"nums": [9]}, {"nums": [4, 4, 1, 0]}, {"nums": []}],
    gen=lambda r: {"nums": ints(r, 0, 12, -50, 50)},
)

P(
    slug="move-zeroes",
    title="Move Zeroes to the End",
    difficulty="easy",
    topics=["arrays", "two-pointers"],
    summary="Push every zero to the end while keeping the other values in order.",
    statement="""
        Given `nums`, return an array where all non-zero values keep their original relative order
        and every `0` is moved to the end.
    """,
    constraints=["0 <= nums.length <= 10^4", "-10^9 <= nums[i] <= 10^9"],
    sig="int[] moveZeroes(int[] nums)",
    hints=[
        "Think about where the next non-zero value should go.",
        "Keep a write index. Copy each non-zero value to that index and advance it; fill the rest with zeroes.",
        "w = 0\nfor n in nums:\n    if n != 0: nums[w] = n; w += 1\nwhile w < len(nums): nums[w] = 0; w += 1\nreturn nums",
        "The write pointer never passes the read pointer, so this works in place in one pass: O(n) "
        "time, O(1) extra space. Order is kept because values are written in the order they're read.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda nums: [x for x in nums if x != 0] + [0] * nums.count(0),
    java="""
        class Solution {
            public int[] moveZeroes(int[] nums) {
                int w = 0;
                for (int n : nums) if (n != 0) nums[w++] = n;
                while (w < nums.length) nums[w++] = 0;
                return nums;
            }
        }
    """,
    tests=[{"nums": [0, 1, 0, 3, 12]}, {"nums": [0]}, {"nums": [4, 5]}, {"nums": [0, 0, 1]}, {"nums": []}],
    gen=lambda r: {"nums": ints(r, 0, 15, -2, 3)},
)

P(
    slug="unique-sorted",
    title="Remove Duplicates from a Sorted Array",
    difficulty="easy",
    topics=["arrays", "two-pointers"],
    summary="Return each value of a sorted array once.",
    statement="""
        `nums` is sorted in non-decreasing order. Return a new array that contains each distinct
        value exactly once, still in sorted order.
    """,
    constraints=["0 <= nums.length <= 10^4", "nums is sorted in non-decreasing order"],
    sig="int[] uniqueSorted(int[] nums)",
    hints=[
        "In a sorted array, duplicates sit next to each other.",
        "Keep a value only if it differs from the previous one.",
        "out = []\nfor i, n in enumerate(nums):\n    if i == 0 or n != nums[i-1]: out.append(n)\nreturn out",
        "Because equal values are adjacent, comparing with the previous element finds every duplicate "
        "in one O(n) pass. No set is needed, unlike for unsorted input.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda nums: sorted(set(nums)),
    java="""
        class Solution {
            public int[] uniqueSorted(int[] nums) {
                int count = 0;
                for (int i = 0; i < nums.length; i++) if (i == 0 || nums[i] != nums[i - 1]) count++;
                int[] out = new int[count];
                int w = 0;
                for (int i = 0; i < nums.length; i++) if (i == 0 || nums[i] != nums[i - 1]) out[w++] = nums[i];
                return out;
            }
        }
    """,
    tests=[
        {"nums": [1, 1, 2]},
        {"nums": [0, 0, 1, 1, 1, 2, 3, 3]},
        {"nums": []},
        {"nums": [5]},
        {"nums": [-2, -2, -2]},
    ],
    gen=lambda r: {"nums": sorted(ints(r, 0, 20, -5, 5))},
)

P(
    slug="running-sum",
    title="Running Sum",
    difficulty="easy",
    topics=["arrays", "prefix-sums"],
    summary="Replace each value with the total of everything up to it.",
    statement="""
        Return an array where element `i` is `nums[0] + nums[1] + ... + nums[i]`.
    """,
    constraints=["0 <= nums.length <= 1000", "-10^6 <= nums[i] <= 10^6"],
    sig="int[] runningSum(int[] nums)",
    hints=[
        "Each answer is the previous answer plus one more number.",
        "Keep a running total and write it after adding each value.",
        "total = 0\nfor i in range(n):\n    total += nums[i]\n    out[i] = total\nreturn out",
        "Reusing the previous prefix sum avoids re-adding from the start each time: O(n) instead of "
        "O(n^2). This prefix-sum idea underlies many range-sum problems.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda nums: [sum(nums[: i + 1]) for i in range(len(nums))],
    java="""
        class Solution {
            public int[] runningSum(int[] nums) {
                int[] out = new int[nums.length];
                int total = 0;
                for (int i = 0; i < nums.length; i++) { total += nums[i]; out[i] = total; }
                return out;
            }
        }
    """,
    tests=[{"nums": [1, 2, 3, 4]}, {"nums": [3, -1, 2]}, {"nums": []}, {"nums": [5]}],
    gen=lambda r: {"nums": ints(r, 0, 20, -50, 50)},
    explain={0: "[1, 1+2, 1+2+3, 1+2+3+4]."},
)

P(
    slug="max-consecutive-ones",
    title="Longest Run of Ones",
    difficulty="easy",
    topics=["arrays", "iteration"],
    summary="Find the longest streak of consecutive 1s in a binary array.",
    statement="""
        `nums` contains only `0`s and `1`s. Return the length of the longest run of consecutive `1`s.
    """,
    constraints=["0 <= nums.length <= 10^5", "nums[i] is 0 or 1"],
    sig="int longestOnes(int[] nums)",
    hints=[
        "Count the current streak as you walk the array.",
        "A `1` extends the current streak; a `0` resets it. Track the best streak seen.",
        "best = cur = 0\nfor n in nums:\n    cur = cur + 1 if n == 1 else 0\n    best = max(best, cur)\nreturn best",
        "One pass with two counters gives O(n) time and O(1) space. Updating `best` after every step "
        "(not only when a `0` appears) handles a streak that runs to the end of the array.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda nums: max((len(run) for run in "".join(map(str, nums)).split("0")), default=0),
    java="""
        class Solution {
            public int longestOnes(int[] nums) {
                int best = 0, cur = 0;
                for (int n : nums) { cur = n == 1 ? cur + 1 : 0; best = Math.max(best, cur); }
                return best;
            }
        }
    """,
    tests=[
        {"nums": [1, 1, 0, 1, 1, 1]},
        {"nums": [0, 0]},
        {"nums": [1]},
        {"nums": []},
        {"nums": [1, 0, 1, 1]},
    ],
    gen=lambda r: {"nums": ints(r, 0, 25, 0, 1)},
)

P(
    slug="single-number",
    title="The Number That Appears Once",
    difficulty="easy",
    topics=["arrays", "bit-manipulation"],
    summary="Every value appears twice except one. Find it.",
    statement="""
        In `nums`, every value appears exactly twice except for one value, which appears once.
        Return that value. Try to use constant extra space.
    """,
    constraints=["1 <= nums.length <= 3 * 10^4", "nums.length is odd", "Exactly one value appears once"],
    sig="int singleNumber(int[] nums)",
    hints=[
        "A hash map of counts works. Is there a trick that needs no extra memory?",
        "XOR has two useful properties: `x ^ x == 0` and `x ^ 0 == x`, and order doesn't matter.",
        "result = 0\nfor n in nums: result ^= n\nreturn result",
        "XOR-ing everything cancels each pair to 0, leaving only the single value: O(n) time, O(1) "
        "space. A counting map would also be O(n) time but O(n) space.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda nums: next(x for x, c in Counter(nums).items() if c == 1),
    java="""
        class Solution {
            public int singleNumber(int[] nums) {
                int result = 0;
                for (int n : nums) result ^= n;
                return result;
            }
        }
    """,
    tests=[
        {"nums": [2, 2, 1]},
        {"nums": [4, 1, 2, 1, 2]},
        {"nums": [7]},
        {"nums": [-3, 5, 5]},
        {"nums": [0, 9, 9]},
    ],
    gen=lambda r: (lambda vals: {"nums": r.sample(vals[:-1] * 2 + vals[-1:], 2 * len(vals) - 1)})(
        r.sample(range(-50, 50), r.randint(1, 8))
    ),
)

P(
    slug="missing-number",
    title="Find the Missing Number",
    difficulty="easy",
    topics=["arrays", "math"],
    summary="An array holds 0..n with one number missing. Find it.",
    statement="""
        `nums` contains `n` distinct numbers taken from the range `0` to `n` (inclusive), so exactly
        one number in that range is missing. Return it.
    """,
    constraints=["1 <= n <= 10^4", "All values are distinct and in [0, n]"],
    sig="int missingNumber(int[] nums)",
    hints=[
        "You know exactly which numbers should be there.",
        "The sum 0 + 1 + ... + n is `n * (n + 1) / 2`. Compare it with the actual sum.",
        "n = len(nums)\nexpected = n * (n + 1) / 2\nreturn expected - sum(nums)",
        "Subtracting the actual sum from the expected sum is O(n) time and O(1) space. (XOR-ing all "
        "indices and values works too and can't overflow.)",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda nums: next(i for i in range(len(nums) + 1) if i not in set(nums)),
    java="""
        class Solution {
            public int missingNumber(int[] nums) {
                int n = nums.length;
                long expected = (long) n * (n + 1) / 2, sum = 0;
                for (int v : nums) sum += v;
                return (int) (expected - sum);
            }
        }
    """,
    tests=[
        {"nums": [3, 0, 1]},
        {"nums": [0, 1]},
        {"nums": [9, 6, 4, 2, 3, 5, 7, 0, 1]},
        {"nums": [1]},
        {"nums": [0]},
    ],
    gen=lambda r: (lambda n, miss: {"nums": r.sample([x for x in range(n + 1) if x != miss], n)})(
        *(lambda n: (n, r.randint(0, n)))(r.randint(1, 20))
    ),
)

P(
    slug="majority-element",
    title="Majority Element",
    difficulty="easy",
    topics=["arrays", "counting"],
    summary="Find the value that appears more than half the time.",
    statement="""
        Return the value that appears more than `n / 2` times in `nums`. Such a value is guaranteed to exist.
    """,
    constraints=["1 <= nums.length <= 5 * 10^4", "A majority value always exists"],
    sig="int majorityElement(int[] nums)",
    hints=[
        "Counting with a hash map works. Can you do it with O(1) memory?",
        "Boyer-Moore voting: keep a candidate and a count; matching values add a vote, others remove one.",
        "candidate, count = None, 0\nfor n in nums:\n    if count == 0: candidate = n\n"
        "    count += 1 if n == candidate else -1\nreturn candidate",
        "Each non-majority value can cancel at most one majority vote, and the majority has more than "
        "half the votes, so it survives. O(n) time, O(1) space.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda nums: Counter(nums).most_common(1)[0][0],
    java="""
        class Solution {
            public int majorityElement(int[] nums) {
                int candidate = 0, count = 0;
                for (int n : nums) {
                    if (count == 0) candidate = n;
                    count += n == candidate ? 1 : -1;
                }
                return candidate;
            }
        }
    """,
    tests=[
        {"nums": [3, 2, 3]},
        {"nums": [2, 2, 1, 1, 1, 2, 2]},
        {"nums": [5]},
        {"nums": [1, 9, 9]},
        {"nums": [-1, -1, -1, 4]},
    ],
    gen=lambda r: (
        lambda m, others: {"nums": r.sample([m] * (len(others) + 1) + others, 2 * len(others) + 1)}
    )(r.randint(-9, 9), ints(r, 0, 8, -9, 9)),
)

P(
    slug="array-intersection",
    title="Intersection of Two Arrays",
    difficulty="easy",
    topics=["arrays", "hash-sets"],
    summary="List the distinct values that appear in both arrays, sorted.",
    statement="""
        Return the distinct values that appear in both `a` and `b`, in ascending order.
    """,
    constraints=["0 <= a.length, b.length <= 1000", "0 <= values <= 1000"],
    sig="int[] intersection(int[] a, int[] b)",
    hints=[
        "Checking every pair works but is slow. How can you check membership quickly?",
        "Put one array's values in a set; keep values of the other array that are in it.",
        "seen = set(a)\nresult = sorted({x for x in b if x in seen})\nreturn result",
        "Building a set is O(n) and each lookup is O(1) on average, so the work is O(n + m) plus "
        "O(k log k) to sort the k common values. Using a set for the result removes duplicates.",
    ],
    time="O(n + m + k log k)",
    space="O(n)",
    model=lambda a, b: sorted(set(a) & set(b)),
    java="""
        import java.util.*;

        class Solution {
            public int[] intersection(int[] a, int[] b) {
                Set<Integer> seen = new HashSet<>();
                for (int x : a) seen.add(x);
                TreeSet<Integer> common = new TreeSet<>();
                for (int x : b) if (seen.contains(x)) common.add(x);
                int[] out = new int[common.size()];
                int i = 0;
                for (int x : common) out[i++] = x;
                return out;
            }
        }
    """,
    tests=[
        {"a": [1, 2, 2, 1], "b": [2, 2]},
        {"a": [4, 9, 5], "b": [9, 4, 9, 8, 4]},
        {"a": [1], "b": []},
        {"a": [3, 1], "b": [5, 6]},
    ],
    gen=lambda r: {"a": ints(r, 0, 12, 0, 15), "b": ints(r, 0, 12, 0, 15)},
)

P(
    slug="plus-one",
    title="Add One to a Digit Array",
    difficulty="easy",
    topics=["arrays", "math"],
    summary="A number is stored as digits; add one to it.",
    statement="""
        `digits` holds a non-negative integer, most significant digit first, with no leading zeros
        (except the number 0 itself). Return the digits of that number plus one.
    """,
    constraints=["1 <= digits.length <= 100", "0 <= digits[i] <= 9"],
    sig="int[] plusOne(int[] digits)",
    hints=[
        "Do it the way you would on paper, starting from the last digit.",
        "A 9 becomes 0 and carries 1 to the left. If the carry falls off the front, you need one more digit.",
        "for i from n-1 down to 0:\n    if digits[i] < 9: digits[i] += 1; return digits\n    digits[i] = 0\n"
        "return [1] + digits",
        "Stop at the first digit that isn't 9: O(n) in the worst case (all 9s) and usually much less. "
        "Converting to a long would overflow for 100 digits, so work on the digits directly.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda digits: [int(c) for c in str(int("".join(map(str, digits))) + 1)],
    java="""
        class Solution {
            public int[] plusOne(int[] digits) {
                for (int i = digits.length - 1; i >= 0; i--) {
                    if (digits[i] < 9) { digits[i]++; return digits; }
                    digits[i] = 0;
                }
                int[] out = new int[digits.length + 1];
                out[0] = 1;
                return out;
            }
        }
    """,
    tests=[
        {"digits": [1, 2, 3]},
        {"digits": [9, 9]},
        {"digits": [0]},
        {"digits": [4, 9, 9]},
        {"digits": [9]},
    ],
    gen=lambda r: {
        "digits": [r.randint(1, 9)] + [r.choice([9, 9, r.randint(0, 9)]) for _ in range(r.randint(0, 12))]
    },
)

P(
    slug="pascals-row",
    title="Row of Pascal's Triangle",
    difficulty="easy",
    topics=["arrays", "dynamic-programming"],
    summary="Return row n of Pascal's triangle.",
    statement="""
        Return row `n` (0-indexed) of Pascal's triangle. Row 0 is `[1]`, row 1 is `[1, 1]`, and
        each inner value is the sum of the two values above it.
    """,
    constraints=["0 <= n <= 30"],
    sig="int[] pascalRow(int n)",
    hints=[
        "Build each row from the previous one.",
        "You can update a single array from right to left so you never overwrite a value you still need.",
        "row = [1]\nrepeat n times:\n    row.append(1)\n    for j from len(row)-2 down to 1: row[j] += row[j-1]\nreturn row",
        "Updating right-to-left in one array gives O(n^2) time and O(n) space. Row 30's largest value "
        "fits in an int (155117520).",
    ],
    time="O(n^2)",
    space="O(n)",
    model=lambda n: __import__("functools").reduce(
        lambda row, _: [1] + [row[i] + row[i + 1] for i in range(len(row) - 1)] + [1], range(n), [1]
    ),
    java="""
        class Solution {
            public int[] pascalRow(int n) {
                int[] row = new int[n + 1];
                row[0] = 1;
                for (int i = 1; i <= n; i++)
                    for (int j = i; j >= 1; j--) row[j] += row[j - 1];
                return row;
            }
        }
    """,
    tests=[{"n": 3}, {"n": 0}, {"n": 1}, {"n": 5}, {"n": 30}],
    gen=lambda r: {"n": r.randint(2, 25)},
    explain={0: "Rows: [1], [1,1], [1,2,1], [1,3,3,1]."},
)

P(
    slug="fizz-buzz",
    title="Fizz Buzz",
    difficulty="easy",
    topics=["strings", "math"],
    summary="Label numbers 1..n with Fizz, Buzz or FizzBuzz.",
    statement="""
        Return a list of strings for the numbers `1` to `n`: `"FizzBuzz"` if the number is divisible
        by 3 and 5, `"Fizz"` if only by 3, `"Buzz"` if only by 5, otherwise the number itself as text.
    """,
    constraints=["1 <= n <= 10^4"],
    sig="String[] fizzBuzz(int n)",
    hints=[
        "Which case must you check first?",
        "Check divisibility by 15 (both) before checking 3 or 5 on their own.",
        "for i in 1..n:\n    if i % 15 == 0: 'FizzBuzz'\n    elif i % 3 == 0: 'Fizz'\n    elif i % 5 == 0: 'Buzz'\n"
        "    else: str(i)",
        'One pass, O(n). The classic bug is checking 3 first, which labels 15 as just "Fizz".',
    ],
    time="O(n)",
    space="O(n)",
    model=lambda n: [
        "FizzBuzz" if i % 15 == 0 else "Fizz" if i % 3 == 0 else "Buzz" if i % 5 == 0 else str(i)
        for i in range(1, n + 1)
    ],
    java="""
        class Solution {
            public String[] fizzBuzz(int n) {
                String[] out = new String[n];
                for (int i = 1; i <= n; i++)
                    out[i - 1] = i % 15 == 0 ? "FizzBuzz" : i % 3 == 0 ? "Fizz" : i % 5 == 0 ? "Buzz" : String.valueOf(i);
                return out;
            }
        }
    """,
    tests=[{"n": 5}, {"n": 15}, {"n": 1}, {"n": 3}],
    gen=lambda r: {"n": r.randint(4, 40)},
)

P(
    slug="count-bits-range",
    title="Count Bits for 0..n",
    difficulty="easy",
    topics=["bit-manipulation", "dynamic-programming"],
    summary="For every number from 0 to n, count its 1 bits.",
    statement="""
        Return an array `ans` of length `n + 1` where `ans[i]` is the number of `1` bits in the
        binary form of `i`.
    """,
    constraints=["0 <= n <= 10^5"],
    sig="int[] countBits(int n)",
    hints=[
        "Can a number's bit count be derived from a smaller number's?",
        "`i >> 1` drops the last bit, so `bits(i) = bits(i >> 1) + (i & 1)`.",
        "ans[0] = 0\nfor i in 1..n:\n    ans[i] = ans[i >> 1] + (i & 1)\nreturn ans",
        "Each value reuses an earlier answer, so the whole table is O(n) time, versus O(n log n) for "
        "counting each number's bits from scratch.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda n: [bin(i).count("1") for i in range(n + 1)],
    java="""
        class Solution {
            public int[] countBits(int n) {
                int[] ans = new int[n + 1];
                for (int i = 1; i <= n; i++) ans[i] = ans[i >> 1] + (i & 1);
                return ans;
            }
        }
    """,
    tests=[{"n": 5}, {"n": 0}, {"n": 2}, {"n": 16}],
    gen=lambda r: {"n": r.randint(3, 64)},
    explain={0: "0=0, 1=1, 10=1, 11=2, 100=1, 101=2."},
)

P(
    slug="hamming-distance",
    title="Hamming Distance",
    difficulty="easy",
    topics=["bit-manipulation", "math"],
    summary="Count the bit positions where two numbers differ.",
    statement="""
        Return the number of bit positions at which the binary forms of the non-negative integers
        `x` and `y` differ.
    """,
    constraints=["0 <= x, y <= 2^31 - 1"],
    sig="int hammingDistance(int x, int y)",
    hints=[
        "Which operator marks exactly the bits where two numbers differ?",
        "`x ^ y` has a 1 wherever the bits differ. Count its 1 bits.",
        "d = x ^ y\ncount = 0\nwhile d > 0:\n    d &= d - 1   # clears the lowest set bit\n    count += 1\nreturn count",
        "XOR then popcount: O(number of bits). `d & (d - 1)` removes one set bit per step, so the loop "
        "runs once per differing bit. `Integer.bitCount(x ^ y)` does the same.",
    ],
    time="O(1)",
    space="O(1)",
    model=lambda x, y: bin(x ^ y).count("1"),
    java="""
        class Solution {
            public int hammingDistance(int x, int y) {
                int d = x ^ y, count = 0;
                while (d != 0) { d &= d - 1; count++; }
                return count;
            }
        }
    """,
    tests=[{"x": 1, "y": 4}, {"x": 3, "y": 1}, {"x": 0, "y": 0}, {"x": 2147483647, "y": 0}],
    gen=lambda r: {"x": r.randint(0, 10**6), "y": r.randint(0, 10**6)},
    explain={0: "0001 vs 0100: two bits differ."},
)

P(
    slug="power-of-two",
    title="Power of Two",
    difficulty="easy",
    topics=["bit-manipulation", "math"],
    summary="Check whether a number is a power of two.",
    statement="""
        Return `true` if `n` is a power of two (`1, 2, 4, 8, ...`), otherwise `false`. Zero and
        negative numbers are not powers of two.
    """,
    constraints=["-2^31 <= n <= 2^31 - 1"],
    sig="boolean isPowerOfTwo(int n)",
    hints=[
        "What does a power of two look like in binary?",
        "It has exactly one `1` bit. `n & (n - 1)` clears the lowest set bit.",
        "return n > 0 and (n & (n - 1)) == 0",
        "A positive number with a single set bit becomes 0 after clearing it: O(1). The `n > 0` check "
        "rules out 0 and negative numbers (the minimum int has one set bit but is negative).",
    ],
    time="O(1)",
    space="O(1)",
    model=lambda n: n > 0 and bin(n).count("1") == 1,
    java="""
        class Solution {
            public boolean isPowerOfTwo(int n) {
                return n > 0 && (n & (n - 1)) == 0;
            }
        }
    """,
    tests=[{"n": 16}, {"n": 6}, {"n": 1}, {"n": 0}, {"n": -8}, {"n": -2147483648}, {"n": 1073741824}],
    gen=lambda r: {"n": r.choice([2 ** r.randint(0, 30), r.randint(-100, 10**6)])},
)

P(
    slug="happy-number",
    title="Happy Number",
    difficulty="easy",
    topics=["math", "hash-sets"],
    summary="Repeatedly sum squared digits; does it reach 1?",
    statement="""
        Start with a positive integer `n` and repeatedly replace it with the sum of the squares of
        its digits. If this process reaches `1`, the number is **happy**. If it loops forever without
        reaching `1`, it isn't. Return whether `n` is happy.
    """,
    constraints=["1 <= n <= 2^31 - 1"],
    sig="boolean isHappy(int n)",
    hints=[
        "If it never reaches 1, the sequence must start repeating. How can you notice a repeat?",
        "Remember every number you've seen (a set), or use slow/fast pointers on the sequence.",
        "seen = set()\nwhile n != 1 and n not in seen:\n    seen.add(n)\n    n = sum of squares of n's digits\n"
        "return n == 1",
        "Values quickly drop below a few hundred, so the loop is short. A set detects the cycle; "
        "Floyd's slow/fast pointers do it in O(1) space.",
    ],
    time="O(log n)",
    space="O(log n)",
    model=lambda n: (lambda f: f(f, n, set()))(
        lambda f, x, seen: (
            True if x == 1 else False if x in seen else f(f, sum(int(c) ** 2 for c in str(x)), seen | {x})
        )
    ),
    java="""
        import java.util.*;

        class Solution {
            public boolean isHappy(int n) {
                Set<Integer> seen = new HashSet<>();
                while (n != 1 && seen.add(n)) {
                    int next = 0;
                    while (n > 0) { int d = n % 10; next += d * d; n /= 10; }
                    n = next;
                }
                return n == 1;
            }
        }
    """,
    tests=[{"n": 19}, {"n": 2}, {"n": 1}, {"n": 7}, {"n": 2147483647}],
    gen=lambda r: {"n": r.randint(1, 10**6)},
    explain={0: "1+81=82, 64+4=68, 36+64=100, 1+0+0=1."},
)

P(
    slug="integer-square-root",
    title="Integer Square Root",
    difficulty="easy",
    topics=["binary-search", "math"],
    summary="Return the floor of the square root without Math.sqrt.",
    statement="""
        Return the largest integer `r` such that `r * r <= x`, for a non-negative integer `x`.
        Don't use built-in square-root functions.
    """,
    constraints=["0 <= x <= 2^31 - 1"],
    sig="int mySqrt(int x)",
    hints=[
        "The answer lies somewhere between 0 and x. How can you search that range quickly?",
        "Binary search for the largest `r` with `r * r <= x`. Use `long` for `r * r` to avoid overflow.",
        "lo, hi = 0, x\nwhile lo < hi:\n    mid = (lo + hi + 1) // 2\n    if mid*mid <= x: lo = mid\n"
        "    else: hi = mid - 1\nreturn lo",
        "Binary search halves the range each step: O(log x). Rounding `mid` up stops an infinite loop "
        "when `lo + 1 == hi`, and computing `mid * mid` in a long avoids overflow near 2^31.",
    ],
    time="O(log x)",
    space="O(1)",
    model=lambda x: __import__("math").isqrt(x),
    java="""
        class Solution {
            public int mySqrt(int x) {
                long lo = 0, hi = x;
                while (lo < hi) {
                    long mid = (lo + hi + 1) / 2;
                    if (mid * mid <= x) lo = mid; else hi = mid - 1;
                }
                return (int) lo;
            }
        }
    """,
    tests=[{"x": 8}, {"x": 16}, {"x": 0}, {"x": 1}, {"x": 2147483647}],
    gen=lambda r: {"x": r.randint(0, 10**9)},
    explain={0: "sqrt(8) is about 2.83, so the answer is 2."},
)

P(
    slug="nth-fibonacci",
    title="Fibonacci Number",
    difficulty="easy",
    topics=["dynamic-programming", "math"],
    summary="Return the nth Fibonacci number.",
    statement="""
        The Fibonacci sequence starts `F(0) = 0`, `F(1) = 1`, and `F(n) = F(n-1) + F(n-2)`.
        Return `F(n)`.
    """,
    constraints=["0 <= n <= 45"],
    sig="int fib(int n)",
    hints=[
        "Plain recursion recomputes the same values many times. Can you build up from the bottom instead?",
        "You only ever need the last two values.",
        "a, b = 0, 1\nrepeat n times: a, b = b, a + b\nreturn a",
        "Iterating with two variables is O(n) time and O(1) space; naive recursion is O(2^n). F(45) "
        "is 1134903170, which still fits in an int.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda n: __import__("functools").reduce(lambda ab, _: (ab[1], ab[0] + ab[1]), range(n), (0, 1))[0],
    java="""
        class Solution {
            public int fib(int n) {
                int a = 0, b = 1;
                for (int i = 0; i < n; i++) { int t = a + b; a = b; b = t; }
                return a;
            }
        }
    """,
    tests=[{"n": 4}, {"n": 0}, {"n": 1}, {"n": 10}, {"n": 45}],
    gen=lambda r: {"n": r.randint(2, 40)},
)

P(
    slug="trailing-zeroes",
    title="Factorial Trailing Zeroes",
    difficulty="easy",
    topics=["math"],
    summary="Count the zeros at the end of n!.",
    statement="""
        Return how many trailing zeros `n!` has. Don't compute `n!` itself; it grows far too large.
    """,
    constraints=["0 <= n <= 10^9"],
    sig="int trailingZeroes(int n)",
    hints=[
        "Each trailing zero comes from a factor of 10 = 2 * 5. Which factor is rarer?",
        "Count the factors of 5 in 1..n: multiples of 5 give one, of 25 another, of 125 another…",
        "count = 0\nwhile n > 0:\n    n //= 5\n    count += n\nreturn count",
        "There are always more 2s than 5s, so zeros = number of 5 factors = n/5 + n/25 + n/125 + ... "
        "That's O(log n).",
    ],
    time="O(log n)",
    space="O(1)",
    model=lambda n: sum(n // 5**k for k in range(1, 15)),
    java="""
        class Solution {
            public int trailingZeroes(int n) {
                int count = 0;
                while (n > 0) { n /= 5; count += n; }
                return count;
            }
        }
    """,
    tests=[{"n": 5}, {"n": 3}, {"n": 25}, {"n": 0}, {"n": 1000000000}],
    gen=lambda r: {"n": r.randint(0, 10**6)},
    explain={0: "5! = 120 has one trailing zero."},
)

P(
    slug="greatest-common-divisor",
    title="Greatest Common Divisor",
    difficulty="easy",
    topics=["math", "recursion"],
    summary="Find the largest number that divides both inputs.",
    statement="""
        Return the greatest common divisor of the positive integers `a` and `b`.
    """,
    constraints=["1 <= a, b <= 10^9"],
    sig="int gcd(int a, int b)",
    hints=[
        "Trying every divisor works but is slow for big numbers. Is there a classic shortcut?",
        "Euclid's algorithm: gcd(a, b) = gcd(b, a % b), and gcd(a, 0) = a.",
        "while b != 0:\n    a, b = b, a % b\nreturn a",
        "Each step at least halves the larger value every two steps, so Euclid's algorithm is "
        "O(log min(a, b)), versus O(min(a, b)) for trial division.",
    ],
    time="O(log min(a, b))",
    space="O(1)",
    model=lambda a, b: __import__("math").gcd(a, b),
    java="""
        class Solution {
            public int gcd(int a, int b) {
                while (b != 0) { int t = a % b; a = b; b = t; }
                return a;
            }
        }
    """,
    tests=[{"a": 12, "b": 18}, {"a": 7, "b": 13}, {"a": 100, "b": 10}, {"a": 1000000000, "b": 999999999}],
    gen=lambda r: (lambda g: {"a": g * r.randint(1, 1000), "b": g * r.randint(1, 1000)})(r.randint(1, 500)),
)

P(
    slug="is-prime",
    title="Is It Prime?",
    difficulty="easy",
    topics=["math"],
    summary="Decide whether a number is prime.",
    statement="""
        Return `true` if `n` is a prime number (greater than 1, with no divisors other than 1 and itself).
    """,
    constraints=["-10^9 <= n <= 2^31 - 1"],
    sig="boolean isPrime(int n)",
    hints=[
        "You don't need to try every divisor up to n.",
        "If n has a divisor, it has one no larger than its square root.",
        "if n < 2: return false\nd = 2\nwhile d * d <= n:\n    if n % d == 0: return false\n    d += 1\nreturn true",
        "Trial division up to sqrt(n) is O(sqrt(n)). Use a long for `d * d` so the loop can't overflow "
        "for n near 2^31.",
    ],
    time="O(sqrt(n))",
    space="O(1)",
    model=lambda n: n >= 2 and all(n % d for d in range(2, __import__("math").isqrt(n) + 1)),
    java="""
        class Solution {
            public boolean isPrime(int n) {
                if (n < 2) return false;
                for (long d = 2; d * d <= n; d++) if (n % d == 0) return false;
                return true;
            }
        }
    """,
    tests=[{"n": 7}, {"n": 9}, {"n": 1}, {"n": 2}, {"n": -7}, {"n": 2147483647}, {"n": 1000000007}],
    gen=lambda r: {"n": r.randint(0, 10**5)},
)

P(
    slug="digit-sum",
    title="Sum of Digits",
    difficulty="easy",
    topics=["math"],
    summary="Add up the digits of a number.",
    statement="""
        Return the sum of the decimal digits of `n`. For negative numbers, ignore the sign.
    """,
    constraints=["-10^9 <= n <= 10^9"],
    sig="int digitSum(int n)",
    hints=[
        "How do you get the last digit of a number, and how do you remove it?",
        "`n % 10` is the last digit and `n / 10` drops it. Work with the absolute value.",
        "n = abs(n)\ntotal = 0\nwhile n > 0:\n    total += n % 10\n    n //= 10\nreturn total",
        "One step per digit: O(log n). Taking the absolute value first matters because `-123 % 10` "
        "is `-3` in Java.",
    ],
    time="O(log n)",
    space="O(1)",
    model=lambda n: sum(int(c) for c in str(abs(n))),
    java="""
        class Solution {
            public int digitSum(int n) {
                n = Math.abs(n);
                int total = 0;
                while (n > 0) { total += n % 10; n /= 10; }
                return total;
            }
        }
    """,
    tests=[{"n": 123}, {"n": -409}, {"n": 0}, {"n": 999999999}],
    gen=lambda r: {"n": r.randint(-(10**9), 10**9)},
)

P(
    slug="reverse-integer-digits",
    title="Reverse the Digits",
    difficulty="easy",
    topics=["math"],
    summary="Reverse a number's digits, keeping its sign.",
    statement="""
        Return `n` with its digits reversed, keeping the sign. Leading zeros disappear
        (`120` becomes `21`). Inputs are chosen so the result fits in an int.
    """,
    constraints=["-10^8 <= n <= 10^8"],
    sig="int reverseDigits(int n)",
    hints=[
        "Peel digits off the end and push them onto a new number.",
        "`result = result * 10 + n % 10`, then `n /= 10`. Java keeps the sign through `%` and `/`.",
        "result = 0\nwhile n != 0:\n    result = result * 10 + n % 10\n    n /= 10   # truncates toward zero\nreturn result",
        "One step per digit, O(log n). In Java, `%` and `/` truncate toward zero, so negative numbers "
        "reverse correctly without special-casing the sign.",
    ],
    time="O(log n)",
    space="O(1)",
    model=lambda n: (-1 if n < 0 else 1) * int(str(abs(n))[::-1]),
    java="""
        class Solution {
            public int reverseDigits(int n) {
                int result = 0;
                while (n != 0) { result = result * 10 + n % 10; n /= 10; }
                return result;
            }
        }
    """,
    tests=[{"n": 123}, {"n": -456}, {"n": 120}, {"n": 0}, {"n": 100000000}],
    gen=lambda r: {"n": r.randint(-(10**8), 10**8)},
)

P(
    slug="perfect-number",
    title="Perfect Number",
    difficulty="easy",
    topics=["math"],
    summary="Is a number equal to the sum of its proper divisors?",
    statement="""
        A perfect number equals the sum of its positive divisors excluding itself (6 = 1 + 2 + 3).
        Return whether `n` is perfect.
    """,
    constraints=["1 <= n <= 10^8"],
    sig="boolean isPerfect(int n)",
    hints=[
        "Divisors come in pairs: if d divides n, so does n / d.",
        "Loop d up to sqrt(n), adding both d and n / d (once when they're equal). Don't count n itself.",
        "if n == 1: return false\ntotal = 1\nd = 2\nwhile d * d <= n:\n    if n % d == 0:\n"
        "        total += d\n        if d != n // d: total += n // d\n    d += 1\nreturn total == n",
        "Pairing divisors makes it O(sqrt(n)) instead of O(n). Starting the total at 1 includes the "
        "divisor 1 while leaving out n.",
    ],
    time="O(sqrt(n))",
    space="O(1)",
    model=lambda n: (
        n > 1 and sum(d for d in range(1, n) if n % d == 0) == n if n < 20000 else n in (33550336,)
    ),
    java="""
        class Solution {
            public boolean isPerfect(int n) {
                if (n == 1) return false;
                long total = 1;
                for (long d = 2; d * d <= n; d++) {
                    if (n % d == 0) { total += d; if (d != n / d) total += n / d; }
                }
                return total == n;
            }
        }
    """,
    tests=[{"n": 28}, {"n": 6}, {"n": 12}, {"n": 1}, {"n": 8128}, {"n": 33550336}, {"n": 496}],
    gen=lambda r: {"n": r.randint(2, 15000)},
)

P(
    slug="count-primes-below",
    title="Count Primes Below n",
    difficulty="easy",
    topics=["math", "arrays"],
    summary="How many primes are smaller than n?",
    statement="""
        Return the number of prime numbers strictly less than `n`.
    """,
    constraints=["0 <= n <= 5 * 10^6"],
    sig="int countPrimes(int n)",
    hints=[
        "Testing each number separately is slow for large n. Can you rule out many numbers at once?",
        "The Sieve of Eratosthenes: for each prime p, cross out p*p, p*p+p, ... as composite.",
        "composite = [false] * n\ncount = 0\nfor i in 2..n-1:\n    if not composite[i]:\n        count += 1\n"
        "        for j in range(i*i, n, i): composite[j] = true\nreturn count",
        "The sieve runs in O(n log log n) with O(n) memory. Starting at `i * i` is enough because "
        "smaller multiples were crossed out by smaller primes. Use a long for `i * i`.",
    ],
    time="O(n log log n)",
    space="O(n)",
    model=lambda n: sum(
        1 for k in range(2, n) if all(k % d for d in range(2, __import__("math").isqrt(k) + 1))
    ),
    java="""
        class Solution {
            public int countPrimes(int n) {
                if (n < 3) return 0;
                boolean[] composite = new boolean[n];
                int count = 0;
                for (int i = 2; i < n; i++) {
                    if (composite[i]) continue;
                    count++;
                    for (long j = (long) i * i; j < n; j += i) composite[(int) j] = true;
                }
                return count;
            }
        }
    """,
    tests=[{"n": 10}, {"n": 0}, {"n": 2}, {"n": 3}, {"n": 100}],
    gen=lambda r: {"n": r.randint(4, 3000)},
    explain={0: "2, 3, 5 and 7."},
)
