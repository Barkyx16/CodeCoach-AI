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
