import java.util.*;

class Solution {
    public int findRotateSteps(String ring, String key) {
        int n = ring.length();
        int[] dp = new int[n];
        Arrays.fill(dp, Integer.MAX_VALUE);
        dp[0] = 0;
        for (char c : key.toCharArray()) {
            int[] next = new int[n];
            Arrays.fill(next, Integer.MAX_VALUE);
            for (int j = 0; j < n; j++) {
                if (ring.charAt(j) != c) continue;
                for (int i = 0; i < n; i++) {
                    if (dp[i] == Integer.MAX_VALUE) continue;
                    int d = Math.abs(i - j);
                    next[j] = Math.min(next[j], dp[i] + Math.min(d, n - d) + 1);
                }
            }
            dp = next;
        }
        int best = Integer.MAX_VALUE;
        for (int v : dp) best = Math.min(best, v);
        return best;
    }
}
