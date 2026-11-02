class Solution {
    public int minInsertions(String s) {
        int n = s.length();
        int[][] dp = new int[n][n];
        for (int i = n - 2; i >= 0; i--)
            for (int j = i + 1; j < n; j++)
                dp[i][j] = s.charAt(i) == s.charAt(j) ? dp[i + 1][j - 1] : 1 + Math.min(dp[i + 1][j], dp[i][j - 1]);
        return dp[0][n - 1];
    }
}
