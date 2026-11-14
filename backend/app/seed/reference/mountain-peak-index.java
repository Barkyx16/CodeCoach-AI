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
