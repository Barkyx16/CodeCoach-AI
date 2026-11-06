class Solution {
    public int profitableSchemes(int n, int minProfit, int[] group, int[] profit) {
        long[][] dp = new long[n + 1][minProfit + 1];
        dp[0][0] = 1;
        for (int c = 0; c < group.length; c++) {
            int g = group[c], p = profit[c];
            for (int people = n; people >= g; people--)
                for (int pr = minProfit; pr >= 0; pr--) {
                    int to = Math.min(minProfit, pr + p);
                    dp[people][to] = (dp[people][to] + dp[people - g][pr]) % 1_000_000_007;
                }
        }
        long total = 0;
        for (int people = 0; people <= n; people++) total = (total + dp[people][minProfit]) % 1_000_000_007;
        return (int) total;
    }
}
