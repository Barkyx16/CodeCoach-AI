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
