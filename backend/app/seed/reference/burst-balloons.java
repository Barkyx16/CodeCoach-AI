class Solution {
    public int maxCoins(int[] nums) {
        int n = nums.length;
        int[] v = new int[n + 2];
        v[0] = v[n + 1] = 1;
        for (int i = 0; i < n; i++) v[i + 1] = nums[i];
        int[][] dp = new int[n + 2][n + 2];
        for (int len = 2; len <= n + 1; len++)
            for (int i = 0; i + len <= n + 1; i++) {
                int j = i + len;
                for (int k = i + 1; k < j; k++) dp[i][j] = Math.max(dp[i][j], dp[i][k] + v[i] * v[k] * v[j] + dp[k][j]);
            }
        return dp[0][n + 1];
    }
}
