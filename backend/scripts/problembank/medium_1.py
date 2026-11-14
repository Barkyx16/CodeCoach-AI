"""Medium problems, part 1: hashing, two pointers, sliding window, stacks and strings."""

from collections import Counter
from itertools import combinations

from scripts.problembank import P, ints, word

P(
    slug="three-sum",
    title="Three Numbers That Sum to Zero",
    difficulty="medium",
    topics=["arrays", "two-pointers", "sorting"],
    summary="List every distinct triplet that adds up to zero.",
    statement="""
        Return all distinct triplets `[a, b, c]` of values from `nums` (at different indices) with
        `a + b + c == 0`. Each triplet is sorted ascending, and the list of triplets is sorted
        ascending (compare first values, then second). No duplicate triplets.
    """,
    constraints=["0 <= nums.length <= 3000", "-10^5 <= nums[i] <= 10^5"],
    sig="int[][] threeSum(int[] nums)",
    hints=[
        "Fix one value, and the problem becomes a two-number search for the rest.",
        "Sort first. For each index `i`, run two pointers on the part after it, looking for `-nums[i]`. Skip equal values to avoid duplicates.",
        "sort nums\nfor i in range(n):\n    if i > 0 and nums[i] == nums[i-1]: continue\n    lo, hi = i+1, n-1\n"
        "    while lo < hi:\n        s = nums[i] + nums[lo] + nums[hi]\n        if s == 0: record; lo += 1 while duplicate; hi -= 1 while duplicate\n"
        "        elif s < 0: lo += 1\n        else: hi -= 1",
        "Sorting is O(n log n) and each fixed `i` costs O(n) with two pointers, so O(n^2) total versus O(n^3) "
        "brute force. Because the array is sorted, triplets come out in sorted order and skipping repeats removes duplicates.",
    ],
    time="O(n^2)",
    space="O(1)",
    model=lambda nums: [
        list(t) for t in sorted({tuple(sorted(c)) for c in combinations(nums, 3) if sum(c) == 0})
    ],
    java="""
        import java.util.*;

        class Solution {
            public int[][] threeSum(int[] nums) {
                Arrays.sort(nums);
                List<int[]> out = new ArrayList<>();
                int n = nums.length;
                for (int i = 0; i < n - 2; i++) {
                    if (i > 0 && nums[i] == nums[i - 1]) continue;
                    int lo = i + 1, hi = n - 1;
                    while (lo < hi) {
                        int s = nums[i] + nums[lo] + nums[hi];
                        if (s == 0) {
                            out.add(new int[] {nums[i], nums[lo], nums[hi]});
                            while (lo < hi && nums[lo] == nums[lo + 1]) lo++;
                            while (lo < hi && nums[hi] == nums[hi - 1]) hi--;
                            lo++; hi--;
                        } else if (s < 0) lo++; else hi--;
                    }
                }
                return out.toArray(new int[0][]);
            }
        }
    """,
    tests=[
        {"nums": [-1, 0, 1, 2, -1, -4]},
        {"nums": [0, 1, 1]},
        {"nums": [0, 0, 0, 0]},
        {"nums": []},
        {"nums": [-2, 0, 1, 1, 2]},
    ],
    gen=lambda r: {"nums": ints(r, 0, 14, -6, 6)},
    explain={0: "Two triplets: -1 + -1 + 2 and -1 + 0 + 1."},
)

P(
    slug="group-anagrams",
    title="Group Anagrams",
    difficulty="medium",
    topics=["strings", "hash-maps", "sorting"],
    summary="Group words that are anagrams of each other.",
    statement="""
        Group the words of `words` that are anagrams of each other. Return one string per group: the
        group's words sorted alphabetically and joined with commas. Sort the groups alphabetically too.
        For `["eat","tea","tan","ate","nat","bat"]` the answer is `["ate,eat,tea", "bat", "nat,tan"]`.
    """,
    constraints=["1 <= words.length <= 10^4", "0 <= words[i].length <= 100", "lower-case letters"],
    sig="String[] groupAnagrams(String[] words)",
    hints=[
        "Anagrams look identical once you put their letters in a standard order.",
        "Use the sorted letters (or a 26-count signature) as a hash-map key that collects each group.",
        "groups = {}\nfor w in words:\n    groups[sorted(w)].append(w)\nreturn sorted(','.join(sorted(g)) for g in groups.values())",
        "Each word's key costs O(k log k) to build, so grouping is O(n k log k). A count-based key makes it O(n k).",
    ],
    time="O(n k log k)",
    space="O(n k)",
    model=lambda words: sorted(
        ",".join(sorted(g))
        for g in __import__("functools")
        .reduce(lambda d, w: (d.setdefault("".join(sorted(w)), []).append(w), d)[1], words, {})
        .values()
    ),
    java="""
        import java.util.*;

        class Solution {
            public String[] groupAnagrams(String[] words) {
                Map<String, List<String>> groups = new HashMap<>();
                for (String w : words) {
                    char[] key = w.toCharArray();
                    Arrays.sort(key);
                    groups.computeIfAbsent(new String(key), k -> new ArrayList<>()).add(w);
                }
                List<String> out = new ArrayList<>();
                for (List<String> g : groups.values()) {
                    Collections.sort(g);
                    out.add(String.join(",", g));
                }
                Collections.sort(out);
                return out.toArray(new String[0]);
            }
        }
    """,
    tests=[
        {"words": ["eat", "tea", "tan", "ate", "nat", "bat"]},
        {"words": [""]},
        {"words": ["a"]},
        {"words": ["ab", "ba", "ab"]},
    ],
    gen=lambda r: {"words": [word(r, 1, 3, "abc") for _ in range(r.randint(1, 8))]},
)

P(
    slug="top-k-frequent",
    title="Top K Frequent Values",
    difficulty="medium",
    topics=["hash-maps", "heaps", "sorting"],
    summary="Return the k values that appear most often.",
    statement="""
        Return the `k` most frequent values in `nums`, ordered from most to least frequent. Break
        frequency ties by the smaller value first. `k` is at most the number of distinct values.
    """,
    constraints=["1 <= nums.length <= 10^5", "1 <= k <= number of distinct values"],
    sig="int[] topKFrequent(int[] nums, int k)",
    hints=[
        "Start by counting how often each value appears.",
        "Then you need the k best (count, value) pairs: sort them, use a heap of size k, or bucket by count.",
        "counts = count values\npairs = sort counts by (-count, value)\nreturn first k values",
        "Counting is O(n); sorting the d distinct pairs is O(d log d). A size-k heap gives O(d log k), and "
        "bucket sort by count gives O(n).",
    ],
    time="O(n + d log d)",
    space="O(n)",
    model=lambda nums, k: [v for v, _ in sorted(Counter(nums).items(), key=lambda kv: (-kv[1], kv[0]))[:k]],
    java="""
        import java.util.*;

        class Solution {
            public int[] topKFrequent(int[] nums, int k) {
                Map<Integer, Integer> counts = new HashMap<>();
                for (int x : nums) counts.merge(x, 1, Integer::sum);
                List<Integer> values = new ArrayList<>(counts.keySet());
                values.sort((a, b) -> !counts.get(a).equals(counts.get(b)) ? counts.get(b) - counts.get(a) : Integer.compare(a, b));
                int[] out = new int[k];
                for (int i = 0; i < k; i++) out[i] = values.get(i);
                return out;
            }
        }
    """,
    tests=[
        {"nums": [1, 1, 1, 2, 2, 3], "k": 2},
        {"nums": [1], "k": 1},
        {"nums": [4, 4, 5, 5, 6], "k": 2},
        {"nums": [3, 0, 1, 0], "k": 3},
    ],
    gen=lambda r: (lambda nums: {"nums": nums, "k": r.randint(1, len(set(nums)))})(ints(r, 1, 20, -4, 6)),
)

P(
    slug="longest-consecutive",
    title="Longest Consecutive Run",
    difficulty="medium",
    topics=["arrays", "hash-sets"],
    summary="Find the longest run of consecutive integers, in any order.",
    statement="""
        Return the length of the longest sequence of consecutive integers (like 4, 5, 6, 7) whose
        values all appear in `nums`. The values can be in any order. Aim for O(n).
    """,
    constraints=["0 <= nums.length <= 10^5", "-10^9 <= nums[i] <= 10^9"],
    sig="int longestConsecutive(int[] nums)",
    hints=[
        "Sorting gives O(n log n). How could a set help you do better?",
        "Only start counting from a value `x` whose `x - 1` is missing: it's the start of a run.",
        "s = set(nums)\nbest = 0\nfor x in s:\n    if x - 1 not in s:\n        length = 1\n        while x + length in s: length += 1\n        best = max(best, length)\nreturn best",
        "Each value is visited by at most one counting walk, so the total is O(n) despite the inner loop.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda nums: max(
        (
            len(list(g))
            for _, g in __import__("itertools").groupby(
                enumerate(sorted(set(nums))), key=lambda iv: iv[1] - iv[0]
            )
        ),
        default=0,
    ),
    java="""
        import java.util.*;

        class Solution {
            public int longestConsecutive(int[] nums) {
                Set<Integer> s = new HashSet<>();
                for (int x : nums) s.add(x);
                int best = 0;
                for (int x : s) {
                    if (s.contains(x - 1)) continue;
                    int length = 1;
                    while (s.contains(x + length)) length++;
                    best = Math.max(best, length);
                }
                return best;
            }
        }
    """,
    tests=[
        {"nums": [100, 4, 200, 1, 3, 2]},
        {"nums": [0, 3, 7, 2, 5, 8, 4, 6, 0, 1]},
        {"nums": []},
        {"nums": [5, 5]},
    ],
    gen=lambda r: {"nums": ints(r, 0, 25, -15, 15)},
)

P(
    slug="rotate-array",
    title="Rotate an Array",
    difficulty="medium",
    topics=["arrays", "two-pointers"],
    summary="Shift every value k places to the right, wrapping around.",
    statement="""
        Rotate `nums` to the right by `k` steps: the last value moves to the front, `k` times. `k`
        may be larger than the array length. Try to use O(1) extra space.
    """,
    constraints=["1 <= nums.length <= 10^5", "0 <= k <= 10^5"],
    sig="int[] rotate(int[] nums, int k)",
    hints=[
        "Rotating by `n` changes nothing, so reduce `k` first.",
        "Reverse the whole array, then reverse the first `k` values and the rest separately.",
        "k %= n\nreverse(nums, 0, n-1)\nreverse(nums, 0, k-1)\nreverse(nums, k, n-1)\nreturn nums",
        "Three reversals put every value in place: O(n) time, O(1) extra space.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda nums, k: nums[len(nums) - k % len(nums) :] + nums[: len(nums) - k % len(nums)],
    java="""
        class Solution {
            private void reverse(int[] a, int i, int j) {
                while (i < j) { int t = a[i]; a[i++] = a[j]; a[j--] = t; }
            }
            public int[] rotate(int[] nums, int k) {
                int n = nums.length;
                k %= n;
                reverse(nums, 0, n - 1);
                reverse(nums, 0, k - 1);
                reverse(nums, k, n - 1);
                return nums;
            }
        }
    """,
    tests=[
        {"nums": [1, 2, 3, 4, 5, 6, 7], "k": 3},
        {"nums": [-1, -100, 3, 99], "k": 2},
        {"nums": [1, 2], "k": 5},
        {"nums": [9], "k": 0},
    ],
    gen=lambda r: {"nums": ints(r, 1, 12, -9, 9), "k": r.randint(0, 30)},
)

P(
    slug="subarray-sum-equals-k",
    title="Subarrays That Sum to K",
    difficulty="medium",
    topics=["arrays", "hash-maps", "prefix-sums"],
    summary="Count contiguous subarrays whose sum is exactly k.",
    statement="""
        Return how many contiguous, non-empty subarrays of `nums` add up to `k`. Values can be negative.
    """,
    constraints=["1 <= nums.length <= 2 * 10^4", "-1000 <= nums[i] <= 1000", "-10^7 <= k <= 10^7"],
    sig="int subarraySum(int[] nums, int k)",
    hints=[
        "The sum of `nums[i..j]` is `prefix[j+1] - prefix[i]`.",
        "As you extend the prefix sum, count how many earlier prefix sums equal `current - k`. A map stores those counts.",
        "seen = {0: 1}\ntotal = count = 0\nfor x in nums:\n    total += x\n    count += seen.get(total - k, 0)\n    seen[total] = seen.get(total, 0) + 1\nreturn count",
        "One pass with a prefix-count map is O(n). A sliding window doesn't work here because negatives "
        'break the "grow then shrink" logic. Starting with `{0: 1}` counts subarrays that begin at index 0.',
    ],
    time="O(n)",
    space="O(n)",
    model=lambda nums, k: sum(
        1 for i in range(len(nums)) for j in range(i, len(nums)) if sum(nums[i : j + 1]) == k
    ),
    java="""
        import java.util.*;

        class Solution {
            public int subarraySum(int[] nums, int k) {
                Map<Integer, Integer> seen = new HashMap<>();
                seen.put(0, 1);
                int total = 0, count = 0;
                for (int x : nums) {
                    total += x;
                    count += seen.getOrDefault(total - k, 0);
                    seen.merge(total, 1, Integer::sum);
                }
                return count;
            }
        }
    """,
    tests=[
        {"nums": [1, 1, 1], "k": 2},
        {"nums": [1, 2, 3], "k": 3},
        {"nums": [1, -1, 0], "k": 0},
        {"nums": [3], "k": 2},
    ],
    gen=lambda r: {"nums": ints(r, 1, 15, -3, 3), "k": r.randint(-3, 4)},
)

P(
    slug="subarray-sum-multiple",
    title="Subarray Sum Divisible by K",
    difficulty="medium",
    topics=["arrays", "hash-maps", "prefix-sums", "math"],
    summary="Is there a subarray of length 2+ whose sum is a multiple of k?",
    statement="""
        Return `true` if `nums` has a contiguous subarray of **at least two** values whose sum is a
        multiple of `k` (0 counts as a multiple). Values are non-negative.
    """,
    constraints=["1 <= nums.length <= 10^5", "0 <= nums[i] <= 10^9", "1 <= k <= 2^31 - 1"],
    sig="boolean checkSubarraySum(int[] nums, int k)",
    hints=[
        "When do two prefix sums differ by a multiple of k?",
        "When they have the same remainder mod k. Remember the first index where each remainder appeared.",
        "first = {0: -1}\ntotal = 0\nfor i, x in enumerate(nums):\n    total = (total + x) % k\n"
        "    if total in first:\n        if i - first[total] >= 2: return true\n    else: first[total] = i\nreturn false",
        "Equal remainders mean the values between them sum to a multiple of k. Keeping only the first index "
        "maximizes the length: O(n) time, O(min(n, k)) space. Taking `% k` each step avoids overflow.",
    ],
    time="O(n)",
    space="O(min(n, k))",
    model=lambda nums, k: any(
        sum(nums[i : j + 1]) % k == 0 for i in range(len(nums)) for j in range(i + 1, len(nums))
    ),
    java="""
        import java.util.*;

        class Solution {
            public boolean checkSubarraySum(int[] nums, int k) {
                Map<Integer, Integer> first = new HashMap<>();
                first.put(0, -1);
                long total = 0;
                for (int i = 0; i < nums.length; i++) {
                    total = (total + nums[i]) % k;
                    Integer seen = first.get((int) total);
                    if (seen != null) { if (i - seen >= 2) return true; }
                    else first.put((int) total, i);
                }
                return false;
            }
        }
    """,
    tests=[
        {"nums": [23, 2, 4, 6, 7], "k": 6},
        {"nums": [23, 2, 6, 4, 7], "k": 13},
        {"nums": [5, 0, 0], "k": 3},
        {"nums": [1, 0], "k": 2},
        {"nums": [0], "k": 1},
    ],
    gen=lambda r: {"nums": ints(r, 1, 10, 0, 20), "k": r.randint(1, 12)},
)

P(
    slug="longest-equal-zeros-ones",
    title="Longest Balanced Binary Subarray",
    difficulty="medium",
    topics=["arrays", "hash-maps", "prefix-sums"],
    summary="Longest subarray with as many 0s as 1s.",
    statement="""
        `nums` contains only `0`s and `1`s. Return the length of the longest contiguous subarray with
        an equal number of `0`s and `1`s.
    """,
    constraints=["1 <= nums.length <= 10^5"],
    sig="int findMaxLength(int[] nums)",
    hints=[
        "Count a 0 as -1. What does a balanced subarray then sum to?",
        "Zero. Two equal prefix sums mark a balanced subarray between them; keep the first index of each sum.",
        "first = {0: -1}\ntotal = best = 0\nfor i, x in enumerate(nums):\n    total += 1 if x == 1 else -1\n"
        "    if total in first: best = max(best, i - first[total])\n    else: first[total] = i\nreturn best",
        'Turning it into "longest zero-sum subarray" with a first-index map gives O(n) time and space.',
    ],
    time="O(n)",
    space="O(n)",
    model=lambda nums: max(
        [0]
        + [
            j - i + 1
            for i in range(len(nums))
            for j in range(i, len(nums))
            if 2 * sum(nums[i : j + 1]) == j - i + 1
        ]
    ),
    java="""
        import java.util.*;

        class Solution {
            public int findMaxLength(int[] nums) {
                Map<Integer, Integer> first = new HashMap<>();
                first.put(0, -1);
                int total = 0, best = 0;
                for (int i = 0; i < nums.length; i++) {
                    total += nums[i] == 1 ? 1 : -1;
                    Integer seen = first.putIfAbsent(total, i);
                    if (seen != null) best = Math.max(best, i - seen);
                }
                return best;
            }
        }
    """,
    tests=[{"nums": [0, 1]}, {"nums": [0, 1, 0]}, {"nums": [0, 0, 1, 0, 0, 0, 1, 1]}, {"nums": [1, 1, 1]}],
    gen=lambda r: {"nums": ints(r, 1, 20, 0, 1)},
)

P(
    slug="sort-colors",
    title="Sort Three Colors",
    difficulty="medium",
    topics=["arrays", "two-pointers", "sorting"],
    summary="Sort an array of 0s, 1s and 2s in one pass.",
    statement="""
        `nums` contains only `0`, `1` and `2`. Return it sorted. Try for one pass and O(1) extra space
        (no library sort).
    """,
    constraints=["1 <= nums.length <= 300", "nums[i] is 0, 1 or 2"],
    sig="int[] sortColors(int[] nums)",
    hints=[
        "Counting each value and rewriting works in two passes. Can you do one?",
        "Dutch national flag: keep three regions with pointers `low`, `mid`, `high`.",
        "low, mid, high = 0, 0, n-1\nwhile mid <= high:\n    if nums[mid] == 0: swap(low, mid); low += 1; mid += 1\n"
        "    elif nums[mid] == 1: mid += 1\n    else: swap(mid, high); high -= 1\nreturn nums",
        "Everything before `low` is 0, between `low` and `mid` is 1, after `high` is 2. Each step shrinks the "
        "unknown middle: one pass, O(1) space. Don't advance `mid` after swapping with `high`: the swapped-in value is unchecked.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda nums: sorted(nums),
    java="""
        class Solution {
            public int[] sortColors(int[] nums) {
                int low = 0, mid = 0, high = nums.length - 1;
                while (mid <= high) {
                    if (nums[mid] == 0) { int t = nums[low]; nums[low++] = nums[mid]; nums[mid++] = t; }
                    else if (nums[mid] == 1) mid++;
                    else { int t = nums[high]; nums[high--] = nums[mid]; nums[mid] = t; }
                }
                return nums;
            }
        }
    """,
    tests=[{"nums": [2, 0, 2, 1, 1, 0]}, {"nums": [2, 0, 1]}, {"nums": [1]}, {"nums": [2, 2, 0, 0]}],
    gen=lambda r: {"nums": ints(r, 1, 20, 0, 2)},
)

P(
    slug="k-closest-values",
    title="K Closest Values",
    difficulty="medium",
    topics=["arrays", "binary-search", "two-pointers"],
    summary="Pick the k values in a sorted array closest to x.",
    statement="""
        `nums` is sorted ascending. Return the `k` values closest to `x`, in ascending order. Closer means
        smaller `|a - x|`; on a tie, the smaller value counts as closer.
    """,
    constraints=["1 <= k <= nums.length <= 10^4", "nums is sorted"],
    sig="int[] findClosestElements(int[] nums, int k, int x)",
    hints=[
        "The answer is a contiguous window of length k. Which window?",
        "Binary search the window's left edge `L` in `[0, n-k]`: compare `x - nums[mid]` with `nums[mid+k] - x`.",
        "lo, hi = 0, n - k\nwhile lo < hi:\n    mid = (lo + hi) // 2\n    if x - nums[mid] > nums[mid + k] - x: lo = mid + 1\n"
        "    else: hi = mid\nreturn nums[lo : lo + k]",
        "If `nums[mid+k]` is closer than `nums[mid]`, the window should slide right. Binary search over left "
        "edges is O(log(n - k) + k).",
    ],
    time="O(log n + k)",
    space="O(1)",
    model=lambda nums, k, x: sorted(sorted(nums, key=lambda a: (abs(a - x), a))[:k]),
    java="""
        class Solution {
            public int[] findClosestElements(int[] nums, int k, int x) {
                int lo = 0, hi = nums.length - k;
                while (lo < hi) {
                    int mid = (lo + hi) >>> 1;
                    if (x - nums[mid] > nums[mid + k] - x) lo = mid + 1; else hi = mid;
                }
                int[] out = new int[k];
                System.arraycopy(nums, lo, out, 0, k);
                return out;
            }
        }
    """,
    tests=[
        {"nums": [1, 2, 3, 4, 5], "k": 4, "x": 3},
        {"nums": [1, 1, 2, 3, 4, 5], "k": 4, "x": -1},
        {"nums": [1, 5, 10], "k": 1, "x": 7},
        {"nums": [1, 3], "k": 1, "x": 2},
    ],
    gen=lambda r: (lambda nums: {"nums": nums, "k": r.randint(1, len(nums)), "x": r.randint(-5, 25)})(
        sorted(ints(r, 1, 12, 0, 20))
    ),
)

P(
    slug="longest-k-distinct",
    title="Longest Substring With at Most K Distinct Letters",
    difficulty="medium",
    topics=["strings", "sliding-window", "hash-maps"],
    summary="Longest substring using no more than k different characters.",
    statement="""
        Return the length of the longest substring of `s` that contains at most `k` distinct characters.
    """,
    constraints=["0 <= s.length <= 5 * 10^4", "0 <= k <= 26", "lower-case letters"],
    sig="int lengthOfLongestKDistinct(String s, int k)",
    hints=[
        "A window that is valid stays valid if you shrink it.",
        "Grow the right edge; when the window has more than `k` distinct letters, move the left edge until it doesn't.",
        "counts = {}\nleft = best = 0\nfor right, c in enumerate(s):\n    counts[c] += 1\n    while len(counts) > k:\n"
        "        counts[s[left]] -= 1; drop it at zero; left += 1\n    best = max(best, right - left + 1)\nreturn best",
        "Each index enters and leaves the window once: O(n) time and O(k) space.",
    ],
    time="O(n)",
    space="O(k)",
    model=lambda s, k: max(
        [0] + [j - i for i in range(len(s)) for j in range(i + 1, len(s) + 1) if len(set(s[i:j])) <= k]
    ),
    java="""
        class Solution {
            public int lengthOfLongestKDistinct(String s, int k) {
                int[] counts = new int[26];
                int left = 0, distinct = 0, best = 0;
                for (int right = 0; right < s.length(); right++) {
                    if (counts[s.charAt(right) - 'a']++ == 0) distinct++;
                    while (distinct > k) if (--counts[s.charAt(left++) - 'a'] == 0) distinct--;
                    best = Math.max(best, right - left + 1);
                }
                return best;
            }
        }
    """,
    tests=[
        {"s": "eceba", "k": 2},
        {"s": "aa", "k": 1},
        {"s": "abc", "k": 0},
        {"s": "", "k": 3},
        {"s": "abaccc", "k": 2},
    ],
    gen=lambda r: {"s": word(r, 0, 15, "abcd"), "k": r.randint(0, 4)},
)

P(
    slug="permutation-in-string",
    title="Permutation Inside a String",
    difficulty="medium",
    topics=["strings", "sliding-window", "hash-maps"],
    summary="Does one string contain a rearrangement of another?",
    statement="""
        Return `true` if some substring of `s2` is a permutation (rearrangement) of `s1`.
    """,
    constraints=["1 <= s1.length, s2.length <= 10^4", "lower-case letters"],
    sig="boolean checkInclusion(String s1, String s2)",
    hints=[
        "A permutation has exactly the same letter counts and the same length.",
        "Slide a window of length `len(s1)` over `s2`, updating counts as one letter enters and one leaves.",
        "need = counts(s1)\nwindow = counts(s2[:m])\nif window == need: return true\nfor i in m..n-1:\n"
        "    add s2[i], remove s2[i-m]\n    if window == need: return true\nreturn false",
        "Each slide updates two counts and compares 26 slots: O(26 n) = O(n).",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda s1, s2: any(
        Counter(s2[i : i + len(s1)]) == Counter(s1) for i in range(len(s2) - len(s1) + 1)
    ),
    java="""
        import java.util.*;

        class Solution {
            public boolean checkInclusion(String s1, String s2) {
                int m = s1.length(), n = s2.length();
                if (m > n) return false;
                int[] need = new int[26], window = new int[26];
                for (int i = 0; i < m; i++) { need[s1.charAt(i) - 'a']++; window[s2.charAt(i) - 'a']++; }
                if (Arrays.equals(need, window)) return true;
                for (int i = m; i < n; i++) {
                    window[s2.charAt(i) - 'a']++;
                    window[s2.charAt(i - m) - 'a']--;
                    if (Arrays.equals(need, window)) return true;
                }
                return false;
            }
        }
    """,
    tests=[
        {"s1": "ab", "s2": "eidbaooo"},
        {"s1": "ab", "s2": "eidboaoo"},
        {"s1": "abc", "s2": "ab"},
        {"s1": "a", "s2": "a"},
    ],
    gen=lambda r: {"s1": word(r, 1, 3, "abc"), "s2": word(r, 1, 12, "abc")},
)

P(
    slug="anagram-start-indices",
    title="Find All Anagram Positions",
    difficulty="medium",
    topics=["strings", "sliding-window", "hash-maps"],
    summary="Every index where an anagram of p starts in s.",
    statement="""
        Return the start indices (ascending) of every substring of `s` that is an anagram of `p`.
    """,
    constraints=["1 <= s.length, p.length <= 3 * 10^4", "lower-case letters"],
    sig="int[] findAnagrams(String s, String p)",
    hints=[
        "This is the permutation check, but you record every match instead of stopping.",
        "Slide a fixed window of length `len(p)` and compare letter counts.",
        "for each window start i:\n    if counts(window) == counts(p): record i\nupdate counts by adding one letter and removing one",
        "Updating counts incrementally keeps it O(26 n).",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda s, p: [i for i in range(len(s) - len(p) + 1) if Counter(s[i : i + len(p)]) == Counter(p)],
    java="""
        import java.util.*;

        class Solution {
            public int[] findAnagrams(String s, String p) {
                List<Integer> out = new ArrayList<>();
                int m = p.length(), n = s.length();
                if (m > n) return new int[0];
                int[] need = new int[26], window = new int[26];
                for (int i = 0; i < m; i++) { need[p.charAt(i) - 'a']++; window[s.charAt(i) - 'a']++; }
                if (Arrays.equals(need, window)) out.add(0);
                for (int i = m; i < n; i++) {
                    window[s.charAt(i) - 'a']++;
                    window[s.charAt(i - m) - 'a']--;
                    if (Arrays.equals(need, window)) out.add(i - m + 1);
                }
                return out.stream().mapToInt(Integer::intValue).toArray();
            }
        }
    """,
    tests=[{"s": "cbaebabacd", "p": "abc"}, {"s": "abab", "p": "ab"}, {"s": "a", "p": "ab"}],
    gen=lambda r: {"s": word(r, 1, 15, "ab"), "p": word(r, 1, 3, "ab")},
)

P(
    slug="max-ones-k-flips",
    title="Longest Ones With K Flips",
    difficulty="medium",
    topics=["arrays", "sliding-window"],
    summary="Flip at most k zeros to get the longest run of ones.",
    statement="""
        `nums` is a binary array. You may change at most `k` zeros into ones. Return the length of the
        longest run of consecutive ones you can get.
    """,
    constraints=["1 <= nums.length <= 10^5", "0 <= k <= nums.length"],
    sig="int longestOnesWithFlips(int[] nums, int k)",
    hints=[
        "Restate it: find the longest window that contains at most `k` zeros.",
        "Slide a window; when it holds more than `k` zeros, move the left edge past a zero.",
        "left = zeros = best = 0\nfor right, x in enumerate(nums):\n    zeros += x == 0\n    while zeros > k:\n"
        "        zeros -= nums[left] == 0; left += 1\n    best = max(best, right - left + 1)\nreturn best",
        "Each index enters and leaves once: O(n) time, O(1) space.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda nums, k: max(
        [0]
        + [j - i for i in range(len(nums)) for j in range(i + 1, len(nums) + 1) if nums[i:j].count(0) <= k]
    ),
    java="""
        class Solution {
            public int longestOnesWithFlips(int[] nums, int k) {
                int left = 0, zeros = 0, best = 0;
                for (int right = 0; right < nums.length; right++) {
                    if (nums[right] == 0) zeros++;
                    while (zeros > k) if (nums[left++] == 0) zeros--;
                    best = Math.max(best, right - left + 1);
                }
                return best;
            }
        }
    """,
    tests=[
        {"nums": [1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 0], "k": 2},
        {"nums": [0, 0, 1, 1, 0, 0, 1, 1, 1, 0, 1, 1, 0, 0, 0, 1, 1, 1, 1], "k": 3},
        {"nums": [0, 0], "k": 0},
    ],
    gen=lambda r: {"nums": ints(r, 1, 15, 0, 1), "k": r.randint(0, 3)},
)

P(
    slug="min-subarray-at-least",
    title="Shortest Subarray With Sum at Least Target",
    difficulty="medium",
    topics=["arrays", "sliding-window"],
    summary="Shortest window of positive numbers reaching a target sum.",
    statement="""
        `nums` holds positive integers. Return the length of the shortest contiguous subarray whose sum is
        at least `target`, or `0` if no such subarray exists.
    """,
    constraints=["1 <= nums.length <= 10^5", "1 <= nums[i] <= 10^4", "1 <= target <= 10^9"],
    sig="int minSubArrayLen(int target, int[] nums)",
    hints=[
        "With only positive numbers, growing a window raises its sum and shrinking lowers it.",
        "Extend the right edge; while the sum reaches the target, record the length and shrink from the left.",
        "left = total = 0\nbest = infinity\nfor right, x in enumerate(nums):\n    total += x\n    while total >= target:\n"
        "        best = min(best, right - left + 1)\n        total -= nums[left]; left += 1\nreturn 0 if best is infinity else best",
        "Positivity is what makes the two-pointer window correct: O(n). (With negatives you'd need a deque of prefix sums.)",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda target, nums: min(
        [j - i for i in range(len(nums)) for j in range(i + 1, len(nums) + 1) if sum(nums[i:j]) >= target]
        or [0]
    ),
    java="""
        class Solution {
            public int minSubArrayLen(int target, int[] nums) {
                int left = 0, best = Integer.MAX_VALUE;
                long total = 0;
                for (int right = 0; right < nums.length; right++) {
                    total += nums[right];
                    while (total >= target) { best = Math.min(best, right - left + 1); total -= nums[left++]; }
                }
                return best == Integer.MAX_VALUE ? 0 : best;
            }
        }
    """,
    tests=[
        {"target": 7, "nums": [2, 3, 1, 2, 4, 3]},
        {"target": 4, "nums": [1, 4, 4]},
        {"target": 11, "nums": [1, 1, 1, 1]},
    ],
    gen=lambda r: {"target": r.randint(1, 40), "nums": ints(r, 1, 15, 1, 9)},
)

P(
    slug="decode-nested-string",
    title="Decode a Nested String",
    difficulty="medium",
    topics=["strings", "stacks", "recursion"],
    summary="Expand patterns like 3[a2[c]].",
    statement="""
        Decode `s`, where `k[text]` means `text` repeated `k` times, and patterns can nest: `"3[a2[c]]"`
        becomes `"accaccacc"`. The input is always valid, and `k` is a positive integer.
    """,
    constraints=["1 <= s.length <= 30", "1 <= k <= 300", "the output length is at most 10^5"],
    sig="String decodeString(String s)",
    hints=[
        "When you reach a `]`, you need the text and the count that started that bracket.",
        "Use two stacks: one for counts and one for the text built before each `[`.",
        "counts, texts = [], []\ncur, k = '', 0\nfor c in s:\n    if digit: k = k*10 + c\n    elif c == '[': push k and cur; cur, k = '', 0\n"
        "    elif c == ']': cur = texts.pop() + cur * counts.pop()\n    else: cur += c\nreturn cur",
        "Each character is processed once, plus the cost of building the output: O(output length). "
        "Counts can have several digits, so accumulate them before the `[`.",
    ],
    time="O(output)",
    space="O(output)",
    model=lambda s: (lambda f: f(f, s))(
        lambda f, t: (
            t
            if "[" not in t
            else f(f, __import__("re").sub(r"(\d+)\[([a-z]*)\]", lambda m: m.group(2) * int(m.group(1)), t))
        )
    ),
    java="""
        import java.util.*;

        class Solution {
            public String decodeString(String s) {
                Deque<Integer> counts = new ArrayDeque<>();
                Deque<StringBuilder> texts = new ArrayDeque<>();
                StringBuilder cur = new StringBuilder();
                int k = 0;
                for (char c : s.toCharArray()) {
                    if (Character.isDigit(c)) k = k * 10 + (c - '0');
                    else if (c == '[') { counts.push(k); texts.push(cur); cur = new StringBuilder(); k = 0; }
                    else if (c == ']') {
                        StringBuilder prev = texts.pop();
                        int times = counts.pop();
                        for (int i = 0; i < times; i++) prev.append(cur);
                        cur = prev;
                    } else cur.append(c);
                }
                return cur.toString();
            }
        }
    """,
    tests=[{"s": "3[a]2[bc]"}, {"s": "3[a2[c]]"}, {"s": "2[abc]3[cd]ef"}, {"s": "abc"}, {"s": "10[x]"}],
    gen=lambda r: {"s": r.choice(["2[a3[b]]", "x2[y]z", "3[2[ab]c]", "4[z]q", "2[3[a]2[b]]"])},
    gen_count=2,
)

P(
    slug="evaluate-rpn",
    title="Evaluate Reverse Polish Notation",
    difficulty="medium",
    topics=["stacks", "math"],
    summary="Compute an expression written in postfix form.",
    statement="""
        Evaluate the postfix expression `tokens` (e.g. `["2","1","+","3","*"]` is `(2 + 1) * 3`). Operators
        are `+ - * /`; division truncates toward zero. The expression is valid and never divides by zero.
    """,
    constraints=["1 <= tokens.length <= 10^4", "intermediate values fit in an int"],
    sig="int evalRPN(String[] tokens)",
    hints=[
        "An operator applies to the two most recent values.",
        "Push numbers on a stack; for an operator, pop `b` then `a` and push `a op b`.",
        "stack = []\nfor t in tokens:\n    if t is an operator:\n        b, a = stack.pop(), stack.pop()\n        stack.append(apply(t, a, b))\n"
        "    else: stack.append(int(t))\nreturn stack[0]",
        "O(n). Order matters: the first value popped is the right-hand operand. Java's `/` already truncates toward zero.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda tokens: __import__("functools").reduce(
        lambda st, t: (
            st[:-2]
            + [
                {
                    "+": lambda a, b: a + b,
                    "-": lambda a, b: a - b,
                    "*": lambda a, b: a * b,
                    "/": lambda a, b: int(a / b),
                }[t](st[-2], st[-1])
            ]
            if t in "+-*/" and len(t) == 1
            else st + [int(t)]
        ),
        tokens,
        [],
    )[0],
    java="""
        import java.util.*;

        class Solution {
            public int evalRPN(String[] tokens) {
                Deque<Integer> stack = new ArrayDeque<>();
                for (String t : tokens) {
                    if (t.length() == 1 && "+-*/".indexOf(t.charAt(0)) >= 0) {
                        int b = stack.pop(), a = stack.pop();
                        switch (t.charAt(0)) {
                            case '+': stack.push(a + b); break;
                            case '-': stack.push(a - b); break;
                            case '*': stack.push(a * b); break;
                            default: stack.push(a / b);
                        }
                    } else stack.push(Integer.parseInt(t));
                }
                return stack.pop();
            }
        }
    """,
    tests=[
        {"tokens": ["2", "1", "+", "3", "*"]},
        {"tokens": ["4", "13", "5", "/", "+"]},
        {"tokens": ["10", "6", "9", "3", "+", "-11", "*", "/", "*", "17", "+", "5", "+"]},
        {"tokens": ["-7", "2", "/"]},
    ],
    gen=lambda r: {
        "tokens": [
            str(r.randint(1, 9)),
            str(r.randint(1, 9)),
            r.choice("+-*"),
            str(r.randint(1, 9)),
            r.choice("+-*/"),
        ]
    },
)

P(
    slug="asteroid-collision",
    title="Asteroid Collisions",
    difficulty="medium",
    topics=["stacks", "simulation"],
    summary="Simulate asteroids moving left and right and colliding.",
    statement="""
        Each value in `asteroids` is an asteroid's size, with its sign giving direction (positive = right,
        negative = left). All move at the same speed. When two meet, the smaller explodes; equal sizes
        both explode. Return the asteroids left after all collisions, in order.
    """,
    constraints=["2 <= asteroids.length <= 10^4", "values are non-zero"],
    sig="int[] asteroidCollision(int[] asteroids)",
    hints=[
        "A collision only happens when a right-mover is followed by a left-mover.",
        "Keep survivors on a stack. A new left-mover fights the right-movers on top of the stack.",
        "stack = []\nfor a in asteroids:\n    alive = True\n    while alive and a < 0 and stack and stack[-1] > 0:\n"
        "        if stack[-1] < -a: stack.pop(); continue\n        if stack[-1] == -a: stack.pop()\n        alive = False\n"
        "    if alive: stack.append(a)\nreturn stack",
        "Each asteroid is pushed and popped at most once: O(n).",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda asteroids: (lambda f: f(f, list(asteroids)))(
        lambda f, a: (
            a
            if not any(a[i] > 0 > a[i + 1] for i in range(len(a) - 1))
            else f(
                f,
                (
                    lambda i: (
                        a[:i]
                        + ([a[i]] if a[i] > -a[i + 1] else [a[i + 1]] if a[i] < -a[i + 1] else [])
                        + a[i + 2 :]
                    )
                )(next(i for i in range(len(a) - 1) if a[i] > 0 > a[i + 1])),
            )
        )
    ),
    java="""
        import java.util.*;

        class Solution {
            public int[] asteroidCollision(int[] asteroids) {
                Deque<Integer> stack = new ArrayDeque<>();
                for (int a : asteroids) {
                    boolean alive = true;
                    while (alive && a < 0 && !stack.isEmpty() && stack.peek() > 0) {
                        int top = stack.peek();
                        if (top < -a) { stack.pop(); continue; }
                        if (top == -a) stack.pop();
                        alive = false;
                    }
                    if (alive) stack.push(a);
                }
                int[] out = new int[stack.size()];
                for (int i = out.length - 1; i >= 0; i--) out[i] = stack.pop();
                return out;
            }
        }
    """,
    tests=[
        {"asteroids": [5, 10, -5]},
        {"asteroids": [8, -8]},
        {"asteroids": [10, 2, -5]},
        {"asteroids": [-2, -1, 1, 2]},
    ],
    gen=lambda r: {"asteroids": [r.choice([-1, 1]) * r.randint(1, 6) for _ in range(r.randint(2, 10))]},
)

P(
    slug="stock-span",
    title="Stock Price Span",
    difficulty="medium",
    topics=["stacks", "arrays"],
    summary="For each day, count the run of days with price at most today's.",
    statement="""
        For each day `i`, the span is the number of consecutive days ending at day `i` (counting backwards,
        including today) whose price is less than or equal to `prices[i]`. Return the spans.
    """,
    constraints=["1 <= prices.length <= 10^5"],
    sig="int[] stockSpan(int[] prices)",
    hints=[
        "Looking back day by day is O(n^2) in the worst case. What can you skip?",
        "Keep a stack of indices with decreasing prices; pop every index whose price is <= today's.",
        "stack = []\nfor i, p in enumerate(prices):\n    while stack and prices[stack[-1]] <= p: stack.pop()\n"
        "    span[i] = i + 1 if not stack else i - stack[-1]\n    stack.append(i)\nreturn span",
        "A popped day can never be the boundary for a later day, so each index is pushed and popped once: O(n).",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda prices: [
        next((i - j for j in range(i - 1, -1, -1) if prices[j] > prices[i]), i + 1)
        for i in range(len(prices))
    ],
    java="""
        import java.util.*;

        class Solution {
            public int[] stockSpan(int[] prices) {
                int[] span = new int[prices.length];
                Deque<Integer> stack = new ArrayDeque<>();
                for (int i = 0; i < prices.length; i++) {
                    while (!stack.isEmpty() && prices[stack.peek()] <= prices[i]) stack.pop();
                    span[i] = stack.isEmpty() ? i + 1 : i - stack.peek();
                    stack.push(i);
                }
                return span;
            }
        }
    """,
    tests=[{"prices": [100, 80, 60, 70, 60, 75, 85]}, {"prices": [5, 5, 5]}, {"prices": [1]}],
    gen=lambda r: {"prices": ints(r, 1, 15, 1, 20)},
)

P(
    slug="next-greater-circular",
    title="Next Greater Element in a Circle",
    difficulty="medium",
    topics=["stacks", "arrays"],
    summary="Next bigger value to the right, wrapping around the end.",
    statement="""
        `nums` is circular: after the last value comes the first. For each value, return the first greater
        value found by moving right (wrapping around), or `-1` if there is none.
    """,
    constraints=["1 <= nums.length <= 10^4"],
    sig="int[] nextGreaterElements(int[] nums)",
    hints=[
        "Wrapping around is like scanning the array twice.",
        "Run a decreasing stack of indices over `2n` steps using `i % n`, only pushing during the first pass.",
        "ans = [-1]*n\nstack = []\nfor i in range(2*n):\n    x = nums[i % n]\n    while stack and nums[stack[-1]] < x: ans[stack.pop()] = x\n"
        "    if i < n: stack.append(i)\nreturn ans",
        "Two passes with a monotonic stack: O(n).",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda nums: [
        next(
            (nums[(i + d) % len(nums)] for d in range(1, len(nums)) if nums[(i + d) % len(nums)] > nums[i]),
            -1,
        )
        for i in range(len(nums))
    ],
    java="""
        import java.util.*;

        class Solution {
            public int[] nextGreaterElements(int[] nums) {
                int n = nums.length;
                int[] ans = new int[n];
                Arrays.fill(ans, -1);
                Deque<Integer> stack = new ArrayDeque<>();
                for (int i = 0; i < 2 * n; i++) {
                    int x = nums[i % n];
                    while (!stack.isEmpty() && nums[stack.peek()] < x) ans[stack.pop()] = x;
                    if (i < n) stack.push(i);
                }
                return ans;
            }
        }
    """,
    tests=[{"nums": [1, 2, 1]}, {"nums": [1, 2, 3, 4, 3]}, {"nums": [5]}, {"nums": [3, 3]}],
    gen=lambda r: {"nums": ints(r, 1, 12, 0, 9)},
)

P(
    slug="remove-k-digits",
    title="Remove K Digits",
    difficulty="medium",
    topics=["stacks", "greedy", "strings"],
    summary="Delete k digits to make the smallest possible number.",
    statement="""
        `num` is a non-negative integer as a string. Remove exactly `k` digits so the remaining number is
        as small as possible. Return it without leading zeros (return `"0"` if nothing is left).
    """,
    constraints=["1 <= k <= num.length <= 10^5", 'num has no leading zeros except "0"'],
    sig="String removeKdigits(String num, int k)",
    hints=[
        "A smaller digit early on matters more than anything later.",
        "Keep a stack of digits. While the new digit is smaller than the top and you can still remove, pop.",
        "stack = []\nfor d in num:\n    while k and stack and stack[-1] > d: stack.pop(); k -= 1\n    stack.append(d)\n"
        "drop k more from the end\nstrip leading zeros\nreturn result or '0'",
        "Greedy with a monotonic stack: each digit is pushed and popped once, O(n). Leftover removals come off the end, "
        "where the digits are already non-decreasing.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda num, k: (
        str(min(int(num[:i] + num[i + 1 :]) if len(num) > 1 else 0 for i in range(len(num))))
        if k == 1
        else (lambda f: f(f, num, k))(
            lambda f, s, kk: (
                s
                if kk == 0
                else f(f, str(min(int(s[:i] + s[i + 1 :] or "0") for i in range(len(s)))), kk - 1)
            )
        )
    ),
    java="""
        class Solution {
            public String removeKdigits(String num, int k) {
                StringBuilder stack = new StringBuilder();
                for (char d : num.toCharArray()) {
                    while (k > 0 && stack.length() > 0 && stack.charAt(stack.length() - 1) > d) {
                        stack.deleteCharAt(stack.length() - 1);
                        k--;
                    }
                    stack.append(d);
                }
                stack.setLength(stack.length() - k);
                int i = 0;
                while (i < stack.length() && stack.charAt(i) == '0') i++;
                String out = stack.substring(i);
                return out.isEmpty() ? "0" : out;
            }
        }
    """,
    tests=[
        {"num": "1432219", "k": 3},
        {"num": "10200", "k": 1},
        {"num": "10", "k": 2},
        {"num": "112", "k": 1},
    ],
    gen=lambda r: (lambda s: {"num": s, "k": r.randint(1, len(s))})(str(r.randint(1, 10**7))),
)

P(
    slug="simplify-unix-path",
    title="Simplify a File Path",
    difficulty="medium",
    topics=["stacks", "strings"],
    summary="Resolve . and .. in an absolute Unix path.",
    statement="""
        Simplify the absolute Unix-style path `path`: `.` means the current folder, `..` means the parent
        (staying at `/` if already there), and repeated slashes count as one. Return the canonical path,
        which starts with `/`, has single slashes, and no trailing slash (except the root `/`).
    """,
    constraints=["1 <= path.length <= 3000", "path starts with '/'"],
    sig="String simplifyPath(String path)",
    hints=[
        "Split the path on `/` and handle one piece at a time.",
        "Use a stack of folder names: skip empty pieces and `.`, pop for `..`, push anything else.",
        "stack = []\nfor part in path.split('/'):\n    if part in ('', '.'): continue\n    if part == '..': stack.pop() if stack else None\n"
        "    else: stack.append(part)\nreturn '/' + '/'.join(stack)",
        "O(n). Names like `...` are ordinary folder names, not special.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda path: (
        "/"
        + "/".join(
            __import__("functools").reduce(
                lambda st, p: st if p in ("", ".") else st[:-1] if p == ".." else st + [p],
                path.split("/"),
                [],
            )
        )
    ),
    java="""
        import java.util.*;

        class Solution {
            public String simplifyPath(String path) {
                Deque<String> stack = new ArrayDeque<>();
                for (String part : path.split("/")) {
                    if (part.isEmpty() || part.equals(".")) continue;
                    if (part.equals("..")) { if (!stack.isEmpty()) stack.pollLast(); }
                    else stack.addLast(part);
                }
                return "/" + String.join("/", stack);
            }
        }
    """,
    tests=[
        {"path": "/home/"},
        {"path": "/../"},
        {"path": "/home//foo/"},
        {"path": "/a/./b/../../c/"},
        {"path": "/.../a/../b"},
    ],
    gen=lambda r: {
        "path": "/" + "/".join(r.choice(["a", "b", "..", ".", "", "c"]) for _ in range(r.randint(1, 8)))
    },
)

P(
    slug="majority-element-two",
    title="Values Appearing More Than n/3 Times",
    difficulty="medium",
    topics=["arrays", "counting"],
    summary="Find every value that appears more than a third of the time.",
    statement="""
        Return, in ascending order, every value that appears more than `n / 3` times in `nums`
        (there can be at most two). Try for O(1) extra space.
    """,
    constraints=["1 <= nums.length <= 5 * 10^4"],
    sig="int[] majorityElement(int[] nums)",
    hints=[
        "How many values can appear more than n/3 times?",
        "At most two. Extended Boyer-Moore keeps two candidates and two counters, then verifies them.",
        "c1, c2, n1, n2 = None, None, 0, 0\nfor x in nums:\n    if x == c1: n1 += 1\n    elif x == c2: n2 += 1\n"
        "    elif n1 == 0: c1, n1 = x, 1\n    elif n2 == 0: c2, n2 = x, 1\n    else: n1 -= 1; n2 -= 1\nkeep candidates that really appear > n/3 times",
        "The voting pass finds the only possible answers; a second pass counts them. O(n) time, O(1) space.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda nums: sorted(v for v, c in Counter(nums).items() if c > len(nums) // 3),
    java="""
        import java.util.*;

        class Solution {
            public int[] majorityElement(int[] nums) {
                int c1 = 0, c2 = 1, n1 = 0, n2 = 0;
                for (int x : nums) {
                    if (x == c1) n1++;
                    else if (x == c2) n2++;
                    else if (n1 == 0) { c1 = x; n1 = 1; }
                    else if (n2 == 0) { c2 = x; n2 = 1; }
                    else { n1--; n2--; }
                }
                int count1 = 0, count2 = 0;
                for (int x : nums) { if (x == c1) count1++; else if (x == c2) count2++; }
                List<Integer> out = new ArrayList<>();
                if (count1 > nums.length / 3) out.add(c1);
                if (count2 > nums.length / 3) out.add(c2);
                Collections.sort(out);
                return out.stream().mapToInt(Integer::intValue).toArray();
            }
        }
    """,
    tests=[
        {"nums": [3, 2, 3]},
        {"nums": [1]},
        {"nums": [1, 2]},
        {"nums": [0, 0, 0]},
        {"nums": [2, 1, 1, 3, 1, 4, 5, 6]},
    ],
    gen=lambda r: {"nums": ints(r, 1, 15, 0, 3)},
)

P(
    slug="find-duplicate-number",
    title="Find the Repeated Number",
    difficulty="medium",
    topics=["arrays", "two-pointers", "binary-search"],
    summary="n+1 numbers in 1..n: find the one that repeats, without changing the array.",
    statement="""
        `nums` has `n + 1` values, each in `[1, n]`. Exactly one value repeats (possibly more than twice).
        Return it without modifying `nums` and using O(1) extra space.
    """,
    constraints=["1 <= n <= 10^5", "one value repeats"],
    sig="int findDuplicate(int[] nums)",
    hints=[
        "Treat the array as a linked list: index `i` points to `nums[i]`.",
        "The repeated value is where two pointers enter a cycle. Use Floyd's tortoise and hare.",
        "slow = fast = nums[0]\ndo: slow = nums[slow]; fast = nums[nums[fast]] until slow == fast\nslow = nums[0]\n"
        "while slow != fast: slow = nums[slow]; fast = nums[fast]\nreturn slow",
        "Two indices point to the duplicate value, which creates a cycle whose entry is the answer. O(n) time, O(1) space. "
        "Binary searching on the value range with counting also works in O(n log n).",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda nums: Counter(nums).most_common(1)[0][0],
    java="""
        class Solution {
            public int findDuplicate(int[] nums) {
                int slow = nums[0], fast = nums[0];
                do { slow = nums[slow]; fast = nums[nums[fast]]; } while (slow != fast);
                slow = nums[0];
                while (slow != fast) { slow = nums[slow]; fast = nums[fast]; }
                return slow;
            }
        }
    """,
    tests=[{"nums": [1, 3, 4, 2, 2]}, {"nums": [3, 1, 3, 4, 2]}, {"nums": [3, 3, 3, 3, 3]}, {"nums": [1, 1]}],
    gen=lambda r: (
        lambda n: (lambda dup: {"nums": r.sample(list(range(1, n + 1)) + [dup], n + 1)})(r.randint(1, n))
    )(r.randint(1, 12)),
)

P(
    slug="h-index",
    title="Researcher's H-Index",
    difficulty="medium",
    topics=["arrays", "sorting", "counting"],
    summary="The largest h such that h papers have at least h citations.",
    statement="""
        `citations[i]` is the number of citations of paper `i`. Return the h-index: the largest `h` such
        that at least `h` papers have at least `h` citations each.
    """,
    constraints=["1 <= citations.length <= 5000", "0 <= citations[i] <= 1000"],
    sig="int hIndex(int[] citations)",
    hints=[
        "The answer can't be more than the number of papers.",
        "Bucket papers by citation count (capping at n), then walk from high to low accumulating counts.",
        "buckets = [0]*(n+1)\nfor c in citations: buckets[min(c, n)] += 1\ntotal = 0\nfor h from n down to 0:\n"
        "    total += buckets[h]\n    if total >= h: return h",
        "Counting sort makes this O(n); sorting descending and finding the last `citations[i] >= i + 1` is O(n log n).",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda citations: max(h for h in range(len(citations) + 1) if sum(c >= h for c in citations) >= h),
    java="""
        class Solution {
            public int hIndex(int[] citations) {
                int n = citations.length;
                int[] buckets = new int[n + 1];
                for (int c : citations) buckets[Math.min(c, n)]++;
                int total = 0;
                for (int h = n; h >= 0; h--) { total += buckets[h]; if (total >= h) return h; }
                return 0;
            }
        }
    """,
    tests=[
        {"citations": [3, 0, 6, 1, 5]},
        {"citations": [1, 3, 1]},
        {"citations": [0]},
        {"citations": [100]},
    ],
    gen=lambda r: {"citations": ints(r, 1, 12, 0, 15)},
)

P(
    slug="sort-by-frequency",
    title="Sort Characters by Frequency",
    difficulty="medium",
    topics=["strings", "hash-maps", "sorting"],
    summary="Rearrange a string so the most frequent letters come first.",
    statement="""
        Return `s` rearranged so characters appear in decreasing order of frequency, with all copies of a
        character together. Break ties by the character's ASCII order (smaller first).
    """,
    constraints=["1 <= s.length <= 5 * 10^5", "printable ASCII"],
    sig="String frequencySort(String s)",
    hints=[
        "Count every character first.",
        "Sort the distinct characters by (-count, character) and write each one `count` times.",
        "counts = count characters\nfor c in sorted(counts, key=lambda c: (-counts[c], c)):\n    out += c * counts[c]\nreturn out",
        "Counting is O(n) and sorting at most 128 distinct characters is constant: O(n) overall.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda s: "".join(c * n for c, n in sorted(Counter(s).items(), key=lambda kv: (-kv[1], kv[0]))),
    java="""
        import java.util.*;

        class Solution {
            public String frequencySort(String s) {
                int[] counts = new int[128];
                for (char c : s.toCharArray()) counts[c]++;
                List<Character> chars = new ArrayList<>();
                for (int c = 0; c < 128; c++) if (counts[c] > 0) chars.add((char) c);
                chars.sort((a, b) -> counts[a] != counts[b] ? counts[b] - counts[a] : a - b);
                StringBuilder sb = new StringBuilder();
                for (char c : chars) for (int i = 0; i < counts[c]; i++) sb.append(c);
                return sb.toString();
            }
        }
    """,
    tests=[{"s": "tree"}, {"s": "cccaaa"}, {"s": "Aabb"}, {"s": "z"}],
    gen=lambda r: {"s": word(r, 1, 20, "abcAB1")},
)

P(
    slug="can-reorganize",
    title="Rearrange So No Neighbors Match",
    difficulty="medium",
    topics=["strings", "greedy", "counting"],
    summary="Can letters be arranged so no two adjacent are equal?",
    statement="""
        Return `true` if the letters of `s` can be rearranged so that no two adjacent characters are the same.
    """,
    constraints=["1 <= s.length <= 500", "lower-case letters"],
    sig="boolean canReorganize(String s)",
    hints=[
        "Which letter is the hardest to keep apart?",
        "The most frequent one. It needs a different letter between each of its copies.",
        "return max(counts) <= (len(s) + 1) // 2",
        "If the top letter fits in every other slot (0, 2, 4, ...), fill the rest in any order and it works: O(n). "
        "Building the actual string uses the same idea with a max-heap.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda s: (
        any(
            all(p[i] != p[i + 1] for i in range(len(p) - 1))
            for p in set(__import__("itertools").permutations(s))
        )
        if len(s) <= 7
        else max(Counter(s).values()) <= (len(s) + 1) // 2
    ),
    java="""
        class Solution {
            public boolean canReorganize(String s) {
                int[] counts = new int[26];
                int top = 0;
                for (char c : s.toCharArray()) top = Math.max(top, ++counts[c - 'a']);
                return top <= (s.length() + 1) / 2;
            }
        }
    """,
    tests=[{"s": "aab"}, {"s": "aaab"}, {"s": "a"}, {"s": "aabb"}, {"s": "aaabb"}],
    gen=lambda r: {"s": word(r, 1, 7, "aab")},
)

P(
    slug="unique-frequencies",
    title="Fewest Deletions for Unique Frequencies",
    difficulty="medium",
    topics=["strings", "greedy", "hash-sets"],
    summary="Delete letters until no two letters share a count.",
    statement="""
        A string is good if no two different letters appear the same number of times. Return the minimum
        number of characters to delete from `s` to make it good (a letter deleted entirely has count 0, which
        doesn't count as a frequency).
    """,
    constraints=["1 <= s.length <= 10^5", "lower-case letters"],
    sig="int minDeletions(String s)",
    hints=[
        "Only the counts matter, not the letters.",
        "Process counts from largest to smallest; if a count is taken, lower it until it's free or zero.",
        "used = set()\ndeletions = 0\nfor c in counts:\n    while c > 0 and c in used: c -= 1; deletions += 1\n    used.add(c)\nreturn deletions",
        "Lowering a clashing count to the nearest free value is always optimal. With 26 letters this is fast: "
        "O(n + 26^2) at worst.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda s: (
        lambda cs: __import__("functools").reduce(
            lambda acc, c: (lambda c2: (acc[0] | ({c2} if c2 else set()), acc[1] + c - c2))(
                next(v for v in range(c, -1, -1) if v == 0 or v not in acc[0])
            ),
            sorted(cs, reverse=True),
            (set(), 0),
        )[1]
    )(Counter(s).values()),
    java="""
        import java.util.*;

        class Solution {
            public int minDeletions(String s) {
                int[] counts = new int[26];
                for (char c : s.toCharArray()) counts[c - 'a']++;
                Set<Integer> used = new HashSet<>();
                int deletions = 0;
                for (int c : counts) {
                    while (c > 0 && used.contains(c)) { c--; deletions++; }
                    used.add(c);
                }
                return deletions;
            }
        }
    """,
    tests=[{"s": "aab"}, {"s": "aaabbbcc"}, {"s": "ceabaacb"}, {"s": "abc"}],
    gen=lambda r: {"s": word(r, 1, 20, "abcd")},
)

P(
    slug="bulls-and-cows",
    title="Bulls and Cows",
    difficulty="medium",
    topics=["strings", "hash-maps", "counting"],
    summary="Score a guess against a secret: right place vs right digit.",
    statement="""
        `secret` and `guess` are digit strings of the same length. Bulls are digits in the right position.
        Cows are digits that are in the secret but in a different position (each secret digit can match only
        once). Return the hint `"xAyB"` with `x` bulls and `y` cows.
    """,
    constraints=["1 <= length <= 1000", "digits only"],
    sig="String getHint(String secret, String guess)",
    hints=[
        "Count the bulls first; they're simple position matches.",
        "For the rest, count unmatched digits on each side; each digit contributes `min(secretCount, guessCount)` cows.",
        "bulls = sum(s == g for s, g in zip(secret, guess))\nfor unmatched positions: count digits in secret and guess separately\n"
        "cows = sum(min(cs[d], cg[d]) for d in 0..9)\nreturn f'{bulls}A{cows}B'",
        "One pass plus 10 digit counts: O(n). Excluding bull positions from the counts avoids double counting.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda secret, guess: (
        lambda bulls, rest: (
            f"{bulls}A{sum((Counter(a for a, _ in rest) & Counter(b for _, b in rest)).values())}B"
        )
    )(
        sum(a == b for a, b in zip(secret, guess, strict=False)),
        [(a, b) for a, b in zip(secret, guess, strict=False) if a != b],
    ),
    java="""
        class Solution {
            public String getHint(String secret, String guess) {
                int bulls = 0, cows = 0;
                int[] cs = new int[10], cg = new int[10];
                for (int i = 0; i < secret.length(); i++) {
                    char a = secret.charAt(i), b = guess.charAt(i);
                    if (a == b) bulls++;
                    else { cs[a - '0']++; cg[b - '0']++; }
                }
                for (int d = 0; d < 10; d++) cows += Math.min(cs[d], cg[d]);
                return bulls + "A" + cows + "B";
            }
        }
    """,
    tests=[
        {"secret": "1807", "guess": "7810"},
        {"secret": "1123", "guess": "0111"},
        {"secret": "1", "guess": "1"},
    ],
    gen=lambda r: (lambda n: {"secret": word(r, n, n, "0123"), "guess": word(r, n, n, "0123")})(
        r.randint(1, 8)
    ),
)

P(
    slug="string-to-int",
    title="Parse an Integer From Text",
    difficulty="medium",
    topics=["strings", "math"],
    summary="Implement a forgiving string-to-integer conversion with clamping.",
    statement="""
        Convert `s` to a 32-bit integer: skip leading spaces, read an optional `+` or `-`, then read digits
        until a non-digit or the end. If there are no digits, return `0`. Clamp the result to
        `[-2^31, 2^31 - 1]`.
    """,
    constraints=["0 <= s.length <= 200", "letters, digits, spaces, '+', '-' and '.'"],
    sig="int myAtoi(String s)",
    hints=[
        "Handle the steps in order: spaces, sign, digits.",
        "Build the number digit by digit and stop growing it once it's beyond the int range.",
        "i = skip spaces\nsign = -1 if s[i] == '-' else 1 (advance past a sign)\nvalue = 0\nwhile digit:\n"
        "    value = value*10 + digit\n    if value > 2^31: break\nreturn clamp(sign * value)",
        "O(n). Checking for overflow while building (or using a long and capping early) is the part that needs care.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda s: (
        lambda m: (
            0 if not m or m.group(2) == "" else max(-(2**31), min(2**31 - 1, int(m.group(1) + m.group(2))))
        )
    )(__import__("re").match(r" *([+-]?)(\d*)", s)),
    java="""
        class Solution {
            public int myAtoi(String s) {
                int i = 0, n = s.length(), sign = 1;
                while (i < n && s.charAt(i) == ' ') i++;
                if (i < n && (s.charAt(i) == '+' || s.charAt(i) == '-')) sign = s.charAt(i++) == '-' ? -1 : 1;
                long value = 0;
                while (i < n && Character.isDigit(s.charAt(i))) {
                    value = value * 10 + (s.charAt(i++) - '0');
                    if (value > Integer.MAX_VALUE + 1L) break;
                }
                value *= sign;
                return (int) Math.max(Integer.MIN_VALUE, Math.min(Integer.MAX_VALUE, value));
            }
        }
    """,
    tests=[
        {"s": "42"},
        {"s": "   -042"},
        {"s": "1337c0d3"},
        {"s": "words and 987"},
        {"s": "-91283472332"},
        {"s": "2147483648"},
        {"s": "+-12"},
        {"s": ""},
    ],
    gen=lambda r: {
        "s": " " * r.randint(0, 2)
        + r.choice(["", "-", "+"])
        + word(r, 0, 12, "0123456789")
        + word(r, 0, 3, "a.9 ")
    },
)
