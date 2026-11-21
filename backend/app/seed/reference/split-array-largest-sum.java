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
