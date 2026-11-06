import java.util.*;

class Solution {
    public int minCost(int n, int[] cuts) {
        int m = cuts.length;
        int[] p = new int[m + 2];
        Arrays.sort(cuts);
        for (int i = 0; i < m; i++) p[i + 1] = cuts[i];
        p[m + 1] = n;
        int[][] dp = new int[m + 2][m + 2];
        for (int len = 2; len <= m + 1; len++)
            for (int i = 0; i + len <= m + 1; i++) {
                int j = i + len;
                dp[i][j] = Integer.MAX_VALUE;
                for (int k = i + 1; k < j; k++) dp[i][j] = Math.min(dp[i][j], dp[i][k] + dp[k][j]);
                dp[i][j] += p[j] - p[i];
            }
        return dp[0][m + 1];
    }
}
