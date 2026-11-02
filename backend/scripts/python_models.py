"""Independent Python models of the medium problems added in session 5.

Each problem's expected outputs were produced by these deliberately simple (often brute-force)
models, and the optimal Java reference must reproduce them through the real driver. Keeping the
models here lets CI re-check that the two implementations still agree with the stored tests
(tests/test_seed_and_reference_solutions.py).
"""

import bisect
import heapq
import sys
from functools import lru_cache


def product_except_self(nums):
    out = []
    for i in range(len(nums)):
        p = 1
        for j, v in enumerate(nums):
            if j != i:
                p *= v
        out.append(p)
    return out


def max_area(height):
    h = height
    return max(min(h[i], h[j]) * (j - i) for i in range(len(h)) for j in range(i + 1, len(h)))


def search_rotated(nums, target):
    return nums.index(target) if target in nums else -1


def coin_change(coins, amount):
    @lru_cache(None)
    def best(a):
        if a == 0:
            return 0
        opts = [best(a - c) for c in coins if c <= a]
        opts = [o for o in opts if o >= 0]
        return 1 + min(opts) if opts else -1

    sys.setrecursionlimit(100000)
    for a in range(amount + 1):  # warm the cache bottom-up
        best(a)
    return best(amount)


def lis(nums):
    tails = []
    for x in nums:
        i = bisect.bisect_left(tails, x)
        if i == len(tails):
            tails.append(x)
        else:
            tails[i] = x
    return len(tails)


def daily_temperatures(temperatures):
    t = temperatures
    out = []
    for i in range(len(t)):
        wait = 0
        for j in range(i + 1, len(t)):
            if t[j] > t[i]:
                wait = j - i
                break
        out.append(wait)
    return out


def can_jump(nums):
    reach = {0}
    for i in range(len(nums)):
        if i in reach:
            reach |= set(range(i, min(len(nums), i + nums[i] + 1)))
    return len(nums) - 1 in reach


def num_decodings(s):
    @lru_cache(None)
    def ways(i):
        if i == len(s):
            return 1
        if s[i] == "0":
            return 0
        total = ways(i + 1)
        if i + 1 < len(s) and 10 <= int(s[i : i + 2]) <= 26:
            total += ways(i + 2)
        return total

    return ways(0)


def kth_largest(nums, k):
    return heapq.nlargest(k, nums)[-1]


def char_replacement(s, k):
    best = 0
    for i in range(len(s)):
        for j in range(i, len(s)):
            sub = s[i : j + 1]
            if len(sub) - max(sub.count(c) for c in set(sub)) <= k:
                best = max(best, len(sub))
    return best


MODELS = {
    "product-except-self": product_except_self,
    "container-with-most-water": max_area,
    "search-rotated-array": search_rotated,
    "coin-change": coin_change,
    "longest-increasing-subsequence": lis,
    "daily-temperatures": daily_temperatures,
    "jump-game": can_jump,
    "decode-ways": num_decodings,
    "kth-largest-element": kth_largest,
    "longest-repeating-replacement": char_replacement,
}
