class Solution {
    public int findTargetSumWays(int[] nums, int target) {
        int total = 0;
        for (int x : nums) total += x;
        if (Math.abs(target) > total || (total + target) % 2 != 0) return 0;
        int goal = (total + target) / 2;
        int[] ways = new int[goal + 1];
        ways[0] = 1;
        for (int x : nums) for (int s = goal; s >= x; s--) ways[s] += ways[s - x];
        return ways[goal];
    }
}
