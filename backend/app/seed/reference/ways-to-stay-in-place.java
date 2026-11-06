class Solution {
    public int numWays(int steps, int arrLen) {
        int limit = Math.min(arrLen, steps / 2 + 1);
        long[] dp = new long[limit];
        dp[0] = 1;
        for (int s = 0; s < steps; s++) {
            long[] next = new long[limit];
            for (int p = 0; p < limit; p++) {
                long v = dp[p];
                if (p > 0) v += dp[p - 1];
                if (p + 1 < limit) v += dp[p + 1];
                next[p] = v % 1_000_000_007;
            }
            dp = next;
        }
        return (int) dp[0];
    }
}
