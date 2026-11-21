class Solution {
    public int countAtMost(int[] nums, int limit) {
        int count = 0;
        for (int i = 0; i < nums.length; i++) {
            if (nums[i] <= limit) {
                count++;
            }
        }
        return count;
    }
}
