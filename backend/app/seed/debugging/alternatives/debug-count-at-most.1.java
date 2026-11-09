class Solution {
    public int countAtMost(int[] nums, int limit) {
        int count = 0;
        for (int n : nums) {
            if (n <= limit) count++;
        }
        return count;
    }
}
