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
