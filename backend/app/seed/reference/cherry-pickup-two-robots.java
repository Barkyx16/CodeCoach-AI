import java.util.*;

class Solution {
    public int cherryPickup(int[][] grid) {
        int m = grid.length, n = grid[0].length;
        int[][] dp = new int[n][n];
        for (int[] row : dp) Arrays.fill(row, -1);
        dp[0][n - 1] = grid[0][0] + (n - 1 != 0 ? grid[0][n - 1] : 0);
        for (int r = 1; r < m; r++) {
            int[][] next = new int[n][n];
            for (int[] row : next) Arrays.fill(row, -1);
            for (int a = 0; a < n; a++)
                for (int b = 0; b < n; b++) {
                    if (dp[a][b] < 0) continue;
                    for (int da = -1; da <= 1; da++)
                        for (int db = -1; db <= 1; db++) {
                            int x = a + da, y = b + db;
                            if (x < 0 || x >= n || y < 0 || y >= n) continue;
                            int gain = grid[r][x] + (x != y ? grid[r][y] : 0);
                            next[x][y] = Math.max(next[x][y], dp[a][b] + gain);
                        }
                }
            dp = next;
        }
        int best = 0;
        for (int[] row : dp) for (int v : row) best = Math.max(best, v);
        return best;
    }
}
