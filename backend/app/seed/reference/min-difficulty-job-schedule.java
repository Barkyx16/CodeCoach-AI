import java.util.*;

class Solution {
    public int minDifficulty(int[] jobs, int d) {
        int n = jobs.length;
        if (n < d) return -1;
        int[][] dp = new int[d + 1][n + 1];
        for (int[] row : dp) Arrays.fill(row, Integer.MAX_VALUE / 2);
        dp[0][0] = 0;
        for (int k = 1; k <= d; k++)
            for (int i = k; i <= n; i++) {
                int hardest = 0;
                for (int j = i - 1; j >= k - 1; j--) {
                    hardest = Math.max(hardest, jobs[j]);
                    dp[k][i] = Math.min(dp[k][i], dp[k - 1][j] + hardest);
                }
            }
        return dp[d][n];
    }
}
