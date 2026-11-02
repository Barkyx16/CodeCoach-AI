import java.util.*;

class Solution {
    public int numSquares(int n) {
        int[] best = new int[n + 1];
        Arrays.fill(best, Integer.MAX_VALUE);
        best[0] = 0;
        for (int i = 1; i <= n; i++)
            for (int s = 1; s * s <= i; s++) best[i] = Math.min(best[i], best[i - s * s] + 1);
        return best[n];
    }
}
