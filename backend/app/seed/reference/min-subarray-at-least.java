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
