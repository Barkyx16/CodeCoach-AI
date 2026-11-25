class Solution {
    private int line(int[] nums, int from, int to) {
        int prev = 0, cur = 0;
        for (int i = from; i <= to; i++) { int next = Math.max(cur, prev + nums[i]); prev = cur; cur = next; }
        return cur;
    }
    public int robCircle(int[] nums) {
        int n = nums.length;
        if (n == 1) return nums[0];
        return Math.max(line(nums, 0, n - 2), line(nums, 1, n - 1));
    }
}
