import java.util.*;

class Solution {
    public int maxStudents(String[] seats) {
        int m = seats.length, n = seats[0].length();
        int[] dp = new int[1 << n];
        Arrays.fill(dp, -1);
        dp[0] = 0;
        for (int r = 0; r < m; r++) {
            int good = 0;
            for (int c = 0; c < n; c++) if (seats[r].charAt(c) == '.') good |= 1 << c;
            int[] next = new int[1 << n];
            Arrays.fill(next, -1);
            for (int mask = 0; mask < (1 << n); mask++) {
                if ((mask & ~good) != 0 || (mask & (mask << 1)) != 0) continue;
                for (int prev = 0; prev < (1 << n); prev++) {
                    if (dp[prev] < 0 || (mask & (prev << 1)) != 0 || (mask & (prev >> 1)) != 0) continue;
                    next[mask] = Math.max(next[mask], dp[prev] + Integer.bitCount(mask));
                }
            }
            dp = next;
        }
        int best = 0;
        for (int v : dp) best = Math.max(best, v);
        return best;
    }
}
