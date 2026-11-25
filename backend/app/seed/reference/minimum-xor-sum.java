import java.util.*;

class Solution {
    public int minimumXORSum(int[] a, int[] b) {
        int n = a.length;
        int[] dp = new int[1 << n];
        Arrays.fill(dp, Integer.MAX_VALUE);
        dp[0] = 0;
        for (int mask = 0; mask < (1 << n); mask++) {
            if (dp[mask] == Integer.MAX_VALUE) continue;
            int i = Integer.bitCount(mask);
            if (i == n) continue;
            for (int j = 0; j < n; j++)
                if ((mask >> j & 1) == 0) dp[mask | 1 << j] = Math.min(dp[mask | 1 << j], dp[mask] + (a[i] ^ b[j]));
        }
        return dp[(1 << n) - 1];
    }
}
