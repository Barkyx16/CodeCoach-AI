class Solution {
    private int atMost(int[] nums, int k) {
        int[] counts = new int[nums.length + 2];
        int left = 0, distinct = 0, total = 0;
        for (int right = 0; right < nums.length; right++) {
            if (counts[nums[right]]++ == 0) distinct++;
            while (distinct > k) if (--counts[nums[left++]] == 0) distinct--;
            total += right - left + 1;
        }
        return total;
    }
    public int subarraysWithKDistinct(int[] nums, int k) {
        return atMost(nums, k) - atMost(nums, k - 1);
    }
}
